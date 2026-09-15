# Coldwriter workspace

This directory is a Coldwriter workspace. It is private and is never a git repository.

## LinkedIn

- Read profiles only with `mcp__mcp-server-linkedin__get_person_profile`, sections `experience, education, about, posts`, one profile per call, only for URLs the user pasted.
- Never call `connect_with_person`, `send_message`, `search_people`, `get_sidebar_profiles`, or any other LinkedIn tool. Coldwriter never writes to LinkedIn. The user sends every note by hand.

## Files

- `queue.md` and `db/` are written only by the Coldwriter scripts. Never edit them directly; pass text to the scripts.
- `constitution.md` is a render of the database. Never edit it; use `/coldwriter:prefer`.
- `me/` belongs to the user: resume, past notes. `me/_profile.md` and `me/corrections.md` are written by the skills.
