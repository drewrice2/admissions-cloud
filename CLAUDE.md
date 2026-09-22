# Gauntlet Admissions — `applications` collection

Firestore project **`gauntlet-hq`**. SA key at repo root: `gauntlet-hq-4a09285efcec.json`.
Full traversal reference (setup, query patterns, recipes, every field): **`FIREBASE_API_CHEATSHEET.md`**.
This file is the *work-focused* cut — the fields that actually drive admissions, and how to read them.

## Quick actions (local or cloud) — use `tools/hq.py`, don't hand-write Firestore code
Setup in a fresh cloud session: `pip install firebase-admin` (creds come from env `GAUNTLET_SA_JSON`).

| Drew says | Run |
|---|---|
| "who is X" / "check on X" | `python3 tools/hq.py find EMAIL` (no hit? pass first name instead) |
| "migrate / defer / move X to C8" | `python3 tools/hq.py migrate EMAIL c8` |
| "accept / admit X" | `python3 tools/hq.py decide EMAIL accepted` |
| "reject / decline X" | `python3 tools/hq.py decide EMAIL rejected` |
| "X withdrew / got a job" | `python3 tools/hq.py decide EMAIL withdrawn` |
| "X signed" | `python3 tools/hq.py signed EMAIL [--envelope ID]` |
| "C7 numbers / who hasn't signed" | `python3 tools/hq.py roster c7` |

Deferring keeps `accepted` + any signed contract (C8 deferrals sign the existing agreement).
Before deferring on an email thread's say-so, read the latest message — people un-defer.

**Retrigger DocuSign** (DocuSign connector, account `906c974f-f83f-45da-af04-f622e7d2bdf4`):
1. `getEnvelopes` with `search_text=EMAIL` — if one is `completed`, just run `hq.py signed`.
2. Otherwise `createEnvelope` status `created`, templateId `53f42ba5-1dd1-44c9-9fd9-715a0d08c0f9`
   (Prime C7; GFA is `2699b060-…` but GFA is on ice), `templateRoles=[{roleName:"Signer 1", name, email}]`.
   Prefill tabs already have values — nothing to fill.
3. `updateEnvelope` status `sent`, then `python3 tools/hq.py envelope EMAIL ENVELOPE_ID`.
Confirm with Drew before sending anything to a candidate.

## Write policy — non-negotiable
**Read anything. Write ONLY `applications` and `applications_internal`.** No other collection may be
written/updated/deleted, ever. The SA bypasses security rules, so this is on us to honor. A `PreToolUse`
hook (`.claude/hooks/firestore-write-guard.py`) denies mutations elsewhere as a backstop.

## Doc model
- Doc ID is opaque (e.g. `00cCHfv6yWOBcey5bxqe`) and is the **join key** into `applications_internal`
  (same ID; holds `llmReview`, `scrapedDataRaw` LinkedIn enrichment, UTM attribution).
- **Schema drifts by age.** Old cohort_3 docs are sparse; current cohort_6 docs populate far more fields.
  Always code defensively — `.get()` with defaults, handle missing keys.

## The fields we care about

These nine are the canonical set for our work. Friendly name → actual Firestore path:

| We call it | Firestore path | Notes |
|---|---|---|
| `applied_for` | `appliedFor` | Cohort. Active = **`cohort_6`**. Drop `"duplicate"`; normalize `cohort-4` typo → `cohort_4`. |
| `firstname` | `personalInfo.firstName` | |
| `lastname` | `personalInfo.lastName` | |
| `email` | `personalInfo.email` | Primary join key to pipeline files & HubSpot. ~95% populated. |
| `linkedInProfile` | `personalInfo.linkedinUrl` **or** `linkedin.linkedinUrl` | Check **both** — either may hold it. |
| `ccat_score` | `ccatScore` (latest); `ccat1Score` / `ccat2Score` per attempt | See CCAT note below — dual schema. |
| `adminDecision` | `adminDecision` | Enum: **`accepted`**, **`gfa-accepted`**, **`rejected`**. The admit/reject write. |
| `yearsExperience` | `personalInfo.yearsEngineeringRange` | Enum: `0 to 1`, `1 to 2`, `3 to 5`, `5 plus` (no `2 to 3`). cohort_6-only, Firebase-only. |
| `technicalAchievement` | `achievement` (map: `{description, link}`) | Often empty `{"description":"","link":""}`. `achievementNoteId` is a separate pointer. |

### `adminDecision` — the admit/reject write (NOT a `status` change)
The accept/reject decision lives in its own `adminDecision` field, separate from the funnel `status`.
Canonical values: **`accepted`** (Prime), **`gfa-accepted`** (GFA route), **`rejected`** (decline).
Write it together with `admissionsUpdatedAt: SERVER_TIMESTAMP`. Never overload `status` for this.
(An older `"admitted"` value was superseded by `accepted` — treat any legacy `"admitted"` as `accepted`.)
On duplicate records, target the real/advanced doc (higher status, has CCAT/submission), not the empty stub.

### `ccat_score` — dual schema, read carefully
- **Latest attempt (unprefixed):** `ccatScore`, plus `ccatPassed`, `ccatPercentile`, `ccatRankingScore`, `ccatInvalid`.
- **Per attempt:** `ccat1*` = first, `ccat2*` = retake. `ccatAttempts` (int) disambiguates.
- When both present, unprefixed = latest, `ccat1*` = first. A retake jump ≥7 pts → flag for deliberation.
- `ccat` map `{updatedBy,updatedAt,score}` is a **manual admin override** — respect it over computed values.
- Band cutoffs (hq-resync): 40+ AUTO_ADVANCE · 35–39/1 RETAKE_ELIGIBLE · 35–39/2+ GFA_ROUTE ·
  32–34/1 RETAKE_ZONE · 32–34 2+ or <32 AUTO_DECLINE · no score PENDING_CCAT.

### Supporting context (not in the core set, but useful)
- `status` — funnel stage: `step-1`…`step-5`, `submitted`, `step-6-approve/reject`, `approved`/`rejected`.
  `step-1` is the form's initial state (~41% never leave it). cohort_6 is currently all steps 1–5.
- `hubspotContactId` — direct HubSpot link but sparse (~27% overall); fall back to `email` match.
- `resume.resumePdfUrl`, `personalInfo.{phone, githubUsername}` when fuller context is needed.

## Type gotchas (will bite range queries)
- `appliedAt` is a **string** ISO timestamp; `createdAt`/`updatedAt`/`submittedAt` are real timestamps.
  Filter dates on `createdAt`, not `appliedAt`.
- `emailSequenceTimestamp` is **mixed type** (`datetime` *or* `str`) — always coerce.
- `pausedTimestamp`, `ccatCompletedAt`, `ccatPassed` can be `null` even when present.

## Cheap reads
- Count: `db.collection("applications").count().get()[0][0].value` (~12,969).
- Project only what you need: `.select(["status","appliedFor","personalInfo"])`.
- Join to internal in one round-trip: `db.get_all([... document refs ...])`.
