"""db.py at the script boundary: run the command, check the database and stdout."""

import json

from conftest import FIXTURES, connect, run

from diff import distance

T = "2026-09-14T20:28:00Z"
ADA_DRAFT = (
    "Hi Ada, your impressive work on Loomly's pricing reset stood out. I'm at Columbia studying"
    " how early teams price, and I'd love to hear how you picked the moment to change it."
)
ADA_FINAL = (
    "Hi Ada, your post on Loomly's pricing reset stood out. I'm at Cornell studying how early"
    " teams price. How did you pick the moment to change it?"
)


def prefs(ws):
    rows = connect(ws).execute("SELECT * FROM preferences ORDER BY id").fetchall()
    return {r["id"]: dict(r) for r in rows}


def latest_sha(ws):
    return connect(ws).execute("SELECT sha FROM constitutions ORDER BY version DESC").fetchone()[0]


def seed_edits(ws):
    """Unlearned edits 41, 47, 52 (edited), 58 (scratch), 60 (untouched). 41 has a contact."""
    conn = connect(ws)
    conn.execute("PRAGMA foreign_keys = ON")
    sha = latest_sha(ws)
    profile = (FIXTURES / "profiles" / "minimal.json").read_text()
    conn.execute(
        "INSERT INTO contacts (id, linkedin_url, name, headline, profile_json, captured_at,"
        " updated_at) VALUES (18, 'https://linkedin.com/in/adanguyen', 'Ada Nguyen',"
        " 'Founder, Loomly', ?, ?, ?)",
        (profile, T, T),
    )
    pairs = [
        (41, "contact:18", 18, ADA_DRAFT, ADA_FINAL, "less eager"),
        (47, "x:47", None, "Hey Sam, your impressive work on keys.", "Hey Sam, your keys.", None),
        (52, "x:52", None, "Senior PM at Google, hi.", "Hi Chris.", "no title"),
        (60, "x:60", None, "Untouched draft.", "Untouched draft.", None),
    ]
    for edit_id, ref, contact_id, draft, final, note in pairs:
        conn.execute(
            "INSERT INTO drafts (id, context_ref, contact_id, text, constitution_sha, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (edit_id, ref, contact_id, draft, sha, T),
        )
        conn.execute(
            "INSERT INTO edits (id, context_ref, contact_id, draft_id, final_text, edit_distance,"
            " reason_text, constitution_sha, reviewed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (edit_id, ref, contact_id, edit_id, final, distance(draft, final), note, sha, T),
        )
    conn.execute(
        "INSERT INTO edits (id, context_ref, final_text, edit_distance, constitution_sha,"
        " reviewed_at) VALUES (58, 'past:1', 'A past note.', 1.0, ?, ?)",
        (sha, T),
    )
    conn.commit()


# --- init ----------------------------------------------------------------------------------


def test_init_creates_the_workspace_and_seeds(tmp_path):
    ws = tmp_path / "ws"
    out = run("db", "init", workspace=ws).stdout.splitlines()
    assert out[:2] == [f"workspace {ws}", "preferences 7 active"]
    assert out[2].startswith("constitution v1 ")
    assert (ws / "me").is_dir()
    assert (ws / "CLAUDE.md").read_text().startswith("# Coldwriter workspace")
    conn = connect(ws)
    rows = conn.execute(
        "SELECT statement, source, status, support_count FROM preferences ORDER BY id"
    ).fetchall()
    assert len(rows) == 7
    assert tuple(rows[1]) == ("No em dashes.", "seed", "active", 2)
    text = (ws / "constitution.md").read_text()
    assert text.startswith("# Constitution v1 · format 1 · ")
    assert "· 7 rules\n" in text and "## Examples" not in text
    sha = out[2].split()[-1]
    assert tuple(conn.execute("SELECT sha, version, text FROM constitutions").fetchone()) == (
        sha,
        1,
        text,
    )


def test_init_rerun_is_a_noop(ws):
    first = run("db", "init", workspace=ws).stdout
    assert run("db", "init", workspace=ws).stdout == first
    assert len(prefs(ws)) == 7
    assert connect(ws).execute("SELECT COUNT(*) FROM constitutions").fetchone()[0] == 1


def test_init_rerun_does_not_resurrect_a_retired_seed(ws):
    conn = connect(ws)
    conn.execute("UPDATE preferences SET status = 'retired' WHERE id = 2")
    conn.commit()
    out = run("db", "init", workspace=ws).stdout
    assert "preferences 6 active" in out and "constitution v2 " in out
    assert len(prefs(ws)) == 7 and prefs(ws)[2]["status"] == "retired"
    assert "- No em dashes." not in (ws / "constitution.md").read_text()


