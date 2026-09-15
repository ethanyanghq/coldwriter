#!/usr/bin/env python3
"""Edit distance and word-level hunks between a draft and its final. Learn core."""

import argparse
import difflib
import json


def distance(a, b):
    """1 - character ratio: 0 is untouched, 1.0 is from scratch."""
    return 1 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def hunks(a, b):
    """Word-level opcodes with the equal runs dropped."""
    a_words, b_words = a.split(), b.split()
    matcher = difflib.SequenceMatcher(None, a_words, b_words, autojunk=False)
    return [
        {
            "op": op,
            "original": " ".join(a_words[i1:i2]),
            "replacement": " ".join(b_words[j1:j2]),
        }
        for op, i1, i2, j1, j2 in matcher.get_opcodes()
        if op != "equal"
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    args = parser.parse_args()
    print(json.dumps({"distance": distance(args.a, args.b), "hunks": hunks(args.a, args.b)}))


if __name__ == "__main__":
    main()
