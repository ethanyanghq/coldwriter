# Script contract

Four stdlib-only Python scripts. Skills invoke them as

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py <command> [options]

and never write to the workspace database or `queue.md` themselves. This file is the contract between skills and scripts. Change it before changing either side.

## Conventions

- `--workspace PATH` on every script; default is the current directory. Every command except `db.py init` requires `<workspace>/db/outreach.sqlite`. Without it: exit 2, stderr `not a Coldwriter workspace: <path> (run /coldwriter:init)`.
- `--domain NAME` on `db.py` commands; default `outreach`. `queue.py` is the outreach consumer and always uses `outreach`.
- Text options (`--text`, `--final`, `--note`, `--profile`, `--reconcile`, `--statement`, `--when`, `--edited`) take the literal value, `@path` to read a file, or `-` to read stdin.
- stdout is the result. `queue.py draft` and `db.py learn emit` print JSON because the model consumes them; every other command prints short text lines. Errors are one line on stderr.
- Exit codes: `0` done (an "already exists" is done), `1` bad input or failed validation with nothing written, `2` no workspace.
- Timestamps are ISO 8601 UTC, `2026-09-14T20:28:00Z`. They are bookkeeping; nothing in the pipeline depends on them.
- Constitution sha: `sha256(text)[:16]` of the version's stored text. A new version exists only when the rules changed: when only `## Examples` moved, `constitution.md` is rewritten with the fresh examples under the latest version's header and no row is inserted.
- Rule statements are compared ignoring case and a trailing `.` or `!`, wherever a duplicate is checked.
- Edit distance: `1 - difflib.SequenceMatcher(None, draft, final, autojunk=False).ratio()` over characters. `0` is untouched, `1.0` is from scratch.
- Hunks: `SequenceMatcher` opcodes over whitespace-split words, `equal` dropped, each `{"op": "replace|delete|insert", "original": "...", "replacement": "..."}`.
- Layering. `db.py`, `diff.py`, `render.py` are the learn core: they never read `contact_id` and know nothing about LinkedIn. `queue.py` is the outreach consumer and imports its helpers (`connect`, `fail`, `latest_constitution`, `load_json`, `now`, `read_arg`) from `db.py`. The one place the core sees consumer data is `v_context_labels`, a view the consumer defines and the core joins by `(domain, context_ref)`.
- Each write happens in one function. Every command that changes preferences re-renders the constitution; `queue.py add`, `review`, `discard`, and `unapprove` re-render `queue.md`.

## db.py

| command | effect | stdout |
|---|---|---|
| `init [--from PATH]` | Creates `me/` and `db/`, applies `db/schema.sql` (idempotent), writes `<workspace>/CLAUDE.md` from `templates/workspace-CLAUDE.md`, inserts each `seeds.yaml` bullet as an `active` preference (`source=seed`, `support_count=2`) unless a rule with the same statement (case-insensitive) exists. With `--from`, also parses a constitution file (format below) and inserts its rules as `active`, `source=imported`, `support_count=2`. Renders the constitution if no version exists or the render differs from the latest. | `workspace <path>`, `preferences <n> active`, `constitution v<n> <sha>` |
| `history --text TEXT [--text TEXT ...]` | Inserts each text as a from-scratch edit: `context_ref=past:<n>` (n continues from the highest existing), `draft_id NULL`, `edit_distance 1.0`, current constitution sha. | `#<edit_id> past:<n>` per text |
| `prefer --statement TEXT [--when TEXT]` | Inserts an `active` preference, `source=manual`, `support_count=3`, `condition` from `--when`. Duplicate statement (any status): exit 1. Re-renders. | `#<id> active`, `constitution v<n> <sha>` |
| `learn emit` | Every unlearned edit with what Stage A and B need. `{"edits": []}` when there are none. | JSON below |
| `learn apply --reconcile JSON [--mode lifecycle\|approve]` | Stage C over the currently unlearned edits, then render, then record. Default mode `lifecycle`. | changelog below |
| `status [--chart]` | Report. `--chart` also writes `<workspace>/learning-curve.svg`. | text below |

