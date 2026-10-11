"""The phone gate: LOCKED until today's required quests are done."""

import sqlite3
from datetime import datetime, timedelta

from . import aw, quests
from .config import Config
from .days import day_for, day_start, iso, week_start


class GateError(Exception):
    """An emergency unlock the rules don't allow."""


def load_events(cfg: Config, at: datetime) -> list[dict] | None:
    """Today's active laptop events, or None when ActivityWatch is unreachable."""
    start = day_start(day_for(at, cfg.rollover_hour), cfg.rollover_hour)
    try:
        return aw.active_events(cfg.aw_url, start, at)
    except aw.AWError:
        return None


def snapshot(
    conn: sqlite3.Connection, cfg: Config, at: datetime, events: list[dict] | None
) -> dict:
    """Everything the Today screen and the phone need, computed in one place."""
    today = day_for(at, cfg.rollover_hour)
    quests.ensure_day(conn, today)
    rows = quests.quests_for(conn, today)
    progress = quests.refresh_auto(conn, rows, events, at)
    rows = quests.quests_for(conn, today)
    return {
        "day": today,
        "quests": rows,
        "progress": progress,
        "aw_ok": events is not None,
        "gate": gate_state(conn, cfg, at, rows),
    }


def gate_state(conn: sqlite3.Connection, cfg: Config, at: datetime, rows) -> dict:
    today = day_for(at, cfg.rollover_hour)
    next_rollover = day_start(today + timedelta(days=1), cfg.rollover_hour)
    if today.isoweekday() in cfg.open_weekdays:
        return {
            "state": "OPEN",
            "reason": "Rest day",
            "remaining": [],
            "expires_at": iso(next_rollover),
        }
    remaining = [q["title"] for q in rows if q["required"] and q["status"] != "done"]
    if not remaining:
        return {
            "state": "OPEN",
            "reason": "Required quests done",
            "remaining": [],
            "expires_at": iso(next_rollover),
        }
    unlock = conn.execute(
        "SELECT * FROM gate_events WHERE type = 'emergency' AND expires_at > ?"
        " ORDER BY expires_at DESC LIMIT 1",
        (iso(at),),
    ).fetchone()
    if unlock:
        return {
            "state": "EMERGENCY",
            "reason": unlock["reason"],
            "remaining": remaining,
            "expires_at": unlock["expires_at"],
        }
    return {"state": "LOCKED", "reason": "Quests left", "remaining": remaining, "expires_at": None}


def emergencies_left(conn: sqlite3.Connection, cfg: Config, at: datetime) -> int:
    since = day_start(week_start(day_for(at, cfg.rollover_hour)), cfg.rollover_hour)
    used = conn.execute(
        "SELECT COUNT(*) FROM gate_events WHERE type = 'emergency' AND created_at >= ?",
        (iso(since),),
    ).fetchone()[0]
    return max(cfg.emergency_per_week - used, 0)


def emergency_unlock(
    conn: sqlite3.Connection, cfg: Config, at: datetime, reason: str, device_id: int | None
) -> str:
    reason = reason.strip()
    if not reason:
        raise GateError("Write a reason for the emergency unlock.")
    if emergencies_left(conn, cfg, at) <= 0:
        raise GateError("No emergency unlocks left this week.")
    expires = at + timedelta(minutes=cfg.emergency_minutes)
    conn.execute(
        "INSERT INTO gate_events (type, reason, device_id, created_at, expires_at)"
        " VALUES ('emergency', ?, ?, ?, ?)",
        (reason, device_id, iso(at), iso(expires)),
    )
    conn.commit()
    return iso(expires)
