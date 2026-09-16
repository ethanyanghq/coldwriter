# Coldwriter workspace

This directory is a Coldwriter workspace. It is private and is never a git repository.

## LinkedIn

- Read profiles only with the LinkedIn MCP server's `get_person_profile` tool, sections `experience,education,posts`, one profile per call, only for URLs the user pasted.
- Never call `connect_with_person`, `send_message`, `search_people`, `get_sidebar_profiles`, or any other tool of that server. Coldwriter never writes to LinkedIn. The user sends every note by hand.

## Scripts

- Run the Coldwriter scripts from this directory; they take the workspace from the current directory. Never `cd` into the plugin.
- When a script prints an error, or prints nothing where a skill expects a line, show what it printed and stop. Never read, grep, or debug the plugin's scripts to work out why; they are not the user's code.

## Files

- `queue.md` and `db/` are written only by the Coldwriter scripts. Never edit them directly; pass text to the scripts.
- `constitution.md` is a render of the database. Never edit it; use `/coldwriter:prefer`.
- `me/` belongs to the user: resume, past notes. `me/_profile.md` and `me/corrections.md` are written by the skills.
