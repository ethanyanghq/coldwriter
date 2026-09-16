#!/usr/bin/env python3
"""Workspace and learn core: init, history, prefer, learn emit, learn apply, status.

Knows nothing about LinkedIn or contacts. A context is (domain, context_ref); the
one consumer-defined thing read here is the v_context_labels view.
"""

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from diff import hunks
from render import parse_constitution, render_constitution

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


# --- shared helpers ------------------------------------------------------------------------


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha16(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def read_arg(value):
    """A text option: the literal value, @path for a file, - for stdin."""
    if value == "-":
        return sys.stdin.read()
    if value.startswith("@"):
        return Path(value[1:]).read_text(encoding="utf-8")
    return value


def fail(message, code=1):
    sys.stderr.write(message + "\n")
    sys.exit(code)


def load_json(text, what):
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        fail(f"{what} is not valid JSON: {e}")


def connect(workspace, create=False):
    """The workspace database. Without create, a missing one is exit 2."""
    path = Path(workspace) / "db" / "outreach.sqlite"
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.exists():
        fail(f"not a Coldwriter workspace: {workspace} (run /coldwriter:init)", 2)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def latest_constitution(conn, domain):
    return conn.execute(
        "SELECT * FROM constitutions WHERE domain = ? ORDER BY version DESC LIMIT 1", (domain,)
    ).fetchone()


def rule(conn, pref_id):
    return conn.execute("SELECT * FROM preferences WHERE id = ?", (pref_id,)).fetchone()


def find_rule(conn, domain, statement):
    """The rule with this statement, ignoring case and a trailing period, any status; live first."""
    return conn.execute(
        "SELECT * FROM preferences WHERE domain = ?"
        " AND lower(rtrim(statement, '.!')) = lower(rtrim(?, '.!'))"
        " ORDER BY status = 'retired', id",
        (domain, statement),
    ).fetchone()


def insert_rule(conn, domain, statement, condition, source, status, support, evidence=()):
    ts = now()
    cur = conn.execute(
        "INSERT INTO preferences (domain, statement, condition, source, status, support_count,"
        " evidence_edit_ids, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (domain, statement, condition, source, status, support, json.dumps(list(evidence)), ts, ts),
    )
    return cur.lastrowid


def retire_rule(conn, pref_id, reason, ts):
    conn.execute(
        "UPDATE preferences SET status = 'retired', retired_reason = ?, updated_at = ?"
        " WHERE id = ?",
        (reason, ts, pref_id),
    )


# --- constitution --------------------------------------------------------------------------


def header(text):
    """The first line, which carries the version and date."""
    return text.split("\n", 1)[0]


def body(text):
    """Everything below the header line."""
    return text.split("\n", 1)[1]


def rules_part(text):
    """The body up to Examples: what a new version is about."""
    return body(text).split("\n## Examples", 1)[0]


def render_preview(conn, domain):
    """(text, version, changed): the next render, or the latest version with fresh Examples
    when the rules are the same."""
    latest = latest_constitution(conn, domain)
    rules = conn.execute(
        "SELECT statement, condition FROM preferences"
        " WHERE domain = ? AND status = 'active' ORDER BY id",
        (domain,),
    ).fetchall()
    examples = conn.execute(
        "SELECT final_text FROM edits WHERE domain = ? ORDER BY reviewed_at DESC, id DESC LIMIT 2",
        (domain,),
    ).fetchall()
    version = latest["version"] + 1 if latest else 1
    text = render_constitution(
        [tuple(r) for r in rules], [e[0] for e in examples], version, now()[:10]
    )
    if latest and rules_part(text) == rules_part(latest["text"]):
        return header(latest["text"]) + "\n" + body(text), latest["version"], False
    return text, version, True


def render_and_record(conn, workspace, domain):
    """Write constitution.md; insert a constitutions row only when the rules changed."""
    text, version, changed = render_preview(conn, domain)
    latest = latest_constitution(conn, domain)
    sha = sha16(text) if changed else latest["sha"]
    if changed:
        conn.execute(
            "INSERT INTO constitutions (sha, domain, version, text, parent_sha, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (sha, domain, version, text, latest["sha"] if latest else None, now()),
        )
    (Path(workspace) / "constitution.md").write_text(text, encoding="utf-8")
    return version, sha, changed


# --- init, history, prefer -----------------------------------------------------------------


def parse_seeds(text):
    return [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]


def init(workspace, from_path, domain):
    (Path(workspace) / "me").mkdir(parents=True, exist_ok=True)
    conn = connect(workspace, create=True)
    conn.executescript((PLUGIN_ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    shutil.copyfile(
        PLUGIN_ROOT / "templates" / "workspace-CLAUDE.md", Path(workspace) / "CLAUDE.md"
    )

    seeds = parse_seeds((PLUGIN_ROOT / "seeds.yaml").read_text(encoding="utf-8"))
    rules = [(statement, None, "seed") for statement in seeds]
    if from_path:
        imported = parse_constitution(Path(from_path).read_text(encoding="utf-8"))
        rules += [(statement, condition, "imported") for statement, condition in imported]
    for statement, condition, source in rules:
        if not find_rule(conn, domain, statement):
            insert_rule(conn, domain, statement, condition, source, "active", 2)

    version, sha, _ = render_and_record(conn, workspace, domain)
    conn.commit()
    active = conn.execute(
        "SELECT COUNT(*) FROM preferences WHERE domain = ? AND status = 'active'", (domain,)
    ).fetchone()[0]
    print(f"workspace {workspace}")
    print(f"preferences {active} active")
    print(f"constitution v{version} {sha}")


def history(conn, domain, texts):
    """Each text becomes a from-scratch edit, past:<n> numbered after the highest existing."""
    sha = latest_constitution(conn, domain)["sha"]
    highest = conn.execute(
        "SELECT MAX(CAST(substr(context_ref, 6) AS INTEGER)) FROM edits"
        " WHERE domain = ? AND context_ref LIKE 'past:%'",
        (domain,),
    ).fetchone()[0]
    n = highest or 0
    for text in texts:
        n += 1
        cur = conn.execute(
            "INSERT INTO edits (domain, context_ref, final_text, edit_distance, constitution_sha,"
            " reviewed_at) VALUES (?, ?, ?, 1.0, ?, ?)",
            (domain, f"past:{n}", text, sha, now()),
        )
        print(f"#{cur.lastrowid} past:{n}")
    conn.commit()


def prefer(conn, workspace, domain, statement, condition):
    existing = find_rule(conn, domain, statement)
    if existing:
        fail(f"duplicate of #{existing['id']} ({existing['status']})")
    pref_id = insert_rule(conn, domain, statement, condition, "manual", "active", 3)
    version, sha, _ = render_and_record(conn, workspace, domain)
    conn.commit()
    print(f"#{pref_id} active")
    print(f"constitution v{version} {sha}")


# --- learn ---------------------------------------------------------------------------------


def unlearned(conn, domain):
    return conn.execute(
        "SELECT u.*, l.label FROM v_unlearned u"
        " LEFT JOIN v_context_labels l ON l.domain = u.domain AND l.context_ref = u.context_ref"
        " WHERE u.domain = ? ORDER BY u.id",
        (domain,),
    ).fetchall()


def kind_of(edit):
    if edit["draft_id"] is None:
        return "scratch"
    if edit["edit_distance"] == 0:
        return "untouched"
    return "edited"


def emit_edit(edit):
    kind = kind_of(edit)
    return {
        "id": edit["id"],
        "context_ref": edit["context_ref"],
        "label": edit["label"],
        "kind": kind,
        "draft": edit["draft_text"],
        "final": edit["final_text"],
        "note": edit["reason_text"],
        "hunks": hunks(edit["draft_text"], edit["final_text"]) if kind == "edited" else [],
    }


def learn_emit(conn, domain):
    edits = unlearned(conn, domain)
    if not edits:
        print('{"edits": []}')
        return
    latest = latest_constitution(conn, domain)
    preferences = conn.execute(
        "SELECT id, statement, condition, status, source, support_count, contradiction_count"
        " FROM preferences WHERE domain = ? AND status != 'retired' ORDER BY id",
        (domain,),
    ).fetchall()
    retired = conn.execute(
        "SELECT statement FROM preferences WHERE domain = ? AND status = 'retired' ORDER BY id",
        (domain,),
    ).fetchall()
    out = {
        "domain": domain,
        "constitution": {
            "version": latest["version"],
            "sha": latest["sha"],
            "text": latest["text"],
        },
        "preferences": [dict(p) for p in preferences],
        "retired": [r[0] for r in retired],
        "edits": [emit_edit(e) for e in edits],
    }
    print(json.dumps(out, indent=2))


def validate(conn, domain, reconcile, batch):
    """Exit 1 on the first bad id. Runs before any write, so a failure writes nothing."""
    kinds = {e["id"]: kind_of(e) for e in batch}
    live = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM preferences WHERE domain = ? AND status != 'retired'", (domain,)
        )
    }
    edit_refs = [
        (f"existing #{i.get('id')}", i.get("support") or []) for i in reconcile["existing"]
    ]
    edit_refs += [
        (f"existing #{i.get('id')}", i.get("contradict") or []) for i in reconcile["existing"]
    ]
    edit_refs += [("new", i.get("evidence") or []) for i in reconcile["new"]]
    for where, ids in edit_refs:
        for edit_id in ids:
            if edit_id not in kinds:
                fail(f"{where}: edit {edit_id} is not an unlearned edit")
            if kinds[edit_id] == "untouched":
                fail(f"{where}: edit {edit_id} is untouched and cannot be evidence")
    rule_refs = [i.get("id") for i in reconcile["existing"]]
    rule_refs += [i.get("keep") for i in reconcile["merge"]]
    rule_refs += [i.get("retire") for i in reconcile["merge"]]
    for pref_id in rule_refs:
        if pref_id not in live:
            fail(f"rule #{pref_id} does not exist or is retired")


def add_counts(conn, pref_id, support, contradict, ts):
    evidence = json.loads(rule(conn, pref_id)["evidence_edit_ids"]) + support + contradict
    conn.execute(
        "UPDATE preferences SET support_count = support_count + ?,"
        " contradiction_count = contradiction_count + ?, evidence_edit_ids = ?, updated_at = ?"
        " WHERE id = ?",
        (len(support), len(contradict), json.dumps(evidence), ts, pref_id),
    )


def add_rule(conn, domain, item, mode):
    """Insert a proposed rule unless its statement exists. Returns (id, re_proposed) or None."""
    statement = item["statement"].strip()
    evidence = item.get("evidence") or []
    match = find_rule(conn, domain, statement)
    if match and (match["status"] != "retired" or len(set(evidence)) < 4):
        return None
    if mode == "approve":
        pref_id = insert_rule(
            conn,
            domain,
            statement,
            item.get("condition"),
            "history",
            "active",
            max(2, len(evidence)),
            evidence,
        )
    else:
        pref_id = insert_rule(
            conn,
            domain,
            statement,
            item.get("condition"),
            "learned",
            "candidate",
            len(evidence),
            evidence,
        )
    return pref_id, match is not None


def activate_candidates(conn, domain, ts):
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM preferences WHERE domain = ? AND status = 'candidate'"
            " AND support_count >= 3 AND support_count > 2 * contradiction_count",
            (domain,),
        )
    ]
    for pref_id in ids:
        conn.execute(
            "UPDATE preferences SET status = 'active', updated_at = ? WHERE id = ?", (ts, pref_id)
        )
    return ids


