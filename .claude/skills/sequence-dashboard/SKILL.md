---
name: sequence-dashboard
description: Drew's daily action dashboard for HubSpot admissions sequences. Trigger whenever Drew asks "what do I need to do today", "sequence dashboard", "any actions on the sequences", "who do I need to call/email/text", "daily actions", or any variant of "what's moving in the sequence." Pulls sequence enrollment states, inbox replies, Firestore signature flips, and open call tasks, then produces one prioritized to-do list — executing the safe actions directly and queueing the rest for Drew.
---

# Sequence Action Dashboard

One invocation = one complete sweep of all four data sources, then ONE prioritized list.
Don't show raw data dumps; show actions. Every item is either DONE (I did it), DO (Drew does
it, with everything he needs inline), or WATCH (no action yet).

## Sequences in scope
- **Admissions — Accepted, Not Signed (C7)** — id `307593114`. The active workhorse (C6 revival + C7 accepts).
- **Admissions — Pre-CCAT Nurture (C7)** — id `307596072`. Kristen's, but flag anomalies.
- **GFA Redirect — Cohort 6** — id `307105087`. DEPRECATED. Only mention if stragglers still frozen (Austin Salter, Eduardo Lopez as of Jul 13 2026).

## The sweep (all four, every time)

1. **Sequence state** — navigate to
   `https://app.hubspot.com/sequences/47653442/sequence/307593114/enrollments?enrolledBy=ALL_USERS`,
   `get_page_text`, and paginate (25/page — check "Page 2"). Statuses that matter:
   - `REPLIED` / "Finished, Replied to email" → reply sitting in the Gauntlet inbox → DO: answer today.
   - `Paused / Paused by task` → stall failure mode → DONE: investigate + fix (see hubspot-sequences skill).
   - `Error` → DO or DONE depending on cause.
   - Opens/clicks → intelligence for call prioritization (openers first).
2. **Inbox replies** — search the Gauntlet inbox (gws / Gmail MCP `search_threads`) for recent
   mail from enrolled addresses (ledger CSVs below). Classify each reply: committing / blocker /
   defer-request / opt-out. Never mark these handled automatically — Drew answers.
3. **Firestore signals** — for every email in the ledgers, check `contractSigned`,
   `contractEnvelopeStatus`, `adminDecision` (project `gauntlet-hq`, SA key at repo root):
   - `contractSigned == True` on a **cohort_6** doc → they signed the STALE C6 envelope →
     DONE-able: run `/migrate-cohort <email> cohort_7` and report; envelope reissue = DO for Drew.
   - `contractSigned == True` on a **cohort_7** doc → 🎉 signed → DONE-able: unenroll them from the
     sequence (they're converted; don't let Day-8 urgency emails hit a signed person). Confirm-first
     if unsure — unenroll is irreversible.
   - New `contractEnvelopeStatus == sent` where ledger said "(no envelope)" → update ledger, drop from envelope-gap list.
4. **Call tasks** — HubSpot tasks queue (sequence call steps land ~Day 2 and Day 6). List due/overdue
   call tasks; prioritize contacts with opens/clicks/replies. Talk tracks are in each task's Notes.

## Ledgers (source of truth for who's tracked)
- `cohort_6_unsigned_pool.csv` — C6 revival batch (19 enrolled, 5 blocked-unsubscribed).
- `cohort_7_unsigned_pool.csv` — C7 accepts (11 enrolled, Gregory Wainer blocked-unsubscribed).
- Keep the `enrollment` column current (signed / replied / migrated / unenrolled states get appended, not overwritten).
- New accepts appear over time: re-run the accepted-not-signed Firestore query (funnel-pools skill)
  and flag "N new accepted-unsigned, not yet enrolled" as a DO.

## Enrollment dedup — mandatory before ANY new enrollment
A fresh pool pull is NOT an enrollment list. Before enrolling anyone, exclude:
1. `adminDecision` not in (accepted, gfa-accepted) — withdrawn/deferred/rejected drop out of the
   pool query automatically; this is why decisions must be WRITTEN to Firestore, not just noted.
2. `contractSigned == True` on ANY doc for that email OR userId (duplicate docs exist — e.g. Adam
   Marquette has a stale unsigned cohort_6 doc beside his signed cohort_7 doc; join on userId too).
3. Anyone whose ledger row (cohort_*_unsigned_pool.csv) shows ANY prior enrollment, reply, or a
   "DO NOT RE-ENROLL" flag. HubSpot happily re-enrolls a Finished contact — the ledger is the guard.
   A reply means a human conversation is in flight; sequences never interrupt conversations.
4. Cohort moves: "defer" = flip `appliedFor` to the target cohort (e.g. cohort_8), decision stays
   accepted (Drew's convention, minted Jul 24 2026 for Zach Humes). They exit the pool by cohort, not by decision.
5. HubSpot unsubscribed contacts (greyed in the picker) — track in ledger as blocked-unsubscribed.

## What I may do autonomously (report, don't ask)
- All reads; ledger CSV updates.
- `/migrate-cohort` on an unambiguous signature/defer signal.
- Fixing sequence mechanics (pause checkboxes, stalled enrollees' root cause — per hubspot-sequences skill).

## What ALWAYS needs Drew's explicit go (queue as DO with a ready-to-fire suggestion)
- Sending or drafting any email/text (draft via `tools/queue-drafts.py` gws flow once approved —
  Gmail MCP strips signature images; see memory).
- Enrolling or unenrolling anyone (exception: may propose unenroll-on-signed and execute on his yes).
- `adminDecision` changes other than migration (defer/withdraw/reject).
- Calls/texts are always Drew's — give him name, number (in ledger), context line, and the talk track.

## Output format
```
## Sequence dashboard — <date>
🔥 Reply now (N)      — who, what they said (one line), suggested angle
📞 Call today (N)     — name, phone, why them today (opened 3x / task due / day-6)
✅ Done for you (N)   — migrations run, ledgers updated, stalls fixed
✉️ Needs your go (N)  — drafts/unenrolls awaiting a yes
👀 Watching (N)       — envelope gaps, unsubscribed accepts, no-engagement cohort
```
Lead with the single most important action. If nothing needs Drew, say so in one line — don't pad.

## Standing context (as of 2026-07-24)
- SEQUENCE COMPLETED Jul 24 for all 30 (Day 10 reached; 0 in progress). Final: 6 signed (Vu, Adam,
  Kejian, Eric Heilman, Eran, Mathias — Mathias got the Day-10 email post-signature; apology draft
  queued in Gmail), Oliver withdrawn, Zach moved to cohort_8, Raymond released (DO NOT RE-ENROLL),
  in-conversation: Jackson (alum chat via Tom Babb), Jose (wants Drew call), Brook (deadline q),
  Rafi (IP limbo — Brett rec'd pass Jul 13). ~16 finished silent (all 6 steps, no reply) — next play
  is Drew's: personal outreach wave, call blitz, or release spots. Envelope gap fixed upstream ~Jul 20.
- OPEN: Rafi Rashid — IP concern (Section 8b); Brett recommended passing on him Jul 13; decision with Drew.
- Unsubscribed accepts needing personal outreach: Gregory Wainer, Eric Bauerfeld, Nathan Bogan, Kyle Benzo, Bojan Stefanovic, Chad Seippel.
- Defer convention: flip `appliedFor` to target cohort, decision stays accepted (NOT adminDecision="deferred").
