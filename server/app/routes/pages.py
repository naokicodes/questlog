"""HTML pages: Today, Quests, Journal, and login."""

import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from .. import aw, gate, media, quests
from ..auth import COOKIE, device_for_token
from ..config import Config
from ..days import day_for, day_start, iso, minutes_between, now
from ..db import has_fts
from ..deps import get_cfg, get_conn

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
markdown = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable(
    ["table", "strikethrough"]
)

EVENING_TEMPLATE = """## Gratitude
-
-
-

## Today


## Tomorrow
- Study subject:
- Morning task:
"""

WEEKDAYS = [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri"), (6, "Sat"), (7, "Sun")]


def _clock(value: str | None) -> str:
    if not value:
        return ""
    return datetime.fromisoformat(value).strftime("%I:%M %p").lstrip("0").lower()


def _day_label(value) -> str:
    d = value if isinstance(value, date) else date.fromisoformat(str(value))
    return d.strftime("%a, %b %d").replace(" 0", " ")


def _minutes(value: float | None) -> str:
    if value is None:
        return "0 min"
    value = round(value)
    return f"{value // 60} h {value % 60} min" if value >= 60 else f"{value} min"


templates.env.filters["clock"] = _clock
templates.env.filters["day_label"] = _day_label
templates.env.filters["minutes"] = _minutes
templates.env.filters["md"] = markdown.render


def render(request: Request, name: str, **ctx):
    ctx.setdefault("device", getattr(request.state, "device", None))
    ctx.setdefault("error", request.query_params.get("error"))
    ctx.setdefault("notice", request.query_params.get("notice"))
    return templates.TemplateResponse(request, name, ctx)


def back(url: str, error: str | None = None, notice: str | None = None) -> RedirectResponse:
    params = {k: v for k, v in (("error", error), ("notice", notice)) if v}
    return RedirectResponse(f"{url}?{urlencode(params)}" if params else url, status_code=303)


# ---------------------------------------------------------------- login


@router.get("/login")
def login_page(request: Request):
    return render(request, "login.html")


@router.post("/login")
def login(
    request: Request,
    token: Annotated[str, Form()],
    conn: sqlite3.Connection = Depends(get_conn),
):
    if device_for_token(conn, token.strip()) is None:
        return back("/login", error="That token doesn't match any device.")
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE, token.strip(), max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax"
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE)
    return response


# ---------------------------------------------------------------- today


@router.get("/")
def today(
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    cfg: Config = Depends(get_cfg),
):
    device = request.state.device
    at = now()
    events = gate.load_events(cfg, at)
    snap = gate.snapshot(conn, cfg, at, events)
    since = iso(day_start(snap["day"], cfg.rollover_hour))
    quest_views = []
    for row in snap["quests"]:
        q = dict(row)
        q["rule"] = quests.rule_of(row)
        q["minutes"] = snap["progress"].get(row["id"])
        q["needs_proof"] = quests.needs_proof(row, device["kind"])
        quest_views.append(q)
    active_session = conn.execute(
        "SELECT s.*, k.name AS skill FROM sessions s JOIN skills k ON k.id = s.skill_id"
        " WHERE s.ended_at IS NULL ORDER BY s.id DESC LIMIT 1"
    ).fetchone()
    finished = conn.execute(
        "SELECT s.*, k.name AS skill FROM sessions s JOIN skills k ON k.id = s.skill_id"
        " WHERE s.ended_at IS NOT NULL AND s.started_at >= ? ORDER BY s.started_at",
        (since,),
    ).fetchall()
    sessions_today = [
        dict(s, minutes=minutes_between(s["started_at"], s["ended_at"])) for s in finished
    ]
    phone_top = conn.execute(
        "SELECT * FROM phone_usage WHERE day = ? ORDER BY seconds DESC LIMIT 8",
        (snap["day"].isoformat(),),
    ).fetchall()
    return render(
        request,
        "today.html",
        active="today",
        snap=snap,
        gate=snap["gate"],
        quests=quest_views,
        done_count=sum(1 for q in quest_views if q["status"] == "done"),
        active_session=active_session,
        sessions_today=sessions_today,
        skills=conn.execute("SELECT * FROM skills ORDER BY id").fetchall(),
        top_apps=aw.minutes_by_app(events)[:8] if events else [],
        phone_top=phone_top,
        emergencies_left=gate.emergencies_left(conn, cfg, at),
        emergency_minutes=cfg.emergency_minutes,
        tomorrow=(snap["day"] + timedelta(days=1)).isoformat(),
    )


