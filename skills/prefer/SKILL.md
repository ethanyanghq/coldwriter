---
name: prefer
description: Add a rule to the constitution by hand.
disable-model-invocation: true
argument-hint: "\"<statement>\" [--when \"<condition>\"]"
---

# prefer

Arguments: $ARGUMENTS

The statement is one imperative sentence testable against a draft. `--when` is a condition such as `the recipient is a founder`. Pass both through exactly as written; do not reword them.

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/db.py prefer --statement "<statement>" --when "<condition>"

Omit `--when` when there is no condition. Show the script's two lines. If it reports `duplicate of #<id>`, say the rule already exists.
