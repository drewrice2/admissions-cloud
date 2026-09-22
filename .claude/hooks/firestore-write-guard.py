#!/usr/bin/env python3
"""PreToolUse guard: block Firestore writes to any collection other than
`applications` or `applications_internal`.

Reads can target anything. The ONLY writable collections are:
    - applications
    - applications_internal

The hook inspects the proposed tool call (Bash command text, or the content of
a Write/Edit/MultiEdit) for Firestore mutation calls (.set / .update / .delete /
.add / .create, including batch and bulk-writer forms) whose target collection
is named inline. If a mutation targets a collection that is NOT one of the two
allowed ones, the tool call is denied. Everything else is allowed.

This is a guardrail, not a permission boundary — the service account bypasses
Firestore security rules, so honoring the read/write policy is on the caller.
Indirect mutations (where the collection is held in a variable on a different
line than the mutation call) cannot be statically resolved and will pass; the
written policy in FIREBASE_API_CHEATSHEET.md still governs those.
"""
import json
import re
import sys

ALLOWED = {"applications", "applications_internal"}

# Mutation verbs that write data in the google-cloud-firestore / firebase APIs.
MUTATION = r"(?:set|update|delete|create|add)"
# A collection literal: collection("X") or collection('X')
COLL = r"""collection\(\s*["']([^"']+)["']\s*\)"""

# Pattern A — chain form: collection("X").document(..).update(..)  /  collection("X").add(..)
#   collection literal, then anything on the same statement (no semicolon) up to a mutation verb.
CHAIN = re.compile(COLL + r"""[^;\n]*?\.\s*""" + MUTATION + r"""\s*\(""")
# Pattern B — wrapper form: batch.set(db.collection("X").document(..), {..})
#   mutation verb, then a collection literal inside the same call (no semicolon).
WRAPPER = re.compile(r"""\.\s*""" + MUTATION + r"""\s*\([^;\n]*?""" + COLL)


def collections_written(text: str) -> set:
    """Return the set of collection names that appear as the target of a write."""
    hits = set()
    hits.update(CHAIN.findall(text))
    hits.update(WRAPPER.findall(text))
    return hits


def extract_text(tool_name: str, tool_input: dict) -> str:
    """Pull the code/command text we should scan from the tool input."""
    if tool_name == "Bash":
        return tool_input.get("command", "") or ""
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string", "") or ""
    if tool_name == "MultiEdit":
        return "\n".join(
            (e.get("new_string", "") or "") for e in tool_input.get("edits", []) or []
        )
    return ""


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # Can't parse input — don't block, just exit cleanly.
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    text = extract_text(tool_name, tool_input)
    if not text:
        sys.exit(0)

    written = collections_written(text)
    forbidden = sorted(c for c in written if c not in ALLOWED)

    if forbidden:
        reason = (
            "BLOCKED: Firestore writes are allowed ONLY in the `applications` and "
            "`applications_internal` collections. This call attempts to write/update/"
            "delete in: " + ", ".join(f"`{c}`" for c in forbidden) + ". "
            "Reads are unrestricted — but those two collections are the only writable "
            "areas. Remove the write or target one of the two allowed collections."
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )
        sys.exit(0)

    # No forbidden write detected — allow (reads and allowed-collection writes pass through).
    sys.exit(0)


if __name__ == "__main__":
    main()
