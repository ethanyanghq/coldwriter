"""The golden path with no model and no LinkedIn: init, capture, add, review, learn, status."""

import json

from conftest import FIXTURES, connect, run


def test_golden_path(tmp_path):
    ws = tmp_path / "ws"
    run("db", "init", workspace=ws)
    for slug, profile in (("chrisdoe", "chris-doe.json"), ("adanguyen", "minimal.json")):
        url = f"https://linkedin.com/in/{slug}"
        path = str(FIXTURES / "profiles" / profile)
        run("queue", "capture", "--url", url, "--profile", "@" + path, workspace=ws)

    targets = json.loads(run("queue", "draft", workspace=ws).stdout)["targets"]
    assert [t["name"] for t in targets] == ["Chris Doe", "Ada Nguyen"]
    run(
        "queue",
        "add",
        "--contact",
        "1",
        "--text",
        "Hey Chris, your ticket-queue post hit home.",
        workspace=ws,
    )
    run(
        "queue",
        "add",
        "--contact",
        "2",
        "--text",
        "Hi Ada, your impressive work stood out.",
        workspace=ws,
    )

    queue = (ws / "queue.md").read_text()
    assert queue.startswith("# Queue · constitution v1 · 2 waiting\n")
    queue = queue.replace("### FINAL\n", "### FINAL\nok\n", 1)
    queue = queue.replace(
        "### FINAL\n\n### note\n",
        "### FINAL\nHi Ada, your work stood out.\n\n### note\nless eager\n",
    )
    (ws / "queue.md").write_text(queue)
    out = run("queue", "review", workspace=ws).stdout.splitlines()
    assert out[0] == "#1 ok" and out[1].startswith("#2 edited · distance 0.")
    assert (ws / "queue.md").read_text() == "# Queue · constitution v1 · 0 waiting\n"

    emitted = json.loads(run("db", "learn", "emit", workspace=ws).stdout)
    assert [(e["id"], e["kind"], e["label"]) for e in emitted["edits"]] == [
        (1, "untouched", "Senior PM, Google"),
        (2, "edited", None),
    ]
    reconcile = {"existing": [{"id": 6, "support": [2], "contradict": []}]}
    out = run("db", "learn", "apply", "--reconcile", json.dumps(reconcile), workspace=ws).stdout
    assert out.startswith("v1 -> v2 · 2 edits · mean distance 0.")
    assert (
        connect(ws).execute("SELECT support_count FROM preferences WHERE id = 6").fetchone()[0] == 3
    )

    run("queue", "sent", "--contact", "1", workspace=ws)
    out = run("db", "status", workspace=ws).stdout.splitlines()
    assert out[0] == "pipeline       queued 0 · drafted 0 · approved 1 · sent 1"
    assert out[1] == "sent this week 1"
    assert out[2].startswith("constitution   v2 ") and out[2].endswith("· 7 rules · 0 candidates")
    assert out[3] == "unlearned      0 edits"
    assert out[4].startswith("curve          v1 0.") and out[4].endswith(" (2)")
    assert out[5].startswith("runs           1, last ")
