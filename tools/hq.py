#!/usr/bin/env python3
"""HQ admissions CLI — Firestore is the source of truth. Works locally and in cloud sessions.

  find     EMAIL|NAME                       look someone up (all records, best first)
  band     EMAIL                            CCAT band + sliding-scale read
  migrate  EMAIL c8                         move / defer to a cohort
  decide   EMAIL accepted|rejected|withdrawn
  signed   EMAIL [--envelope ID]            mark contract signed
  envelope EMAIL ENVELOPE_ID                link a freshly sent DocuSign
  set      EMAIL key=value ...              update known fields (see SETTABLE)
  create   EMAIL --first F --last L --cohort c7 [--decision accepted] [--signed] [--ccat N] ...
  roster   c7 [--envelopes]                 accepted / signed / unsigned (+ envelope ids for DocuSign check)
  emails   c7 [--signed|--unsigned] [--track prime|gfa|all] [--names]

Global flags go BEFORE the subcommand: --dry-run, --doc DOC_ID (target one specific doc).
Writes hit the single most-advanced record for the email, never old stubs, and print old -> new.
Only the `applications` collection is ever written.

Credentials: env GAUNTLET_SA_JSON (base64 or raw JSON of the SA key), else gauntlet-hq-*.json at repo root.
"""
import argparse, base64, glob, json, os, sys, warnings

warnings.filterwarnings("ignore")
import firebase_admin
from firebase_admin import credentials, firestore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLL = "applications"
DECISIONS = {"accepted", "rejected", "withdrawn", "gfa-accepted"}
ALIASES = {"accept": "accepted", "admit": "accepted", "admitted": "accepted", "reject": "rejected",
           "decline": "rejected", "declined": "rejected", "withdraw": "withdrawn", "gfa": "gfa-accepted"}
STEP = {"step-1": 1, "step-2": 2, "step-3": 3, "step-4": 4, "step-5": 5, "submitted": 6,
        "step-6-approve": 7, "approved": 8}
# friendly key -> (firestore path, type). Only existing schema fields; never invent new ones.
SETTABLE = {
    "first": ("personalInfo.firstName", str), "last": ("personalInfo.lastName", str),
    "email": ("personalInfo.email", str), "phone": ("personalInfo.phone", str),
    "linkedin": ("personalInfo.linkedinUrl", str), "github": ("personalInfo.githubUsername", str),
    "resume": ("resume.resumePdfUrl", str), "hubspot": ("hubspotContactId", str),
    "ccat": ("ccatScore", int), "ccat1": ("ccat1Score", int), "ccat2": ("ccat2Score", int),
    "attempts": ("ccatAttempts", int), "status": ("status", str),
    "signed": ("contractSigned", bool), "envelope": ("contractEnvelopeId", str),
}
FIELDS = ["personalInfo", "appliedFor", "adminDecision", "contractSigned", "contractEnvelopeId",
          "ccatScore", "ccat1Score", "ccat2Score", "ccatAttempts", "ccat", "status", "updatedAt"]


def db():
    raw = os.environ.get("GAUNTLET_SA_JSON", "").strip().strip("'\"").strip()
    if raw:
        cred = credentials.Certificate(json.loads(raw if raw.startswith("{") else base64.b64decode(raw)))
    else:
        keys = glob.glob(os.path.join(ROOT, "gauntlet-hq-*.json"))
        if not keys:
            sys.exit("No credentials: set GAUNTLET_SA_JSON or put gauntlet-hq-*.json at repo root.")
        cred = credentials.Certificate(keys[0])
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()


def cohort(s):
    s = s.lower().strip()
    return s if s.startswith("cohort_") else "cohort_" + "".join(ch for ch in s if ch.isdigit())


def get(x, path):
    for part in path.split("."):
        x = (x or {}).get(part)
    return x


def records(d, email):
    return [x for x in d.collection(COLL).where("personalInfo.email", "==", email.strip().lower()).stream()
            if x.to_dict().get("appliedFor") != "duplicate"]


