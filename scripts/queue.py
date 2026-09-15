#!/usr/bin/env python3
"""Outreach consumer: contacts, drafts, the review queue, and sending.

Imports the learn core's helpers from db.py and is the only writer of queue.md.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from db import connect, fail, latest_constitution, load_json, now, read_arg
from diff import distance

DOMAIN = "outreach"
H2 = re.compile(r"^## \[(\d+)\]")


def normalize_url(url):
    """Lowercase, https, no www, no query, no fragment, no trailing slash."""
    url = url.strip().lower()
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    host = parts.netloc[4:] if parts.netloc.startswith("www.") else parts.netloc
    return urlunsplit(("https", host, parts.path.rstrip("/"), "", ""))


def contact(conn, contact_id):
    row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if row is None:
        fail(f"no contact #{contact_id}")
    return row


def final_edit(conn, contact_id):
    row = conn.execute(
        "SELECT * FROM edits WHERE domain = ? AND context_ref = ?",
        (DOMAIN, f"contact:{contact_id}"),
    ).fetchone()
    if row is None:
        fail(f"#{contact_id} has no final")
    return row


def read_optional(path):
    return path.read_text(encoding="utf-8") if path.exists() else None


# --- capture, draft, add -------------------------------------------------------------------


def capture(conn, url, profile):
    url = normalize_url(url)
    name = (profile.get("name") or "").strip()
    if not name:
        fail("profile has no name")
    existing = conn.execute(
        "SELECT id, name FROM contacts WHERE linkedin_url = ?", (url,)
    ).fetchone()
    if existing:
        print(f"#{existing['id']} exists {existing['name']}")
        return
    ts = now()
    cur = conn.execute(
        "INSERT INTO contacts (linkedin_url, name, headline, company, title, profile_json,"
        " captured_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            url,
            name,
            profile.get("headline"),
            profile.get("company"),
            profile.get("title"),
            json.dumps(profile),
            ts,
            ts,
        ),
    )
    conn.commit()
    print(f"#{cur.lastrowid} captured {name}")


def targets(conn, redraft):
    """Contacts needing a draft: no edits row and not sent, or the one asked for."""
    if redraft is None:
        return conn.execute(
            "SELECT * FROM contacts c WHERE status != 'sent'"
            " AND NOT EXISTS (SELECT 1 FROM edits e WHERE e.contact_id = c.id) ORDER BY id"
        ).fetchall()
    row = contact(conn, redraft)
    if conn.execute("SELECT 1 FROM edits WHERE contact_id = ?", (redraft,)).fetchone():
        fail(f"#{redraft} already reviewed")
    return [row]


def draft(conn, workspace, redraft):
    latest = latest_constitution(conn, DOMAIN)
    exemplars = conn.execute(
        "SELECT draft_text, final_text, reason_text FROM v_exemplars WHERE domain = ?"
        " ORDER BY reviewed_at DESC, edit_id DESC LIMIT 5",
        (DOMAIN,),
    ).fetchall()
    out = {
        "constitution": {
            "version": latest["version"],
            "sha": latest["sha"],
            "text": latest["text"],
        },
        "profile": read_optional(workspace / "me" / "_profile.md"),
        "corrections": read_optional(workspace / "me" / "corrections.md"),
        "exemplars": [
            {"draft": e["draft_text"], "final": e["final_text"], "note": e["reason_text"]}
            for e in exemplars
        ],
        "targets": [
            {
                "contact_id": c["id"],
                "name": c["name"],
                "url": c["linkedin_url"],
                "profile": json.loads(c["profile_json"]),
            }
            for c in targets(conn, redraft)
        ],
    }
    print(json.dumps(out, indent=2))


def add(conn, workspace, contact_id, text, sources):
    contact(conn, contact_id)
    cur = conn.execute(
        "INSERT INTO drafts (domain, context_ref, contact_id, text, sources_json,"
        " constitution_sha, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            DOMAIN,
            f"contact:{contact_id}",
            contact_id,
            text,
            json.dumps(sources),
            latest_constitution(conn, DOMAIN)["sha"],
            now(),
        ),
    )
    conn.commit()
    render_queue(conn, workspace)
    print(f"#{cur.lastrowid} draft for #{contact_id} · {len(text)} chars")


# --- queue.md ------------------------------------------------------------------------------


def render_queue(conn, workspace):
    """Rewrite queue.md from v_queue. Returns how many contacts are waiting."""
    version = latest_constitution(conn, DOMAIN)["version"]
    rows = conn.execute(
        "SELECT q.text, c.id, c.name, c.headline, c.linkedin_url FROM v_queue q"
        " JOIN contacts c ON c.id = q.contact_id WHERE q.domain = ? ORDER BY q.created_at, q.id",
        (DOMAIN,),
    ).fetchall()
    parts = [f"# Queue · constitution v{version} · {len(rows)} waiting\n"]
    for r in rows:
        title = f"[{r['id']}] {r['name']}" + (f" — {r['headline']}" if r["headline"] else "")
        parts.append(
            f"\n## {title}\n<{r['linkedin_url']}>\n\n### draft · {len(r['text'])} chars\n"
            f"{r['text']}\n\n### FINAL\n\n### note\n"
        )
    (workspace / "queue.md").write_text("".join(parts), encoding="utf-8")
    return len(rows)


def parse_queue(text):
    """[(contact_id, final, note)] from queue.md. Only the FINAL and note sections are read."""
    contacts, section = [], None
    for line in text.splitlines():
        opened = H2.match(line)
        if opened:
            contacts.append((int(opened.group(1)), {"FINAL": [], "note": []}))
            section = None
        elif line.startswith("### "):
            section = line[4:].split(" · ")[0].strip()
        elif contacts and section in ("FINAL", "note"):
            contacts[-1][1][section].append(line)
    return [
        (contact_id, "\n".join(s["FINAL"]).strip(), "\n".join(s["note"]).strip())
        for contact_id, s in contacts
    ]


def review_contact(conn, workspace, contact_id, final, note):
    """Record one contact's FINAL and note. Returns False when it is not in the queue."""
    queued = conn.execute(
        "SELECT * FROM v_queue WHERE domain = ? AND context_ref = ?",
        (DOMAIN, f"contact:{contact_id}"),
    ).fetchone()
    if queued is None:
        sys.stderr.write(f"#{contact_id} not in queue\n")
        return False
    if not final:
        print(f"#{contact_id} untouched")
        return True
    if final.lower() == "ok":
        final, d = queued["text"], 0.0
        line = f"#{contact_id} ok"
    else:
        d = distance(queued["text"], final)
        line = f"#{contact_id} edited · distance {d:.2f}"
    conn.execute(
        "INSERT INTO edits (domain, context_ref, contact_id, draft_id, final_text, edit_distance,"
        " reason_text, constitution_sha, reviewed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            DOMAIN,
            f"contact:{contact_id}",
            contact_id,
            queued["id"],
            final,
            d,
            note or None,
            queued["constitution_sha"],
            now(),
        ),
    )
    wrong = [ln[6:].strip() for ln in note.splitlines() if ln.lower().startswith("wrong:")]
    if wrong:
        with open(workspace / "me" / "corrections.md", "a", encoding="utf-8") as f:
            f.writelines(f"- {w}\n" for w in wrong)
    print(line)
    return True


