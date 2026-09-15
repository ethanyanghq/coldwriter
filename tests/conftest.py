import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "db" / "schema.sql"


@pytest.fixture
def db(tmp_path):
    """A fresh workspace database with the schema applied and foreign keys on."""
    conn = sqlite3.connect(tmp_path / "outreach.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text())
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()
