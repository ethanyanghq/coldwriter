---
name: draft
description: Write one connection note for every queued contact, following the constitution.
model: opus
argument-hint: "[--redraft <id>]"
---

# draft

1. Get the context:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py draft $ARGUMENTS

   `targets` empty: say there is nothing to draft and stop.

2. For each target, write one note that obeys every rule in `constitution.text`. The exemplars show the user's voice; weigh `final` over `draft`. `profile` is who the user is and what they want. `corrections` are facts the user has had to fix; never repeat them. Anchor the note in one specific thing from the recipient's profile (a post, a role, a project), not their headline. Use a hook from the user's profile only when the recipient's profile genuinely shares it (same school, same past employer); if it is a stretch, leave it out. As you write, list what you drew on: post ids, experience entries, the hook.

3. Record each note:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py add --contact <id> --text "<note>" --sources '["post 7f3a1c", "hook: Cornell"]'

   Show each `#<draft_id> draft for #<id> · <n> chars` line. Then tell the user to open `queue.md`, fill in FINAL (`ok`, or the text they want) and note for each contact, and run `/coldwriter:review`.

Never edit `queue.md` yourself.
