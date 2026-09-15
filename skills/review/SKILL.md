---
name: review
description: Record your edits to queue.md: approve, edit, or leave each draft.
disable-model-invocation: true
argument-hint: "[<id> ok | <id> <instruction> | <id> leave it ...]"
---

# review

No arguments: the user has edited `queue.md`. Run it and show the lines:

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py review

With arguments, the user is reviewing in conversation: "17 ok. 18, cut the second sentence, less eager. 19 leave it." For each contact they mention:

- `ok` (or "fine", "send it"): record it as is.

      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py review --contact 17 --final ok

- An instruction: rewrite the draft (it is in `queue.md`) to follow it, show the result, and once they say it is right, record it with their instruction as the note.

      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py review --contact 18 --final "<revised note>" --note "cut the second sentence, less eager"

- "leave it", "skip", or nothing: do nothing. It stays in the queue.

A fact they corrected goes in the note as `wrong: <fact>`, so the script adds it to `me/corrections.md`.

Never edit `queue.md` yourself; the script re-renders it.