def retire_contradicted(conn, domain, active_before, contradicted, ts):
    """Anti-churn: only rules that were active before this run can retire in it."""
    rows = conn.execute(
        "SELECT id FROM preferences WHERE domain = ? AND status = 'active'"
        " AND contradiction_count >= support_count",
        (domain,),
    )
    ids = [r["id"] for r in rows if r["id"] in active_before]
    for pref_id in ids:
        edits = ", ".join(str(e) for e in contradicted.get(pref_id, []))
        retire_rule(conn, pref_id, f"contradicted by edits {edits}", ts)
    return ids


def merge_rules(conn, keep, retire, ts):
    support = rule(conn, retire)["support_count"]
    retire_rule(conn, retire, f"merged into #{keep}", ts)
    conn.execute(
        "UPDATE preferences SET support_count = support_count + ?, updated_at = ? WHERE id = ?",
        (support, ts, keep),
    )


def changelog(conn, before, version, batch, activated, retired, created, merged):
    distances = [e["edit_distance"] for e in batch if e["draft_id"] is not None]
    mean = f"{sum(distances) / len(distances):.2f}" if distances else "n/a"
    lines = [f"v{before['version']} -> v{version} · {len(batch)} edits · mean distance {mean}"]
    new_ids = {pref_id for pref_id, _ in created}
    for pref_id in activated:
        if pref_id not in new_ids:
            r = rule(conn, pref_id)
            lines.append(
                f"activated  {tag(pref_id)} {r['statement']}  (support {r['support_count']})"
            )
    for pref_id in retired:
        r = rule(conn, pref_id)
        lines.append(f"retired    {tag(pref_id)} {r['statement']}  ({r['retired_reason']})")
    for pref_id, re_proposed in created:
        r = rule(conn, pref_id)
        evidence = f"evidence {len(json.loads(r['evidence_edit_ids']))}"
        if re_proposed:
            evidence += ", re-proposed"
        lines.append(f"new        {tag(pref_id)} [{r['status']}] {r['statement']}  ({evidence})")
    for retire, keep in merged:
        lines.append(f"merged     #{retire} -> #{keep}")
    return "\n".join(lines)


