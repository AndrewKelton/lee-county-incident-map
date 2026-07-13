from unittest.mock import patch

import pytest

from leecad.crawl import coordinator
from leecad.geocoding.postgres_cache import PostgresCache
from leecad.postgres_schema import DatabaseSchemaError, require_tables
from leecad.store.postgres import PostgresStore


class RecordingCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, params=None):
        self.connection.statements.append((statement, params))

    def fetchall(self):
        return [(table,) for table in self.connection.available_tables]


class RecordingConnection:
    def __init__(self, available_tables=()):
        self.available_tables = set(available_tables)
        self.statements = []
        self.closed = False

    def cursor(self):
        return RecordingCursor(self)

    def close(self):
        self.closed = True


def assert_read_only_startup(connection):
    sql = "\n".join(statement for statement, _params in connection.statements).upper()
    for forbidden in ("CREATE ", "ALTER ", "DROP ", "INSERT ", "UPDATE ", "DELETE "):
        assert forbidden not in sql


def test_postgres_store_startup_does_not_mutate_schema():
    connection = RecordingConnection({"incidents"})
    with patch("leecad.store.postgres.psycopg.connect", return_value=connection):
        store = PostgresStore("postgresql://unused")

    assert_read_only_startup(connection)
    store.close()


def test_postgres_cache_startup_does_not_mutate_schema():
    connection = RecordingConnection({"geocode_cache"})
    with patch("leecad.geocoding.postgres_cache.psycopg.connect", return_value=connection):
        cache = PostgresCache("postgresql://unused")

    assert_read_only_startup(connection)
    cache.close()


def test_crawl_schema_check_does_not_mutate_schema():
    connection = RecordingConnection({"crawl_queries"})
    coordinator.require_schema(connection)

    assert_read_only_startup(connection)


def test_missing_migrated_table_fails_without_writing():
    connection = RecordingConnection()

    with pytest.raises(DatabaseSchemaError, match="missing public tables: incidents"):
        require_tables(connection, {"incidents"})

    assert_read_only_startup(connection)


def test_constructor_closes_connection_when_schema_check_fails():
    connection = RecordingConnection()
    with (
        patch("leecad.store.postgres.psycopg.connect", return_value=connection),
        pytest.raises(DatabaseSchemaError),
    ):
        PostgresStore("postgresql://unused")

    assert connection.closed
