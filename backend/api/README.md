# leecad-api

API over the incident database. Its own uv project, like `pipeline` and `database`. Shares a
database URL with them and nothing else; the schema belongs to `backend/database`'s migrations.
Incidents are read-only; `users` and `refresh_tokens` are the only tables it writes.

## Run

```sh
cp .env.example .env          # set DATABASE_URL and JWT_SECRET
uv sync
uv run flask --app leecad_api.app:create_app run --port 5001
```

## Test

```sh
../database/local-db.sh up
TEST_DATABASE_URL=postgresql://leecad:leecad-local-only@localhost:5433/leecad uv run pytest
```

## Endpoints

| | |
|---|---|
| `GET /api/v1/health` | liveness and dataset revision |
| `GET /api/v1/incidents` | filtered list, newest first, cursor paginated |
| `GET /api/v1/incidents?format=geojson` | same list, ready for Leaflet |
| `GET /api/v1/incidents/{source}/{id}` | one incident |
| `GET /api/v1/incident-types` | categories with counts, for filter menus |
| `GET /api/v1/stats/summary` | totals and breakdowns for charts |
| `POST /api/v1/auth/register` | create an account, signed in |
| `POST /api/v1/auth/login` | start a session |
| `POST /api/v1/auth/refresh` | swap the refresh cookie for a new access token |
| `POST /api/v1/auth/logout` | end this session |
| `GET /api/v1/users/me` | the signed-in account, needs a bearer token |

Filters: `days` or `from`/`to`, `category`, `city`, `source`, `bbox`, `mapped`. Paging: `limit`,
`cursor`.

Full parameter and response reference is in `openapi.yaml`. To click through it:

```sh
docker run --rm -p 8080:8080 -e SWAGGER_JSON=/spec/openapi.yaml \
  -v "$PWD:/spec" swaggerapi/swagger-ui
```

## Things to note

- Filter on `category`, not `nature`. Raw nature has 519 values with typos and near duplicates.
- Duplicate incidents are hidden. ~21k appear in both the Sheriff feed and the CCM import.
- Bad geocodes are repaired from CCM, but a trusted Sheriff pin is never replaced.
- GeoJSON coordinates are `[lon, lat]`.
- `by_hour` skips incidents recorded at exactly midnight, because CCM uses that to mean "time
  unknown". It reports how many it skipped.