def tag(pref_id):
    return f"#{pref_id}".ljust(3)


def learn_apply(conn, workspace, domain, reconcile, mode):
    """Stage C: the contract's seven steps, in order, over the currently unlearned edits."""
    reconcile = {key: reconcile.get(key) or [] for key in ("existing", "new", "merge")}
    batch = unlearned(conn, domain)
    validate(conn, domain, reconcile, batch)
    before = latest_constitution(conn, domain)
    active_before = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM preferences WHERE domain = ? AND status = 'active'", (domain,)
        )
    }
    ts = now()

    contradicted = {}
    for item in reconcile["existing"]:
        support, contradict = item.get("support") or [], item.get("contradict") or []
        add_counts(conn, item["id"], support, contradict, ts)
        contradicted[item["id"]] = contradict
    created = [c for c in (add_rule(conn, domain, item, mode) for item in reconcile["new"]) if c]
    activated = activate_candidates(conn, domain, ts)
    retired = retire_contradicted(conn, domain, active_before, contradicted, ts)
    merged = [(item["retire"], item["keep"]) for item in reconcile["merge"]]
    for retire, keep in merged:
        merge_rules(conn, keep, retire, ts)
    conn.execute(
        "UPDATE edits SET learned_at = ? WHERE domain = ? AND learned_at IS NULL", (ts, domain)
    )

    version, sha, changed = render_and_record(conn, workspace, domain)
    summary = changelog(conn, before, version, batch, activated, retired, created, merged)
    cur = conn.execute(
        "INSERT INTO learn_runs (domain, ran_at, edits_consumed, constitution_sha_from,"
        " constitution_sha_to, prefs_created, prefs_activated, prefs_retired, summary)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            domain,
            ts,
            len(batch),
            before["sha"],
            sha,
            len(created),
            len(activated),
            len(retired) + len(merged),
            summary,
        ),
    )
    if changed:
        conn.execute(
            "UPDATE constitutions SET learn_run_id = ? WHERE sha = ?", (cur.lastrowid, sha)
        )
    conn.commit()
    print(summary)