def review(conn, workspace, contact_id, final, note):
    """The whole queue.md, or one contact given on the command line. Returns per-contact results."""
    if contact_id is None:
        path = workspace / "queue.md"
        if not path.exists():
            fail("no queue.md (run /coldwriter:draft)")
        items = parse_queue(path.read_text(encoding="utf-8"))
    else:
        items = [(contact_id, final.strip(), note.strip())]
    results = [review_contact(conn, workspace, *item) for item in items]
    conn.commit()
    render_queue(conn, workspace)
    return results


# --- send, sent ----------------------------------------------------------------------------


def send_list(conn):
    print(f"sent this week {conn.execute('SELECT n FROM v_sends_this_week').fetchone()[0]}")
    rows = conn.execute(
        "SELECT id, name, linkedin_url FROM contacts WHERE status = 'approved' ORDER BY id"
    )
    for r in rows:
        print(f"#{r['id']} {r['name']} · {r['linkedin_url']}")


def send_contact(conn, contact_id):
    row = contact(conn, contact_id)
    text = final_edit(conn, contact_id)["final_text"]
    if shutil.which("pbcopy"):
        subprocess.run(["pbcopy"], input=text, text=True, check=False)
    else:
        print("clipboard unavailable")
    opener = shutil.which("open") or shutil.which("xdg-open")
    if opener:
        subprocess.run([opener, row["linkedin_url"]], check=False)
    else:
        print(row["linkedin_url"])
    print(text)
    print(f"{len(text)} chars")


