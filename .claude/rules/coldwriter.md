# Coldwriter

A Claude Code plugin: LinkedIn coffee-chat notes drafted in the user's voice and learned from their edits. Skills in `skills/<name>/SKILL.md` hold every instruction the model follows. Python scripts in `scripts/` are the only things that write to the workspace database or `queue.md`. The script layer's commands, output formats, and data shapes are specified in `scripts/README.md`; read it before touching a script or a skill that calls one.

## Layout

    .claude-plugin/plugin.json   manifest
    skills/<name>/SKILL.md       one per user command, invoked as /coldwriter:<name>
    scripts/                     db.py diff.py render.py (learn core) and queue.py (outreach consumer)
    db/schema.sql                applied to <workspace>/db/outreach.sqlite by init
    seeds.yaml                   starting rules
    templates/                   files copied into a workspace
    tests/                       pytest; tests/fixtures/ are the contract's examples
    TODO.md                      build checklist; check items off as they land

A workspace is created by `/coldwriter:init`, is never a git repo, and is never this directory. It holds `me/`, `constitution.md`, `queue.md`, `db/outreach.sqlite`. For manual runs use a gitignored `.workspace/` here and pass `--workspace .workspace`. Tests use temp directories.

## Invariants

These are product decisions, not defaults. Do not soften them.

- The plugin never writes to LinkedIn and never holds credentials. The user sends every note.
- Scripts are the only writers of the database and `queue.md`. The model passes text to scripts; it never edits either file.
- `constitution.md` is a render of the `preferences` table. Never a source, never hand-edited.
- Nothing derived is stored. Diff hunks and distances are computed when needed.
- No gates, caps, linters, or refusals. Scripts diff, count, and render; nothing blocks an action.
- One draft per contact. The user's edit is the signal.
- The pipeline ends at `sent`. No outcomes, no follow-ups, no analytics.
- No dates in the pipeline. A contact is queued, drafted, approved, or sent.
- The learn core (`db.py`, `diff.py`, `render.py`, the `learn` skill) knows nothing about LinkedIn or contacts and reads `contact_id` nowhere.
- Untouched drafts never count as support for a rule.

## Coding standards

- **Minimum that works.** Build the smallest thing that satisfies the contract and the test. No flags, options, or abstractions for needs that do not exist yet. When in doubt, delete.
- **Readable over clever.** A function does one thing and fits on a screen. Names say what; comments say why, and only where the code cannot. No metaprogramming, no dense one-liners.
- **Intelligent engineering.** Handle the failures that will actually happen (rerunning init, an empty queue, a profile with no posts, a FINAL left blank) plainly and in one place. Do not handle the ones that will not. Each state transition lives in one function.
- **Python 3.9, stdlib only.** macOS ships 3.9.6 and the plugin promises no installs. No `match`, no `X | Y` annotations, no `tomllib`, no third-party imports. `sqlite3`, `difflib`, `json`, `argparse`, `pathlib`, `hashlib`, `datetime` cover everything.
- **Scripts are CLIs with a module inside.** Plain functions on top, `argparse` at the bottom, importable by tests and by each other (`queue.py` imports helpers from `db.py`).
- **Output is the interface.** Print exactly what the contract says and nothing more. JSON only where the contract says JSON.
- **SQL is written out.** No query builders. Views in `db/schema.sql` do the reading; scripts do the writing.
- **Skills are short and literal.** A SKILL.md names the judgment the model exercises and the exact script invocation. It does not restate the contract.
- **Tests describe behavior at the script boundary.** Run the command, check the database and the output. Inputs live in `tests/fixtures/` and are the examples the contract cites.
- Match the style of the file you are in.

## Commands

    make test       pytest on Python 3.9 via uv
    make lint       ruff check and format check
    make validate   claude plugin validate --strict .
    make guard      nothing private tracked; no LinkedIn write tools or secrets in scripts/ or skills/
    make check      all of the above; CI runs exactly this

Done means `make check` is green, no new dependencies, and every changed behavior has a test.

## Never add

Discovery or search, enrichment, CSV or paste import, any LinkedIn write, guards or banned-phrase lists, caps, outcome tracking, funnels, labels or target taxonomies, draft variants, a GUI, a hand-editable constitution, a second writer of the queue file. If a task seems to need one, stop and ask.
