"""App factory. Run with: uv run uvicorn app.main:app --host 127.0.0.1 --port 8000"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .auth import COOKIE, device_for_token
from .config import SERVER_DIR, Config, load_config
from .days import iso, now
from .routes import api, pages

STATIC_DIR = SERVER_DIR / "static"
PUBLIC_PATHS = ("/login", "/static/", "/sw.js", "/favicon.ico")


def create_app(cfg: Config) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        db.init_db(cfg.db_path)
        cfg.media_dir.mkdir(parents=True, exist_ok=True)
        conn = db.connect(cfg.db_path)
        try:
            db.seed_defaults(conn)
        finally:
            conn.close()
        yield

    app = FastAPI(title="Questlog", lifespan=lifespan)
    app.state.config = cfg

    @app.middleware("http")
    async def require_device(request: Request, call_next):
        path = request.url.path
        if path.startswith(PUBLIC_PATHS):
            return await call_next(request)
        token = request.cookies.get(COOKIE)
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header[7:].strip()
        device = None
        if token:
            conn = db.connect(cfg.db_path)
            try:
                row = device_for_token(conn, token)
                if row is not None:
                    device = dict(row)
                    conn.execute(
                        "UPDATE devices SET last_seen_at = ? WHERE id = ?", (iso(now()), row["id"])
                    )
                    conn.commit()
            finally:
                conn.close()
        if device is None:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Log in with a device token."}, status_code=401)
            return RedirectResponse("/login", status_code=303)
        request.state.device = device
        return await call_next(request)

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return FileResponse(
            STATIC_DIR / "sw.js",
            media_type="text/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(STATIC_DIR / "icon-192.png", media_type="image/png")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/media", StaticFiles(directory=cfg.media_dir, check_dir=False), name="media")
    app.include_router(api.router)
    app.include_router(pages.router)
    return app


app = create_app(load_config())
