#!/usr/bin/env python3
"""Build the Cohort Pulse report page (read-only Firestore pull -> HTML).

  python3 tools/report/build.py [OUT.html]

Reads `applications` + `applications_internal` (UTM only); writes nothing to Firestore.
The page template is tools/report/template.html; data is embedded at __DATA__.
"""
import collections, statistics as S, datetime as dt
import os, sys, json, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import hq
d = hq.db()
def ser(v):
    if hasattr(v, "isoformat"): return v.isoformat()
    if isinstance(v, dict): return {k: ser(x) for k, x in v.items()}
    if isinstance(v, list): return [ser(x) for x in v]
    return v
F = ["appliedFor","status","createdAt","submittedAt","appliedAt","ccatScore","ccat1Score","ccat2Score","ccatAttempts",
     "ccatCompletedAt","ccat1CompletedAt","ccat2CompletedAt","ccatOrderedAt","ccat","adminDecision","admissionsUpdatedAt",
     "contractSigned","contractSignedAt","contractSyncedAt","contractEnvelopeStatus","contractEnvelopeId","personalInfo.email","personalInfo.yearsEngineeringRange","migrationInfo","updatedAt"]
apps = {x.id: ser(x.to_dict()) for x in d.collection("applications").select(F).stream()}
internal = {x.id: ser(x.to_dict()) for x in d.collection("applications_internal").select(["utmSource","utmMedium","utmCampaign"]).stream()}

A = apps; I = internal
NOW = dt.datetime.now(dt.timezone.utc)
COH = ["cohort_4","cohort_5","cohort_6","cohort_7","cohort_8"]
LAB = {c: "C"+c[-1] for c in COH}
STEP = {"step-1":1,"step-2":2,"step-3":3,"step-3-paused":3,"step-4":4,"step-5":5,"submitted":6,"step-6-approve":7,"step-6-reject":7,"approved":8,"rejected":7}
def ts(s):
    if not s or not isinstance(s,str): return None
    try: return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    except: return None
def score(a):
    o = a.get("ccat")
    if isinstance(o,dict) and isinstance(o.get("score"),(int,float)): return o["score"]
    v = a.get("ccatScore"); return v if isinstance(v,(int,float)) else None
def accepted(a): return a.get("adminDecision") in ("accepted","gfa-accepted") or (a.get("adminDecision") in (None,"") and a.get("status") in ("step-6-approve","approved"))
def first_ccat(a): return ts(a.get("ccat1CompletedAt")) or ts(a.get("ccatCompletedAt"))
def qual_date(a):
    """When the applicant first reached 40+ (None if never). Attempt 1, else the retake, else the override/latest."""
    sc = score(a)
    if sc is None or sc < 40: return None
    s1, s2 = a.get("ccat1Score"), a.get("ccat2Score")
    if isinstance(s1, (int, float)) and s1 >= 40: return ts(a.get("ccat1CompletedAt")) or ts(a.get("ccatCompletedAt"))
    if isinstance(s2, (int, float)) and s2 >= 40: return ts(a.get("ccat2CompletedAt")) or ts(a.get("ccatCompletedAt"))
    return ts(a.get("ccatCompletedAt")) or ts((a.get("ccat") or {}).get("updatedAt"))
def signed_date(a): return ts(a.get("contractSignedAt")) or ts(a.get("contractSyncedAt"))
def rank(a): return (a.get("adminDecision") not in (None,""), score(a) is not None, STEP.get(a.get("status"),0), a.get("updatedAt") or "")
# dedupe by (cohort,email)
best = {}
for k,a in A.items():
    c = a.get("appliedFor")
    if c == "cohort-4": c = "cohort_4"
    if c not in COH: continue
    e = ((a.get("personalInfo") or {}).get("email") or k).strip().lower()
    a["_id"]=k; a["_c"]=c
    if (c,e) not in best or rank(a) > rank(best[(c,e)]): best[(c,e)] = a
