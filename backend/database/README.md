## Setup

Use Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```bash
cd backend/database
uv sync
```

## Local PostGIS database

Docker Desktop or Docker Engine with Compose is required. Start PostgreSQL 18
with PostGIS 3.6 and apply every migration with one command:

```bash
cd backend/database
./local-db.sh up
```

The database listens on `localhost:5433`. Defaults are in
`.env.example`.

Stop the container without deleting its data:

```bash
./local-db.sh down
```

Use a direct PostgreSQL connection. Pooled Neon URLs are rejected:

```bash
export ALEMBIC_DATABASE_URL='postgresql://...'
uv run alembic current
uv run alembic upgrade head
```

## Adopting the production baseline

Revision `0001` represents the three tables and eight
indexes that already exist in production on July 12, 2026.

For an existing database whose schema has first been verified against the
baseline, record ownership without executing the baseline DDL:

```bash
uv run alembic stamp 0001
uv run alembic current --check-heads
```

For an empty database, execute the migration normally:

```bash
uv run alembic upgrade head
```

Don't run `stamp` to bypass a failed migration. Stamping is only for a database that already matches revision `0001`.

## Migration verification

Database CI applies every migration to an empty PostgreSQL 18 database, rolls the
whole chain back, and applies it again. The second upgrade fails if a downgrade
left anything behind.
