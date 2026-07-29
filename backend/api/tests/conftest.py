import os

import pytest

from leecad_api.app import create_app


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set; see backend/api/README.md")
    return url


@pytest.fixture
def client(database_url):
    return create_app(database_url).test_client()