R = list(best.values())
by = collections.defaultdict(list)
for a in R: by[a["_c"]].append(a)
out = {"asOf": NOW.strftime("%Y-%m-%d %H:%M UTC"), "cohorts":[LAB[c] for c in COH], "raw": len(A)}

# 1. Pacing: anchor = Monday of first week with >=20 new apps
anch = {}
for c in COH:
    wk = collections.Counter()
    for a in by[c]:
        t = ts(a.get("createdAt"))
        if t: d=t.date(); wk[d-dt.timedelta(d.weekday())]+=1
    anch[c] = min(w for w,n in wk.items() if n>=20)
pace = {}
for c in COH:
    days = sorted((ts(a["createdAt"]).date()-anch[c]).days for a in by[c] if ts(a.get("createdAt")))
    days = [d for d in days if d>=-7]
    horizon = min(max((NOW.date()-anch[c]).days, 0), 120)
    if c != "cohort_8": horizon = min(max(days), 120)
    cum=[sum(1 for d in days if d <= x) for x in range(0, horizon+1)]
    cds = [((ts(a.get("ccat1CompletedAt")) or ts(a.get("ccatCompletedAt"))).date()-anch[c]).days for a in by[c] if (ts(a.get("ccat1CompletedAt")) or ts(a.get("ccatCompletedAt"))) and ts(a.get("createdAt")) and (ts(a["createdAt"]).date()-anch[c]).days >= -7]
    ccum=[sum(1 for d in cds if d <= x) for x in range(0, horizon+1)]
    if c != "cohort_8":  # trim the flat tail after the window's last application
        end = max(i for i in range(len(cum)) if i == 0 or cum[i] != cum[i-1]) + 1
        cum, ccum = cum[:end], ccum[:end]
    pace[LAB[c]] = {"open": anch[c].isoformat(), "cum": cum, "ccat_cum": ccum, "pre_window": sum(1 for a in by[c] if ts(a.get("createdAt")) and (ts(a["createdAt"]).date()-anch[c]).days < -7)}
out["pacing"] = pace

# 1b. Countdown pacing: cumulative volume at T-minus days before cohort start (window: T-11 weeks -> T-0).
# Start dates (Day 1). C4-C7: "Final - 2026 Gauntlet AI Schedule" sheet (G4-G7 remote start).
# C8: 2027-01-25 per Drew (2026-09-23). NOTE apply_admin/settings.currentCohort.startDate still says 2027-02-01;
# it is deliberately not used here. No per-cohort start date is stored reliably in Firestore.
START = {"cohort_4": "2026-02-16", "cohort_5": "2026-04-27", "cohort_6": "2026-07-06", "cohort_7": "2026-09-14",
         "cohort_8": "2027-01-25"}
T0 = 77
tm = {}
for c in COH:
    st = dt.date.fromisoformat(START[c])
    keep = [a for a in by[c] if ts(a.get("createdAt")) and (ts(a["createdAt"]).date()-anch[c]).days >= -7]
    ad = [(ts(a["createdAt"]).date()-st).days for a in keep]
    cdd = [((ts(a.get("ccat1CompletedAt")) or ts(a.get("ccatCompletedAt"))).date()-st).days for a in keep if (ts(a.get("ccat1CompletedAt")) or ts(a.get("ccatCompletedAt")))]
    qd = [(q.date()-st).days for q in (qual_date(a) for a in keep) if q]
    today = (NOW.date()-st).days
    last = min(0, today)
    rng = range(-T0, last+1)
    # signed date: contractSignedAt, else contractSyncedAt (set by the DocuSign sync, usually within ~2h of signing)
    signers = [a for a in by[c] if accepted(a) and a.get("contractSigned")]
    sdt = [ts(a.get("contractSignedAt")) or ts(a.get("contractSyncedAt")) for a in signers]
    # Undated signers predate the DocuSign->Firestore sync (~Jun 3, 2026); the DocuSign-exact ledger shows
    # C6's 13 of them were already signed by T-10w, so count them as signed before the window opens.
    sd = [(t.date()-st).days if t else -10**6 for t in sdt]
    tm[LAB[c]] = {"start": START[c], "today": today, "cum": [sum(1 for x in ad if x <= o) for o in rng],
                  "ccat_cum": [sum(1 for x in cdd if x <= o) for o in rng], "now": len(ad), "ccat_now": len(cdd),
                  "signed_cum": [sum(1 for x in sd if x <= o) for o in rng], "signed_total": len(signers),
                  "signed_dated": sum(1 for t in sdt if t), "signed_after_start": sum(1 for x in sd if x > 0),
                  "qual_cum": [sum(1 for x in qd if x <= o) for o in rng], "qual_now": len(qd)}
