---
name: unapprove
description: Put an approved note back in the queue so you can review it again.
disable-model-invocation: true
argument-hint: "<id>"
---

# unapprove

For a note recorded as final by mistake: an instruction taken as the note, or an `ok` you want back. It must be approved and not yet sent.

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py unapprove --contact <id>

Show the script's line verbatim. On `not approved`, say what state the contact is in; a sent note stays sent. On `already learned`, say the edit is already in the rules and that `edited:` at send time is how to change it. Otherwise the draft is back in `queue.md`, ready for `/coldwriter:review`.

Never edit `queue.md` yourself; the script re-renders it.
