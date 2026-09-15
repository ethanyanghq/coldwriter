"""The schema is shared by every script. These pin its behavior before any script
exists: the status triggers, the queue view, and the views /learn reads."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
T = "2026-09-14T20:28:00Z"


def constitution(db, version=1):
    sha = f"sha{version:02d}"
    db.execute(
        "INSERT INTO constitutions (sha, version, text, created_at) VALUES (?, ?, ?, ?)",
        (sha, version, f"# Constitution v{version}", T),
    )
    return sha


def contact(db, url="https://linkedin.com/in/chrisdoe"):
    profile = json.loads((FIXTURES / "profiles" / "chris-doe.json").read_text())
    cur = db.execute(
        "INSERT INTO contacts (linkedin_url, name, headline, company, title, profile_json,"
        " captured_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            url,
            profile["name"],
            profile["headline"],
            profile["company"],
            profile["title"],
            json.dumps(profile),
            T,
            T,
        ),
    )
    return cur.lastrowid


def draft(db, contact_id, sha, text="draft"):
    cur = db.execute(
        "INSERT INTO drafts (context_ref, contact_id, text, constitution_sha, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (f"contact:{contact_id}", contact_id, text, sha, T),
    )
    return cur.lastrowid


def edit(db, sha, contact_id=None, draft_id=None, final="final", distance=0.3, ref=None):
    ref = ref or f"contact:{contact_id}"
    cur = db.execute(
        "INSERT INTO edits (context_ref, contact_id, draft_id, final_text, edit_distance,"
        " constitution_sha, reviewed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ref, contact_id, draft_id, final, distance, sha, T),
    )
    return cur.lastrowid


def status(db, contact_id):
    return db.execute("SELECT status FROM contacts WHERE id = ?", (contact_id,)).fetchone()[0]


def test_schema_version(db):
    row = db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    assert row[0] == "9"


def test_contact_walks_the_pipeline_through_triggers(db):
    sha = constitution(db)
    c = contact(db)
    assert status(db, c) == "queued"

    d = draft(db, c, sha)
    assert status(db, c) == "drafted"
    assert [r["id"] for r in db.execute("SELECT id FROM v_queue")] == [d]

    e = edit(db, sha, contact_id=c, draft_id=d)
    assert status(db, c) == "approved"
    assert db.execute("SELECT COUNT(*) FROM v_queue").fetchone()[0] == 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.execute("INSERT INTO sends (contact_id, edit_id, sent_at) VALUES (?, ?, ?)", (c, e, now))
    assert status(db, c) == "sent"
    assert db.execute("SELECT n FROM v_sends_this_week").fetchone()[0] == 1


def test_queue_shows_only_the_newest_draft_per_contact(db):
    sha = constitution(db)
    c = contact(db)
    draft(db, c, sha, "first")
    d2 = draft(db, c, sha, "second")
    rows = db.execute("SELECT id, text FROM v_queue").fetchall()
    assert [(r["id"], r["text"]) for r in rows] == [(d2, "second")]


def test_one_edit_per_context(db):
    sha = constitution(db)
    c = contact(db)
    d = draft(db, c, sha)
    edit(db, sha, contact_id=c, draft_id=d)
    with pytest.raises(sqlite3.IntegrityError):
        edit(db, sha, contact_id=c, draft_id=d)


def test_learning_curve_ignores_from_scratch_finals(db):
    sha = constitution(db)
    c = contact(db)
    d = draft(db, c, sha)
    edit(db, sha, contact_id=c, draft_id=d, distance=0.4)
    edit(db, sha, final="a past note", distance=1.0, ref="past:1")
    row = db.execute("SELECT n_edits, mean_edit_distance FROM v_learning_curve").fetchone()
    assert (row["n_edits"], row["mean_edit_distance"]) == (1, 0.4)


def test_unlearned_view_carries_the_draft_and_drops_learned_edits(db):
    sha = constitution(db)
    c = contact(db)
    d = draft(db, c, sha, "the draft")
    e = edit(db, sha, contact_id=c, draft_id=d)
    past = edit(db, sha, final="a past note", distance=1.0, ref="past:1")
    rows = {r["id"]: r["draft_text"] for r in db.execute("SELECT id, draft_text FROM v_unlearned")}
    assert rows == {e: "the draft", past: None}

    db.execute("UPDATE edits SET learned_at = ? WHERE id = ?", (T, e))
    assert [r["id"] for r in db.execute("SELECT id FROM v_unlearned")] == [past]


def test_context_labels_prefer_the_headline(db):
    c = contact(db)
    db.execute("UPDATE contacts SET headline = NULL WHERE id = ?", (c,))
    label = db.execute("SELECT label FROM v_context_labels").fetchone()["label"]
    assert label == "Senior Product Manager, Google"

    db.execute("UPDATE contacts SET headline = 'Senior PM, Google' WHERE id = ?", (c,))
    rows = db.execute("SELECT context_ref, label FROM v_context_labels").fetchall()
    assert [(r["context_ref"], r["label"]) for r in rows] == [(f"contact:{c}", "Senior PM, Google")]


def test_preferences_reject_unknown_source_and_status(db):
    insert = (
        "INSERT INTO preferences (statement, source, status, created_at, updated_at)"
        " VALUES ('x', ?, ?, ?, ?)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, ("guess", "active", T, T))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, ("seed", "pending", T, T))
