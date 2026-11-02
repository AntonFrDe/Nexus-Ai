from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexus.core.config import Settings
from nexus.main import create_app

TOKEN = "test-token"


def authed(settings: Settings, **options) -> TestClient:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    return TestClient(create_app(settings), headers=headers, **options)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path, allowed_hosts=["testserver"], api_token=TOKEN, secret_backend="file"
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with authed(settings) as test_client:
        yield test_client