def test_init_from_imports_only_the_rules_it_does_not_have(tmp_path):
    ws = tmp_path / "ws"
    out = run("db", "init", "--from", str(FIXTURES / "constitution-v7.md"), workspace=ws).stdout
    assert "preferences 9 active" in out
    rows = prefs(ws)
    assert rows[1]["source"] == "seed"
    assert (rows[8]["statement"], rows[8]["source"], rows[8]["support_count"]) == (
        "Never open with the recipient's job title.",
        "imported",
        2,
    )
    assert rows[9]["condition"] == "the recipient is a founder"
    text = (ws / "constitution.md").read_text()
    assert "## When the recipient is a founder\n- Ask about a decision they made" in text


def test_missing_workspace_is_exit_2(tmp_path):
    proc = run("db", "status", workspace=tmp_path, expect=2)
    assert proc.stderr.strip() == f"not a Coldwriter workspace: {tmp_path} (run /coldwriter:init)"


# --- history, prefer -----------------------------------------------------------------------


def test_history_numbers_past_notes_after_the_highest_existing(ws):
    out = run("db", "history", "--text", "first note", "--text", "second", workspace=ws).stdout
    assert out.splitlines() == ["#1 past:1", "#2 past:2"]
    out = run("db", "history", "--text", "-", stdin="third note", workspace=ws).stdout
    assert out.strip() == "#3 past:3"
    row = connect(ws).execute("SELECT * FROM edits WHERE id = 3").fetchone()
    assert (row["draft_id"], row["edit_distance"], row["final_text"]) == (None, 1.0, "third note")
    assert (row["constitution_sha"], row["learned_at"]) == (latest_sha(ws), None)


def test_prefer_inserts_a_manual_rule_and_rejects_duplicates(ws):
    out = run(
        "db",
        "prefer",
        "--statement",
        "Never open with a compliment.",
        "--when",
        "the recipient is a founder",
        workspace=ws,
    ).stdout.splitlines()
    assert out[0] == "#8 active" and out[1].startswith("constitution v2 ")
    row = prefs(ws)[8]
    assert (row["source"], row["support_count"], row["condition"]) == (
        "manual",
        3,
        "the recipient is a founder",
    )
    text = (ws / "constitution.md").read_text()
    assert "## When the recipient is a founder\n- Never open with a compliment.\n" in text

    proc = run("db", "prefer", "--statement", "no EM dashes.", workspace=ws, expect=1)
    assert proc.stderr.strip() == "duplicate of #2 (active)"
    proc = run("db", "prefer", "--statement", "No em dashes", workspace=ws, expect=1)
    assert proc.stderr.strip() == "duplicate of #2 (active)"
    assert len(prefs(ws)) == 8
    assert connect(ws).execute("SELECT COUNT(*) FROM constitutions").fetchone()[0] == 2


# --- learn emit ----------------------------------------------------------------------------


def test_learn_emit_is_empty_when_nothing_is_unlearned(ws):
    assert run("db", "learn", "emit", workspace=ws).stdout.strip() == '{"edits": []}'


def test_learn_emit_shape(ws):
    seed_edits(ws)
    conn = connect(ws)
    conn.execute("UPDATE preferences SET status = 'retired' WHERE id = 7")
    conn.commit()
    out = json.loads(run("db", "learn", "emit", workspace=ws).stdout)
    assert out["domain"] == "outreach"
    assert out["constitution"]["version"] == 1 and out["constitution"]["sha"] == latest_sha(ws)
    assert out["constitution"]["text"].startswith("# Constitution v1")
    assert [p["id"] for p in out["preferences"]] == [1, 2, 3, 4, 5, 6]
    assert out["preferences"][1] == {
        "id": 2,
        "statement": "No em dashes.",
        "condition": None,
        "status": "active",
        "source": "seed",
        "support_count": 2,
        "contradiction_count": 0,
    }
    assert out["retired"] == [prefs(ws)[7]["statement"]]
    edits = {e["id"]: e for e in out["edits"]}
    assert sorted(edits) == [41, 47, 52, 58, 60]
    ada = edits[41]
    assert (ada["context_ref"], ada["label"], ada["kind"]) == (
        "contact:18",
        "Founder, Loomly",
        "edited",
    )
    assert (ada["draft"], ada["final"], ada["note"]) == (ADA_DRAFT, ADA_FINAL, "less eager")
    assert {"op": "replace", "original": "impressive work", "replacement": "post"} in ada["hunks"]
    assert edits[47]["label"] is None
    assert (edits[58]["kind"], edits[58]["draft"], edits[58]["hunks"]) == ("scratch", None, [])
    assert (edits[60]["kind"], edits[60]["hunks"]) == ("untouched", [])