# DocuSign-exact confirmed counts at weeks-before-Day-1, from "ledger-v0-summary" (Drive, built 2026-09-15).
# C6 and C7 are complete cohorts, so these checkpoints are final.
LEDGER = {"C6": {10: 13, 8: 13, 6: 13, 4: 14, 2: 25, 1: 38, 0: 50}, "C7": {10: 4, 8: 10, 6: 14, 4: 21, 2: 31, 1: 38, 0: 54}}
out["tminus"] = {"days": T0, "cohorts": tm, "ledger": LEDGER}

# Weekly brief: org-wide activity (all C4-C8 records, deduped) in rolling 7-day windows ending now.
WK = 12
def wk_counts(dates, span=7):
    c = [0] * WK
    for t in dates:
        if not t: continue
        k = (NOW - t).days // span
        if 0 <= k < WK: c[WK - 1 - k] += 1
    return c
def period_metrics(span):
    return [
        {"key": "apps", "label": "New applications", "series": wk_counts((ts(a.get("createdAt")) for a in R), span)},
        {"key": "ccat", "label": "CCATs completed", "series": wk_counts((first_ccat(a) for a in R), span)},
        {"key": "qual", "label": "New 40+ scorers", "series": wk_counts((qual_date(a) for a in R), span)},
        {"key": "acc", "label": "Accepted", "series": wk_counts((ts(a.get("admissionsUpdatedAt")) for a in R if accepted(a)), span), "approx": True},
        {"key": "signed", "label": "Signed", "series": wk_counts((signed_date(a) for a in R if accepted(a) and a.get("contractSigned")), span)},
    ]
out["monthly"] = {"days": 30, "metrics": period_metrics(30)}
out["weekly"] = {"weeks": WK, "metrics": [
    {"key": "apps", "label": "New applications", "series": wk_counts(ts(a.get("createdAt")) for a in R)},
    {"key": "ccat", "label": "CCATs completed", "series": wk_counts(first_ccat(a) for a in R)},
    {"key": "qual", "label": "New 40+ scorers", "series": wk_counts(qual_date(a) for a in R)},
    {"key": "acc", "label": "Accepted", "series": wk_counts(ts(a.get("admissionsUpdatedAt")) for a in R if accepted(a)), "approx": True},
    {"key": "signed", "label": "Signed", "series": wk_counts(signed_date(a) for a in R if accepted(a) and a.get("contractSigned"))},
]}

# 2. Funnel rates
fun = {}
for c in COH:
    xs = by[c]; n=len(xs)
    past1 = sum(1 for a in xs if STEP.get(a.get("status"),0)>=2 or score(a) is not None)
    took = sum(1 for a in xs if score(a) is not None)
    acc = sum(1 for a in xs if accepted(a))
    sig = sum(1 for a in xs if accepted(a) and a.get("contractSigned"))
    rej = sum(1 for a in xs if a.get("adminDecision")=="rejected")
    fun[LAB[c]] = {"started":n,"past_step1":past1,"ccat":took,"accepted":acc,"signed":sig,"rejected":rej}
out["funnel"] = fun

