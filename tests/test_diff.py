import json

from conftest import run

from diff import distance, hunks


def test_identical_is_zero():
    assert distance("Hey Chris, hit home.", "Hey Chris, hit home.") == 0
    assert hunks("Hey Chris, hit home.", "Hey Chris, hit home.") == []


def test_disjoint_is_one():
    assert distance("abc", "xyz") == 1.0


def test_one_replaced_word_is_one_replace_hunk():
    assert hunks("your impressive work", "your fine work") == [
        {"op": "replace", "original": "impressive", "replacement": "fine"}
    ]


def test_delete_and_insert_hunks():
    assert hunks("your impressive work", "your work") == [
        {"op": "delete", "original": "impressive", "replacement": ""}
    ]
    assert hunks("your work", "your own work") == [
        {"op": "insert", "original": "", "replacement": "own"}
    ]


def test_cli_prints_distance_and_hunks():
    out = json.loads(run("diff", "--a", "your impressive work", "--b", "your work").stdout)
    assert 0 < out["distance"] < 1
    assert out["hunks"] == [{"op": "delete", "original": "impressive", "replacement": ""}]
