import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.infrastructure.db.models import Base
from app.infrastructure.db.session import SessionLocal
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def _schema():
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield


@pytest.fixture()
def db_session():
    with SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture(autouse=True)
def _truncate(db_session):
    yield
    tables = ",".join(reversed([t.name for t in Base.metadata.sorted_tables]))
    db_session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    db_session.commit()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")
    get_settings.cache_clear()
    yield TestClient(create_app(), raise_server_exceptions=False)
    get_settings.cache_clear()
