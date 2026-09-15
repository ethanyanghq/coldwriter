from conftest import FIXTURES
from render import parse_constitution, render_constitution

FIXTURE = FIXTURES / "constitution-v7.md"


def test_render_then_parse_round_trips_the_fixture():
    text = FIXTURE.read_text()
    rules = parse_constitution(text)
    assert len(rules) == 9
    assert rules[0] == ("Keep the note under 300 characters.", None)
    founder = "the recipient is a founder"
    assert rules[-1] == ("Ask about a decision they made, not a topic.", founder)
    examples = [line[2:] for line in text.splitlines() if line.startswith("> ")]
    assert render_constitution(rules, examples, 7, "2026-09-14") == text


def test_examples_are_the_two_most_recent_and_never_parsed_as_rules():
    text = render_constitution([("No em dashes.", None)], ["- newest", "second", "third"], 2, "d")
    assert text.count("\n> ") == 2
    assert "third" not in text
    assert parse_constitution(text) == [("No em dashes.", None)]


def test_empty_rule_set_renders_a_valid_header():
    text = render_constitution([], [], 1, "2026-09-14")
    assert text.startswith("# Constitution v1 · format 1 · 2026-09-14 · 0 rules\n<!-- Generated.")
    assert "## Rules\n" in text
    assert parse_constitution(text) == []
