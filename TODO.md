# TODO

What is left to build, in build order. Check items off as they land. The contract for
every script command is `scripts/README.md`; change it before changing a script or skill.

## 1. Modules

### diff.py
- [x] `distance(a, b)`: `1 - SequenceMatcher(autojunk=False).ratio()` over characters
- [x] `hunks(a, b)`: word-level opcodes, `equal` dropped
- [x] CLI `--a --b` printing `{"distance", "hunks"}`
- [x] `tests/test_diff.py`: identical is 0, disjoint is 1.0, one replaced word is one `replace` hunk

### render.py
- [x] `render_constitution(rules, examples, version, date)`: header line, generated comment, `## Rules`, one `## When <condition>` per distinct condition, `## Examples` with the two most recent finals
- [x] `parse_constitution(text)` returning `[(statement, condition)]`, skipping Examples
- [x] CLI preview (reads the db, writes nothing)
- [x] `tests/test_render.py`: render then parse round-trips `tests/fixtures/constitution-v7.md`; an empty rule set renders a valid header

## 2. db.py (learn core and workspace)

- [x] Shared helpers: `connect(workspace)` (exit 2 with the contract's message), `now()`, `read_arg()` for `@path` and `-`, `sha16()`, `plugin_root()`
- [x] `render_and_record(conn)`: render, sha, no-op if unchanged, insert `constitutions` row with parent, write `constitution.md`. Used by init, prefer, learn apply
- [x] `init`: create `me/` and `db/`; apply schema; copy `templates/workspace-CLAUDE.md`; parse `seeds.yaml` bullets; case-insensitive dedupe so a rerun is a no-op; `--from` via `parse_constitution`; render v1
- [x] `history --text ...` (repeatable): `past:<n>` edits, distance 1.0
- [x] `prefer --statement [--when]`: duplicate statement exits 1
- [x] `learn emit`: kind classification, hunks, `label` from `v_context_labels`, non-retired preferences, retired statements, `{"edits": []}` when empty
- [x] `learn apply --reconcile [--mode]`: the seven steps in order. Validation is all-or-nothing; anti-churn (retire only rules active before the run); a re-proposed rule needs 4 or more distinct edits; `approve` mode inserts new rules as active/history; changelog stored as `learn_runs.summary`
- [x] `status [--chart]`: text report in the contract's layout; SVG written as a plain string, no library
- [x] `tests/test_db.py`: init idempotence; `--from`; history numbering; prefer duplicate; emit shape against fixtures; apply with `tests/fixtures/reconcile.json` checking counts, activation, retirement, merge, `learned_at`, and the unchanged-render case; approve mode; status output

## 3. queue.py (outreach consumer)

- [x] URL normalization: lowercase, https, no www, no query, no fragment, no trailing slash
- [x] `capture`: exists vs captured; missing `name` exits 1
- [x] `draft [--redraft]`: targets query, five exemplars newest first, profile and corrections files or null
- [x] `add`: insert draft, re-render queue
- [x] `render`: `queue.md` from `v_queue`, exact H2/H3 format, `0 waiting` case
- [x] `review`: file parser (H2 opens a contact, only three H3s), `ok` / text / empty; `wrong:` lines appended to `me/corrections.md`; unknown id reported on stderr and skipped; `--contact --final --note` goes through the same insert
- [x] `discard --contact | --all`: delete unreviewed drafts, contact back to `queued`, reviewed contact exits 1, re-render
- [x] `open`, `open --contact` (pbcopy and open with print fallbacks), `sent [--edited]` with final_text write-back, distance recompute, `learned_at` cleared
- [x] `unapprove --contact`: delete the edits row, contact back to `drafted`, exit 1 when sent, unreviewed, or already learned, re-render
- [x] `tests/test_queue.py`: capture dedupe; draft targets exclude reviewed and sent; review of `tests/fixtures/queue.md` yields ok, edited, untouched and one corrections line; `sent --edited` clears `learned_at`
- [x] `tests/test_pipeline.py`: golden path with no model and no LinkedIn: init, capture, add, review, learn apply, status

## 4. Skills (replace the eight stubs)

- [x] **init**: script call; the "tell me about yourself" prompt; read `me/` (PDFs included); write `me/_profile.md`, facts only; past notes go to `db.py history`, then learn in approval mode, keep or drop one rule at a time
- [x] **capture**: `get_person_profile` with the four sections, one URL per call in the order given, normalize to profile JSON, `queue.py capture`. Name no other LinkedIn tool: `make guard` greps for them
- [x] **draft**: `queue.py draft`, one note per target obeying the constitution, a hook only on a genuine match, sources cited, `queue.py add`
- [x] **review**: `queue.py review`; the conversational form maps to `--contact` calls
- [x] **discard**: one script call per form; never touches reviewed drafts
- [x] **send**: list, then per contact `open --contact`, wait for `y` / `skip` / `edited: ...`, call `sent` accordingly
- [x] **unapprove**: one script call
- [x] **prefer**: one script call
- [x] **learn**: emit, Stage A per batch of at most 25 edits, Stage B once (merges first if the render exceeds 80 lines), apply. The observation and reconcile JSON shapes and the support and contradiction definitions live here. Suggest running at 15 or more unlearned edits; never refuse
- [x] **status**: one script call, `--chart` passed through

## 5. Release

- [x] `.claude-plugin/marketplace.json` so `/plugin marketplace add <owner>/coldwriter` resolves a single-plugin repo (verify with `claude plugin validate`)
- [x] README: recommended MCP servers and the suggested `.mcp.json`
- [ ] README: the learning-curve SVG from real data (run `/coldwriter:status --chart` in a workspace after a few learn runs, copy `learning-curve.svg` in, link it)
- [x] Manual smoke test: `claude --plugin-dir .` against a workspace outside the checkout (`~/coldwriter-workspace`) with a real MCP capture (init, capture, draft, review, learn, status ran on 2026-09-15; `send --contact` and `sent` are exercised by your first real send)
- [x] Accept the trust dialog here once so `.claude/settings.json` applies
- [x] First push: confirm `claude plugin validate` runs without login in CI
- [x] CHANGELOG 0.1.0
- [x] `claude plugin tag --push` (tag `coldwriter--v0.1.0` is on origin; `/plugin marketplace add ethanyanghq/coldwriter` + `/plugin install coldwriter@coldwriter` verified from an empty directory)
- [ ] Handles: `github.com/coldwriter` (free as of 2026-09-15), `@coldwriter` (free on Bluesky; X unchecked), a domain (`coldwriter.com` is registered and parked for sale; `.dev`, `.io`, `.app` have no DNS)
- [x] Optional, after the skills exist: `evals/` cases for `claude plugin eval` (one case written; the command is early access and not enabled on this account, so it has not been run)
