"""Time helpers. A 'day' starts at the rollover hour (4:00 am by default)."""

from datetime import date, datetime, time, timedelta


def now() -> datetime:
    return datetime.now().astimezone()


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def day_for(dt: datetime, rollover_hour: int) -> date:
    return (dt - timedelta(hours=rollover_hour)).date()


def day_start(d: date, rollover_hour: int) -> datetime:
    return datetime.combine(d, time(rollover_hour)).astimezone()


def week_start(d: date) -> date:
    return d - timedelta(days=d.isoweekday() - 1)


def minutes_between(start_iso: str, end_iso: str) -> float:
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return (end - start).total_seconds() / 60
