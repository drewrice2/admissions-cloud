# Firestore Traversal Cheatsheet — `applications` & `applications_internal`

> ## ⚠️ WRITE SCOPE — READ THIS FIRST ⚠️
> **ALL data may be READ. Writes are allowed in ONLY two collections: `applications` and `applications_internal`.**
>
> - ✅ **READ:** anything in the project is fair game to read.
> - ✏️ **WRITE / UPDATE / DELETE:** permitted **only** in `applications` and `applications_internal`. **No other collection may be written, updated, or deleted — ever.**
>
> The SA key technically has full read/write and bypasses security rules, so nothing stops an errant write. **The restriction is a policy, not a permission boundary — you must enforce it yourself.** When in doubt: read, don't write. The **only** two collections you may update are `applications` and `applications_internal`.

Reference for working against the **`gauntlet-hq`** Firebase project's admissions data.
Service account JSON at repo root: `gauntlet-hq-4a09285efcec.json`
(App Engine default SA — `gauntlet-hq@appspot.gserviceaccount.com`. Has full Firestore read/write and bypasses security rules — **but writes are policy-restricted to `applications` and `applications_internal` only**. Read anything; update nothing else.)

`.env` also holds the *public* web SDK config (`FIREBASE_API_KEY`, etc.). Those are **not** what reads Firestore — the SA JSON is. Web keys are only useful if signing in as a real user (we don't).

---

## 1. Setup

```bash
pip install google-cloud-firestore
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/gauntlet-hq-4a09285efcec.json"
```

```python
from google.cloud import firestore
db = firestore.Client(project="gauntlet-hq")
```

ADC env var is the canonical auth path. Don't pass `credentials=` explicitly unless you need to override.

> **Reminder:** this client can read **everything** in the project, but you may only **write/update/delete** in `applications` and `applications_internal`. Those two collections are the *only* writable areas. Every other collection is read-only by policy.

**Security:** the SA JSON is a private key — never commit, never share. Treat with the same care as a password. Revoke from <https://console.cloud.google.com/iam-admin/serviceaccounts?project=gauntlet-hq> if leaked.

---

## 2. Collection sizes (as of 2026-05-27)

| Collection | Docs | Read? | Write/Update? | Purpose |
|---|---:|---|---|---|
| `applications` | **12,920** | ✅ Yes | ✅ **Yes (one of only two writable collections)** | User-facing application records (the form, CCAT results, status) |
| `applications_internal` | **3,605** | ✅ Yes | ✅ **Yes (one of only two writable collections)** | Sidecar: LLM reviews, scraped LinkedIn data, UTM attribution |
| *any other collection* | — | ✅ Yes | ❌ **No — never write/update/delete** | Read-only by policy |

**Write policy (again):** `applications` and `applications_internal` are the **only** two collections you are allowed to update. Read anywhere you like; update nowhere else.

Cheap exact count:
```python
db.collection("applications").count().get()[0][0].value
```
(Aggregation queries are free of the 10k-result limit and don't read full docs.)

---

## 3. `applications` schema

Doc ID is opaque (e.g. `00cCHfv6yWOBcey5bxqe`). Same ID is used as the join key in `applications_internal`.

### Top-level fields

| Field | % populated | Type | Notes |
|---|---:|---|---|
| `userId` | 100% | str | Firebase Auth UID |
| `status` | 100% | str | Funnel stage — see §5 |
| `appliedFor` | 100% | str | Cohort — see §5 |
| `createdAt` | 100% | timestamp | |
| `updatedAt` | 100% | timestamp | |
| `personalInfo` | 100% | map | applicant identity, see below |
| `technicalAssessment` | 100% | map | `selectedLanguage`, `status`, `startedAt`, `completedAt`, ... |
| `additionalInfo` | 100% | map | often empty `{}` |
| `appliedAt` | 98% | str (ISO) | string, not timestamp — be careful in range queries |
| `id` | 69% | str | redundant copy of doc ID on newer docs only |
| `resume` | 68% | map | `{ resumePdfUrl, socialProfiles }` |
| `ccatCompleted` | 70% | bool | |
| `ccatCompletedAt` | 21% | timestamp\|null | |
| `lastStatusChange` | 68% | map\|null | `{ from, to, timestamp, reason }` |
| `buttonClicks` | 48% | map | step UX tracking |
| `prep` | 32% | map | |
| `emailSequence` | 32% | str | e.g. `apply_emailSeq_01` |
| `emailSequenceTimestamp` | 32% | timestamp **or** str | **mixed types** — handle both |
| `linkedin` | 32% | map | `{ linkedinUrl }` |
| `ccatOrderId` / `ccatEventId` / `ccatAccessUrl` / `ccatStatus` / `ccatOrderedAt` | 16% | str/timestamp | first CCAT attempt |
| `ccatScore` / `ccatPercentile` / `ccatRankingScore` / `ccatPassed` / `ccatInvalid` / `ccatReportUrl` / `ccatMetAllRanges` / `ccatScores` | 12–14% | mixed | parsed result of attempt 1 |
| `ccat1*` (same fields with `ccat1` prefix) | 12% | mixed | attempt 1 in newer schema |
| `ccat2*` (same fields with `ccat2` prefix) | 5–6% | mixed | attempt 2 (retake) |
| `ccatAttempts` | 12% | int | |
| `submittedAt` | 7% | timestamp | only for fully submitted apps |
| `admissionsUpdatedAt` | 11% | timestamp | last touched by admissions |
| `migrationInfo` / `migrationMetadata` | ≤13% | map | migration artifacts — schema drift markers |
| `pausedTimestamp` | 10% | timestamp\|null | |
| `workAuthorizationSubmitAttestedAt` | 4% | timestamp | |
| `elevatorPitch` | 2% | map | `{ videoUrl, submittedAt }` |
| `verifications` | 2% | map | `{ threeYearsExperience }` |
| `comments` | 2% | list | reviewer comments |
| `hubspotContactId` | <2% | str | **bridge to HubSpot** — sparse, only on newer records |
| `reviewStartedAt` / `reviewStartedBy` / `secondStepStartedAt` / `secondStepStartedBy` | <1% | mixed | older review-flow fields |
| `statusHistory` | <1% | map | keyed by epoch ms |
| `contractSigned` | <1% | bool | |
| `step` | 2% | str | legacy — usually use `status` |
| `ccat` | 7% | map | `{ updatedBy, updatedAt, score }` — manual override |

### `personalInfo` subkeys (from 100-doc sample)

| Subkey | % present |
|---|---:|
| `email` | 98% |
| `firstName` | 92% |
| `lastName` | 91% |
| `phone` | 89% |
| `workAuthorization` | 62% |
| `referralSource` | 26% |
| `githubUsername` | 19% |
| `linkedinUrl` | 17% |
| `workAuthorizationConfirmed` | 11% |
| `demographics`, `address`, `socialProfiles`, `dateOfBirth`, `personalStatement`, `xUrl`, `githubUrl` | ~9% each |
| `phoneValidated`, `fullName`, `referralSourceOther` | ~7% each |

### Subcollections

- `applications/{appId}/aiReviews/{reviewId}` — exists on some docs; an LLM review per doc.
  Fields: `scrapedData`, `createdBy`, `report`, `status`, `createdAt`, `retryCount`, `applicationId`, `currentStep`, `updatedAt`, `completedAt`, `progress`, `errorMessage`, `metadata`, `steps`.
- No other subcollections seen on a 20-doc sample.

---

## 4. `applications_internal` schema

Doc ID == matching `applications` doc ID (verified 100/100 in sample). `applicationId` field also stores it. ~98% of internal docs have an existing `applications` parent (occasional orphans from deletes).

| Field | % populated | Type | Notes |
|---|---:|---|---|
| `applicationId` | 100% | str | == doc ID |
| `userId` | 100% | str | Firebase Auth UID |
| `email` | 100% | str | applicant email (denormalized) |
| `createdAt` | 100% | timestamp | |
| `updatedAt` | 100% | timestamp | |
| `llmReview` | 86% | map | `{ tokensUsed, status, report, promptId, ... }` (8 keys) |
| `promptId` | 86% | str\|null | |
| `promptDocumentId` | 86% | str\|null | usually == `promptId` |
| `scrapedDataRaw` | 86% | map\|null | LinkedIn enrichment (36 keys: `current_company_company_id`, `location`, `avatar`, `memorialized_account`, ...) |
| `utmSource` | 38% | str | `reddit`, etc. |
| `utmMedium` | 38% | str | |
| `utmCampaign` | 28% | str | |
| `utmContent` | 28% | str | |
| `buttonClicks` | 9% | map | |

No subcollections seen.

---

## 5. Enumerations (full-collection counts)

### `applications.status` — 12,920 total (2026-05-27)

| Count | Status |
|---:|---|
| 5,263 | `step-1` |
| 3,269 | `step-2` |
| 2,910 | `step-3` |
| 506 | `step-4` |
| 494 | `step-5` |
| 130 | `step-3-paused` |
| 100 | `submitted` |
| 92 | `step-6-approve` |
| 89 | `approved` |
| 55 | `step-6-reject` |
| 8 | `rejected` |
| 1 | `second-step` |
| 1 | `under-review` |
| 1 | `request-info` |
| 1 | *(null)* |

### `personalInfo.yearsEngineeringRange` — enum (cohort_6 only, 28 docs)

Currently only collected on the new cohort_6 application form (step 5: Engineering Background). Four values:

| Count | Value |
|---:|---|
| 10 | `1 to 2` |
| 8 | `5 plus` |
| 5 | `0 to 1` |
| 5 | `3 to 5` |

Note the gap — there is **no `2 to 3` bucket** in the form. Treat the canonical set as: `0 to 1`, `1 to 2`, `3 to 5`, `5 plus`. This field is **Firebase-only** — not synced to HubSpot per the cohort_5/6 sync spec.

### `applications.appliedFor` (2026-05-27)

| Count | Cohort |
|---:|---|
| 8,896 | `cohort_3` |
| 2,046 | `cohort_5` |
| 975 | `cohort_4` |
| 738 | `cohort_6` |
| 226 | `duplicate` ← not a cohort; flag |
| 37 | `cohort_2` |
| 2 | *(null)* |

Note: cohort_5 dropped (~2,562 → 2,046) and cohort_6 grew (~74 → 738) since 2026-05-21 due to a retag operation — most cohort_6 docs carry `retaggedFrom: "cohort_5"`. The `cohort-4` (hyphen) typo variant is no longer present.

---

## 6. Querying — patterns that work

> **Reads are unrestricted** — every pattern below is safe to run against any collection. **Writes are not:** if a pattern mutates data (`.set()`, `.update()`, `.delete()`, batch writes), it may target **only** `applications` or `applications_internal`. Those two collections are the sole writable areas.

### Get one doc
```python
doc = db.collection("applications").document(doc_id).get()
if doc.exists:
    data = doc.to_dict()
```

### Filter (use `FieldFilter`, positional args are deprecated)
```python
from google.cloud.firestore import FieldFilter

q = (db.collection("applications")
       .where(filter=FieldFilter("status", "==", "approved"))
       .where(filter=FieldFilter("appliedFor", "==", "cohort_5")))
for d in q.stream():
    print(d.id, d.to_dict()["personalInfo"].get("email"))
```

Operators: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not-in`, `array-contains`, `array-contains-any`.

### Range queries on timestamps
```python
from datetime import datetime, timezone
start = datetime(2026, 1, 1, tzinfo=timezone.utc)
q = (db.collection("applications")
       .where(filter=FieldFilter("createdAt", ">=", start))
       .order_by("createdAt"))
```

### Nested fields — dot notation works
```python
db.collection("applications").where(filter=FieldFilter("personalInfo.email", "==", "x@y.com")).stream()
```

### Project only the fields you need (cheap)
```python
db.collection("applications").select(["status", "appliedFor", "createdAt"]).stream()
```

### Pagination (cursor)
```python
last = None
while True:
    q = db.collection("applications").order_by("__name__").limit(500)
    if last: q = q.start_after(last)
    docs = list(q.stream())
    if not docs: break
    for d in docs: ...
    last = docs[-1]
```

### Aggregations (count + sum + avg without reading docs)
```python
db.collection("applications").where(filter=FieldFilter("status","==","approved")).count().get()
```

### Read a subcollection
```python
db.collection("applications").document(app_id).collection("aiReviews").stream()
```

### Collection-group query (across `aiReviews` under every app)
```python
db.collection_group("aiReviews").where(filter=FieldFilter("status","==","completed")).stream()
```

### Joining `applications` ↔ `applications_internal`
The doc IDs match, so:
```python
internal = db.collection("applications_internal").document(app_id).get()
```
or batch via `get_all` (avoids N round-trips):
```python
ids = [...]
refs = [db.collection("applications_internal").document(i) for i in ids]
snaps = db.get_all(refs)  # returns list[DocumentSnapshot], same order
```

---

## 6b. Writes — allowed ONLY in `applications` and `applications_internal`

**Before writing anything, confirm the target collection is one of these two. There are no other writable collections.**

```python
WRITABLE = {"applications", "applications_internal"}  # the ONLY collections you may update

def assert_writable(collection_name: str):
    if collection_name not in WRITABLE:
        raise PermissionError(
            f"Refusing to write to '{collection_name}'. "
            "Only 'applications' and 'applications_internal' are writable."
        )
```

```python
# OK — applications is one of the two writable collections
assert_writable("applications")
db.collection("applications").document(app_id).update({"status": "approved"})

# OK — applications_internal is the other writable collection
assert_writable("applications_internal")
db.collection("applications_internal").document(app_id).set({...}, merge=True)

# NOT OK — any other collection is read-only. Do not do this.
# db.collection("some_other_collection").document(x).update({...})  # ❌ forbidden
```

To repeat: **`applications` and `applications_internal` are the only two collections that can be updated.** Reading from anywhere else is fine; writing/updating/deleting anywhere else is not.

> **Enforcement:** this repo ships a Claude Code `PreToolUse` guard (`.claude/hooks/firestore-write-guard.py`) that **denies** any tool call containing a Firestore mutation (`.set`/`.update`/`.delete`/`.add`/`.create`, including batch forms) targeting a collection other than these two. Reads are never blocked. It's a backstop for the policy, not a substitute for it — the SA still bypasses Firestore security rules.

---

## 7. Limits & costs

- **Writes are policy-limited to `applications` and `applications_internal` only** — no other collection may be written, updated, or deleted. (Reads are unrestricted.)
- **1 write/sec per doc** (sustained). Bursts OK.
- **10 MB max doc size**, 20k fields/doc, 1MB per write payload.
- **500 ops per batch** (`db.batch()`).
- **1500 ops/sec** sustained per collection group for query throughput on default index.
- Composite-index needed for any query that filters on >1 field where one is range. Firestore returns a console link in the error — open and click "Create".
- Reads bill per document returned. **`select(...)` returns 1 read per doc but transfers less data; aggregation queries bill 1 read per ~1k docs scanned.** Aggregations are the cheapest way to count.

---

## 8. Gotchas (verified in this dataset)

0. **You may only ever write to `applications` and `applications_internal`.** Everything is readable, but these are the *only* two collections you can update. The SA key won't stop you from writing elsewhere — the limit is on you to honor.
1. **`appliedAt` is a string ISO timestamp**, but `createdAt`/`updatedAt` are real timestamps. Range-filtering on `appliedAt` won't behave like a date — convert or trust `createdAt`.
2. **`emailSequenceTimestamp` is mixed type** — sometimes `datetime`, sometimes `str`. Always coerce: `isinstance(v, str) ? parse : v`.
3. **CCAT data has two coexisting schemas**: old (`ccatScore`, `ccatPassed`, ...) and new (`ccat1*`, `ccat2*`). When a record has both, the `ccat*` (unprefixed) ones are the **latest attempt** and `ccat1*` is the first attempt. Check `ccatAttempts` and `migrationInfo` to disambiguate.
4. **`hubspotContactId` is sparse** (~<2%). To bridge old apps to HubSpot, fall back to `personalInfo.email` and match HubSpot's `email` property.
5. **Duplicate marker**: 170 docs have `appliedFor == "duplicate"` — exclude from cohort analytics.
6. **Cohort typo**: 2 docs use `cohort-4` (hyphen) instead of `cohort_4` (underscore). Normalize when grouping.
7. **`applications_internal` orphans**: ~2% of internal docs have no matching `applications` doc. Either join with `get_all` and check `.exists`, or filter on join.
8. **No subcollection on most docs**. `aiReviews` only exists on a minority — query it via `collection_group("aiReviews")` if you want everything at once.
9. **Status `step-1` is the form's initial state**, not "intent to apply" — 5,214 docs (41%) never moved past it. Treat with care in conversion analytics.
10. **`personalInfo.email` ≠ `applications_internal.email` always** — they should match but verify; the latter is denormalized at apply time.

---

## 9. Recipes

### a. Funnel breakdown by cohort
```python
from collections import Counter
from google.cloud.firestore import FieldFilter

funnel = Counter()
for d in db.collection("applications").select(["status","appliedFor"]).stream():
    x = d.to_dict()
    funnel[(x.get("appliedFor"), x.get("status"))] += 1
```

### b. All approved cohort_5 applicants with email + LinkedIn
```python
q = (db.collection("applications")
       .where(filter=FieldFilter("appliedFor","==","cohort_5"))
       .where(filter=FieldFilter("status","==","approved"))
       .select(["personalInfo","linkedin","resume"]))
for d in q.stream():
    pi = d.to_dict().get("personalInfo", {})
    li = d.to_dict().get("linkedin", {})
    print(d.id, pi.get("email"), li.get("linkedinUrl"))
```

### c. CCAT pass rate per cohort (using either schema)
```python
def latest_ccat_passed(doc):
    # newer schema first
    if "ccat2Passed" in doc: return doc["ccat2Passed"]
    if "ccat1Passed" in doc and not doc.get("ccatPassed"): return doc["ccat1Passed"]
    return doc.get("ccatPassed")

by_cohort = {}
for d in db.collection("applications").select(
        ["appliedFor","ccatPassed","ccat1Passed","ccat2Passed"]).stream():
    x = d.to_dict()
    p = latest_ccat_passed(x)
    if p is None: continue
    bucket = by_cohort.setdefault(x.get("appliedFor"), [0,0])
    bucket[0 if p else 1] += 1
for c, (yes, no) in by_cohort.items():
    print(f"{c}: {yes} pass / {yes+no} taken = {yes*100/(yes+no):.1f}%")
```

### d. Join applications + applications_internal for a status group
```python
from google.cloud.firestore import FieldFilter
target_status = "submitted"
app_ids = [d.id for d in db.collection("applications")
              .where(filter=FieldFilter("status","==",target_status))
              .select([]).stream()]

internal_refs = [db.collection("applications_internal").document(i) for i in app_ids]
internals = {s.id: s.to_dict() for s in db.get_all(internal_refs) if s.exists}

for aid in app_ids:
    inter = internals.get(aid, {})
    print(aid, inter.get("utmSource"), (inter.get("llmReview") or {}).get("status"))
```

### e. UTM attribution rollup
```python
from collections import Counter
utm = Counter()
for d in db.collection("applications_internal").select(
        ["utmSource","utmMedium","utmCampaign"]).stream():
    x = d.to_dict()
    utm[(x.get("utmSource"), x.get("utmMedium"), x.get("utmCampaign"))] += 1
for k, n in utm.most_common(20): print(n, k)
```

### f. Pull every aiReview report across the project
```python
for d in db.collection_group("aiReviews").stream():
    x = d.to_dict()
    app_id = d.reference.parent.parent.id  # applications/{id}/aiReviews/{x}
    print(app_id, x.get("status"), x.get("currentStep"))
```

### g. Find apps with HubSpot link
```python
from google.cloud.firestore import FieldFilter
for d in (db.collection("applications")
            .where(filter=FieldFilter("hubspotContactId", "!=", None))
            .stream()):
    print(d.id, d.to_dict().get("hubspotContactId"))
```

### h. Resume URLs for cohort_5 submissions
```python
from google.cloud.firestore import FieldFilter
q = (db.collection("applications")
       .where(filter=FieldFilter("appliedFor","==","cohort_5"))
       .where(filter=FieldFilter("status","in",["submitted","approved","step-6-approve","step-6-reject","rejected"]))
       .select(["personalInfo","resume"]))
for d in q.stream():
    x = d.to_dict()
    print(x.get("personalInfo",{}).get("email"), x.get("resume",{}).get("resumePdfUrl"))
```

---

## 10. Quick smoke test

```bash
GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/gauntlet-hq-4a09285efcec.json" python3 -c "
from google.cloud import firestore
db = firestore.Client(project='gauntlet-hq')
print('applications:', db.collection('applications').count().get()[0][0].value)
print('applications_internal:', db.collection('applications_internal').count().get()[0][0].value)
"
```

Expected output:
```
applications: 12772
applications_internal: 3455
```

---

## Final reminder

**Read freely — write narrowly.** All data in the `gauntlet-hq` project may be **read**. The **only** two collections that may be **updated** (written / modified / deleted) are **`applications`** and **`applications_internal`**. No other collection is writable under any circumstances.
