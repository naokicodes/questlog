"""JSON API used by the Android companion (and anything else that wants it)."""

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import gate
from ..config import Config
from ..days import day_for, iso, now
from ..deps import get_cfg, get_conn, get_device

router = APIRouter(prefix="/api")


@router.get("/gate")
def get_gate(conn: sqlite3.Connection = Depends(get_conn), cfg: Config = Depends(get_cfg)):
    at = now()
    snap = gate.snapshot(conn, cfg, at, gate.load_events(cfg, at))
    result = dict(snap["gate"])
    result["emergencies_left"] = gate.emergencies_left(conn, cfg, at)
    result["checked_at"] = iso(at)
    return result


class EmergencyIn(BaseModel):
    reason: str


@router.post("/gate/emergency")
def post_emergency(
    body: EmergencyIn,
    conn: sqlite3.Connection = Depends(get_conn),
    cfg: Config = Depends(get_cfg),
    device: dict = Depends(get_device),
):
    try:
        expires = gate.emergency_unlock(conn, cfg, now(), body.reason, device["id"])
    except gate.GateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"state": "EMERGENCY", "expires_at": expires}


@router.get("/today")
def get_today(conn: sqlite3.Connection = Depends(get_conn), cfg: Config = Depends(get_cfg)):
    at = now()
    snap = gate.snapshot(conn, cfg, at, gate.load_events(cfg, at))
    return {
        "day": snap["day"].isoformat(),
        "activitywatch_running": snap["aw_ok"],
        "gate": snap["gate"],
        "quests": [
            {
                "id": q["id"],
                "title": q["title"],
                "skill": q["skill"],
                "verify": q["verify"],
                "required": bool(q["required"]),
                "status": q["status"],
                "minutes": round(snap["progress"].get(q["id"], 0), 1)
                if q["verify"] == "auto"
                else None,
            }
            for q in snap["quests"]
        ],
    }


class UsageItem(BaseModel):
    package: str
    label: str | None = None
    seconds: int


class UsageIn(BaseModel):
    day: date | None = None
    items: list[UsageItem]


@router.post("/phone/usage")
def post_phone_usage(
    body: UsageIn,
    conn: sqlite3.Connection = Depends(get_conn),
    cfg: Config = Depends(get_cfg),
):
    d = body.day or day_for(now(), cfg.rollover_hour)
    conn.executemany(
        "INSERT INTO phone_usage (day, package, label, seconds) VALUES (?, ?, ?, ?)"
        " ON CONFLICT (day, package) DO UPDATE SET label = excluded.label,"
        " seconds = excluded.seconds",
        [(d.isoformat(), i.package, i.label, i.seconds) for i in body.items],
    )
    conn.commit()
    return {"saved": len(body.items), "day": d.isoformat()}
