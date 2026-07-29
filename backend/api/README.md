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

Point `DATABASE_URL` at a read-only role. `baseline_auditor` on Neon is that role.

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
| `GET /api/v1/incidents` | filtered list, newest first, cursor paginated |
| `GET /api/v1/incidents?format=geojson` | the same list as a FeatureCollection for Leaflet |
| `GET /api/v1/incidents/{source}/{id}` | one incident |
| `GET /api/v1/incident-types` | category catalog with counts, for filter menus |
| `GET /api/v1/stats/summary` | totals and breakdowns for charts |

Filters shared by the list and the stats endpoints: `days` or `from`/`to`, `category`, `city`,
`source`, `bbox`, `mapped`. Paging uses `limit` and `cursor`.

## API reference

`openapi.yaml` documents every parameter and response. To click through it:

```sh
docker run --rm -p 8080:8080 -e SWAGGER_JSON=/spec/openapi.yaml \
  -v "$PWD:/spec" swaggerapi/swagger-ui
```

Then open http://localhost:8080. It also imports into Postman and Bruno.

`tests/test_openapi.py` fails if the spec and the routes disagree, so adding an endpoint without
documenting it breaks the build.

## Three rules every endpoint applies

Callers never deal with these.

**Duplicates are hidden.** About 21,000 incidents appear in both the Sheriff feed and the
CommunityCrimeMap import under the same number. Only the Sheriff copy is returned, including from
the detail endpoint.

**Bad coordinates are repaired.** Where the Sheriff's pin is missing, outside Lee County, or from a
geocoder tier known to return street centroids, CommunityCrimeMap's coordinate is used instead. A
trusted Sheriff pin is never replaced, because it is the more precise of the two.

**Raw `nature` is mapped to a stable `category`.** The feed has 519 distinct nature values including
near duplicates and upstream typos. Filter on `category`. An unmapped nature reads as `OTHER`.

Two smaller ones worth knowing: GeoJSON coordinates are `[longitude, latitude]`, and `by_hour` in the
stats response leaves out incidents recorded at exactly midnight, because the CommunityCrimeMap
import uses midnight to mean "time not recorded". The response says how many were left out.
