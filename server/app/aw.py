"""Reads active (non-AFK) window time from ActivityWatch's REST API."""

import re
from datetime import datetime

import httpx

QUERY = [
    'afk = flood(query_bucket(find_bucket("aw-watcher-afk_")));',
    'win = flood(query_bucket(find_bucket("aw-watcher-window_")));',
    'win = filter_period_intersect(win, filter_keyvals(afk, "status", ["not-afk"]));',
    'win = merge_events_by_keys(win, ["app", "title"]);',
    "RETURN = sort_by_duration(win);",
]


class AWError(Exception):
    """ActivityWatch is not running or the query failed."""


def active_events(
    base_url: str, start: datetime, end: datetime, timeout: float = 5.0
) -> list[dict]:
    payload = {"timeperiods": [f"{start.isoformat()}/{end.isoformat()}"], "query": QUERY}
    try:
        response = httpx.post(f"{base_url}/api/0/query/", json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AWError(str(exc)) from exc
    events = data[0] if data else []
    return [
        {
            "app": e.get("data", {}).get("app", ""),
            "title": e.get("data", {}).get("title", ""),
            "seconds": float(e.get("duration", 0)),
        }
        for e in events
    ]


def minutes_by_app(events: list[dict]) -> list[tuple[str, float]]:
    totals: dict[str, float] = {}
    for e in events:
        totals[e["app"]] = totals.get(e["app"], 0.0) + e["seconds"] / 60
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)


def matched_minutes(events: list[dict], apps: list[str], title_regex: str | None) -> float:
    wanted = {a.lower() for a in apps if a}
    pattern = re.compile(title_regex, re.IGNORECASE) if title_regex else None
    if not wanted and pattern is None:
        return 0.0
    total = 0.0
    for e in events:
        if wanted and e["app"].lower() not in wanted:
            continue
        if pattern and not pattern.search(e["title"]):
            continue
        total += e["seconds"]
    return total / 60
