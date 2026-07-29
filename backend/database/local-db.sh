#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

export POSTGRES_DB="${POSTGRES_DB:-leecad}"
export POSTGRES_USER="${POSTGRES_USER:-leecad}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-leecad-local-only}"
export POSTGRES_PORT="${POSTGRES_PORT:-5433}"
export ALEMBIC_DATABASE_URL="${ALEMBIC_DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}}"

case "${1:-up}" in
    up)
        docker compose up -d --wait database
        uv sync --locked
        uv run alembic upgrade head

        postgis_version="$(
            docker compose exec -T database \
                psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc \
                "SELECT extversion FROM pg_extension WHERE extname = 'postgis'"
        )"
        if [[ -z "$postgis_version" ]]; then
            echo "PostGIS was not enabled in the local database" >&2
            exit 1
        fi

        echo "local database ready on localhost:${POSTGRES_PORT} (PostGIS ${postgis_version})"
        ;;
    down)
        docker compose down
        ;;
    *)
        echo "usage: $0 [up|down]" >&2
        exit 2
        ;;
esac
