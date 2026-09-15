import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SCHEMA = ROOT / "db" / "schema.sql"
FIXTURES = Path(__file__).parent / "fixtures"


def run(script, *args, workspace=None, stdin=None, expect=0, env=None):
    """Run scripts/<script>.py the way a skill does and assert on its exit code."""
    cmd = [sys.executable, str(SCRIPTS / f"{script}.py"), *args]
    if workspace is not None:
        cmd += ["--workspace", str(workspace)]
    proc = subprocess.run(
        cmd, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env
    )
    assert proc.returncode == expect, proc.stderr or proc.stdout
    return proc


def connect(workspace):
    conn = sqlite3.connect(workspace / "db" / "outreach.sqlite")
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def db(tmp_path):
    """A fresh workspace database with the schema applied and foreign keys on."""
    conn = sqlite3.connect(tmp_path / "outreach.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text())
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


@pytest.fixture
def ws(tmp_path):
    """An initialized workspace directory."""
    path = tmp_path / "ws"
    run("db", "init", workspace=path)
    return path
