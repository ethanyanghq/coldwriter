#!/usr/bin/env python3
"""Render constitution.md from rules and parse one back. Learn core."""

import argparse
import sys

FORMAT = 1
COMMENT = (
    "<!-- Generated. Edits here are overwritten. Use /coldwriter:prefer or /coldwriter:learn. -->"
)


def render_constitution(rules, examples, version, date):
    """rules is [(statement, condition)] in id order; examples are finals, newest first."""
    conditions = []
    for _, condition in rules:
        if condition and condition not in conditions:
            conditions.append(condition)
    lines = [f"# Constitution v{version} · format {FORMAT} · {date} · {len(rules)} rules", COMMENT]
    lines += ["", "## Rules"] + [f"- {s}" for s, c in rules if not c]
    for condition in conditions:
        lines += ["", f"## When {condition}"] + [f"- {s}" for s, c in rules if c == condition]
    if examples:
        lines += ["", "## Examples"] + ["> " + e.replace("\n", "\n> ") for e in examples[:2]]
    return "\n".join(lines) + "\n"


def parse_constitution(text):
    """[(statement, condition)] from a format-1 render; Examples and unknown sections skipped."""
    rules, condition, keep = [], None, False
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            keep = heading == "Rules" or heading.startswith("When ")
            condition = heading[5:] if heading.startswith("When ") else None
        elif keep and line.startswith("- "):
            rules.append((line[2:].strip(), condition))
    return rules


def main():
    parser = argparse.ArgumentParser(description="Print the next render. Writes nothing.")
    parser.add_argument("--workspace", default=".")
    args = parser.parse_args()
    from db import connect, render_preview  # imported here: db.py imports this module

    text, _, _ = render_preview(connect(args.workspace), "outreach")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