# --- status --------------------------------------------------------------------------------


def has_view(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'view' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def count(conn, domain, status):
    return conn.execute(
        "SELECT COUNT(*) FROM preferences WHERE domain = ? AND status = ?", (domain, status)
    ).fetchone()[0]


def status(conn, workspace, domain, chart):
    lines = []
    if has_view(conn, "v_pipeline"):
        counts = dict(conn.execute("SELECT status, n FROM v_pipeline").fetchall())
        # 'queued' is printed as 'captured': queue.md's "waiting" means drafted, not this.
        stages = (("queued", "captured"), ("drafted", "drafted"))
        stages += (("approved", "approved"), ("sent", "sent"))
        lines.append(("pipeline", " · ".join(f"{label} {counts.get(s, 0)}" for s, label in stages)))
    if has_view(conn, "v_sends_this_week"):
        lines.append(
            ("sent this week", conn.execute("SELECT n FROM v_sends_this_week").fetchone()[0])
        )
    latest = latest_constitution(conn, domain)
    rules = f"{count(conn, domain, 'active')} rules · {count(conn, domain, 'candidate')} candidates"
    lines.append(("constitution", f"v{latest['version']} · {rules}"))
    unlearned_n = conn.execute(
        "SELECT COUNT(*) FROM edits WHERE domain = ? AND learned_at IS NULL", (domain,)
    ).fetchone()[0]
    lines.append(("unlearned", f"{unlearned_n} edits"))
    curve = conn.execute(
        "SELECT version, mean_edit_distance, n_edits FROM v_learning_curve WHERE domain = ?",
        (domain,),
    ).fetchall()
    lines.append(("curve", "  ".join(f"v{v} {m:.2f} ({n})" for v, m, n in curve) or "none"))
    runs, last = conn.execute(
        "SELECT COUNT(*), MAX(ran_at) FROM learn_runs WHERE domain = ?", (domain,)
    ).fetchone()
    lines.append(("runs", f"{runs}, last {last}" if runs else "0"))
    for label, value in lines:
        print(f"{label:<15}{value}")
    if chart:
        (Path(workspace) / "learning-curve.svg").write_text(curve_svg(curve), encoding="utf-8")


def curve_svg(points):
    """Mean edit distance per constitution version, as a plain SVG string."""
    w, h, pad = 480, 240, 40
    step = (w - 2 * pad) / max(1, len(points) - 1)
    xy = [(pad + i * step, h - pad - m * (h - 2 * pad)) for i, (_, m, _) in enumerate(points)]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"'
        ' font-family="sans-serif" font-size="12">',
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h - pad}" stroke="#888"/>',
        f'<line x1="{pad}" y1="{h - pad}" x2="{w - pad}" y2="{h - pad}" stroke="#888"/>',
        f'<text x="{pad}" y="{pad - 10}">mean edit distance per constitution version</text>',
    ]
    if len(xy) > 1:
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
        parts.append(f'<polyline fill="none" stroke="#1f77b4" stroke-width="2" points="{line}"/>')
    for (v, m, n), (x, y) in zip(points, xy):
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#1f77b4"/>')
        parts.append(f'<text x="{x:.1f}" y="{h - pad + 16}" text-anchor="middle">v{v}</text>')
        parts.append(f'<text x="{x:.1f}" y="{y - 8:.1f}" text-anchor="middle">{m:.2f} ({n})</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# --- CLI -----------------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--workspace", default=".")
    common.add_argument("--domain", default="outreach")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("init", parents=[common])
    p.add_argument("--from", dest="from_path")
    p = commands.add_parser("history", parents=[common])
    p.add_argument("--text", action="append", required=True)
    p = commands.add_parser("prefer", parents=[common])
    p.add_argument("--statement", required=True)
    p.add_argument("--when")
    stages = commands.add_parser("learn").add_subparsers(dest="stage", required=True)
    stages.add_parser("emit", parents=[common])
    p = stages.add_parser("apply", parents=[common])
    p.add_argument("--reconcile", required=True)
    p.add_argument("--mode", choices=["lifecycle", "approve"], default="lifecycle")
    p = commands.add_parser("status", parents=[common])
    p.add_argument("--chart", action="store_true")
    args = parser.parse_args()

    if args.command == "init":
        init(args.workspace, args.from_path, args.domain)
        return
    conn = connect(args.workspace)
    if args.command == "history":
        history(conn, args.domain, [read_arg(t) for t in args.text])
    elif args.command == "prefer":
        condition = read_arg(args.when).strip() if args.when else None
        prefer(conn, args.workspace, args.domain, read_arg(args.statement).strip(), condition)
    elif args.command == "learn" and args.stage == "emit":
        learn_emit(conn, args.domain)
    elif args.command == "learn":
        reconcile = load_json(read_arg(args.reconcile), "reconcile")
        learn_apply(conn, args.workspace, args.domain, reconcile, args.mode)
    elif args.command == "status":
        status(conn, args.workspace, args.domain, args.chart)


if __name__ == "__main__":
    main()
