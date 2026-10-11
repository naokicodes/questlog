"""FastAPI dependencies shared by the page and API routes."""

from fastapi import Request

from . import db
from .config import Config


def get_conn(request: Request):
    conn = db.connect(request.app.state.config.db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_cfg(request: Request) -> Config:
    return request.app.state.config


def get_device(request: Request) -> dict:
    return request.state.device
