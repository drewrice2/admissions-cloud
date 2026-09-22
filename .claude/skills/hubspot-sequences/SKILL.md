---
name: hubspot-sequences
description: Build or edit HubSpot sequences in portal 47653442 via Claude-in-Chrome browser automation. Use whenever Drew asks to create, edit, rename, audit, or fix a HubSpot sequence, sequence step, email template, task, or enrollment. Contains the exact UI techniques that work (and the ones that don't).
---

# HubSpot Sequences — portal 47653442

Sequences live at `https://app.hubspot.com/sequences/47653442`. Individual sequence:
`.../sequence/<id>/edit` (steps), `.../sequence/<id>/enrollments?enrolledBy=ALL_USERS` (who's in it).

Known sequences:
- **Admissions — Pre-CCAT Nurture (C7)** — id `307596072`. 8 steps / 13 days. Kristen runs it. Goal: drive LinkedIn-qualified applicants to take the CCAT.
- **Admissions — Accepted, Not Signed (C7)** — id `307593114`. Drew runs it. Goal: get accepted folks to sign; breakup email offers deferral to Cohort 8.
- **Admissions — Re-engagement, Pre-CCAT (C7)** — id `309531485`. Drew signs AND must enroll. 7 steps / 13 days.
  Built 2026-08-17 for the 60-person historical-applicant re-scrape. Copy is dateless on purpose (audience
  spans 1–12 months since applying). See `c7_reengagement_campaign.md` at repo root for the suppression
  ledger and the hand-lists that were deliberately NOT enrolled.
- **GFA Redirect — Cohort 6** — id `307105087`. DEPRECATED, do not touch.

## Copy conventions
- CONTRACT SIGNING (changed 2026-08-17): the enrollment agreement is now emailed directly by Ash,
  the CTO — it does NOT live in the application portal anymore. Accepted-Not-Signed CTAs say "sign
  the agreement from Ash (our CTO)" + "reply if it hasn't landed and I'll have it resent." Never
  link the portal for signing. (All 4 emails + both task talk tracks swept 2026-08-17.)
- CCAT/portal CTA link (pre-CCAT/application contexts only): `https://apply.gauntletai.com` — put it in EVERY email, not just the last one.
  Old `app.gauntlethq.com` is superseded (Drew reconfirmed 2026-08-17). It is NOT a dead link — it still
  returns 200 and serves a live app titled "Gauntlet HQ", so a stale reference is a silent dead end rather
  than an obvious 404. Pre-CCAT Nurture was fully swept 2026-08-17 (2 email links + 1 paste-ready task note).
- CCAT prep guide: `https://www.criteriacorp.com/candidates/ccat-prep`.
- C7 dates: kicks off September 14 (remote), October 5 (on-site). Urgency phrasing: "coming up quickly" — Drew explicitly rejected "final stretch" / "final days" as overclaiming.
- Avoid "white-glove" in names. Naming pattern: `Admissions — <Purpose> (C7)`; templates `<Purpose> — Step N — Day X <Gist>`.
- Kristen signs pre-CCAT emails; Drew signs accepted-not-signed emails. Emails send from whoever ENROLLS the contact (they need sequences-send permission), not the sequence owner.
- Never leave bracket placeholders like `[Google / Stripe / McKinsey]` in a template — they send literally.

## Mechanics conventions
- Task steps: UNCHECK "Pause sequence until task is completed" — a missed task must never stall the automated email spine. (This is exactly how GFA Redirect died: 5 people frozen on a call task.)
- Put a paste-ready message or 3-bullet talk track in every task's Notes field.
- Step-1 email = new thread; mid-sequence follow-up = Reply on that thread; late-stage urgency + breakup = new threads with fresh subjects.
- Set sequence sharing to Everyone.

## UI techniques that work (all via `mcp__claude-in-chrome__javascript_tool`, action `javascript_exec`)
- **Scrolling**: `window.scrollTo` does nothing. In the **sequence editor** the scroller is
  `.ScrollContainer__DefaultScrollContainer-WvXIN`; elsewhere it's `.copilot-app-container`. Safest is to
  pick the last match of `[...document.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+50&&e.clientHeight>300)`.
- **Email body** (template modal): second contenteditable — `document.querySelectorAll('[contenteditable="true"]')[1]`. Set `innerHTML` with `<p>` paragraphs and `<a href>` links, then `el.dispatchEvent(new Event('input',{bubbles:true}))`.
- **Personalization token**: NEVER type `{{...}}` (rejected as invalid characters). Write body with `Hi ,`, place the cursor via Range/Selection between "Hi " and ",", then Insert → Personalization tokens → search "first" → First Name → Insert. Verify a "Contact: First Name" chip appears.
- **Surgical body edits**: find the target `<p>` by textContent and edit only it — rebuilding whole innerHTML destroys token chips.
- **NEVER change a link with `a.setAttribute('href', …)`.** The editor keeps its own model: the visible text
  change persists but the href does NOT, leaving a deceptive link that reads correct and goes somewhere else.
  Instead: select the anchor contents (`range.selectNodeContents(a)`), click the chain icon in the bottom
  toolbar, and fill the **Create link** dialog's URL field. Verify with `a.getAttribute('href')` before saving.
- **Auditing for a bad URL, check hrefs — not page text.** A link whose text is "Take the CCAT here →" hides
  its destination. Sweep with
  `[...document.querySelectorAll('a')].filter(a=>/badhost/.test(a.getAttribute('href')||''))`,
  and open every task panel separately — **task Notes are not in the DOM until their panel is opened**, so a
  whole-page scan will report clean while a paste-ready note still carries the old URL.
- **Template name / sequence title**: real `<input>`; set via `Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(input, v)` then dispatch `input` + `change`. Sequence title: click the pencil next to the H1 first.
- **Task title**: contenteditable, NOT an input — focus it, `document.execCommand('selectAll')`, `document.execCommand('insertText', false, newTitle)`.
- **Task pause checkbox**: the checkbox in the right panel with `getBoundingClientRect().left > 1150`; `.click()` it to toggle.
- **Delay pills**: click the orange "Delay: N business day(s)" pill → popover with number input → triple-click input, type, click Save (Save sometimes needs a second click).
- **Save buttons**, by exact text: template modal → `Update existing template` (often needs a second click; "modal closed" from the finder = success); task panel → visible `Save`; whole sequence → `Save existing sequence` (greyed-out afterwards = saved). Template renames commit directly; no sequence-level save needed.
- **`Update existing template` is UNRELIABLE (2026-08-17: worked on 2 templates, silently failed on 2 others
  despite hit-tested real clicks).** When it won't commit: step card → `…` next to the pencil →
  **Replace email** → `Create new` → build a `v2` template (create-path saves reliably) → the step adopts it.
  A Replace stages a sequence-level change: finish with `Save existing sequence` ("Data will reset for N step(s)"
  is just stats-reset). Thread setting (REPLY/NEW THREAD) survives the swap.
- **Modal save buttons drift below the fold and the modal bounces between two scroll offsets.** Before every
  modal-save click: walk ALL scrollable ancestors of the button to `scrollTop=scrollHeight`, re-read
  `getBoundingClientRect`, confirm `document.elementFromPoint` hits the button, then click. If a JS rect says
  the button is off-viewport but a screenshot shows it, trust the screenshot's pixel position — the DOM rect
  can be stale in the other direction too.
- **"Modal still open" ≠ save failed.** The DOM often keeps reporting the modal for several seconds after a
  successful save (and screenshots lag further). The ONLY trustworthy verdict is a full page reload followed by
  a text/href scan.
- **Modal can migrate into an iframe**: after JS-clicking `Update existing template`, the template modal sometimes re-renders inside an iframe where page-level JS can't reach it — fall back to real coordinate clicks (button sits bottom-left, ~(219, 670)).
- **Blank lines between paragraphs**: an *empty* `<p>` collapses, but `<p><br></p>` survives. Build the body,
  then splice spacers in without touching the paragraph holding the token chip:
  `[...ce.children].filter(n=>n.tagName==='P').slice(0,-1).forEach(p=>{const s=document.createElement('p');s.appendChild(document.createElement('br'));p.after(s)})`
  then dispatch `input`. Much faster than the old click-Home-Return-Up dance, and the chip survives.
- **Personalization token fallback**: always set one (`there`) so a contact with no first name doesn't get "Hi ,".
  The fallback field only appears *after* the token is chosen — and clicking the Token box again reopens the
  token search, so verify by screenshot that you're typing into **Fallback value**, not the search box.
- **Screenshots lag the DOM badly in this editor.** A screenshot showing a modal still open is often stale.
  Confirm state via JS (e.g. is the `Save template` button still in the DOM?) before clicking Save a second
  time — a blind second click risks a duplicate template.
- **Panels animate for ~2-4s.** Coordinates measured before a panel settles are wrong and clicks land on the
  page behind it. Wait, screenshot, *then* click. Task panels settle at: pause checkbox (1120, 147),
  title (1318, 234), notes (1318, 460), Add (1151, 704).
- **Task panel saves are draft-only**: the panel's `Save` stages the change; it only persists after the sequence-level `Save existing sequence`. Verify persistence by reloading and reopening the task.
- After every click that changes layout, screenshot before the next coordinate click — panels animate in and coordinates shift.
- Read full sequence copy fast: click all "See more" buttons via JS, then `get_page_text`.

## Enrollment hygiene
- "Mark as done" for stale enrollees = **unenroll** (select checkboxes → bulk unenroll, or per-row Actions). Cancels pending emails and open tasks. Confirm with Drew before unenrolling — it's not reversible in-place.
- Status "Paused / Paused by task" = the stall failure mode; fix the sequence's pause checkboxes, not just the enrollee.

## Enrollment mechanics (hard-won 2026-08-18)
- **The enroll flow (`/edit/enroll`) renders inside a full-viewport IFRAME** (same-origin). Page-level DOM
  queries see none of it — "button not in DOM" while the screenshot shows it means look in
  `document.querySelectorAll('iframe')[n].contentDocument`.
- **Coordinate frames differ**: the DOM viewport can be ~1512 CSS px while screenshots render 1568 px wide
  (~3.7% scale). Real clicks use the DOM/CSS frame — compute click points from `getBoundingClientRect()`,
  never by eyeballing screenshot pixels; a screenshot-pixel click misses small buttons by ~40 px.
- **Contact picker**: search one email at a time; clicking the result row's checkbox registers with React
  even when `input.checked` reads stale-false — trust the "N selected" counter, not the checkbox property.
  A contact with no HubSpot record simply returns "No contacts match" (create the contact first).
- **The final "Enroll N of N contacts" click opens a CONFIRMATION dialog** ("Enroll N contacts in '…'?")
  which itself lives in the iframe. Miss it and the whole flow silently evaporates with zero enrollments.
  Confirm-button text includes a hidden "Loading" suffix — match with a prefix regex, not equality.
  Synthetic pointer/mouse event sequences dispatched on the iframe's buttons DO fire (React delegated
  listeners); use them when real clicks won't land.
- Verify enrollment ONLY via the Enrollments tab counters after a reload ("All enrollments N").
