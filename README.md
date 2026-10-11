# Questlog

A personal self-help app that makes the phone's fun apps cost something.

The laptop is for work and the phone is where the time goes. Questlog keeps a daily list of
quests, checks some of them off automatically from laptop activity, and keeps distracting
phone apps locked until the required ones are done. It also holds a simple journal with photos
of a paper journal, and logs practice sessions.

Built for my own use and shared as-is. Issues are welcome; feature requests probably won't get
built unless I need them too.

## What works now

- **Today screen.** The gate (Locked, Open, or Unlocked for an emergency), today's quests, a
  start/end session log, quick planning, and today's laptop time per app.
- **Daily quests.** Repeat on chosen weekdays. Checked by ticking off, by a photo or recording,
  or automatically from ActivityWatch ("60 active minutes in `Code.exe`").
- **Phone rules.** From the phone, ticking a quest off needs a photo or recording as proof.
  Auto quests can't be overridden from the phone. Emergency unlocks need a reason, are limited
  per week, and are logged.
- **Journal.** Markdown entries with photos and audio, an evening review template, full-text search.
- **API for the Android companion.** `GET /api/gate`, `POST /api/gate/emergency`,
  `GET /api/today`, `POST /api/phone/usage`.
- **Days roll over at 4:00 am. Sundays are open.** Both are set in `server/config.toml`.

Not built yet: the Android blocker (Phase 4), the tray app, XP and levels (Phase 5).
See [`docs/blueprint.md`](docs/blueprint.md) for the whole design.

## Set up (Windows 11)

1. Double-click **`setup.bat`**. It installs Git, uv, ActivityWatch, and Tailscale if they're
   missing (nothing else, and it never upgrades other software), installs the server's Python
   packages, and prints a **laptop login token**.
2. Open **ActivityWatch** once from the Start menu so it starts tracking.
3. Double-click **`run.bat`**. The browser opens `http://localhost:8000`. Paste the token.

Check that ActivityWatch sees your apps, and get their exact names for auto quests:

```powershell
cd server
uv run python manage.py aw-today
```

## Use it from the phone

1. In the [Tailscale admin console](https://login.tailscale.com/admin/dns), turn on MagicDNS and
   HTTPS Certificates.
2. Run **`phone-access.bat`** on the laptop. It publishes the server to your tailnet over HTTPS
   and creates a **phone login token**.
3. On the phone: install Tailscale, log in with the same account, open the `https://…ts.net`
   address it printed, log in with the phone token, then choose **Install app** in the
   browser menu.

`run.bat` has to be running on the laptop for the phone to connect.

## Back up

Double-click **`backup.bat`**. It copies the database and media to
`%USERPROFILE%\questlog-backups` and keeps the newest 14. Copy that folder to a drive or a
cloud folder now and then: everything lives on one laptop.

## Develop

```powershell
cd server
uv sync
uv run pytest
uv run ruff check . ; uv run ruff format .
uv run uvicorn app.main:app --reload --port 8000
```

Useful commands (run from `server/`):

| Command | What it does |
|---|---|
| `uv run python manage.py devices` | List devices and when each was last seen |
| `uv run python manage.py add-device NAME --kind laptop\|phone` | New login token |
| `uv run python manage.py aw-today` | Today's active minutes per app |
| `uv run python manage.py backup --dest DIR` | Back up to a folder |

## Repo layout

```text
questlog/
├── server/            FastAPI server, pages, static files, tests
│   ├── app/           routes, gate and quest logic, ActivityWatch client, templates
│   ├── static/        CSS, PWA manifest, service worker, icons
│   ├── tests/
│   ├── manage.py      command line tools
│   └── config.example.toml
├── tray/              Windows tray app (later)
├── android/           Kotlin companion (Phase 4)
├── docs/blueprint.md  the full design
├── setup.bat  run.bat  phone-access.bat  backup.bat
└── LICENSE
```

## Privacy

Nothing personal is in this repo. `server/data.db`, `server/media/`, and `server/config.toml`
are gitignored, and login tokens are only stored as hashes. The server only listens on
`127.0.0.1`; the phone reaches it through Tailscale, never the open internet.

## License

MIT
