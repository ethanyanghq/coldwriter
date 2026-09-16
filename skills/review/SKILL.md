---
name: review
description: Approve, edit, or leave each draft, in conversation or through queue.md.
argument-hint: "[<id> ok | <id> <your note> | <id> <instruction> | <id> leave it ...]"
---

# review

With arguments, the user is reviewing in conversation. With none, they have edited `queue.md`.

## In conversation

For each contact they mention, decide which of these their words are. A full note reads as a message to the recipient; an instruction reads as a request to you. When unsure, treat it as an instruction: a wrong rewrite is shown and waits, while a wrongly recorded note goes straight to the clipboard.

- `ok` (or "fine", "send it"): record the draft as is.

      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py review --contact 17 --final ok

- The note they would send, in their own words: record it verbatim. Their reason, if they give one, is the note.

      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py review --contact 18 --final "<their text>" --note "<their reason, if any>"

- An instruction ("cut the second sentence, less eager"): rewrite the draft (it is in `queue.md`) applying only that instruction and changing nothing else. Show the result and ask for `yes`. If they say yes, record it with the instruction as the note. If they answer with the text they want instead, record their text, still with the instruction as the note. `ok` always means the draft in `queue.md`, never a rewrite, so do not offer it here. If the instruction itself says to send ("..., then send"), record the rewrite without waiting and say that you did.

      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py review --contact 18 --final "<revised note>" --note "cut the second sentence, less eager"

- "leave it", "skip", or nothing: do nothing. It stays in the queue.

A fact they corrected goes in the note as `wrong: <fact>`, so the script adds it to `me/corrections.md`.

Every recorded contact is now approved. Hand it over right away, one at a time:

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py open --contact <id>

This copies the note to the clipboard and opens the profile; it sends nothing, so describe it as copying and opening. Start your message with what was recorded (`#18 recorded your text as the final` or `#18 recorded the rewrite`), so a misread is caught here. Then tell the user: click Connect, then Add a note, paste, and Send. Ask for `y`, `skip`, or `edited: <the text you actually sent>`, and wait.

If they say what you recorded was an instruction, not their note: put it back and handle it as an instruction.

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py unapprove --contact <id>

- `y`: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py sent --contact <id>`
- `edited: <text>`: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py sent --contact <id> --edited "<text>"`
- `skip`: nothing. It stays approved; `/coldwriter:send` picks it up later.

## From queue.md

Run it and show its lines verbatim. Do not read `queue.md` afterwards: the script re-renders it and reviewed contacts drop out, so an empty queue is the normal result. If any contact was approved, say `/coldwriter:send` is next.

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/queue.py review

## After either

Show the script's `#<id> ...` lines verbatim, then one `unlearned <n> edits` line: the last run's. Every run prints that line, and only the last one is current, so the earlier ones are left out. At 15 or more, suggest `/coldwriter:learn`; never insist.

A recorded or sent note is the user's decision. Do not check it against the constitution or point out rules it breaks; `/coldwriter:learn` is where edits meet rules.

The user sends every note by hand. Never call a tool that writes to LinkedIn. Never edit `queue.md` yourself.