### learn emit

    {
      "domain": "outreach",
      "constitution": {"version": 4, "sha": "3f9c1e2a7b4d5c6f", "text": "# Constitution v4 ..."},
      "preferences": [
        {"id": 12, "statement": "No em dashes.", "condition": null, "status": "active",
         "source": "seed", "support_count": 2, "contradiction_count": 0}
      ],
      "retired": ["Never mention their company by name."],
      "edits": [
        {"id": 41, "context_ref": "contact:17", "label": "Senior PM, Google", "kind": "edited",
         "draft": "...", "final": "...", "note": "less eager",
         "hunks": [{"op": "replace", "original": "your impressive work", "replacement": "your work"}]}
      ]
    }

`preferences` holds every non-retired rule. `retired` holds retired statements so they are not re-proposed. `kind` is `edited` (draft differs from final), `untouched` (distance 0), or `scratch` (no draft). `label` comes from `v_context_labels` and is `null` when the consumer has nothing for that context. `hunks` is empty for `untouched` and `scratch`. The learn skill splits `edits` into batches of at most 25 for Stage A.

### learn apply

Input, the Stage B result (example: `tests/fixtures/reconcile.json`):

    {
      "existing": [{"id": 12, "support": [41, 47], "contradict": [], "note": "..."}],
      "new":      [{"statement": "Never open with the recipient's job title.",
                    "condition": null, "evidence": [41, 52, 58]}],
      "merge":    [{"keep": 12, "retire": 31, "reason": "same rule, narrower wording"}]
    }

Steps, in order:

