import os

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    os.environ.setdefault("INTERNAL_API_TOKEN", "test-internal-token")
    get_settings.cache_clear()
    return TestClient(create_app(), raise_server_exceptions=False)
