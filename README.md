# Coldwriter

A LinkedIn coffee-chat engine that runs inside Claude Code. Point it at profiles, get one connection note in your voice, edit it, and it learns from every edit. You press Send.

**Status:** pre-release, under construction.

## The three no's

1. **Never sends.** Nothing here writes to LinkedIn. The note lands on your clipboard; you paste it.
2. **No credentials.** Claude Code is the model. Profiles are read through a LinkedIn MCP server you choose and log into yourself.
3. **No filtering.** No discovery, no scoring, no caps. Every URL you paste is someone you already decided to message.

## How it works

`/coldwriter:capture <url>` reads a profile. `/coldwriter:draft` writes one note per contact into `queue.md`. You edit the file. `/coldwriter:review` records what you changed. `/coldwriter:send` puts each note on your clipboard. `/coldwriter:learn` turns your edits into rules and renders them as `constitution.md`, which the next drafts follow.

## Install

```
/plugin marketplace add <owner>/coldwriter
/coldwriter:init
```

## Development

`make check` runs what CI runs: guard, lint, validate, tests. The script layer, its output formats, and its data shapes are specified in [scripts/README.md](scripts/README.md).
