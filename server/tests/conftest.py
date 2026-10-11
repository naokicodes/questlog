import pytest
from fastapi.testclient import TestClient

from app import db
from app.auth import create_device
from app.config import Config
from app.main import create_app


@pytest.fixture
def cfg(tmp_path):
    return Config(
        db_path=tmp_path / "test.db",
        media_dir=tmp_path / "media",
        aw_url="http://127.0.0.1:9",  # nothing listens here: ActivityWatch "offline"
    )


@pytest.fixture
def conn(cfg):
    db.init_db(cfg.db_path)
    c = db.connect(cfg.db_path)
    db.seed_defaults(c)
    # Tests run on any weekday, so make the starter quests show up every day.
    c.execute("UPDATE quest_templates SET weekdays = '1,2,3,4,5,6,7'")
    c.commit()
    yield c
    c.close()


@pytest.fixture
def make_client(cfg, conn):
    def _make(kind: str = "laptop") -> TestClient:
        token = create_device(conn, f"test-{kind}", kind)
        client = TestClient(create_app(cfg))
        client.__enter__()
        client.cookies.set("questlog_token", token)
        return client

    return _make
