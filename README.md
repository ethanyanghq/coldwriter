# Coldwriter

A LinkedIn coffee-chat engine that runs inside Claude Code. Point it at profiles, get one connection note in your voice, edit it, and it learns from every edit. You press Send.

**Status:** pre-release.

## The three no's

1. **Never sends.** Nothing here writes to LinkedIn. The note lands on your clipboard; you paste it.
2. **No credentials.** Claude Code is the model. Profiles are read through a LinkedIn MCP server you choose and sign in to yourself.
3. **No filtering.** No discovery, no scoring, no caps. Every URL you paste is someone you already decided to message.

## How it works

`/coldwriter:capture <url>` reads a profile and drafts one note for it, shown in chat. You reply with `ok`, the note you would send instead, or an instruction. An approved note lands on your clipboard with the profile open; you paste it and reply `y`. That is the whole loop. The drafts also sit in `queue.md`, so you can edit the file instead and run `/coldwriter:review`. `/coldwriter:draft` redrafts. `/coldwriter:discard` throws away drafts you have not reviewed. `/coldwriter:unapprove <id>` puts an approved note back in the queue. `/coldwriter:send` sends anything approved but not yet sent. `/coldwriter:learn` turns your edits into rules and renders them as `constitution.md`, which the next drafts follow. `/coldwriter:prefer` adds a rule by hand. `/coldwriter:status` shows the pipeline and the learning curve.

## Install

In Claude Code:

```
/plugin marketplace add ethanyanghq/coldwriter
/plugin install coldwriter@coldwriter
```

Then, in an empty directory that will be your workspace:

```
/coldwriter:init
```

That creates `me/` (drop your resume and past notes there), `constitution.md`, `queue.md`, and `db/outreach.sqlite`. The workspace is private and is never a git repository. Python 3.9 or newer is the only requirement; macOS ships it.

## LinkedIn access

Profiles are read through an MCP server that drives a browser session you own. The reference server is [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) (Apache-2.0). Sign in once:

```
uvx mcp-server-linkedin@latest --login
```

or reuse the session from a browser you are already signed in to:

```
uvx mcp-server-linkedin@latest --import-from-browser
```

Then put this `.mcp.json` in your workspace directory:

```json
{
  "mcpServers": {
    "mcp-server-linkedin": {
      "command": "uvx",
      "args": ["mcp-server-linkedin@latest"],
      "env": { "UV_HTTP_TIMEOUT": "300" }
    }
  }
}
```

Coldwriter calls one tool, `get_person_profile`, one profile per call, only for URLs you pasted. The workspace `CLAUDE.md` names the tools it must never call. Any server that exposes a comparable profile tool works; the capture skill maps the server's output to Coldwriter's profile shape. [devag7/linkedin-mcp](https://github.com/devag7/linkedin-mcp) (MIT) is an alternative.

## The learning curve

Every review stores the distance between the draft and what you actually sent. `/coldwriter:status` prints the mean per constitution version; `/coldwriter:status --chart` writes it as `learning-curve.svg` in the workspace. A version whose mean is lower than the last is the signal. It is the only metric.

## Development

`make check` runs what CI runs: guard, lint, validate, tests. The script layer, its output formats, and its data shapes are specified in [scripts/README.md](scripts/README.md). Skills live in `skills/<name>/SKILL.md` and hold every instruction the model follows.
