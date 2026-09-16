---
name: capture
description: Read one or more LinkedIn profile URLs through the LinkedIn MCP server and queue them for drafting.
argument-hint: "<url> [<url> ...]"
---

# capture

URLs: $ARGUMENTS

For each URL, in the order given, one at a time:

1. Check it before reading anything, because the profile read is slow:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py capture --url "<url>"

   `#<id> exists <name>`: show that line and move to the next URL. Exit 2 (`not a Coldwriter workspace`): show the line, say the user needs to run `/coldwriter:init` in their workspace directory, and stop. `new`: go on.

2. Say `reading <url>, this takes a minute`, then read the profile with the LinkedIn MCP server's `get_person_profile` tool, sections `experience,education,posts` (the About text comes with the main page). Only that tool, only these URLs. Never search, never read suggested profiles, never call a tool that writes to LinkedIn. If the tool is unavailable, say so and stop; do not paste or guess a profile.

3. Map the response to this shape. Everything but `name` may be null; unknown fields are dropped; keep every text verbatim, do not summarize. The server returns scraped page text, so split it yourself.

       {"name": "Chris Doe", "headline": "Senior PM, Google", "location": "Mountain View, CA",
        "company": "Google", "title": "Senior Product Manager", "about": "...",
        "experience": [{"title": "...", "company": "...", "start": "2021-03", "end": null, "description": "..."}],
        "education":  [{"school": "...", "degree": "...", "field": "...", "start": "2014", "end": "2018"}],
        "posts":      [{"id": null, "date": "2mo", "text": "..."}]}

   `posts` is one entry per post in the activity feed, most recent first, text verbatim. Keep reposts, with the text prefixed `Reposted from <author>: `. `date` is whatever the feed shows (`2mo` is fine); `id` is null unless the server gives one. Drop counters, buttons, and boilerplate. An empty feed is `[]`.

4. Write the JSON to a temporary file outside the workspace (your scratchpad) with the Write tool, then record it:

       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py capture --url "<url>" --profile @<path>

   Show the script's line: `#<id> captured <name>`.

When all URLs are done and at least one was captured, invoke the `coldwriter:draft` skill so every new contact gets its note in the same turn.
