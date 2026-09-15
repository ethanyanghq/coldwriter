# TODO

What is left to build, in build order. Check items off as they land. The contract for
every script command is `scripts/README.md`; change it before changing a script or skill.

## 1. Modules

### diff.py
- [ ] `distance(a, b)`: `1 - SequenceMatcher(autojunk=False).ratio()` over characters
- [ ] `hunks(a, b)`: word-level opcodes, `equal` dropped
- [ ] CLI `--a --b` printing `{"distance", "hunks"}`
- [ ] `tests/test_diff.py`: identical is 0, disjoint is 1.0, one replaced word is one `replace` hunk

### render.py
- [ ] `render_constitution(rules, examples, version, date)`: header line, generated comment, `## Rules`, one `## When <condition>` per distinct condition, `## Examples` with the two most recent finals
- [ ] `parse_constitution(text)` returning `[(statement, condition)]`, skipping Examples
- [ ] CLI preview (reads the db, writes nothing)
- [ ] `tests/test_render.py`: render then parse round-trips `tests/fixtures/constitution-v7.md`; an empty rule set renders a valid header

## 2. db.py (learn core and workspace)

- [ ] Shared helpers: `connect(workspace)` (exit 2 with the contract's message), `now()`, `read_arg()` for `@path` and `-`, `sha16()`, `plugin_root()`
- [ ] `render_and_record(conn)`: render, sha, no-op if unchanged, insert `constitutions` row with parent, write `constitution.md`. Used by init, prefer, learn apply
- [ ] `init`: create `me/` and `db/`; apply schema; copy `templates/workspace-CLAUDE.md`; parse `seeds.yaml` bullets; case-insensitive dedupe so a rerun is a no-op; `--from` via `parse_constitution`; render v1
- [ ] `history --text ...` (repeatable): `past:<n>` edits, distance 1.0
- [ ] `prefer --statement [--when]`: duplicate statement exits 1
- [ ] `learn emit`: kind classification, hunks, `label` from `v_context_labels`, non-retired preferences, retired statements, `{"edits": []}` when empty
- [ ] `learn apply --reconcile [--mode]`: the seven steps in order. Validation is all-or-nothing; anti-churn (retire only rules active before the run); a re-proposed rule needs 4 or more distinct edits; `approve` mode inserts new rules as active/history; changelog stored as `learn_runs.summary`
- [ ] `status [--chart]`: text report in the contract's layout; SVG written as a plain string, no library
- [ ] `tests/test_db.py`: init idempotence; `--from`; history numbering; prefer duplicate; emit shape against fixtures; apply with `tests/fixtures/reconcile.json` checking counts, activation, retirement, merge, `learned_at`, and the unchanged-render case; approve mode; status output

## 3. queue.py (outreach consumer)

- [ ] URL normalization: lowercase, https, no query, no fragment, no trailing slash
- [ ] `capture`: exists vs captured; missing `name` exits 1
- [ ] `draft [--redraft]`: targets query, five exemplars newest first, profile and corrections files or null
- [ ] `add`: insert draft, re-render queue
- [ ] `render`: `queue.md` from `v_queue`, exact H2/H3 format, `0 waiting` case
- [ ] `review`: file parser (H2 opens a contact, only three H3s), `ok` / text / empty; `wrong:` lines appended to `me/corrections.md`; unknown id reported on stderr and skipped; `--contact --final --note` goes through the same insert
- [ ] `send`, `send --contact` (pbcopy and open with print fallbacks), `sent [--edited]` with final_text write-back, distance recompute, `learned_at` cleared
- [ ] `tests/test_queue.py`: capture dedupe; draft targets exclude reviewed and sent; review of `tests/fixtures/queue.md` yields ok, edited, untouched and one corrections line; `sent --edited` clears `learned_at`
- [ ] `tests/test_pipeline.py`: golden path with no model and no LinkedIn: init, capture, add, review, learn apply, status

## 4. Skills (replace the eight stubs)

- [ ] **init**: script call; the "tell me about yourself" prompt; read `me/` (PDFs included); write `me/_profile.md`, facts only; past notes go to `db.py history`, then learn in approval mode, keep or drop one rule at a time
- [ ] **capture**: `get_person_profile` with the four sections, one URL per call in the order given, normalize to profile JSON, `queue.py capture`. Name no other LinkedIn tool: `make guard` greps for them
- [ ] **draft**: `queue.py draft`, one note per target obeying the constitution, a hook only on a genuine match, sources cited, `queue.py add`
- [ ] **review**: `queue.py review`; the conversational form maps to `--contact` calls
- [ ] **send**: list, then per contact `send --contact`, wait for `y` / `skip` / `edited: ...`, call `sent` accordingly
- [ ] **prefer**: one script call
- [ ] **learn**: emit, Stage A per batch of at most 25 edits, Stage B once (merges first if the render exceeds 80 lines), apply. The observation and reconcile JSON shapes and the support and contradiction definitions live here. Suggest running at 15 or more unlearned edits; never refuse
- [ ] **status**: one script call, `--chart` passed through

## 5. Release

- [ ] `.claude-plugin/marketplace.json` so `/plugin marketplace add <owner>/coldwriter` resolves a single-plugin repo (verify with `claude plugin validate`)
- [ ] README: recommended MCP servers and the suggested `.mcp.json`; the learning-curve SVG from real data
- [ ] Manual smoke test: `claude --plugin-dir .` against `.workspace/` with a real MCP capture
- [ ] Accept the trust dialog here once so `.claude/settings.json` applies
- [ ] First push: confirm `claude plugin validate` runs without login in CI
- [ ] CHANGELOG 0.1.0, `claude plugin tag`
- [ ] Handles: `github.com/coldwriter`, `@coldwriter`, a domain
- [ ] Optional, after the skills exist: `evals/` cases for `claude plugin eval`
