from datetime import datetime, timedelta

import pytest

from app import gate, quests
from app.days import day_for


def at(y, m, d, h=10):
    return datetime(y, m, d, h).astimezone()


MONDAY = at(2026, 10, 12)
SUNDAY = at(2026, 10, 18)


def test_sunday_is_open(conn, cfg):
    snap = gate.snapshot(conn, cfg, SUNDAY, None)
    assert snap["gate"]["state"] == "OPEN"


def test_locked_until_required_quests_done(conn, cfg):
    snap = gate.snapshot(conn, cfg, MONDAY, None)
    assert snap["gate"]["state"] == "LOCKED"
    assert len(snap["gate"]["remaining"]) == 4
    for q in snap["quests"]:
        quests.complete(conn, q["id"], "laptop", None, MONDAY)
    assert gate.snapshot(conn, cfg, MONDAY, None)["gate"]["state"] == "OPEN"


def test_auto_quest_completes_from_activitywatch(conn, cfg):
    events = [{"app": "Code.exe", "title": "questlog", "seconds": 61 * 60}]
    snap = gate.snapshot(conn, cfg, MONDAY, events)
    coding = next(q for q in snap["quests"] if q["verify"] == "auto")
    assert coding["status"] == "done"
    assert coding["completed_via"] == "auto"


def test_phone_needs_proof(conn, cfg):
    snap = gate.snapshot(conn, cfg, MONDAY, None)
    manual = next(q for q in snap["quests"] if q["verify"] == "manual")
    with pytest.raises(quests.QuestError):
        quests.complete(conn, manual["id"], "phone", None, MONDAY)
    cur = conn.execute(
        "INSERT INTO attachments (path, mime, sha256, created_at)"
        " VALUES ('x.jpg', 'image/jpeg', 'abc', '')"
    )
    quests.complete(conn, manual["id"], "phone", cur.lastrowid, MONDAY)  # with proof


def test_phone_cannot_override_auto(conn, cfg):
    snap = gate.snapshot(conn, cfg, MONDAY, None)
    auto = next(q for q in snap["quests"] if q["verify"] == "auto")
    with pytest.raises(quests.QuestError):
        quests.complete(conn, auto["id"], "phone", None, MONDAY)


def test_emergency_unlock_and_weekly_limit(conn, cfg):
    gate.snapshot(conn, cfg, MONDAY, None)
    expires = gate.emergency_unlock(conn, cfg, MONDAY, "Family call", None)
    assert gate.snapshot(conn, cfg, MONDAY, None)["gate"]["state"] == "EMERGENCY"
    later = MONDAY + timedelta(minutes=cfg.emergency_minutes + 1)
    assert gate.snapshot(conn, cfg, later, None)["gate"]["state"] == "LOCKED"
    assert expires
    gate.emergency_unlock(conn, cfg, later, "Two", None)
    gate.emergency_unlock(conn, cfg, later, "Three", None)
    with pytest.raises(gate.GateError):
        gate.emergency_unlock(conn, cfg, later, "Four", None)
    next_week = MONDAY + timedelta(days=7)
    assert gate.emergencies_left(conn, cfg, next_week) == cfg.emergency_per_week


def test_emergency_needs_reason(conn, cfg):
    with pytest.raises(gate.GateError):
        gate.emergency_unlock(conn, cfg, MONDAY, "   ", None)


def test_quests_generated_once_per_day(conn, cfg):
    gate.snapshot(conn, cfg, MONDAY, None)
    gate.snapshot(conn, cfg, MONDAY, None)
    d = day_for(MONDAY, cfg.rollover_hour)
    assert len(quests.quests_for(conn, d)) == 4
