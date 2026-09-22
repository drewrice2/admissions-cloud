# Gauntlet Admissions — `applications` collection

Firestore project **`gauntlet-hq`**. SA key: local file `gauntlet-hq-*.json` at repo root (never committed), or env `GAUNTLET_SA_JSON` in cloud.
Full traversal reference (setup, query patterns, recipes, every field): **`FIREBASE_API_CHEATSHEET.md`**.
This file is the *work-focused* cut — the fields that actually drive admissions, and how to read them.

## Source of truth
**Firestore is the source of truth.** DocuSign, Gmail and HubSpot are gut-checks: when they disagree with
Firestore, verify, then correct Firestore (e.g. DocuSign `completed` but `contractSigned` empty → mark signed).
Never "fix" Firestore from a single ambiguous signal — read the latest evidence first.

**Cohort state (update as it changes):** C7 kicked off 2026-09-14. **"Defer" = move to `cohort_8`** (next cohort,
late Jan/Feb 2027). No C8 DocuSign template exists yet — C8 deferrals keep their existing signed agreement.

## Standing rules (Drew's preferences — follow without being told)
- Confirm with Drew before **sending** anything to a candidate. Gmail *drafts* are fine without asking.
- Never mention Drew's personal email address; drafts live in "the Gauntlet inbox".
- GFA is on ice (Sept 2026): never write `gfa-accepted`; a 35–39 on 2+ attempts parks for Drew.
- Deferring keeps `adminDecision: accepted` and any signed contract. Withdrawals (job offer, can't commit) → `withdrawn`.
- Admission bar lives in `policy/admissions-criteria.md` (CCAT sliding scale, wunderkind cap). Criteria changes need Brett — flag, don't adjust.
- After any batch of writes, report a short table: who, what changed (old → new), and anything left for Drew.

## Quick actions — use `tools/hq.py`, don't hand-write Firestore code
Cloud setup script: `pip install --ignore-installed pyjwt firebase-admin` (creds from env `GAUNTLET_SA_JSON`).
Global flags go before the subcommand: `hq.py --dry-run …`, `hq.py --doc DOC_ID …`.

| Drew says | Run |
|---|---|
| "who is X" / "check on X" | `python3 tools/hq.py find EMAIL` — or a name: `find "nathan chan"` |
| "should we admit X" / "what's X's CCAT situation" | `python3 tools/hq.py band EMAIL` |
| "migrate / defer / move X to C8" | `python3 tools/hq.py migrate EMAIL c8` |
| "accept / admit X" | `python3 tools/hq.py decide EMAIL accepted` |
| "reject / decline X" | `python3 tools/hq.py decide EMAIL rejected` |
| "X withdrew / got a job" | `python3 tools/hq.py decide EMAIL withdrawn` |
| "X signed" | `python3 tools/hq.py signed EMAIL [--envelope ID]` |
| "add X's CCAT / LinkedIn / resume / phone" | `python3 tools/hq.py set EMAIL ccat=43 linkedin=URL resume=URL` |
| "X has no record, make one" | Look them up in HubSpot first, then `hq.py create EMAIL --first F --last L --cohort c7 --decision accepted [--signed] [--ccat N] [--hubspot ID]` |
| "C7 numbers / who hasn't signed" | `python3 tools/hq.py roster c7` |
| "give me the emails of …" | `python3 tools/hq.py emails c7 --signed --track prime` (`--unsigned`, `--track gfa`, `--names`) |

Writes always target the person's most-advanced record (has decision > has CCAT > furthest status) and print
`old -> new`, so any mistake can be reversed by running the inverse command. Records it skipped are listed.

## Recipes (the recurring workflows)

**A. DocuSign gut-check ("is everyone who signed marked signed?")**
1. `hq.py roster c7 --envelopes` → copy the `ENVELOPE_IDS:` line.
2. DocuSign `getEnvelopes` (account `906c974f-f83f-45da-af04-f622e7d2bdf4`) with `envelope_ids=<that list>`.
3. Every envelope with status `completed` → `hq.py signed EMAIL --envelope ID`.
4. For `NO_ENVELOPE:` people, also `getEnvelopes search_text=EMAIL from_date=2026-06-01` — HQ sometimes sent
   one without recording it. Link a real one with `hq.py envelope`/`signed`; ignore old C5/C6 envelopes.
5. Report: newly marked signed, still out (sent/delivered), no contract at all.

**B. Inbox sweep for defers / withdrawals / "I'm in"**
1. Gmail `search_threads` for replies in the last few days (e.g. `in:inbox -from:me newer_than:3d (defer OR withdraw OR cohort)`),
   plus replies on the latest last-call / launch thread.
2. For each person, **read their most recent message** (people reverse themselves — Noel Romero un-deferred).
3. Map: "defer"/"next cohort" → `migrate EMAIL c8`; "withdraw"/"took a job" → `decide EMAIL withdrawn`;
   "signed" → recipe A for them; questions → leave for Drew.
4. `find` first; skip anyone already in the target state. Report the table, including anything ambiguous.

**C. Retrigger / send a DocuSign** (confirm with Drew first — this emails the candidate)
1. `getEnvelopes search_text=EMAIL` — if one is `completed`, just `hq.py signed` and stop.
2. `createEnvelope` status `created`, templateId `53f42ba5-1dd1-44c9-9fd9-715a0d08c0f9` (Prime C7),
   `templateRoles=[{roleName:"Signer 1", name, email}]`. Prefill tabs already have values.
3. `updateEnvelope` status `sent`, then `hq.py envelope EMAIL ENVELOPE_ID`.
Old "Please sign" envelopes from June are C6 contracts — don't treat them as valid for C7.

**D. Last-call / blast gap check** ("who didn't get the email?")
1. `hq.py emails c7 --unsigned --names` = who still needs it.
2. Diff against the BCC list of the previous send (Gmail `get_thread` on it).
3. Run recipe A on the gap before drafting — half of "unsigned" is usually stale sync.
4. Draft as a **reply on the original thread** with the gap in BCC; Drew sends.

**E. After deferrals** — draft (don't send) a note to andria@ and tom@ listing who moved C7 → C8 so they're pulled
from C7 onboarding sends and platform invites.

**F. Admit call on a borderline score** — `hq.py band EMAIL`, then check LinkedIn for *bonafide* hands-on SWE years
before applying the sliding scale. Recommend; Drew decides.

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
| `applied_for` | `appliedFor` | Cohort. C7 running (kicked off 2026-09-14); **`cohort_8`** = next. Drop `"duplicate"`; normalize `cohort-4` typo → `cohort_4`. |
| `firstname` | `personalInfo.firstName` | |
| `lastname` | `personalInfo.lastName` | |
| `email` | `personalInfo.email` | Primary join key to pipeline files & HubSpot. ~95% populated. |
| `linkedInProfile` | `personalInfo.linkedinUrl` **or** `linkedin.linkedinUrl` | Check **both** — either may hold it. |
| `ccat_score` | `ccatScore` (latest); `ccat1Score` / `ccat2Score` per attempt | See CCAT note below — dual schema. |
| `adminDecision` | `adminDecision` | Enum: **`accepted`**, **`gfa-accepted`**, **`rejected`**, **`withdrawn`**. The admit/reject write. |
| `yearsExperience` | `personalInfo.yearsEngineeringRange` | Self-reported. Old enum `0 to 1`/`1 to 2`/`3 to 5`/`5 plus`; newer `Less than 3 years`/`3-5 years`/`6-9 years`/`10 plus years`. |
| `technicalAchievement` | `achievement` (map: `{description, link}`) | Often empty `{"description":"","link":""}`. `achievementNoteId` is a separate pointer. |

### `adminDecision` — the admit/reject write (NOT a `status` change)
The accept/reject decision lives in its own `adminDecision` field, separate from the funnel `status`.
Canonical values: **`accepted`** (Prime), **`gfa-accepted`** (GFA route), **`rejected`** (decline), **`withdrawn`** (candidate pulled out).
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
  `step-1` is the form's initial state (~41% never leave it).
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
