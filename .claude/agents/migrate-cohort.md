---
name: migrate-cohort
description: Migrate an applicant to a different cohort by email. Usage: /migrate-cohort <email> <cohort> (e.g. /migrate-cohort foo@gmail.com c8)
---

Run `python3 tools/hq.py migrate <email> <cohort>` from the repo root (cohort accepts `c8`, `cohort_8`).
It moves only the most-advanced record and prints any records it left untouched. Report that output.
If NOT FOUND, run `python3 tools/hq.py find <first name>` and ask the user which match they meant.