@router.post("/quests/{quest_id}/done")
async def quest_done(
    request: Request,
    quest_id: int,
    proof: Annotated[UploadFile | None, File()] = None,
    conn: sqlite3.Connection = Depends(get_conn),
    cfg: Config = Depends(get_cfg),
):
    at = now()
    try:
        proof_id = None
        if not media.is_empty(proof):
            proof_id = await media.save_upload(conn, cfg.media_dir, proof, at)
        quests.complete(conn, quest_id, request.state.device["kind"], proof_id, at)
    except (quests.QuestError, media.MediaError) as exc:
        return back("/", error=str(exc))
    return back("/", notice="Quest done.")


@router.post("/quests/{quest_id}/undo")
def quest_undo(request: Request, quest_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    try:
        quests.undo(conn, quest_id, request.state.device["kind"])
    except quests.QuestError as exc:
        return back("/", error=str(exc))
    return back("/", notice="Quest set back to pending.")


@router.post("/quests/one-off")
def quest_one_off(
    title: Annotated[str, Form()],
    day: Annotated[str, Form()],
    skill_id: Annotated[str, Form()] = "",
    verify: Annotated[str, Form()] = "manual",
    required: Annotated[str | None, Form()] = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return back("/", error="Pick a valid date.")
    if not title.strip():
        return back("/", error="Give the quest a title.")
    if verify not in ("manual", "photo"):
        verify = "manual"
    conn.execute(
        "INSERT INTO quests (template_id, day, title, skill_id, verify, required)"
        " VALUES (NULL, ?, ?, ?, ?, ?)",
        (
            d.isoformat(),
            title.strip(),
            int(skill_id) if skill_id else None,
            verify,
            1 if required else 0,
        ),
    )
    conn.commit()
    return back("/", notice=f"Added for {_day_label(d)}.")


# ---------------------------------------------------------------- sessions


@router.post("/sessions/start")
def session_start(
    skill_id: Annotated[int, Form()],
    begin_action: Annotated[str, Form()] = "",
    conn: sqlite3.Connection = Depends(get_conn),
):
    if conn.execute("SELECT 1 FROM sessions WHERE ended_at IS NULL").fetchone():
        return back("/", error="End the current session before starting another.")
    conn.execute(
        "INSERT INTO sessions (skill_id, started_at, begin_action) VALUES (?, ?, ?)",
        (skill_id, iso(now()), begin_action.strip()),
    )
    conn.commit()
    return back("/", notice="Session started.")


@router.post("/sessions/{session_id}/end")
def session_end(
    session_id: int,
    end_action: Annotated[str, Form()] = "",
    note: Annotated[str, Form()] = "",
    conn: sqlite3.Connection = Depends(get_conn),
):
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None or row["ended_at"]:
        return back("/", error="That session isn't running.")
    ended = iso(now())
    if minutes_between(row["started_at"], ended) > 120 and not note.strip():
        return back("/", error="Sessions over 2 hours need a note. Add one, then end it.")
    conn.execute(
        "UPDATE sessions SET ended_at = ?, end_action = ?, note = ? WHERE id = ?",
        (ended, end_action.strip(), note.strip(), session_id),
    )
    conn.commit()
    return back("/", notice="Session ended.")


# ---------------------------------------------------------------- gate


@router.post("/gate/emergency")
def gate_emergency(
    request: Request,
    reason: Annotated[str, Form()] = "",
    conn: sqlite3.Connection = Depends(get_conn),
    cfg: Config = Depends(get_cfg),
):
    try:
        gate.emergency_unlock(conn, cfg, now(), reason, request.state.device["id"])
    except gate.GateError as exc:
        return back("/", error=str(exc))
    return back("/", notice=f"Unlocked for {cfg.emergency_minutes} minutes. It's logged.")


# ---------------------------------------------------------------- quest templates


@router.get("/quests")
def quest_templates(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute(
        "SELECT t.*, s.name AS skill FROM quest_templates t LEFT JOIN skills s"
        " ON s.id = t.skill_id WHERE t.archived = 0 ORDER BY t.id"
    ).fetchall()
    views = []
    for row in rows:
        t = dict(row)
        t["rule"] = json.loads(row["rule_json"]) if row["rule_json"] else None
        days = {int(x) for x in row["weekdays"].split(",") if x}
        t["days_label"] = " ".join(label for n, label in WEEKDAYS if n in days)
        views.append(t)
    return render(
        request,
        "quests.html",
        active="quests",
        templates_list=views,
        skills=conn.execute("SELECT * FROM skills ORDER BY id").fetchall(),
        weekdays=WEEKDAYS,
    )


@router.post("/quests/templates")
def quest_template_add(
    title: Annotated[str, Form()],
    verify: Annotated[str, Form()],
    skill_id: Annotated[str, Form()] = "",
    apps: Annotated[str, Form()] = "",
    title_regex: Annotated[str, Form()] = "",
    min_minutes: Annotated[str, Form()] = "",
    required: Annotated[str | None, Form()] = None,
    weekdays: Annotated[list[str], Form()] = [],
    conn: sqlite3.Connection = Depends(get_conn),
):
    if not title.strip():
        return back("/quests", error="Give the quest a title.")
    if verify not in ("auto", "manual", "photo"):
        return back("/quests", error="Pick how the quest gets checked.")
    days = sorted({int(d) for d in weekdays if d.isdigit() and 1 <= int(d) <= 7})
    if not days:
        return back("/quests", error="Pick at least one day.")
    rule = None
    if verify == "auto":
        app_list = [a.strip() for a in apps.split(",") if a.strip()]
        if not app_list and not title_regex.strip():
            return back("/quests", error="Auto quests need app names or a window-title pattern.")
        if title_regex.strip():
            try:
                re.compile(title_regex)
            except re.error:
                return back("/quests", error="That window-title pattern isn't a valid regex.")
        if not min_minutes.isdigit() or int(min_minutes) <= 0:
            return back("/quests", error="Auto quests need a number of minutes.")
        rule = {
            "type": "aw_minutes",
            "apps": app_list,
            "title_regex": title_regex.strip() or None,
            "min_minutes": int(min_minutes),
        }
    conn.execute(
        "INSERT INTO quest_templates (title, skill_id, verify, rule_json, required, weekdays)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            title.strip(),
            int(skill_id) if skill_id else None,
            verify,
            json.dumps(rule) if rule else None,
            1 if required else 0,
            ",".join(str(d) for d in days),
        ),
    )
    conn.commit()
    return back("/quests", notice="Quest added. It shows up on matching days, starting today.")


@router.post("/quests/templates/{template_id}/archive")
def quest_template_archive(template_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    conn.execute("UPDATE quest_templates SET archived = 1 WHERE id = ?", (template_id,))
    conn.commit()
    return back("/quests", notice="Quest removed from future days. Today's copy stays.")


# ---------------------------------------------------------------- journal


def _fts_query(text: str) -> str:
    return " ".join('"' + word.replace('"', '""') + '"' for word in text.split())


@router.get("/journal")
def journal_list(request: Request, q: str = "", conn: sqlite3.Connection = Depends(get_conn)):
    q = q.strip()
    if q and has_fts(conn):
        rows = conn.execute(
            "SELECT e.* FROM journal_fts f JOIN journal_entries e ON e.id = f.rowid"
            " WHERE journal_fts MATCH ? ORDER BY e.day DESC, e.id DESC LIMIT 100",
            (_fts_query(q),),
        ).fetchall()
    elif q:
        like = f"%{q}%"
        rows = conn.execute(
            "SELECT * FROM journal_entries WHERE title LIKE ? OR body_md LIKE ?"
            " ORDER BY day DESC, id DESC LIMIT 100",
            (like, like),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM journal_entries ORDER BY day DESC, id DESC LIMIT 60"
        ).fetchall()
    counts = dict(
        conn.execute(
            "SELECT entry_id, COUNT(*) FROM attachments WHERE entry_id IS NOT NULL"
            " GROUP BY entry_id"
        ).fetchall()
    )
    entries = [dict(r, attachments=counts.get(r["id"], 0)) for r in rows]
    return render(request, "journal_list.html", active="journal", entries=entries, q=q)


@router.get("/journal/new")
def journal_new(request: Request, kind: str = "", cfg: Config = Depends(get_cfg)):
    today_d = day_for(now(), cfg.rollover_hour)
    evening = kind == "evening"
    entry = {
        "id": None,
        "day": today_d.isoformat(),
        "title": "Evening review" if evening else "",
        "body_md": EVENING_TEMPLATE if evening else "",
        "tags": "review" if evening else "",
    }
    return render(request, "journal_edit.html", active="journal", entry=entry, attachments=[])


async def _save_files(conn, cfg: Config, files: list[UploadFile], entry_id: int) -> str | None:
    for f in files:
        if media.is_empty(f):
            continue
        try:
            await media.save_upload(conn, cfg.media_dir, f, now(), entry_id=entry_id)
        except media.MediaError as exc:
            return f"{f.filename}: {exc}"
    return None


@router.post("/journal")
async def journal_create(
    day: Annotated[str, Form()],
    title: Annotated[str, Form()] = "",
    body_md: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile], File()] = [],
    conn: sqlite3.Connection = Depends(get_conn),
    cfg: Config = Depends(get_cfg),
):
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return back("/journal/new", error="Pick a valid date.")
    stamp = iso(now())
    cur = conn.execute(
        "INSERT INTO journal_entries (day, title, body_md, tags, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (d.isoformat(), title.strip(), body_md, tags.strip(), stamp, stamp),
    )
    conn.commit()
    error = await _save_files(conn, cfg, files, cur.lastrowid)
    return back(f"/journal/{cur.lastrowid}", error=error, notice=None if error else "Saved.")


def _entry_or_none(conn, entry_id: int):
    return conn.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,)).fetchone()


