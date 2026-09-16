# Changelog

## Unreleased

From a UX smoke test against a mock LinkedIn server:

- `prefer` and the learn loop treat "No em dashes" and "No em dashes." as the same rule.
- A learn run that changes no rule keeps the constitution version; `constitution.md` is rewritten with fresh Examples. The learning curve no longer gets a bucket for an unchanged rule set.
- `capture` checks the URL with `queue.py capture --url` before the slow profile read, so a duplicate or a missing workspace costs nothing. The sections it asks for are `experience,education,posts`.
- `queue.py add` prints `#<contact> <name> · n chars`; the draft id is gone from the output. `status` prints `captured` instead of `queued` and no longer shows the constitution sha. `discard --all` says `nothing to discard`.
- `draft` shows the note and nothing else, and never rates whether a contact is worth messaging. `review` confirms a rewrite with `yes`, shows `unlearned` once, and never checks a recorded note against the rules.
- `init` with past notes proposes rules as one numbered list and takes one reply. Its prompt asks only for what `me/` is missing. Rules learned from past notes state the pattern, not the verbatim line.
- The workspace `CLAUDE.md` names the tool rather than the server, and tells the model to show a script's error and stop instead of reading the plugin's scripts.
- `capture` drafts right after reading, and `draft` shows each note in chat and asks for the review there. `queue.md` stays as the batch path.
- `review` in conversation sends an approved note straight away: clipboard, profile open, `y` to record. A rewrite from an instruction changes only what was asked; a note the user types themselves is stored verbatim.
- `queue.py review` ends with `unlearned <n> edits`; the skill suggests `learn` at 15.
- `capture` says it is reading before the slow profile call.
- `queue.py discard --contact ID | --all` and the `discard` skill remove unreviewed drafts and put those contacts back to `queued`. Reviewed drafts are never touched.
- The `draft` skill asks before writing when the workspace has no profile and no exemplars.
- `queue.py unapprove --contact ID` and the `unapprove` skill put an approved, unsent note back in the queue. A note already consumed by `learn` stays.
- `queue.py send` is now `queue.py open`: it copies and opens, and the name no longer reads as an outward action to the permission classifier.
- `review` in conversation treats an ambiguous reply as an instruction, and says what it recorded before the paste step, so a reply misread as the note is caught before sending.

## 0.1.1

- `draft` and `learn` run on Opus regardless of the session model.
- Contact URLs are normalized without `www.`, so both forms of a profile URL are one contact.
- A workspace never lives inside the plugin checkout; `make guard` fails if one does.

## 0.1.0

First release.

- Eight skills: `init`, `capture`, `draft`, `review`, `send`, `prefer`, `learn`, `status`.
- Scripts, stdlib only, Python 3.9 or newer: `db.py` (workspace and learn core), `queue.py` (contacts, drafts, queue, sending), `diff.py`, `render.py`. Contract in `scripts/README.md`.
- One SQLite database per workspace; `constitution.md` and `queue.md` are renders of it.
- The learn loop: edits become observations, observations become rule changes, rules render as a versioned constitution with a changelog per run.
- Never writes to LinkedIn, holds no credentials, adds no gates.
