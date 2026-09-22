# Admissions Criteria

## Prime (Commercial)

### Hard Gates

| Criterion | Threshold | Notes |
|-----------|-----------|-------|
| CCAT Score | Sliding scale (see below) | Primary screening gate. No exceptions below scale without COO approval. |
| Core SWE Experience | 3+ years (90% of cohort) | Bonafide SWE only. 10% max wunderkind exception (<3yr). |
| Interview | Pass | Single interview covering technical fundamentals, communication, collaboration, resilience, program fit. See `criteria/behavioral-interview-rubric.md` for scoring dimensions. |

### CCAT Sliding Scale

Experience compensates for CCAT within the 36–39 range. Years = bonafide SWE experience only (see definition below).

| SWE Experience | Min CCAT | Notes |
|---------------|----------|-------|
| 0–6 years | 40+ | Standard gate |
| 7–15 years | 38+ | Senior/staff engineers with deep production experience |
| 15+ years | 36+ | Principal+ level, extensive track record |

**Bonafide SWE experience only.** Only core software engineering roles with hands-on coding count toward the sliding scale. The following do **not** qualify: Data Science, Machine Learning (research-only), Data Analytics, Technical Program Management, non-coding Product Management, QA/Testing-only roles, IT/Systems Administration, and DevOps-only roles. If a candidate has a mixed background, only years spent in a hands-on coding role count.

### Wunderkind Exception (10% Cap)

Up to 10% of a cohort may be admitted with <3 years bonafide SWE. These candidates must demonstrate undeniable, extraordinary talent — e.g., triple major, exceptional open-source contributions, or comparable intensity. Requires `wunderkind` flag and Drew's explicit approval. `/status` tracks the cohort ratio.

### Soft Signals

- GitHub activity and project quality
- LinkedIn profile completeness and career trajectory
- Open source contributions
- Engineering discipline (see `experience-tiers.md`)
- Company/team pedigree (informational, not preferential)

## Gauntlet for America (GFA)

### Hard Gates

| Criterion | Threshold | Notes |
|-----------|-----------|-------|
| CCAT Score | 35+ | Lower threshold than commercial. |
| Core SWE Experience | Flexible | Shorter tenure accepted. Holistic evaluation. |
| Interview | Pass | Same interview as commercial. |

### Additional GFA Requirements

- U.S. citizenship (required for federal placement)
- Background check eligibility
- Clearance readiness (adds weeks/months — tracked in candidate file's GFA Compliance section)
- Willingness to accept federal employment terms

### GFA Candidate Sources

1. Candidates who score 35–39 on CCAT after two attempts (exhausted Prime retake path)
2. Direct GFA applicants (new application path under development)

GFA is a terminal routing decision after the Prime path is exhausted. No candidate is routed to GFA on a first CCAT attempt.

## Triage Bands

Band definitions live in `criteria/taxonomy.md`. Per-band actions and templates live in `runbooks/status-action-matrix.md`. Apply the `deliberation` flag on top of any band when human judgment is needed; check `decisions/decision-log.md` for precedent.

## Rules

1. **Merit-based only.** No demographic, institutional, or network preferences.
2. **Sparse profiles get outreach before decline.** Always.
3. **CCAT retake jumps are a yellow flag**, not a hard gate. Tech eval is the real signal. See `runbooks/email-rules.md` §CCAT retake.
4. **GFA is not a consolation.** Never position as "you didn't make commercial."
5. **Criteria changes require Brett's approval.** Flag, don't adjust.
