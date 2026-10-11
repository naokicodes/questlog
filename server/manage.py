"""Questlog command line. Run from the server folder:

uv run python manage.py first-run
uv run python manage.py add-device "Nao's phone" --kind phone
uv run python manage.py devices
uv run python manage.py aw-today
uv run python manage.py backup --dest C:\\path\\to\\backups
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from app import aw, db
from app.auth import create_device
from app.config import load_config
from app.days import day_for, day_start, now


def cmd_init(cfg) -> None:
    db.init_db(cfg.db_path)
    cfg.media_dir.mkdir(parents=True, exist_ok=True)
    conn = db.connect(cfg.db_path)
    try:
        seeded = db.seed_defaults(conn)
    finally:
        conn.close()
    print(f"Database ready: {cfg.db_path}")
    if seeded:
        print("Added starter skills and daily quests.")


def print_token(name: str, kind: str, token: str) -> None:
    print()
    print(f"Login token for {name} ({kind}):")
    print()
    print(f"    {token}")
    print()
    print("Paste it on the login page. It is shown only once, so copy it now.")


def cmd_first_run(cfg) -> None:
    cmd_init(cfg)
    conn = db.connect(cfg.db_path)
    try:
        if conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]:
            print("Devices already set up. Use 'add-device' if you need a new token.")
            return
        token = create_device(conn, "Laptop", "laptop")
    finally:
        conn.close()
    print_token("Laptop", "laptop", token)


def cmd_add_device(cfg, name: str, kind: str) -> None:
    cmd_init(cfg)
    conn = db.connect(cfg.db_path)
    try:
        token = create_device(conn, name, kind)
    finally:
        conn.close()
    print_token(name, kind, token)


def cmd_devices(cfg) -> None:
    conn = db.connect(cfg.db_path)
    try:
        rows = conn.execute("SELECT * FROM devices ORDER BY id").fetchall()
    finally:
        conn.close()
    if not rows:
        print("No devices yet. Run 'first-run'.")
    for r in rows:
        print(
            f"{r['id']:>3}  {r['kind']:<7} {r['name']:<24} last seen {r['last_seen_at'] or 'never'}"
        )


def cmd_aw_today(cfg) -> None:
    at = now()
    start = day_start(day_for(at, cfg.rollover_hour), cfg.rollover_hour)
    try:
        events = aw.active_events(cfg.aw_url, start, at)
    except aw.AWError as exc:
        print(f"Can't reach ActivityWatch at {cfg.aw_url}. Is it running?\n  ({exc})")
        sys.exit(1)
    rows = aw.minutes_by_app(events)
    print(f"Active (non-AFK) minutes since {start:%a %d %b %I:%M %p}:\n")
    if not rows:
        print("  Nothing recorded yet.")
    for app_name, minutes in rows:
        print(f"  {minutes:7.1f} min   {app_name}")
    print("\nUse these exact app names in auto quests.")


def cmd_backup(cfg, dest: Path, keep: int) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"questlog-{datetime.now():%Y%m%d-%H%M%S}"
    target.mkdir()
    src = db.connect(cfg.db_path)
    out = db.connect(target / "data.db")
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    if cfg.media_dir.exists():
        shutil.copytree(cfg.media_dir, target / "media")
    print(f"Backed up to {target}")
    old = sorted(p for p in dest.glob("questlog-*") if p.is_dir())[:-keep]
    for p in old:
        shutil.rmtree(p)
        print(f"Removed old backup {p.name}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="manage.py", description="Questlog tools")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="Create the database and starter data")
    sub.add_parser("first-run", help="init + create the laptop login token")
    add = sub.add_parser("add-device", help="Create a login token for a device")
    add.add_argument("name")
    add.add_argument("--kind", choices=["laptop", "phone"], required=True)
    sub.add_parser("devices", help="List devices")
    sub.add_parser("aw-today", help="Show today's active minutes per app from ActivityWatch")
    bk = sub.add_parser("backup", help="Back up the database and media")
    bk.add_argument("--dest", type=Path, default=Path.home() / "questlog-backups")
    bk.add_argument("--keep", type=int, default=14)
    args = parser.parse_args()
    cfg = load_config()
    if args.cmd == "init":
        cmd_init(cfg)
    elif args.cmd == "first-run":
        cmd_first_run(cfg)
    elif args.cmd == "add-device":
        cmd_add_device(cfg, args.name, args.kind)
    elif args.cmd == "devices":
        cmd_devices(cfg)
    elif args.cmd == "aw-today":
        cmd_aw_today(cfg)
    elif args.cmd == "backup":
        cmd_backup(cfg, args.dest, args.keep)


if __name__ == "__main__":
    main()