def rank(doc):
    x = doc.to_dict(); ts = x.get("updatedAt")
    return (x.get("adminDecision") is not None, x.get("ccatScore") is not None,
            STEP.get(x.get("status"), 0), ts.timestamp() if hasattr(ts, "timestamp") else 0)


def name(x):
    pi = x.get("personalInfo") or {}
    return f"{pi.get('firstName') or ''} {pi.get('lastName') or ''}".strip()


def line(doc):
    x = doc.to_dict(); pi = x.get("personalInfo") or {}
    return (f"{doc.id} | {name(x)} | {pi.get('email')} | {x.get('appliedFor')} | decision={x.get('adminDecision')} | "
            f"signed={x.get('contractSigned')} | ccat={x.get('ccatScore')} (attempts {x.get('ccatAttempts')}) | "
            f"status={x.get('status')} | envelope={x.get('contractEnvelopeId')}")


def target(d, a):
    if a.doc:
        doc = d.collection(COLL).document(a.doc).get()
        if not doc.exists:
            sys.exit(f"No doc {a.doc}")
        return doc
    docs = records(d, a.email)
    if not docs:
        sys.exit(f"NOT FOUND: {a.email} — try `find <first name>`, or `create` if they truly have no record.")
    best = max(docs, key=rank)
    for o in docs:
        if o.id != best.id:
            print(f"  (left untouched: {line(o)})")
    return best


def write(doc, fields, dry):
    before = doc.to_dict()
    changes = {k: v for k, v in fields.items() if not isinstance(v, type(firestore.SERVER_TIMESTAMP))}
    for k, v in changes.items():
        print(f"  {k}: {get(before, k)!r} -> {v!r}")
    if dry:
        print("DRY RUN — nothing written."); return
    fields["updatedAt"] = firestore.SERVER_TIMESTAMP
    doc.reference.update(fields)
    print("UPDATED:", line(doc.reference.get()))


