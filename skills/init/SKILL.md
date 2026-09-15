---
name: init
description: Create or refresh a Coldwriter workspace in the current directory: schema, seed rules, your profile, and optionally your past notes.
disable-model-invocation: true
argument-hint: "[--from <constitution.md>]"
---

# init

The current directory is the workspace. Rerunning is safe; do it after changing `me/`.

1. Run the scripts, passing `--from <path>` through if given, and show their output:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/db.py init $ARGUMENTS
       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py render

2. If `me/_profile.md` does not exist yet, ask and wait for the answer:

   > Tell me about yourself: where you are, what you want from these chats, and a few hooks people might share with you (school, hometown, hobby, past employer). Drop your resume into `me/`. If you have connection notes you have sent before, put those in too. That part is optional.

3. Read everything in `me/` (PDFs included) and the answer. Write `me/_profile.md`: who they are, what they want from these chats, their hooks, and three things they have done worth mentioning. Facts only: no adjectives, nothing they did not say or show. Leave `me/corrections.md` alone.

4. If `me/` holds notes they have sent (or they pasted some), record each verbatim:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/db.py history --text "<note>" --text "<note>"

   Then follow `${CLAUDE_PLUGIN_ROOT}/skills/learn/SKILL.md` in approval mode.

5. Say what the workspace now holds and that the next step is `/coldwriter:capture <url>`.
