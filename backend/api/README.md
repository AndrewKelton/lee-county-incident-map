# leecad-api

Public read API over the Lee County incident database. Its own uv project, like
`backend/pipeline` and `backend/database`. It shares a database URL with them. The schema belongs to
`backend/database`'s migrations; this service only reads it.

## Run

```sh
cp .env.example .env
uv sync
uv run flask --app leecad_api.app:create_app run --port 5001
```

## Test

Needs a migrated database:

```sh
../database/local-db.sh up
TEST_DATABASE_URL=postgresql://leecad:leecad-local-only@localhost:5433/leecad uv run pytest
```

## Endpoints

| | |
|---|---|
| `GET /api/v1/health` | 200 with the current dataset revision, 503 if the database is unreachable |