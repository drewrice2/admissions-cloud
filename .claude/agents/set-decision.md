---
name: set-decision
description: Set adminDecision on an applicant by email. Usage: /set-decision <email> <decision> where decision is accepted, rejected, or withdrawn.
---

Run `python3 tools/hq.py decide <email> <decision>` from the repo root.
Shorthands work: admit/accept → accepted, decline/reject → rejected, withdraw → withdrawn.
GFA is on ice — don't use gfa-accepted without Drew's explicit OK. Report the tool output.