1. Validate. Every id in `support`, `contradict`, and `evidence` is an unlearned edit and not an `untouched` one (an untouched draft is never evidence for or against a rule); every `existing.id`, `merge.keep`, `merge.retire` exists and is not retired. Any failure: exit 1, nothing written.
2. Counts. `support_count += len(support)`, `contradiction_count += len(contradict)`, `evidence_edit_ids` extended with both.
3. New rules. Dedupe the statement against all rules including retired. A match on a retired rule is skipped unless `evidence` spans at least 4 distinct edits, in which case it is inserted and marked `re-proposed` in the changelog. Insert as `candidate`, `source=learned`, `support_count=len(evidence)`. In `approve` mode insert as `active`, `source=history`, `support_count=max(2, len(evidence))`; the skill has already removed the rules the user dropped.
4. Lifecycle. `candidate` becomes `active` when `support_count >= 3 and support_count > 2 * contradiction_count`; rules inserted in step 3 are eligible. `active` becomes `retired` with `retired_reason="contradicted by edits <ids>"` (the ids from this run's `contradict`) when `contradiction_count >= support_count`, evaluated only for rules that were active before this run.
5. Merges. Retire `retire` with `retired_reason="merged into #<keep>"` and add its `support_count` to `keep`.
6. Set `learned_at` on every edit in the batch, untouched ones included.
7. Render. Insert the `constitutions` row (parent is the previous sha) and the `learn_runs` row with the changelog as `summary`. If the rules are unchanged, no constitution row is inserted, the run records the existing sha, and the changelog header reads `v<n> -> v<n>`; `constitution.md` is still rewritten so its Examples are current.

Changelog, printed and stored:

    v6 -> v7 · 22 edits · mean distance 0.31
    activated  #44 Never open with the recipient's job title  (support 4)
    retired    #3  No em dashes  (contradicted by edits 41, 47, 52)
    new        #51 [candidate] At most one sentence about yourself  (evidence 2)
    merged     #31 -> #12

Mean distance is over the batch's non-scratch edits, `n/a` when there are none. A rule inserted and activated in the same run appears once, as `new #<id> [active]`; a re-proposed one as `(evidence <n>, re-proposed)`. The changelog is one header line when nothing changed.

### status

    pipeline       captured 3 · drafted 2 · approved 1 · sent 40
    sent this week 4
    constitution   v7 · 14 rules · 2 candidates
    unlearned      9 edits
    curve          v1 0.62 (12)  v2 0.48 (15)  v3 0.31 (22)
    runs           3, last 2026-09-12T10:02:11Z

`curve` is `v<version> <mean_edit_distance> (<n_edits>)` from `v_learning_curve`, `none` when empty; `runs` is `0` before the first run. `pipeline` and `sent this week` come from the consumer's views and are omitted when those views do not exist. `captured` is the `queued` contact status, printed under a name that does not collide with `queue.md`, whose "waiting" count is the drafted contacts.

## queue.py

| command | effect | stdout |
|---|---|---|
| `capture --url URL [--profile JSON]` | Normalizes the URL (lowercase, `https`, no `www.`, no query, no fragment, no trailing slash). If a contact with that URL exists, does nothing. Without `--profile`, only reports: the skill runs this before the slow profile read. With it, inserts the contact as `queued` with `name`, `headline`, `company`, `title` copied from the profile JSON. `name` missing: exit 1. | `#<id> exists <name>`; without a profile `new`; with one `#<id> captured <name>` |
| `draft [--redraft ID]` | Emits drafting context for every contact that has no `edits` row and is not `sent`; with `--redraft`, for that contact only (exit 1 if it has an `edits` row). Writes nothing. | JSON below |
| `add --contact ID --text TEXT [--sources JSON]` | Inserts a draft (`context_ref=contact:<id>`, current constitution sha, `sources_json` default `[]`). Re-renders `queue.md`. The contact id is the only id the user ever types, so the draft id is not printed. | `#<id> <name> · <n> chars` |
| `discard --contact ID` or `discard --all` | Deletes every draft of a contact that has no `edits` row and sets the contact back to `queued`, so `draft` starts it over. `--all` does that for every such contact. Reviewed contacts keep all their drafts, so learn history is never touched; `--contact` on one: exit 1. Re-renders `queue.md`. | `#<id> discarded <n> drafts` per contact, lowest id first; `nothing to discard` when `--all` found no contact |
| `review [--contact ID --final TEXT [--note TEXT]]` | Without options, parses `<workspace>/queue.md`. With `--contact`, records one contact the same way. Re-renders `queue.md`. | one line per contact: `#<id> ok`, `#<id> edited · distance <d>`, `#<id> untouched`; then `unlearned <n> edits` |
| `open` | Lists what is ready. | `sent this week <n>`, then `#<id> <name> · <url>` per `approved` contact, lowest id first |
| `open --contact ID` | Copies the final text to the clipboard (`pbcopy`; else prints `clipboard unavailable`), opens the profile URL (`open`, then `xdg-open`; else prints the URL), prints the note. Named for what it does: nothing here sends. | the note text, then `<n> chars` |
| `sent --contact ID [--edited TEXT]` | With `--edited`, overwrites `edits.final_text`, recomputes the distance against its draft, and clears `learned_at`. Inserts the `sends` row. Contact not `approved`: exit 1. | `#<id> sent · <n> chars` |
| `unapprove --contact ID` | Deletes the contact's `edits` row and sets it back to `drafted`, so its newest draft is in the queue again. Not `approved` (`sent`, `drafted`, `queued`): exit 1. Already consumed by `learn`: exit 1, because the edit is evidence in the rules; `sent --edited` is how a learned note changes. A `wrong:` line already appended to `me/corrections.md` stays. Re-renders `queue.md`. | `#<id> unapproved` |
| `render` | Rewrites `queue.md` from `v_queue`. | `queue.md · <n> waiting` |

There is no "skip" command: skipping a contact in `open` is not calling `sent`.

### draft

    {
      "constitution": {"version": 4, "sha": "3f9c1e2a7b4d5c6f", "text": "..."},
      "profile": "<contents of me/_profile.md, or null>",
      "corrections": "<contents of me/corrections.md, or null>",
      "exemplars": [{"draft": "...", "final": "...", "note": "..."}],
      "targets": [{"contact_id": 17, "name": "Chris Doe", "url": "https://linkedin.com/in/chrisdoe",
                   "profile": {"name": "Chris Doe", "headline": "..."}}]
    }

`exemplars` are the five most recently reviewed `(draft, final, note)` pairs, newest first; `draft` is `null` for from-scratch finals. `targets` is empty when nothing needs a draft.

### review: parsing queue.md

`## [<id>]` opens a contact. `### draft`, `### FINAL`, `### note` are the only H3s; a section's text is everything until the next H2 or H3, stripped. Per contact:

| FINAL | effect |
|---|---|
| `ok` (case-insensitive) | `final_text` = the draft, distance 0 |
| any other text | `final_text` = that text, distance computed against the newest draft |
| empty | untouched: no row, the contact stays in the queue |

The note is stored verbatim as `reason_text`. If a line of the note starts with `wrong:` (any case), the text after it is appended to `me/corrections.md` as `- <text>`. The edit carries the draft's constitution sha, since the learning curve measures the version that produced the draft. A contact id that is not in `v_queue` is reported on stderr and skipped (with `--contact`, that is exit 1). No `queue.md` yet: exit 1. Example: `tests/fixtures/queue.md`.

## Formats

### queue.md

Rendered from `v_queue`. The user edits only FINAL and note.

    # Queue · constitution v4 · 6 waiting

    ## [17] Chris Doe — Senior PM, Google
    <https://linkedin.com/in/chrisdoe>

    ### draft · 291 chars
    Hey Chris, your post on killing the internal ticket queue hit home. ...

    ### FINAL

    ### note

The H2 is `## [<id>] <name> — <headline>`, headline omitted when null. An empty queue renders the H1 alone with `0 waiting`.

### constitution.md, format 1

    # Constitution v7 · format 1 · 2026-09-14 · 14 rules
    <!-- Generated. Edits here are overwritten. Use /coldwriter:prefer or /coldwriter:learn. -->

    ## Rules
    - Keep the note under 300 characters.

    ## When the recipient is a founder
    - Ask about a decision they made, not a topic.

    ## Examples
    > <most recent final, verbatim>
    > <second most recent final>

Active rules only, one per bullet. `## Rules` holds unconditional rules; each distinct `condition` gets a `## When <condition>` section. `## Examples` holds the two most recent `final_text` values. `db.py init --from` reads `## Rules` and `## When ...` and skips `## Examples`. Example: `tests/fixtures/constitution-v7.md`.

### profile JSON

The capture skill maps any MCP server's output to this shape. Unknown fields are dropped; everything but `name` may be null.

    {
      "name": "Chris Doe",
      "headline": "Senior PM, Google",
      "location": "Mountain View, CA",
      "company": "Google",
      "title": "Senior Product Manager",
      "about": "...",
      "experience": [{"title": "...", "company": "...", "start": "2021-03", "end": null, "description": "..."}],
      "education":  [{"school": "...", "degree": "...", "field": "...", "start": "2014", "end": "2018"}],
      "posts":      [{"id": "7f3a1c", "date": "2026-09-02", "text": "..."}]
    }

Examples: `tests/fixtures/profiles/chris-doe.json`, `tests/fixtures/profiles/minimal.json`.

## diff.py and render.py

Modules first, CLIs second.

- `diff.py`: `distance(a, b) -> float` and `hunks(a, b) -> list`. CLI `diff.py --a TEXT --b TEXT` prints `{"distance": ..., "hunks": [...]}`.
- `render.py`: `render_constitution(rules, examples, version, date) -> str` and `parse_constitution(text) -> list of (statement, condition)`. CLI `render.py [--workspace PATH]` prints what the next render would be and writes nothing.
