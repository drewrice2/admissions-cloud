---
name: funnel-pools
description: Pull the middle-of-funnel pools from Firestore — pre-CCAT nurture pool, accepted-but-not-signed, deferral audit, cohort decision counts. Use when Drew asks "how many are pre-CCAT / unsigned / accepted", "who's in the pool", "boss check-in numbers", or wants an enrollment CSV for a HubSpot sequence.
---

# Funnel pools — Firestore queries

Project `gauntlet-hq`, SA key `gauntlet-hq-4a09285efcec.json` at repo root. READ-ONLY here;
writes only ever to `applications`/`applications_internal` per CLAUDE.md.

Run: `python3 .claude/skills/funnel-pools/pools.py [cohort_7]` — prints all pools; add `--csv <pool>` to write an enrollment CSV.

## The pools (definitions)
- **Pre-CCAT nurture pool** (feeds "Admissions — Pre-CCAT Nurture"): `appliedFor == cohort_N`, no `ccatScore`, has LinkedIn (`personalInfo.linkedinUrl` OR `linkedin.linkedinUrl`), no `adminDecision`. (Jul 2026 snapshot: 67 of 122 C7 applicants.)
- **Accepted, not signed** (feeds "Admissions — Accepted, Not Signed"): `adminDecision in (accepted, gfa-accepted)` and `contractSigned != True`. Sub-split by `contractEnvelopeStatus`: `sent` = envelope out, chase signature; missing = no envelope yet — investigate upstream friction (password reset / phone verification) before chasing.
- **Deferral audit**: as of Jul 2026 there is NO deferral marker anywhere (adminDecision values in use: accepted, gfa-accepted, rejected, withdrawn). Convention if/when adopted: `adminDecision: "deferred"` + `admissionsUpdatedAt` bump. Deferral asks live in email threads only — search the Gauntlet inbox.
- **C6 revival pool**: cohort_6 accepted-but-unsigned (24 people as of Jul 2026) — candidates for a "join Cohort 7" ask.

## Query gotchas (from CLAUDE.md, repeated because they bite)
- `.select()` projections + `.get()` with defaults everywhere; schema drifts by cohort age.
- `contractSigned` may be `True` or absent (never `False` in practice) — test `is not True`.
- Filter dates on `createdAt` (timestamp), never `appliedAt` (string).
- `ccatScore` unprefixed = latest attempt; `ccat` map = manual admin override, respect it.
- Email is the join key to HubSpot; `hubspotContactId` is only ~27% populated.