# --- learn apply ---------------------------------------------------------------------------


def apply(ws, reconcile, *options, expect=0):
    text = reconcile if isinstance(reconcile, str) else json.dumps(reconcile)
    return run("db", "learn", "apply", "--reconcile", text, *options, workspace=ws, expect=expect)


def test_learn_apply_with_the_reconcile_fixture(ws):
    run("db", "prefer", "--statement", "Never open with a compliment.", workspace=ws)
    run("db", "prefer", "--statement", "Never praise their work with adjectives.", workspace=ws)
    seed_edits(ws)
    v3 = latest_sha(ws)

    out = apply(ws, "@" + str(FIXTURES / "reconcile.json")).stdout
    lines = out.splitlines()
    edited = [
        (ADA_DRAFT, ADA_FINAL),
        ("Hey Sam, your impressive work on keys.", "Hey Sam, your keys."),
    ]
    edited.append(("Senior PM at Google, hi.", "Hi Chris."))
    mean = (
        sum(distance(a, b) for a, b in edited) / 4
    )  # the untouched edit counts, the past note not
    assert lines == [
        f"v3 -> v4 · 5 edits · mean distance {mean:.2f}",
        "retired    #2  No em dashes.  (contradicted by edits 41, 47, 52)",
        "new        #10 [active] Never open with the recipient's job title.  (evidence 3)",
        "new        #11 [candidate] Ask about a decision they made, not a topic.  (evidence 2)",
        "merged     #9 -> #6",
    ]

    p = prefs(ws)
    assert (p[6]["support_count"], p[6]["contradiction_count"]) == (2 + 2 + 3, 0)
    assert json.loads(p[6]["evidence_edit_ids"]) == [41, 47]
    assert (p[2]["status"], p[2]["contradiction_count"]) == ("retired", 3)
    assert json.loads(p[2]["evidence_edit_ids"]) == [41, 47, 52]
    assert (p[9]["status"], p[9]["retired_reason"]) == ("retired", "merged into #6")
    assert (p[10]["status"], p[10]["source"], p[10]["support_count"]) == ("active", "learned", 3)
    assert (p[11]["status"], p[11]["condition"], p[11]["support_count"]) == (
        "candidate",
        "the recipient is a founder",
        2,
    )

    conn = connect(ws)
    assert conn.execute("SELECT COUNT(*) FROM edits WHERE learned_at IS NULL").fetchone()[0] == 0
    learn_run = conn.execute("SELECT * FROM learn_runs").fetchone()
    assert learn_run["summary"] == out.rstrip("\n")
    assert (learn_run["edits_consumed"], learn_run["prefs_created"]) == (5, 2)
    assert (learn_run["prefs_activated"], learn_run["prefs_retired"]) == (1, 2)
    assert (learn_run["constitution_sha_from"], learn_run["constitution_sha_to"]) == (
        v3,
        latest_sha(ws),
    )
    v4 = conn.execute("SELECT * FROM constitutions WHERE version = 4").fetchone()
    assert (v4["parent_sha"], v4["learn_run_id"]) == (v3, learn_run["id"])
    text = (ws / "constitution.md").read_text()
    assert text == v4["text"] and text.startswith("# Constitution v4 ")
    assert "- No em dashes." not in text
    assert "- Never open with the recipient's job title." in text
    assert "## Examples\n> " in text
    assert "runs           1, last " in run("db", "status", workspace=ws).stdout


def test_learn_apply_validation_is_all_or_nothing(ws):
    seed_edits(ws)
    cases = [
        ({"existing": [{"id": 2, "support": [999]}]}, "edit 999 is not an unlearned edit"),
        ({"existing": [{"id": 77, "support": [41]}]}, "rule #77 does not exist"),
        ({"existing": [{"id": 2, "support": [60]}]}, "edit 60 is untouched"),
        ({"new": [{"statement": "X.", "evidence": [41, 60]}]}, "edit 60 is untouched"),
        ({"merge": [{"keep": 2, "retire": 77}]}, "rule #77 does not exist"),
        ("{not json", "not valid JSON"),
    ]
    for reconcile, message in cases:
        proc = apply(ws, reconcile, expect=1)
        assert message in proc.stderr, reconcile
    conn = connect(ws)
    assert conn.execute("SELECT COUNT(*) FROM edits WHERE learned_at IS NULL").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM learn_runs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM constitutions").fetchone()[0] == 1
    assert len(prefs(ws)) == 7 and prefs(ws)[2]["contradiction_count"] == 0


