---
name: send
description: Put each approved note on the clipboard, open the profile, and record that you sent it.
disable-model-invocation: true
---

# send

Notes approved in conversation are sent as part of `review`; this is for the rest.

1. List what is ready and show it:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py send

   No contacts listed: stop.

2. For each listed contact, in order:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py send --contact <id>

   The note is on the clipboard and the profile is open in the browser. Tell the user: click Connect, then Add a note, paste, and Send. Ask them to reply `y`, `skip`, or `edited: <the text you actually sent>`. Wait for the reply.

   - `y`:

         python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py sent --contact <id>

   - `edited: <text>`:

         python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py sent --contact <id> --edited "<text>"

   - `skip`: nothing. It stays approved for next time.

   Show the script's line and move to the next contact.

The user sends every note by hand. Never call a tool that writes to LinkedIn.
