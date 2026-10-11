"""SQLite helpers: connections, schema setup, and first-run seed data."""

import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent

DEFAULT_SKILLS = [
    # (name, laptop_tracked)
    ("Study", 0),
    ("Coding", 1),
    ("Guitar", 0),
    ("Singing", 0),
    ("Drawing", 0),
    ("Drums", 0),
    ("Music Production", 1),
]

MON_TO_SAT = "1,2,3,4,5,6"

DEFAULT_TEMPLATES = [
    # (title, skill, verify, rule, required, weekdays)
    ("Study: today's one subject", "Study", "manual", None, 1, MON_TO_SAT),
    (
        "Coding: one project, 60 min",
        "Coding",
        "auto",
        {"type": "aw_minutes", "apps": ["Code.exe"], "title_regex": None, "min_minutes": 60},
        1,
        MON_TO_SAT,
    ),
    ("Guitar practice", "Guitar", "manual", None, 1, MON_TO_SAT),
    ("Singing practice", "Singing", "manual", None, 1, MON_TO_SAT),
]


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def has_fts(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'journal_fts'"
    ).fetchone()
    return row is not None


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        conn.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
        try:
            conn.executescript((HERE / "schema_fts.sql").read_text(encoding="utf-8"))
        except sqlite3.OperationalError:
            # This Python's SQLite has no FTS5. Journal search falls back to LIKE.
            pass
        conn.commit()
    finally:
        conn.close()


def seed_defaults(conn: sqlite3.Connection) -> bool:
    """Adds starter skills and quest templates if the database is empty."""
    if conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]:
        return False
    conn.executemany("INSERT INTO skills (name, laptop_tracked) VALUES (?, ?)", DEFAULT_SKILLS)
    ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM skills")}
    for title, skill, verify, rule, required, weekdays in DEFAULT_TEMPLATES:
        conn.execute(
            "INSERT INTO quest_templates (title, skill_id, verify, rule_json, required, weekdays)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (title, ids[skill], verify, json.dumps(rule) if rule else None, required, weekdays),
        )
    conn.commit()
    return True