# 3. CCAT band mix (policy bands)
bands = {}
for c in COH:
    b = collections.Counter()
    for a in by[c]:
        s = score(a)
        if s is None: continue
        b["<32" if s<32 else "32-34" if s<35 else "35-39" if s<40 else "40+"]+=1
    bands[LAB[c]] = {k:b[k] for k in ["<32","32-34","35-39","40+"]}
    sc=[score(a) for a in by[c] if score(a) is not None]
    bands[LAB[c]]["mean"]=round(S.mean(sc),1) if sc else None
    if sc:
        sc.sort(); q=lambda f: sc[int(f*(len(sc)-1))]
        bands[LAB[c]]["dist"]={"p10":q(.1),"p25":q(.25),"median":q(.5),"p75":q(.75),"p90":q(.9),"mean":round(S.mean(sc),1),"n":len(sc)}
out["bands"] = bands

# 5. CCAT velocity by application month (all cohorts C4+), first attempt within 14d
vel = collections.defaultdict(lambda:[0,0,0])
for a in R:
    t = ts(a.get("createdAt"))
    if not t or t.year<2025: continue
    m = t.strftime("%Y-%m")
    cc = ts(a.get("ccat1CompletedAt")) or ts(a.get("ccatCompletedAt"))
    vel[m][0]+=1
    if cc and (cc-t).days<=14: vel[m][1]+=1
    if cc: vel[m][2]+=1
out["velocity"] = [{"month":m,"n":v[0],"within14":v[1],"ever":v[2],"complete": (NOW-dt.datetime.fromisoformat(m+"-01T00:00:00+00:00")).days>=45} for m,v in sorted(vel.items()) if v[0]>=30]

# 6. Pending pool aging: active cohorts C7,C8 — no CCAT, no decision, status past step-1
pool = {}
for c in ["cohort_7","cohort_8"]:
    b = collections.Counter()
    for a in by[c]:
        if score(a) is None and a.get("adminDecision") in (None,"") and STEP.get(a.get("status"),0)>=2:
            d = (NOW-ts(a["createdAt"])).days if ts(a.get("createdAt")) else 999
            b["0-7" if d<=7 else "8-14" if d<=14 else "15-30" if d<=30 else "31+"]+=1
    pool[LAB[c]] = {k:b[k] for k in ["0-7","8-14","15-30","31+"]}
out["pool"] = pool

# 7. Decision SLA: days CCAT complete -> admissionsUpdatedAt (decided); undecided aging
sla = {}; und = {}
for c in ["cohort_6","cohort_7","cohort_8"]:
    ds=[]; ub=collections.Counter()
    for a in by[c]:
        cc = ts(a.get("ccatCompletedAt")) or ts(a.get("ccat2CompletedAt")) or ts(a.get("ccat1CompletedAt"))
        if not cc or score(a) is None: continue
        if a.get("adminDecision") not in (None,""):
            u = ts(a.get("admissionsUpdatedAt"))
            if u and u>=cc: ds.append((u-cc).total_seconds()/86400)
        else:
            d=(NOW-cc).days; ub["0-3" if d<=3 else "4-7" if d<=7 else "8-14" if d<=14 else "15+"]+=1
    ds.sort()
    q=lambda p: round(ds[int(p*(len(ds)-1))],1) if ds else None
    sla[LAB[c]]={"n":len(ds),"p25":q(.25),"median":q(.5),"p75":q(.75),"p90":q(.9),
                 "hist":[sum(1 for d in ds if lo<=d<hi) for lo,hi in [(0,1),(1,3),(3,7),(7,14),(14,30),(30,9999)]]}
    und[LAB[c]]={k:ub[k] for k in ["0-3","4-7","8-14","15+"]}
out["sla"]=sla; out["undecided"]=und

