---
name: discard
description: Throw away unreviewed drafts so the next draft run starts those contacts over.
disable-model-invocation: true
argument-hint: "[<id> | --all]"
---

# discard

Use this when drafts were written against the wrong inputs (an empty `me/`, a profile that was not ready) and should not be reviewed, because reviewing them would teach the learn loop about missing inputs rather than voice. Reviewed drafts are never removed.

One contact:

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py discard --contact <id>

Every unreviewed draft in the workspace:

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py discard --all

Show the script's lines verbatim. If it reports `already reviewed`, say the draft was already recorded and stays. Then say the contacts are queued again and `/coldwriter:draft` will write them fresh.

Never edit `queue.md` yourself; the script re-renders it.
