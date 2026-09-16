"""queue.py at the script boundary: run the command, check the database, stdout and queue.md."""

import json
import os
import stat

from conftest import FIXTURES, connect, run

from diff import distance

CHRIS = FIXTURES / "profiles" / "chris-doe.json"
ADA = FIXTURES / "profiles" / "minimal.json"
QUEUE = FIXTURES / "queue.md"
T = "2026-09-14T20:28:00Z"


def capture(ws, url, profile=CHRIS):
    return run("queue", "capture", "--url", url, "--profile", "@" + str(profile), workspace=ws)


def add(ws, contact_id, text):
    return run("queue", "add", "--contact", str(contact_id), "--text", text, workspace=ws)


def review(ws, contact_id, final, note="", expect=0):
    args = ["--contact", str(contact_id), "--final", final, "--note", note]
    return run("queue", "review", *args, workspace=ws, expect=expect)


def status(ws, contact_id):
    row = connect(ws).execute("SELECT status FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    return row[0]


def fixture_drafts():
    """The three draft texts in tests/fixtures/queue.md, by contact id."""
    drafts = {}
    for block in QUEUE.read_text().split("\n## [")[1:]:
        contact_id = int(block.split("]")[0])
        drafts[contact_id] = block.split("chars\n", 1)[1].split("\n\n### FINAL")[0]
    return drafts


def load_fixture_queue(ws):
    """Contacts 17, 18, 19 with the fixture's drafts, and the fixture as queue.md."""
    conn = connect(ws)
    people = [(17, "Chris Doe", "Senior PM, Google"), (18, "Ada Nguyen", "Founder, Loomly")]
    people.append((19, "Sam Okafor", "Staff Engineer, Stripe"))
    for contact_id, name, headline in people:
        slug = name.lower().replace(" ", "")
        conn.execute(
            "INSERT INTO contacts (id, linkedin_url, name, headline, profile_json, captured_at,"
            " updated_at) VALUES (?, ?, ?, ?, '{}', ?, ?)",
            (contact_id, f"https://linkedin.com/in/{slug}", name, headline, T, T),
        )
    conn.commit()
    for contact_id, text in fixture_drafts().items():
        add(ws, contact_id, text)
    assert skeleton((ws / "queue.md").read_text()) == skeleton(QUEUE.read_text())
    (ws / "queue.md").write_text(QUEUE.read_text())


def skeleton(text):
    """The lines the script renders and the user does not edit."""
    return [ln for ln in text.splitlines() if ln.startswith(("## [", "<https", "### draft"))]


# --- capture -------------------------------------------------------------------------------


def test_capture_normalizes_the_url_and_dedupes(ws):
    out = capture(ws, "HTTP://www.LinkedIn.com/in/ChrisDoe/?trk=x#top").stdout
    assert out.strip() == "#1 captured Chris Doe"
    row = connect(ws).execute("SELECT * FROM contacts").fetchone()
    assert row["linkedin_url"] == "https://linkedin.com/in/chrisdoe"
    assert (row["headline"], row["company"], row["title"], row["status"]) == (
        "Senior PM, Google",
        "Google",
        "Senior Product Manager",
        "queued",
    )
    assert json.loads(row["profile_json"])["posts"][0]["id"] == "7f3a1c"

    assert capture(ws, "linkedin.com/in/chrisdoe").stdout.strip() == "#1 exists Chris Doe"
    exists = capture(ws, "https://www.linkedin.com/in/chrisdoe/").stdout.strip()
    assert exists == "#1 exists Chris Doe"
    assert connect(ws).execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 1


def test_capture_without_a_name_is_exit_1(ws):
    args = ["--url", "https://linkedin.com/in/x", "--profile"]
    proc = run("queue", "capture", *args, '{"headline": "x"}', workspace=ws, expect=1)
    assert proc.stderr.strip() == "profile has no name"
    proc = run("queue", "capture", *args, "{oops", workspace=ws, expect=1)
    assert proc.stderr.startswith("profile is not valid JSON")
    assert connect(ws).execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0


# --- draft, add, render --------------------------------------------------------------------


def test_draft_targets_exclude_reviewed_and_sent(ws):
    out = json.loads(run("queue", "draft", workspace=ws).stdout)
    assert (out["targets"], out["exemplars"], out["profile"], out["corrections"]) == (
        [],
        [],
        None,
        None,
    )
    assert out["constitution"]["version"] == 1

    capture(ws, "https://linkedin.com/in/chrisdoe")
    capture(ws, "https://linkedin.com/in/adanguyen", ADA)
    capture(ws, "https://linkedin.com/in/samokafor", ADA)
    add(ws, 1, "Hey Chris.")
    review(ws, 1, "Hey Chris!", "warmer")
    add(ws, 2, "Hi Ada.")
    (ws / "me" / "_profile.md").write_text("Cornell, PM roles.")

    out = json.loads(run("queue", "draft", workspace=ws).stdout)
    assert [t["contact_id"] for t in out["targets"]] == [
        2,
        3,
    ]  # 2 drafted but unreviewed, 3 never drafted
    assert out["targets"][0]["url"] == "https://linkedin.com/in/adanguyen"
    assert out["targets"][0]["profile"] == json.loads(ADA.read_text())
    assert out["profile"] == "Cornell, PM roles."
    assert out["exemplars"] == [{"draft": "Hey Chris.", "final": "Hey Chris!", "note": "warmer"}]

    run("queue", "sent", "--contact", "1", workspace=ws)
    out = json.loads(run("queue", "draft", workspace=ws).stdout)
    assert [t["contact_id"] for t in out["targets"]] == [2, 3]

    out = json.loads(run("queue", "draft", "--redraft", "2", workspace=ws).stdout)
    assert [t["contact_id"] for t in out["targets"]] == [2]
    proc = run("queue", "draft", "--redraft", "1", workspace=ws, expect=1)
    assert proc.stderr.strip() == "#1 already reviewed"
    proc = run("queue", "draft", "--redraft", "99", workspace=ws, expect=1)
    assert proc.stderr.strip() == "no contact #99"


def test_draft_exemplars_are_the_five_newest_first(ws):
    texts = [f"past note {i}" for i in range(1, 8)]
    run("db", "history", *[a for t in texts for a in ("--text", t)], workspace=ws)
    out = json.loads(run("queue", "draft", workspace=ws).stdout)
    assert [e["final"] for e in out["exemplars"]] == texts[:1:-1]
    assert out["exemplars"][0]["draft"] is None


def test_add_renders_the_queue_in_the_contract_format(ws):
    capture(ws, "https://linkedin.com/in/chrisdoe")
    capture(ws, "https://linkedin.com/in/adanguyen", ADA)
    assert add(ws, 1, "Hey Chris, hit home.").stdout.strip() == "#1 draft for #1 · 20 chars"
    assert add(ws, 2, "Hi Ada.").stdout.strip() == "#2 draft for #2 · 7 chars"
    assert (ws / "queue.md").read_text() == (
        "# Queue · constitution v1 · 2 waiting\n"
        "\n## [1] Chris Doe — Senior PM, Google\n<https://linkedin.com/in/chrisdoe>\n"
        "\n### draft · 20 chars\nHey Chris, hit home.\n\n### FINAL\n\n### note\n"
        "\n## [2] Ada Nguyen\n<https://linkedin.com/in/adanguyen>\n"
        "\n### draft · 7 chars\nHi Ada.\n\n### FINAL\n\n### note\n"
    )
    assert status(ws, 1) == "drafted"
    row = connect(ws).execute("SELECT * FROM drafts WHERE id = 1").fetchone()
    assert (row["context_ref"], row["contact_id"], row["sources_json"]) == ("contact:1", 1, "[]")

    add(ws, 2, "Hi Ada, again.")
    assert "Hi Ada." not in (ws / "queue.md").read_text()
    proc = run("queue", "add", "--contact", "99", "--text", "x", workspace=ws, expect=1)
    assert proc.stderr.strip() == "no contact #99"


def test_add_stores_sources(ws):
    capture(ws, "https://linkedin.com/in/chrisdoe")
    run(
        "queue",
        "add",
        "--contact",
        "1",
        "--text",
        "x",
        "--sources",
        '["post 7f3a1c"]',
        workspace=ws,
    )
    row = connect(ws).execute("SELECT sources_json FROM drafts").fetchone()
    assert json.loads(row[0]) == ["post 7f3a1c"]


def test_render_empty_queue(ws):
    assert run("queue", "render", workspace=ws).stdout.strip() == "queue.md · 0 waiting"
    assert (ws / "queue.md").read_text() == "# Queue · constitution v1 · 0 waiting\n"


# --- discard -------------------------------------------------------------------------------


def test_discard_removes_unreviewed_drafts_and_keeps_reviewed_ones(ws):
    capture(ws, "https://linkedin.com/in/chrisdoe")
    capture(ws, "https://linkedin.com/in/adanguyen", ADA)
    capture(ws, "https://linkedin.com/in/samokafor", ADA)
    add(ws, 1, "Hey Chris.")
    review(ws, 1, "ok")
    add(ws, 2, "Hi Ada.")
    add(ws, 2, "Hi Ada, again.")

    out = run("queue", "discard", "--contact", "2", workspace=ws).stdout
    assert out.strip() == "#2 discarded 2 drafts"
    conn = connect(ws)
    assert conn.execute("SELECT COUNT(*) FROM drafts WHERE contact_id = 2").fetchone()[0] == 0
    assert status(ws, 2) == "queued"
    assert (ws / "queue.md").read_text() == "# Queue · constitution v1 · 0 waiting\n"
    assert run("queue", "discard", "--contact", "3", workspace=ws).stdout.strip() == (
        "#3 discarded 0 drafts"
    )

    proc = run("queue", "discard", "--contact", "1", workspace=ws, expect=1)
    assert proc.stderr.strip() == "#1 already reviewed"
    assert conn.execute("SELECT COUNT(*) FROM drafts WHERE contact_id = 1").fetchone()[0] == 1
    assert status(ws, 1) == "approved"
    proc = run("queue", "discard", "--contact", "99", workspace=ws, expect=1)
    assert proc.stderr.strip() == "no contact #99"

    out = json.loads(run("queue", "draft", workspace=ws).stdout)
    assert [t["contact_id"] for t in out["targets"]] == [2, 3]


def test_discard_all_leaves_reviewed_contacts_alone(ws):
    load_fixture_queue(ws)
    review(ws, 17, "ok")
    out = run("queue", "discard", "--all", workspace=ws).stdout.splitlines()
    assert out == ["#18 discarded 1 drafts", "#19 discarded 1 drafts"]
    conn = connect(ws)
    assert [r[0] for r in conn.execute("SELECT contact_id FROM drafts")] == [17]
    assert [status(ws, c) for c in (17, 18, 19)] == ["approved", "queued", "queued"]
    assert (ws / "queue.md").read_text() == "# Queue · constitution v1 · 0 waiting\n"
    assert run("queue", "discard", "--all", workspace=ws).stdout == ""


# --- review --------------------------------------------------------------------------------


def test_review_of_the_fixture_queue(ws):
    load_fixture_queue(ws)
    drafts = fixture_drafts()
    ada_final = (
        "Hi Ada, your post on Loomly's pricing reset stood out. I'm at Cornell studying how early"
        " teams price. How did you pick the moment to change it?"
    )
    d = distance(drafts[18], ada_final)
    out = run("queue", "review", workspace=ws).stdout.splitlines()
    assert out == ["#17 ok", f"#18 edited · distance {d:.2f}", "#19 untouched", "unlearned 2 edits"]

    conn = connect(ws)
    edits = {r["contact_id"]: r for r in conn.execute("SELECT * FROM edits")}
    assert sorted(edits) == [17, 18]
    assert (edits[17]["final_text"], edits[17]["edit_distance"], edits[17]["reason_text"]) == (
        drafts[17],
        0.0,
        None,
    )
    assert (edits[18]["final_text"], edits[18]["edit_distance"]) == (ada_final, d)
    assert edits[18]["reason_text"] == "less eager\nwrong: I'm at Cornell, not Columbia"
    assert (
        edits[18]["draft_id"]
        == conn.execute("SELECT id FROM drafts WHERE contact_id = 18").fetchone()[0]
    )
    assert (ws / "me" / "corrections.md").read_text() == "- I'm at Cornell, not Columbia\n"
    assert [status(ws, c) for c in (17, 18, 19)] == ["approved", "approved", "drafted"]
    queue = (ws / "queue.md").read_text()
    assert queue.startswith("# Queue · constitution v1 · 1 waiting\n\n## [19] Sam Okafor")


def test_review_skips_ids_not_in_the_queue(ws):
    load_fixture_queue(ws)
    path = ws / "queue.md"
    path.write_text(path.read_text() + "\n## [99] Nobody\n\n### FINAL\nok\n")
    proc = run("queue", "review", workspace=ws)
    assert proc.stderr.strip() == "#99 not in queue"
    assert proc.stdout.splitlines()[0] == "#17 ok"


def test_review_one_contact_goes_through_the_same_path(ws):
    load_fixture_queue(ws)
    assert review(ws, 19, "OK", "fine").stdout.splitlines() == ["#19 ok", "unlearned 1 edits"]
    row = connect(ws).execute("SELECT * FROM edits WHERE contact_id = 19").fetchone()
    assert (row["edit_distance"], row["reason_text"]) == (0.0, "fine")
    assert review(ws, 17, "").stdout.splitlines()[0] == "#17 untouched"
    proc = review(ws, 19, "ok", expect=1)
    assert proc.stderr.strip() == "#19 not in queue"
    assert "## [17]" in (ws / "queue.md").read_text()


def test_review_without_a_queue_file_is_exit_1(ws):
    proc = run("queue", "review", workspace=ws, expect=1)
    assert proc.stderr.strip() == "no queue.md (run /coldwriter:draft)"


# --- send, sent ----------------------------------------------------------------------------


def fake_bin(tmp_path):
    """pbcopy and open stand-ins that record what they were given."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    scripts = (("pbcopy", f"/bin/cat > {bin_dir}/clip"), ("open", f'echo "$1" > {bin_dir}/opened'))
    for name, script in scripts:
        path = bin_dir / name
        path.write_text(f"#!/bin/sh\n{script}\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return bin_dir


def test_open_lists_approved_contacts_and_copies_the_note(ws, tmp_path):
    capture(ws, "https://linkedin.com/in/chrisdoe")
    capture(ws, "https://linkedin.com/in/adanguyen", ADA)
    add(ws, 1, "Hey Chris, hit home.")
    add(ws, 2, "Hi Ada.")
    review(ws, 2, "ok")
    review(ws, 1, "ok")
    assert run("queue", "open", workspace=ws).stdout.splitlines() == [
        "sent this week 0",
        "#1 Chris Doe · https://linkedin.com/in/chrisdoe",
        "#2 Ada Nguyen · https://linkedin.com/in/adanguyen",
    ]

    bin_dir = fake_bin(tmp_path)
    env = dict(os.environ, PATH=str(bin_dir))
    out = run("queue", "open", "--contact", "1", workspace=ws, env=env).stdout
    assert out == "Hey Chris, hit home.\n20 chars\n"
    assert (bin_dir / "clip").read_text() == "Hey Chris, hit home."
    assert (bin_dir / "opened").read_text() == "https://linkedin.com/in/chrisdoe\n"

    env = dict(os.environ, PATH=str(tmp_path / "empty"))
    out = run("queue", "open", "--contact", "1", workspace=ws, env=env).stdout
    url = "https://linkedin.com/in/chrisdoe"
    assert out == f"clipboard unavailable\n{url}\nHey Chris, hit home.\n20 chars\n"
    proc = run("queue", "open", "--contact", "99", workspace=ws, env=env, expect=1)
    assert proc.stderr.strip() == "no contact #99"


def test_sent_records_the_send_and_edited_writes_back(ws):
    capture(ws, "https://linkedin.com/in/chrisdoe")
    capture(ws, "https://linkedin.com/in/adanguyen", ADA)
    add(ws, 1, "Hey Chris, hit home.")
    add(ws, 2, "Hi Ada.")
    review(ws, 1, "ok")
    review(ws, 2, "ok")
    run("db", "learn", "apply", "--reconcile", "{}", workspace=ws)

    assert (
        run("queue", "sent", "--contact", "1", workspace=ws).stdout.strip() == "#1 sent · 20 chars"
    )
    conn = connect(ws)
    assert status(ws, 1) == "sent"
    assert conn.execute("SELECT edit_id FROM sends WHERE contact_id = 1").fetchone()[0] == 1
    assert conn.execute("SELECT learned_at FROM edits WHERE id = 1").fetchone()[0] is not None

    out = run("queue", "sent", "--contact", "2", "--edited", "Hi Ada, hello.", workspace=ws).stdout
    assert out.strip() == "#2 sent · 14 chars"
    row = conn.execute("SELECT * FROM edits WHERE contact_id = 2").fetchone()
    assert (row["final_text"], row["edit_distance"], row["learned_at"]) == (
        "Hi Ada, hello.",
        distance("Hi Ada.", "Hi Ada, hello."),
        None,
    )
    assert status(ws, 2) == "sent"

    proc = run("queue", "sent", "--contact", "1", workspace=ws, expect=1)
    assert proc.stderr.strip() == "#1 is sent, not approved"
    assert run("queue", "open", workspace=ws).stdout == "sent this week 2\n"


def test_unapprove_puts_the_draft_back_in_the_queue(ws):
    load_fixture_queue(ws)
    review(ws, 17, "Hey Chris, rewritten.", "too eager")
    review(ws, 18, "ok")
    run("queue", "sent", "--contact", "18", workspace=ws)

    out = run("queue", "unapprove", "--contact", "17", workspace=ws).stdout
    assert out.strip() == "#17 unapproved"
    conn = connect(ws)
    assert conn.execute("SELECT COUNT(*) FROM edits WHERE contact_id = 17").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM drafts WHERE contact_id = 17").fetchone()[0] == 1
    assert status(ws, 17) == "drafted"
    heads = [ln for ln in (ws / "queue.md").read_text().splitlines() if ln.startswith("## [")]
    assert [h.split("]")[0] for h in heads] == ["## [17", "## [19"]
    assert run("queue", "open", workspace=ws).stdout == "sent this week 1\n"
    review(ws, 17, "ok")
    assert status(ws, 17) == "approved"

    proc = run("queue", "unapprove", "--contact", "18", workspace=ws, expect=1)
    assert proc.stderr.strip() == "#18 is sent, not approved"
    proc = run("queue", "unapprove", "--contact", "19", workspace=ws, expect=1)
    assert proc.stderr.strip() == "#19 is drafted, not approved"

    review(ws, 19, "ok")
    run("db", "learn", "apply", "--reconcile", "{}", workspace=ws)
    proc = run("queue", "unapprove", "--contact", "19", workspace=ws, expect=1)
    assert proc.stderr.strip() == "#19 already learned"
    assert status(ws, 19) == "approved"
