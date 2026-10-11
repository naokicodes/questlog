"""Loads config.toml (or config.example.toml as a fallback)."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    db_path: Path
    media_dir: Path
    rollover_hour: int = 4
    open_weekdays: list[int] = field(default_factory=lambda: [7])
    emergency_minutes: int = 15
    emergency_per_week: int = 3
    aw_url: str = "http://localhost:5600"


def load_config(path: Path | None = None) -> Config:
    if path is None:
        env = os.environ.get("QUESTLOG_CONFIG")
        path = Path(env) if env else SERVER_DIR / "config.toml"
    if not path.exists():
        path = SERVER_DIR / "config.example.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    server = data.get("server", {})
    day = data.get("day", {})
    gate = data.get("gate", {})
    aw = data.get("activitywatch", {})
    base = path.parent
    return Config(
        db_path=(base / server.get("db_path", "data.db")).resolve(),
        media_dir=(base / server.get("media_dir", "media")).resolve(),
        rollover_hour=int(day.get("rollover_hour", 4)),
        open_weekdays=[int(d) for d in day.get("open_weekdays", [7])],
        emergency_minutes=int(gate.get("emergency_minutes", 15)),
        emergency_per_week=int(gate.get("emergency_per_week", 3)),
        aw_url=str(aw.get("url", "http://localhost:5600")).rstrip("/"),
    )
