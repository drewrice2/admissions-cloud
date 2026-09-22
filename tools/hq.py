#!/usr/bin/env python3
"""One-stop HQ admissions CLI. Works locally and in cloud sessions.

  python3 tools/hq.py find     EMAIL
  python3 tools/hq.py migrate  EMAIL c8
  python3 tools/hq.py decide   EMAIL accepted|rejected|withdrawn
  python3 tools/hq.py signed   EMAIL [--envelope ENVELOPE_ID]
  python3 tools/hq.py envelope EMAIL ENVELOPE_ID          # link a freshly sent DocuSign
  python3 tools/hq.py roster   c7                         # accepted / signed / unsigned

Writes target the single most-advanced record for the email (never old stubs);
pass --doc DOC_ID to override. Only `applications` is ever written.

Credentials: env GAUNTLET_SA_JSON (raw JSON or base64 of the SA key), else the
local key file gauntlet-hq-*.json at the repo root.
"""
import argparse, base64, glob, json, os, sys, warnings

warnings.filterwarnings("ignore")
import firebase_admin
from firebase_admin import credentials, firestore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLL = "applications"  # the only collection this tool writes
DECISIONS = {"accepted", "rejected", "withdrawn", "gfa-accepted"}
ALIASES = {"accept": "accepted", "admit": "accepted", "reject": "rejected", "decline": "rejected",
           "declined": "rejected", "withdraw": "withdrawn", "gfa": "gfa-accepted"}
STEP = {"step-1": 1, "step-2": 2, "step-3": 3, "step-4": 4, "step-5": 5, "submitted": 6,
        "step-6-approve": 7, "approved": 8}


def db():
    raw = os.environ.get("GAUNTLET_SA_JSON", "").strip()
    if raw:
        info = json.loads(raw if raw.startswith("{") else base64.b64decode(raw))
        cred = credentials.Certificate(info)
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
    if s.startswith("cohort_"):
        return s
    return "cohort_" + s.lstrip("c").lstrip("ohort-").lstrip("_")


def records(d, email):
    return [x for x in d.collection(COLL).where("personalInfo.email", "==", email.strip().lower()).stream()
            if x.to_dict().get("appliedFor") != "duplicate"]


def rank(doc):
    x = doc.to_dict(); ts = x.get("updatedAt")
    return (x.get("adminDecision") is not None, x.get("ccatScore") is not None,
            STEP.get(x.get("status"), 0), ts.timestamp() if hasattr(ts, "timestamp") else 0)


def line(doc):
    x = doc.to_dict(); pi = x.get("personalInfo", {}) or {}
    return (f"{doc.id} | {pi.get('firstName','')} {pi.get('lastName','')} | {pi.get('email')} | "
            f"{x.get('appliedFor')} | decision={x.get('adminDecision')} | signed={x.get('contractSigned')} | "
            f"ccat={x.get('ccatScore')} (attempts {x.get('ccatAttempts')}) | status={x.get('status')} | "
            f"envelope={x.get('contractEnvelopeId')}")


def target(d, a):
    if a.doc:
        doc = d.collection(COLL).document(a.doc).get()
        if not doc.exists:
            sys.exit(f"No doc {a.doc}")
        return doc
    docs = records(d, a.email)
    if not docs:
        sys.exit(f"NOT FOUND: {a.email} — check spelling or search by name with `find`.")
    best = max(docs, key=rank)
    for o in docs:
        if o.id != best.id:
            print(f"  (left untouched: {line(o)})")
    return best


def write(doc, fields, dry):
    fields["updatedAt"] = firestore.SERVER_TIMESTAMP
    if dry:
        print("DRY RUN, would set:", {k: v for k, v in fields.items() if k != "updatedAt"}); return
    doc.reference.update(fields)
    print("UPDATED:", line(doc.reference.get()))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    sp = p.add_subparsers(dest="cmd", required=True)
    for name, extra in [("find", []), ("migrate", ["cohort"]), ("decide", ["decision"]),
                        ("signed", []), ("envelope", ["envelope_id"])]:
        s = sp.add_parser(name); s.add_argument("email")
        for e in extra: s.add_argument(e)
        s.add_argument("--doc")
        if name == "signed": s.add_argument("--envelope")
    sp.add_parser("roster").add_argument("cohort")
    a = p.parse_args()
    d = db()

    if a.cmd == "find":
        docs = records(d, a.email)
        if not docs:
            first = a.email.split("@")[0].lower()
            docs = [x for x in d.collection(COLL).select(["personalInfo", "appliedFor", "adminDecision",
                    "contractSigned", "ccatScore", "ccatAttempts", "status", "contractEnvelopeId"]).stream()
                    if first in f"{(x.to_dict().get('personalInfo') or {}).get('firstName','')} "
                                 f"{(x.to_dict().get('personalInfo') or {}).get('lastName','')}".lower()]
        for x in sorted(docs, key=rank, reverse=True): print(line(x))
        if not docs: print("NOT FOUND")
    elif a.cmd == "migrate":
        doc = target(d, a); c = cohort(a.cohort)
        if doc.to_dict().get("appliedFor") == c: print("Already", c, "->", line(doc))
        else: write(doc, {"appliedFor": c}, a.dry_run)
    elif a.cmd == "decide":
        dec = ALIASES.get(a.decision.lower(), a.decision.lower())
        if dec not in DECISIONS: sys.exit(f"Bad decision {dec}; use {sorted(DECISIONS)}")
        if dec == "gfa-accepted": print("WARNING: GFA is on ice (Sept 2026) — confirm with Drew.")
        write(target(d, a), {"adminDecision": dec, "admissionsUpdatedAt": firestore.SERVER_TIMESTAMP}, a.dry_run)
    elif a.cmd == "signed":
        f = {"contractSigned": True, "contractEnvelopeStatus": "completed", "contractSyncedAt": firestore.SERVER_TIMESTAMP}
        if a.envelope: f["contractEnvelopeId"] = a.envelope
        write(target(d, a), f, a.dry_run)
    elif a.cmd == "envelope":
        write(target(d, a), {"contractEnvelopeId": a.envelope_id, "contractEnvelopeStatus": "sent",
                             "contractSyncedAt": firestore.SERVER_TIMESTAMP}, a.dry_run)
    elif a.cmd == "roster":
        c = cohort(a.cohort); seen = {}
        for x in d.collection(COLL).where("appliedFor", "==", c).stream():
            v = x.to_dict()
            if v.get("adminDecision") in ("accepted", "gfa-accepted"):
                e = ((v.get("personalInfo") or {}).get("email") or x.id).lower()
                if e not in seen or rank(x) > rank(seen[e]): seen[e] = x
        signed = [x for x in seen.values() if x.to_dict().get("contractSigned")]
        print(f"{c}: accepted {len(seen)} | signed {len(signed)} | unsigned {len(seen) - len(signed)}")
        for x in seen.values():
            if not x.to_dict().get("contractSigned"): print("  unsigned:", line(x))


if __name__ == "__main__":
    main()
