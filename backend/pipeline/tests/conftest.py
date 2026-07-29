import io
import os

import pytest

from leecad.pipeline.s3_buffer import S3Buffer

APPLICATION_TABLES = ("incidents", "geocode_cache", "crawl_queries")


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: needs a live Postgres")


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL is not set; start a database (backend/database/local-db.sh up) "
            "and point TEST_DATABASE_URL at it to run integration tests"
        )
    return url


@pytest.fixture
def postgres_store(database_url):
    from leecad.store.postgres import PostgresStore

    store = PostgresStore(database_url)
    # Truncate up front, not on teardown, so a failing test leaves its rows for inspection.
    with store.conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(APPLICATION_TABLES)} RESTART IDENTITY CASCADE")
    store.conn.commit()
    try:
        yield store
    finally:
        store.close()


class FakeS3Error(RuntimeError):
    """Raised by FakeS3 for keys a test asked it to fail on."""


class _FakePaginator:
    def __init__(self, fake):
        self.fake = fake

    def paginate(self, Bucket, Prefix=""):  # noqa: N803 boto3 spells these capitalized
        self.fake._check_bucket(Bucket)
        keys = sorted(k for k in self.fake.objects if k.startswith(Prefix))
        contents = [{"Key": k} for k in keys]
        # boto3 omits Contents entirely when nothing matches.
        yield {"Contents": contents} if contents else {}


class FakeS3:
    """In-memory stand-in for a boto3 S3 client, sufficient for S3Buffer."""

    def __init__(self, bucket="test-bucket"):
        self.bucket = bucket
        self.objects: dict[str, bytes] = {}
        self.fail_on: set[str] = set()
        self.error = FakeS3Error

    def _check_bucket(self, bucket):
        if bucket != self.bucket:
            raise FakeS3Error(f"no such bucket: {bucket}")

    def _check_key(self, key):
        if key in self.fail_on:
            raise self.error(f"simulated S3 failure on {key}")

    def put_object(self, Bucket, Key, Body, ContentType=None):  # noqa: N803
        self._check_bucket(Bucket)
        self._check_key(Key)
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):  # noqa: N803
        self._check_bucket(Bucket)
        self._check_key(Key)
        if Key not in self.objects:
            raise FakeS3Error(f"no such key: {Key}")
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_objects(self, Bucket, Delete):  # noqa: N803
        self._check_bucket(Bucket)
        for entry in Delete["Objects"]:
            self._check_key(entry["Key"])
            self.objects.pop(entry["Key"], None)

    def get_paginator(self, operation_name):
        if operation_name != "list_objects_v2":
            raise FakeS3Error(f"unsupported paginator: {operation_name}")
        return _FakePaginator(self)


@pytest.fixture
def fake_s3():
    return FakeS3()


@pytest.fixture
def buffer(fake_s3):
    return S3Buffer(bucket=fake_s3.bucket, client=fake_s3)
