"""Saves uploaded photos and recordings under media/YYYY/MM/<sha256>.<ext>."""

import hashlib
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile

from .days import iso

MAX_BYTES = 25 * 1024 * 1024

EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


class MediaError(Exception):
    """The upload was rejected."""


def is_empty(upload: UploadFile | None) -> bool:
    return upload is None or not upload.filename


async def save_upload(
    conn: sqlite3.Connection,
    media_dir: Path,
    upload: UploadFile,
    at: datetime,
    entry_id: int | None = None,
) -> int:
    mime = (upload.content_type or "").split(";")[0].strip().lower()
    ext = EXTENSIONS.get(mime)
    if ext is None:
        raise MediaError("Only photos and audio recordings can be uploaded.")
    digest = hashlib.sha256()
    size = 0
    with tempfile.NamedTemporaryFile(delete=False, dir=media_dir) as tmp:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                raise MediaError("That file is over 25 MB.")
            digest.update(chunk)
            tmp.write(chunk)
    sha = digest.hexdigest()
    rel = Path(f"{at:%Y}") / f"{at:%m}" / f"{sha}{ext}"
    dest = media_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        Path(tmp.name).unlink(missing_ok=True)
    else:
        Path(tmp.name).replace(dest)
    cur = conn.execute(
        "INSERT INTO attachments (entry_id, path, mime, sha256, original_name, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (entry_id, rel.as_posix(), mime, sha, upload.filename, iso(at)),
    )
    conn.commit()
    return cur.lastrowid
