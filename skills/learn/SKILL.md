---
name: learn
description: Turn your reviewed edits into rule changes and render a new constitution version.
---

# learn

The learn core. You observe (A) and reconcile (B); the script applies (C). You never write to the database.

## Emit

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/db.py learn emit

`{"edits": []}`: say there is nothing to learn and stop. Fewer than 15 edits: say the batch is small and that 15 or more gives better rules, then continue if the user wants to. Never refuse.

## A. Observe, per batch of at most 25 edits

Each edit has a `kind`: `edited` (draft differs from final), `untouched` (distance 0), or `scratch` (a note the user wrote with no draft). `hunks` are word-level `(op, original, replacement)`. `label` is the recipient's headline when known.

Write 0 to 3 observations per edit, each anchored to a specific hunk or to the note:

    {"edit_id": 41, "anchor": "hunk 2", "what": "removed 'impressive' before 'work'",
     "why": "note: less eager", "generalizes_as": "avoid adjectives about their work",
     "recipient_kind": "founder", "kind": "style"}

- `edited`: what changed and in which direction. `why` comes from the note; `null` when there is no note and no obvious reason.
- `untouched`: no observations. An untouched draft is an exemplar, never evidence for or against a rule.
- `scratch`: the text is ground truth. Note which rules it obeys where a choice was involved, and which it violates.
- `kind` is `style` or `fact`. Fact fixes (names, schools, dates) are `fact`; they are already in `me/corrections.md` and never become rules.
- `recipient_kind` is `null` unless the label makes it plain.

## B. Reconcile, once over all observations

Inputs: every observation, `preferences` (all non-retired rules with their counts), `retired` (statements never to propose again), and `constitution.text`. If the constitution is longer than 80 lines, look for merges first.

Output exactly this shape:

    {
      "existing": [{"id": 12, "support": [41, 47], "contradict": [], "note": "..."}],
      "new":      [{"statement": "Never open with the recipient's job title.",
                    "condition": null, "evidence": [41, 52, 58]}],
      "merge":    [{"keep": 12, "retire": 31, "reason": "same rule, narrower wording"}]
    }

Definitions you are held to:

- Support for rule R from edit E: the draft violated R and the final obeys it (the user moved toward R), or the note states R. For `scratch`: the text obeys R where a choice was involved.
- Contradiction: the draft obeyed R and the final violates it (the user moved away from R), or the note rejects R.
- Neutral is the default. R not implicated: no count. Do not stretch. Never cite an untouched edit anywhere; the script rejects it.
- New rule: only when two or more observations from two or more distinct edits share a `generalizes_as`. One imperative sentence, testable against a draft. Prefer constraints ("Never", "At most", "Only") over aspirations ("Be warm"); texture is what exemplars are for. A `condition` only when every evidence edit shares `recipient_kind` and the rule would be wrong without it. Never propose a statement that is in `retired` or already in `preferences`; cite the existing rule under `existing` instead.
- Merge: two existing rules the same in substance. Keep the better-worded one.

## C. Apply

Write the reconcile JSON to a file and run:

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/db.py learn apply --reconcile @<path>

Show the changelog it prints. Exit 1 names a bad id: fix the JSON and rerun.

## Approval mode

Used by `/coldwriter:init` for past notes. Run A and B as above. Before applying, show each rule in `new` one at a time and ask keep or drop. Remove the dropped ones from `new`, then:

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/db.py learn apply --mode approve --reconcile @<path>