def test_retirement_is_evaluated_only_for_rules_active_before_the_run(ws):
    seed_edits(ws)
    conn = connect(ws)
    conn.execute(
        "INSERT INTO preferences (id, statement, source, status, support_count, created_at,"
        " updated_at) VALUES (8, 'Sign off with your name.', 'learned', 'candidate', 1, ?, ?)",
        (T, T),
    )
    conn.commit()
    out = apply(ws, {"existing": [{"id": 8, "support": [], "contradict": [41, 47]}]}).stdout
    row = prefs(ws)[8]
    assert (row["status"], row["support_count"], row["contradiction_count"]) == ("candidate", 1, 2)
    assert out.splitlines()[1:] == []


def test_a_retired_statement_returns_only_with_four_distinct_edits(ws):
    seed_edits(ws)
    conn = connect(ws)
    conn.execute("UPDATE preferences SET status = 'retired' WHERE id = 2")
    conn.commit()
    out = apply(ws, {"new": [{"statement": "no em dashes.", "evidence": [41, 47, 52, 52]}]}).stdout
    assert out.splitlines()[1:] == [] and len(prefs(ws)) == 7

    conn.execute("UPDATE edits SET learned_at = NULL")
    conn.commit()
    out = apply(ws, {"new": [{"statement": "no em dashes.", "evidence": [41, 47, 52, 58]}]}).stdout
    assert out.splitlines()[1] == "new        #8  [active] no em dashes.  (evidence 4, re-proposed)"
    assert prefs(ws)[2]["status"] == "retired" and prefs(ws)[8]["source"] == "learned"


def test_approve_mode_inserts_kept_rules_as_active_history(ws):
    run("db", "history", "--text", "Hey Chris — loved it.", "--text", "Hi Ada — hi.", workspace=ws)
    reconcile = {
        "existing": [{"id": 2, "support": [], "contradict": [1, 2]}],
        "new": [
            {"statement": "Mention a shared school when there is one.", "evidence": [1]},
            {"statement": "Close with a specific ask.", "condition": None, "evidence": [1, 2]},
        ],
    }
    out = apply(ws, reconcile, "--mode", "approve").stdout
    assert out.splitlines() == [
        "v1 -> v2 · 2 edits · mean distance n/a",
        "retired    #2  No em dashes.  (contradicted by edits 1, 2)",
        "new        #8  [active] Mention a shared school when there is one.  (evidence 1)",
        "new        #9  [active] Close with a specific ask.  (evidence 2)",
    ]
    p = prefs(ws)
    assert (p[8]["status"], p[8]["source"], p[8]["support_count"]) == ("active", "history", 2)
    assert (p[9]["status"], p[9]["source"], p[9]["support_count"]) == ("active", "history", 2)
    assert "- Close with a specific ask." in (ws / "constitution.md").read_text()


def test_unchanged_rules_keep_the_version_and_refresh_the_examples(ws):
    seed_edits(ws)
    assert "## Examples" not in (ws / "constitution.md").read_text()
    first = apply(ws, {}).stdout.splitlines()
    assert len(first) == 1 and first[0].startswith("v1 -> v1 · 5 edits · mean distance 0.")
    text = (ws / "constitution.md").read_text()
    assert text.startswith("# Constitution v1 ") and "## Examples\n> " in text
    second = apply(ws, {}).stdout.splitlines()
    assert second == ["v1 -> v1 · 0 edits · mean distance n/a"]
    conn = connect(ws)
    assert conn.execute("SELECT COUNT(*) FROM constitutions").fetchone()[0] == 1
    assert "## Examples" not in conn.execute("SELECT text FROM constitutions").fetchone()[0]
    runs = conn.execute(
        "SELECT constitution_sha_from, constitution_sha_to FROM learn_runs"
    ).fetchall()
    assert runs[1][0] == runs[1][1] == runs[0][1] == latest_sha(ws)


# --- status --------------------------------------------------------------------------------


def test_status_report_and_chart(ws):
    seed_edits(ws)
    out = run("db", "status", "--chart", workspace=ws).stdout.splitlines()
    assert out[0] == "pipeline       captured 0 · drafted 0 · approved 1 · sent 0"
    assert out[1] == "sent this week 0"
    assert out[2] == "constitution   v1 · 7 rules · 0 candidates"
    assert out[3] == "unlearned      5 edits"
    assert out[4].startswith("curve          v1 0.") and out[4].endswith(" (4)")
    assert out[5] == "runs           0"
    svg = (ws / "learning-curve.svg").read_text()
    assert svg.startswith("<svg") and ">v1</text>" in svg


def test_status_on_a_fresh_workspace(ws):
    out = run("db", "status", workspace=ws).stdout.splitlines()
    assert out[4] == "curve          none" and out[5] == "runs           0"
    assert not (ws / "learning-curve.svg").exists()
