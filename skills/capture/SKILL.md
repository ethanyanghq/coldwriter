---
name: capture
description: Read one or more LinkedIn profile URLs through the LinkedIn MCP server and queue them for drafting.
argument-hint: "<url> [<url> ...]"
---

# capture

URLs: $ARGUMENTS

For each URL, in the order given, one at a time:

1. Read the profile with the MCP tool `get_person_profile`, sections `experience, education, about, posts`. Only that tool, only these URLs. Never search, never read suggested profiles, never call a tool that writes to LinkedIn. If the tool is unavailable, say so and stop; do not paste or guess a profile.

2. Map the response to the profile JSON in `${CLAUDE_PLUGIN_ROOT}/scripts/README.md`: `name`, `headline`, `location`, `company`, `title`, `about`, `experience[]`, `education[]`, `posts[]`. Drop fields it does not name, use `null` for anything missing, keep every text verbatim. `name` is required.

3. Record it, passing the JSON on stdin:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py capture --url "<url>" --profile - <<'JSON'
       {"name": "...", ...}
       JSON

   Show the script's line: `#<id> captured <name>` or `#<id> exists <name>`.

When all URLs are done, say the next step is `/coldwriter:draft`.