# 8. Accepted-but-unsigned aging (days since admissionsUpdatedAt)
uns = {}
for c in ["cohort_7","cohort_8"]:
    b=collections.Counter(); env=collections.Counter()
    for a in by[c]:
        if accepted(a) and not a.get("contractSigned"):
            u=ts(a.get("admissionsUpdatedAt")); d=(NOW-u).days if u else None
            k="unknown" if d is None else "0-7" if d<=7 else "8-14" if d<=14 else "15-30" if d<=30 else "31+"
            b[(k, "sent" if a.get("contractEnvelopeId") else "not sent")]+=1
    uns[LAB[c]]={k:{"sent":b[(k,"sent")],"not sent":b[(k,"not sent")]} for k in ["0-7","8-14","15-30","31+","unknown"]}
out["unsigned"]=uns

# 9. Retake delta
dl=[]
for a in R:
    s1,s2=a.get("ccat1Score"),a.get("ccat2Score")
    if isinstance(s1,(int,float)) and isinstance(s2,(int,float)): dl.append(int(s2-s1))
h=collections.Counter(max(-10,min(15,d)) for d in dl)
out["retake"]={"n":len(dl),"median":S.median(dl) if dl else None,"ge7":sum(d>=7 for d in dl),"le0":sum(d<=0 for d in dl),
               "hist":[{"d":d,"n":h[d]} for d in range(-10,16)]}
# retake: by starting band
rb=collections.defaultdict(list)
for a in R:
    s1,s2=a.get("ccat1Score"),a.get("ccat2Score")
    if isinstance(s1,(int,float)) and isinstance(s2,(int,float)):
        rb["<32" if s1<32 else "32-34" if s1<35 else "35-39" if s1<40 else "40+"].append(s2>=40)
out["retake"]["to40"]={k:[sum(v),len(v)] for k,v in rb.items()}

# 10. Source quality
norm={"reddit":"reddit","facebook":"meta","meta":"meta","fb":"meta","ig":"meta","instagram":"meta","referral":"referral","referrals":"referral",
      "austenli6.24":"austen","austen":"austen","hs_email":"hubspot email","hs_automation":"hubspot automation","linktree_ig":"meta","adwords":"google ads","x":"x/twitter","twitter":"x/twitter"}
src=collections.defaultdict(lambda:[0,0,0,0])
for a in R:
    u=(I.get(a["_id"]) or {}).get("utmSource")
    k=norm.get((u or "").strip().lower(), (u or "").strip().lower() or "(none)")
    src[k][0]+=1
    s=score(a)
    if s is not None:
        src[k][1]+=1; src[k][2]+= s>=40
    if accepted(a): src[k][3]+=1
out["sources"]=sorted([{"src":k,"apps":v[0],"ccat":v[1],"pass40":v[2],"accepted":v[3]} for k,v in src.items() if v[1]>=15],key=lambda r:-r["apps"])
out["utm_coverage"]=[sum(1 for a in R if (I.get(a["_id"]) or {}).get("utmSource")), len(R)]

# 4. Projection for C8: apps to date vs C7 pacing, times C6/C7 apps->signed rates
c7=pace["C7"]["ccat_cum"]; c8=pace["C8"]["ccat_cum"]; day=len(c8)-1
ratio = c8[-1]/c7[day]
final = ratio*c7[-1]
rates={k:fun[k]["signed"]/fun[k]["ccat"] for k in ["C5","C6","C7"]}
out["projection"]={"day":day,"c8_ccat":c8[-1],"c7_ccat_same_day":c7[day],"c7_ccat_final":c7[-1],"c8_ccat_final_est":round(final),
  "c8_apps":pace["C8"]["cum"][-1],"c7_apps_same_day":pace["C7"]["cum"][day],
  "rates":{k:round(v,4) for k,v in rates.items()},
  "signed_lo":round(final*min(rates.values())),"signed_hi":round(final*max(rates.values())),"signed_mid":round(final*rates["C7"]),
  "c8_signed_now":fun["C8"]["signed"],"c8_accepted_now":fun["C8"]["accepted"]}
HERE = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HERE, "template.html")).read().replace("__DATA__", json.dumps(out))
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "cohort_pulse.html")
open(dest, "w").write(html); print("wrote", dest, "as of", out["asOf"])