def band(x):
    ov = get(x, "ccat.score")
    score = ov if isinstance(ov, (int, float)) else x.get("ccatScore")
    c1, c2 = x.get("ccat1Score"), x.get("ccat2Score")
    if score is None:
        score = c2 if c2 is not None else c1
    attempts = x.get("ccatAttempts") or sum(v is not None for v in (c1, c2)) or (1 if score is not None else 0)
    yrs = (get(x, "personalInfo.yearsEngineeringRange") or "").strip()
    notes = []
    if isinstance(ov, (int, float)):
        notes.append(f"manual override score {ov} in `ccat` map")
    if c1 is not None and c2 is not None and c2 - c1 >= 7:
        notes.append(f"retake jump {c1}->{c2} (+{c2 - c1}) — yellow flag, deliberate")
    if score is None:
        b = "PENDING_CCAT"
    elif score >= 40:
        b = "AUTO_ADVANCE"
    elif score >= 35:
        b = "RETAKE_ELIGIBLE" if attempts < 2 else "GFA_ROUTE (GFA on ice — park for Drew)"
    elif score >= 32:
        b = "RETAKE_ZONE" if attempts < 2 else "AUTO_DECLINE"
    else:
        b = "AUTO_DECLINE"
    if score is not None and 36 <= score <= 39:
        senior = {"10 plus years": "10+ yrs self-reported: clears at 38 (7–15y) or 36 (15y+)",
                  "6-9 years": "6–9 yrs self-reported: clears at 38 only if 7+ yrs verified",
                  "5 plus": "'5 plus' self-reported: could be 7+ — check LinkedIn"}.get(yrs)
        if senior:
            need = 38 if "36 (15y+)" not in senior else 36
            ok = score >= 38 or (score >= 36 and need == 36)
            notes.append(f"SLIDING SCALE {'possible' if ok else 'not met'}: {senior}. "
                         "Bonafide hands-on SWE years only — verify on LinkedIn before admitting.")
        else:
            notes.append(f"sliding scale does not apply (years: {yrs or 'unknown'} → needs 40)")
    return score, attempts, yrs, b, notes


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--doc")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("find").add_argument("email")
    sp.add_parser("band").add_argument("email")
    s = sp.add_parser("migrate"); s.add_argument("email"); s.add_argument("cohort")
    s = sp.add_parser("decide"); s.add_argument("email"); s.add_argument("decision"); s.add_argument("--allow-gfa", action="store_true")
    s = sp.add_parser("signed"); s.add_argument("email"); s.add_argument("--envelope")
    s = sp.add_parser("envelope"); s.add_argument("email"); s.add_argument("envelope_id")
    s = sp.add_parser("set"); s.add_argument("email"); s.add_argument("pairs", nargs="+")
    s = sp.add_parser("create"); s.add_argument("email")
    s.add_argument("--first", required=True); s.add_argument("--last", required=True)
    s.add_argument("--cohort", required=True); s.add_argument("--decision")
    s.add_argument("--signed", action="store_true"); s.add_argument("--ccat", type=int)
    s.add_argument("--linkedin"); s.add_argument("--resume"); s.add_argument("--hubspot"); s.add_argument("--phone")
    s.add_argument("--status", default="submitted"); s.add_argument("--force", action="store_true")
    s = sp.add_parser("roster"); s.add_argument("cohort"); s.add_argument("--envelopes", action="store_true")
    s = sp.add_parser("emails"); s.add_argument("cohort")
    g = s.add_mutually_exclusive_group(); g.add_argument("--signed", action="store_true"); g.add_argument("--unsigned", action="store_true")
    s.add_argument("--track", choices=["prime", "gfa", "all"], default="all"); s.add_argument("--names", action="store_true")
    a = p.parse_args()
    d = db()

    if a.cmd == "find":
        q = a.email.strip().lower()
        docs = records(d, q) if "@" in q else []
        if not docs:
            toks = q.split("@")[0].replace(".", " ").split()
            docs = [x for x in d.collection(COLL).select(FIELDS).stream()
                    if all(t in name(x.to_dict()).lower() for t in toks)]
        for x in sorted(docs, key=rank, reverse=True): print(line(x))
        if not docs: print("NOT FOUND")

    elif a.cmd == "band":
        doc = target(d, a); x = doc.to_dict()
        score, att, yrs, b, notes = band(x)
        print(f"{name(x)} | {x.get('appliedFor')} | ccat={score} attempts={att} (c1={x.get('ccat1Score')}, "
              f"c2={x.get('ccat2Score')}) | years={yrs or '?'} | BAND: {b}")
        for n in notes: print("  -", n)

    elif a.cmd == "migrate":
        doc = target(d, a); c = cohort(a.cohort)
        if doc.to_dict().get("appliedFor") == c: print("Already", c, "->", line(doc))
        else: write(doc, {"appliedFor": c}, a.dry_run)

    elif a.cmd == "decide":
        dec = ALIASES.get(a.decision.lower(), a.decision.lower())
        if dec not in DECISIONS: sys.exit(f"Bad decision {dec}; use {sorted(DECISIONS)}")
        if dec == "gfa-accepted" and not a.allow_gfa: sys.exit("GFA is on ice (Sept 2026). Only with Drew's explicit OK: add --allow-gfa.")
        write(target(d, a), {"adminDecision": dec, "admissionsUpdatedAt": firestore.SERVER_TIMESTAMP}, a.dry_run)

    elif a.cmd == "signed":
        f = {"contractSigned": True, "contractEnvelopeStatus": "completed", "contractSyncedAt": firestore.SERVER_TIMESTAMP}
        if a.envelope: f["contractEnvelopeId"] = a.envelope
        write(target(d, a), f, a.dry_run)

    elif a.cmd == "envelope":
        write(target(d, a), {"contractEnvelopeId": a.envelope_id, "contractEnvelopeStatus": "sent",
                             "contractSyncedAt": firestore.SERVER_TIMESTAMP}, a.dry_run)

    elif a.cmd == "set":
        doc = target(d, a); x = doc.to_dict(); f = {}
        for pair in a.pairs:
            if "=" not in pair: sys.exit(f"Use key=value, got {pair}")
            k, v = pair.split("=", 1)
            if k not in SETTABLE: sys.exit(f"Unknown key {k}. Settable: {', '.join(SETTABLE)}")
            path, typ = SETTABLE[k]
            f[path] = (v.lower() in ("1", "true", "yes", "y")) if typ is bool else typ(v)
        if "ccatScore" in f and x.get("ccat1Score") is None and x.get("ccatAttempts") is None and "ccat1Score" not in f:
            f["ccat1Score"] = f["ccatScore"]; f.setdefault("ccatAttempts", 1)
        write(doc, f, a.dry_run)

    elif a.cmd == "create":
        existing = records(d, a.email)
        if existing and not a.force:
            for x in existing: print(line(x))
            sys.exit("Record(s) already exist — use migrate/decide/set instead (or --force if truly separate).")
        doc = {"personalInfo": {"firstName": a.first, "lastName": a.last, "email": a.email.strip().lower()},
               "appliedFor": cohort(a.cohort), "status": a.status,
               "createdAt": firestore.SERVER_TIMESTAMP, "updatedAt": firestore.SERVER_TIMESTAMP}
        if a.phone: doc["personalInfo"]["phone"] = a.phone
        if a.linkedin: doc["personalInfo"]["linkedinUrl"] = a.linkedin
        if a.resume: doc["resume"] = {"resumePdfUrl": a.resume}
        if a.hubspot: doc["hubspotContactId"] = a.hubspot
        if a.ccat is not None: doc.update(ccatScore=a.ccat, ccat1Score=a.ccat, ccatAttempts=1)
        if a.decision:
            dec = ALIASES.get(a.decision.lower(), a.decision.lower())
            if dec not in DECISIONS - {"gfa-accepted"}: sys.exit(f"Bad decision {dec}")
            doc.update(adminDecision=dec, admissionsUpdatedAt=firestore.SERVER_TIMESTAMP)
        if a.signed: doc["contractSigned"] = True
        if a.dry_run: print("DRY RUN, would create:", doc); return
        ref = d.collection(COLL).document(); ref.set(doc)
        print("CREATED:", line(ref.get()))

    elif a.cmd in ("roster", "emails"):
        c = cohort(a.cohort); best = {}
        for x in d.collection(COLL).where("appliedFor", "==", c).select(FIELDS).stream():
            v = x.to_dict()
            if v.get("adminDecision") not in ("accepted", "gfa-accepted"): continue
            e = (get(v, "personalInfo.email") or x.id).lower()
            if e not in best or rank(x) > rank(best[e]): best[e] = x
        docs = sorted(best.values(), key=lambda x: name(x.to_dict()).lower())
        if a.cmd == "roster":
            signed = [x for x in docs if x.to_dict().get("contractSigned")]
            gfa = [x for x in docs if x.to_dict().get("adminDecision") == "gfa-accepted"]
            print(f"{c}: accepted {len(docs)} (GFA {len(gfa)}) | signed {len(signed)} | unsigned {len(docs) - len(signed)}")
            uns = [x for x in docs if not x.to_dict().get("contractSigned")]
            for x in uns: print("  unsigned:", line(x))
            if a.envelopes:
                envs = [x.to_dict().get("contractEnvelopeId") for x in uns if x.to_dict().get("contractEnvelopeId")]
                print("ENVELOPE_IDS:", ",".join(envs))
                print("NO_ENVELOPE:", ", ".join(get(x.to_dict(), "personalInfo.email") for x in uns
                                                if not x.to_dict().get("contractEnvelopeId")))
        else:
            sel = [x.to_dict() for x in docs]
            if a.signed: sel = [v for v in sel if v.get("contractSigned")]
            if a.unsigned: sel = [v for v in sel if not v.get("contractSigned")]
            if a.track == "prime": sel = [v for v in sel if v.get("adminDecision") == "accepted"]
            if a.track == "gfa": sel = [v for v in sel if v.get("adminDecision") == "gfa-accepted"]
            print(f"# {len(sel)} — {c} {'signed' if a.signed else 'unsigned' if a.unsigned else 'all accepted'} ({a.track})")
            if a.names:
                for v in sel: print(f"{name(v)} <{get(v, 'personalInfo.email')}>")
            else:
                print(", ".join(get(v, "personalInfo.email") for v in sel))


if __name__ == "__main__":
    main()
