#!/usr/bin/env python3
"""Middle-of-funnel pool report. Usage: pools.py [cohort_7] [--csv pre_ccat|unsigned]"""
import csv
import sys
from collections import Counter
from pathlib import Path

from google.cloud import firestore
from google.oauth2 import service_account

REPO = Path(__file__).resolve().parents[3]
ACCEPT_VALUES = ("accepted", "gfa-accepted", "admitted")  # legacy "admitted" == accepted

FIELDS = [
    "adminDecision", "ccatScore", "contractSigned", "contractEnvelopeStatus",
    "status", "personalInfo.email", "personalInfo.firstName", "personalInfo.lastName",
    "personalInfo.linkedinUrl", "linkedin.linkedinUrl", "personalInfo.phone",
]


def db():
    creds = service_account.Credentials.from_service_account_file(
        REPO / "gauntlet-hq-4a09285efcec.json")
    return firestore.Client(project="gauntlet-hq", credentials=creds)


def linkedin(x):
    return (x.get("personalInfo") or {}).get("linkedinUrl") or (x.get("linkedin") or {}).get("linkedinUrl")


def person(x):
    p = x.get("personalInfo") or {}
    return {
        "firstName": p.get("firstName", ""), "lastName": p.get("lastName", ""),
        "email": p.get("email", ""), "phone": p.get("phone", ""),
        "linkedin": linkedin(x) or "",
    }


def main():
    cohort = next((a for a in sys.argv[1:] if a.startswith("cohort")), "cohort_7")
    csv_pool = sys.argv[sys.argv.index("--csv") + 1] if "--csv" in sys.argv else None

    docs = db().collection("applications").where("appliedFor", "==", cohort).select(FIELDS).stream()
    total, decisions = 0, Counter()
    pre_ccat, unsigned, defer_check = [], [], Counter()
    for d in docs:
        x = d.to_dict()
        total += 1
        ad = x.get("adminDecision")
        decisions[ad or "(none)"] += 1
        if ad and "defer" in str(ad).lower():
            defer_check[ad] += 1
        if not ad and not x.get("ccatScore") and linkedin(x):
            pre_ccat.append(person(x))
        if ad in ACCEPT_VALUES and x.get("contractSigned") is not True:
            unsigned.append({**person(x), "envelope": x.get("contractEnvelopeStatus") or "(no envelope)"})

    print(f"=== {cohort} ({total} applications) ===")
    print(f"decisions: {dict(decisions)}")
    print(f"deferral markers: {dict(defer_check) or 'none (no defer convention exists)'}")
    print(f"\nPre-CCAT nurture pool (no decision, no CCAT, has LinkedIn): {len(pre_ccat)}")
    print(f"Accepted, not signed: {len(unsigned)}")
    for u in unsigned:
        print(f"  {u['firstName']} {u['lastName']} <{u['email']}> env={u['envelope']}")

    if csv_pool:
        rows = pre_ccat if csv_pool == "pre_ccat" else unsigned
        out = REPO / f"{cohort}_{csv_pool}_pool.csv"
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nWrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
