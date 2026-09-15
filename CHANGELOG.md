# Changelog

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