@router.get("/journal/{entry_id}")
def journal_view(request: Request, entry_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    entry = _entry_or_none(conn, entry_id)
    if entry is None:
        return back("/journal", error="That entry doesn't exist.")
    attachments = conn.execute(
        "SELECT * FROM attachments WHERE entry_id = ? ORDER BY id", (entry_id,)
    ).fetchall()
    return render(
        request, "journal_view.html", active="journal", entry=entry, attachments=attachments
    )


@router.get("/journal/{entry_id}/edit")
def journal_edit(request: Request, entry_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    entry = _entry_or_none(conn, entry_id)
    if entry is None:
        return back("/journal", error="That entry doesn't exist.")
    attachments = conn.execute(
        "SELECT * FROM attachments WHERE entry_id = ? ORDER BY id", (entry_id,)
    ).fetchall()
    return render(
        request, "journal_edit.html", active="journal", entry=dict(entry), attachments=attachments
    )


@router.post("/journal/{entry_id}")
async def journal_update(
    entry_id: int,
    day: Annotated[str, Form()],
    title: Annotated[str, Form()] = "",
    body_md: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile], File()] = [],
    conn: sqlite3.Connection = Depends(get_conn),
    cfg: Config = Depends(get_cfg),
):
    if _entry_or_none(conn, entry_id) is None:
        return back("/journal", error="That entry doesn't exist.")
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return back(f"/journal/{entry_id}/edit", error="Pick a valid date.")
    conn.execute(
        "UPDATE journal_entries SET day = ?, title = ?, body_md = ?, tags = ?, updated_at = ?"
        " WHERE id = ?",
        (d.isoformat(), title.strip(), body_md, tags.strip(), iso(now()), entry_id),
    )
    conn.commit()
    error = await _save_files(conn, cfg, files, entry_id)
    return back(f"/journal/{entry_id}", error=error, notice=None if error else "Saved.")