def sent(conn, contact_id, edited):
    row = contact(conn, contact_id)
    if row["status"] != "approved":
        fail(f"#{contact_id} is {row['status']}, not approved")
    edit = final_edit(conn, contact_id)
    text = edit["final_text"]
    if edited is not None:
        text = edited
        draft_text = conn.execute(
            "SELECT text FROM drafts WHERE id = ?", (edit["draft_id"],)
        ).fetchone()[0]
        conn.execute(
            "UPDATE edits SET final_text = ?, edit_distance = ?, learned_at = NULL WHERE id = ?",
            (text, distance(draft_text, text), edit["id"]),
        )
    conn.execute(
        "INSERT INTO sends (contact_id, edit_id, sent_at) VALUES (?, ?, ?)",
        (contact_id, edit["id"], now()),
    )
    conn.commit()
    print(f"#{contact_id} sent · {len(text)} chars")


# --- CLI -----------------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--workspace", default=".")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("capture", parents=[common])
    p.add_argument("--url", required=True)
    p.add_argument("--profile", required=True)
    p = commands.add_parser("draft", parents=[common])
    p.add_argument("--redraft", type=int)
    p = commands.add_parser("add", parents=[common])
    p.add_argument("--contact", type=int, required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--sources", default="[]")
    p = commands.add_parser("review", parents=[common])
    p.add_argument("--contact", type=int)
    p.add_argument("--final", default="")
    p.add_argument("--note", default="")
    p = commands.add_parser("send", parents=[common])
    p.add_argument("--contact", type=int)
    p = commands.add_parser("sent", parents=[common])
    p.add_argument("--contact", type=int, required=True)
    p.add_argument("--edited")
    commands.add_parser("render", parents=[common])
    args = parser.parse_args()

    workspace = Path(args.workspace)
    conn = connect(workspace)
    if args.command == "capture":
        capture(conn, args.url, load_json(read_arg(args.profile), "profile"))
    elif args.command == "draft":
        draft(conn, workspace, args.redraft)
    elif args.command == "add":
        sources = load_json(read_arg(args.sources), "sources")
        add(conn, workspace, args.contact, read_arg(args.text), sources)
    elif args.command == "review":
        results = review(conn, workspace, args.contact, read_arg(args.final), read_arg(args.note))
        if args.contact is not None and not results[0]:
            sys.exit(1)
    elif args.command == "send" and args.contact is None:
        send_list(conn)
    elif args.command == "send":
        send_contact(conn, args.contact)
    elif args.command == "sent":
        edited = read_arg(args.edited) if args.edited is not None else None
        sent(conn, args.contact, edited)
    elif args.command == "render":
        print(f"queue.md · {render_queue(conn, workspace)} waiting")


if __name__ == "__main__":
    main()
