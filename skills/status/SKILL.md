---
name: status
description: Pipeline counts, sends this week, the learning curve, and constitution history.
argument-hint: "[--chart]"
---

# status

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/db.py status $ARGUMENTS

Show the report verbatim in a code block; do not paraphrase the numbers. With `--chart` it also writes `learning-curve.svg` in the workspace; say so.
