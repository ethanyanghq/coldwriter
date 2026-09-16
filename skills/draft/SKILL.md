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

   `exemplars` empty and `profile` null: the workspace holds nothing of the user's voice yet. Say so and ask whether to draft anyway or to fill `me/` and rerun `/coldwriter:init` first. Drafts written this way can be thrown away with `/coldwriter:discard --all`.

2. For each target, write one note that obeys every rule in `constitution.text`. The exemplars show the user's voice; weigh `final` over `draft`. `profile` is who the user is and what they want. `corrections` are facts the user has had to fix; never repeat them. Anchor the note in one specific thing from the recipient's profile (a post, a role, a project), not their headline. Use a hook from the user's profile only when the recipient's profile genuinely shares it (same school, same past employer); if it is a stretch, leave it out. As you write, list what you drew on: post ids, experience entries, the hook.

3. Record each note:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py add --contact <id> --text "<note>" --sources '["post 7f3a1c", "hook: Cornell"]'

   Show each `#<id> <name> · <n> chars` line, followed by the note itself in full, and nothing else: no sources, no notes on hooks, length, or corrections. Sources are stored and shown when asked.

4. Ask for their review here: for each contact, reply with the id and `ok`, the note they would send instead, or an instruction. Mention that they can also edit `queue.md` and run `/coldwriter:review`. When they reply, invoke the `coldwriter:review` skill with their reply as its arguments.

The user chose every contact. Never say whether one is worth messaging or fits what they want. Never edit `queue.md` yourself.
