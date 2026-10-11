"""Daily quests: generating them from templates and checking auto quests."""

import json
import sqlite3
from datetime import date, datetime

from . import aw
from .days import iso


class QuestError(Exception):
    """A quest action the rules don't allow."""


def ensure_day(conn: sqlite3.Connection, d: date) -> None:
    """Creates today's quests from active templates. Safe to call often."""
    weekday = str(d.isoweekday())
    for t in conn.execute("SELECT * FROM quest_templates WHERE archived = 0").fetchall():
        if weekday in t["weekdays"].split(","):
            conn.execute(
                "INSERT OR IGNORE INTO quests"
                " (template_id, day, title, skill_id, verify, rule_json, required)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    t["id"],
                    d.isoformat(),
                    t["title"],
                    t["skill_id"],
                    t["verify"],
                    t["rule_json"],
                    t["required"],
                ),
            )
    conn.commit()


def quests_for(conn: sqlite3.Connection, d: date) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT q.*, s.name AS skill FROM quests q LEFT JOIN skills s ON s.id = q.skill_id"
        " WHERE q.day = ? ORDER BY q.required DESC, q.id",
        (d.isoformat(),),
    ).fetchall()


def rule_of(quest) -> dict | None:
    return json.loads(quest["rule_json"]) if quest["rule_json"] else None


def refresh_auto(
    conn: sqlite3.Connection, quests, events: list[dict] | None, at: datetime
) -> dict[int, float]:
    """Marks auto quests done when ActivityWatch shows enough time. Returns minutes per quest."""
    progress: dict[int, float] = {}
    if events is None:
        return progress
    for q in quests:
        rule = rule_of(q)
        if q["verify"] != "auto" or not rule:
            continue
        minutes = aw.matched_minutes(events, rule.get("apps", []), rule.get("title_regex"))
        progress[q["id"]] = minutes
        if q["status"] != "done" and minutes >= float(rule.get("min_minutes", 0)):
            conn.execute(
                "UPDATE quests SET status = 'done', completed_at = ?, completed_via = 'auto'"
                " WHERE id = ?",
                (iso(at), q["id"]),
            )
    conn.commit()
    return progress


def needs_proof(quest, device_kind: str) -> bool:
    if quest["verify"] == "photo":
        return True
    return quest["verify"] == "manual" and device_kind == "phone"


def complete(
    conn: sqlite3.Connection, quest_id: int, device_kind: str, proof_id: int | None, at: datetime
) -> None:
    quest = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
    if quest is None:
        raise QuestError("That quest doesn't exist.")
    if quest["status"] == "done":
        return
    if quest["verify"] == "auto":
        if device_kind != "laptop":
            raise QuestError("Auto quests can only be overridden from the laptop.")
        via = "laptop-override"
    elif needs_proof(quest, device_kind) and proof_id is None:
        raise QuestError("Add a photo or recording to finish this quest from here.")
    else:
        via = "laptop" if device_kind == "laptop" else "phone+proof"
    conn.execute(
        "UPDATE quests SET status = 'done', completed_at = ?, completed_via = ?, proof_id = ?"
        " WHERE id = ?",
        (iso(at), via, proof_id, quest_id),
    )
    conn.commit()


def undo(conn: sqlite3.Connection, quest_id: int, device_kind: str) -> None:
    if device_kind != "laptop":
        raise QuestError("Undo only works from the laptop.")
    conn.execute(
        "UPDATE quests SET status = 'pending', completed_at = NULL, completed_via = NULL,"
        " proof_id = NULL WHERE id = ?",
        (quest_id,),
    )
    conn.commit()
