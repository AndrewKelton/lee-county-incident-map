# Lee County Sheriff Activity — Data Pipeline

A resilient, cloud-deployed ingestion pipeline that collects, normalizes, geocodes, and archives public Computer-Aided Dispatch (CAD) data from the Lee County (FL) Sheriff's Office. It is the data-collection backend for an interactive map that visualizes public-safety incidents geographically and over time.

This repository is the **ingestion layer** of a larger UCF Senior Design project. It runs autonomously in the cloud, accumulating a clean, geocoded, queryable history of sheriff incidents and traffic crashes that downstream components (an interactive map, heatmaps, DBSCAN clustering, and trend analysis) build on top of.

---

## What it does

Every scheduled run, the pipeline:

1. **Fetches** the latest public CAD records from a Lee County API.
2. **Normalizes** each record into a single canonical schema, regardless of the source's quirks.
3. **Geocodes** addresses to coordinates using a three-tier fallback strategy, with a persistent cache so each address is resolved at most once.
4. **Stores** the results idempotently — new records are inserted, existing ones are deduplicated, missing coordinates are backfilled, and live status changes are updated in place.

Two feeds run on independent schedules:

- **Sheriff incidents** — the general CAD feed (disturbances, thefts, animal calls, etc.). The API returns the most recent ~1,000 records (≈ two weeks of activity), so this runs every 12 hours.
- **Traffic crashes** — a separate feed that returns only the 5 most recent active calls, so it runs every 5 minutes to avoid missing records as they roll off.

---

## Architecture

![Architecture](docs/architecture.svg)

The design is built around three swappable abstractions, so adding a data source, changing a geocoder, or switching storage backends never requires touching unrelated code.

### Adapters (`adapters/`)

Each data source is a self-contained adapter implementing a common `IncidentSource` interface with two responsibilities: `fetch_raw()` (hit the API, return raw records) and `normalize(raw, fetched_at)` (map one raw record to the canonical model). The only code that knows anything source-specific lives in its adapter. Adding a new source — a new county, should one ever publish a public API — is a single new file plus one line in the runner's registry.

### Canonical model (`models.py`)

Every adapter emits a `NormalizedIncident` (a Pydantic model). Downstream code only ever sees this one type, never a source's raw shape. The full original payload is preserved in a `raw` field so no information is lost and new fields can be backfilled later.

### Geocoding (`geocoding/`)

Addresses arrive as free text and must be resolved to coordinates. No single free geocoder handles every case, so the pipeline chains three behind a common interface, trying each in order until one succeeds:

1. **Census Geocoder** — fast and parallel, handles standard street addresses (`535 PINE ISLAND RD`).
2. **Overpass / OpenStreetMap** — resolves *intersections* (`CLAYTON AVE / LEELAND HEIGHTS BLVD E`) by finding the two named roads in OSM and returning the node they physically share. Census cannot do this, and intersections are a large fraction of CAD addresses — especially for traffic crashes.
3. **Nominatim** — a fuzzy last-resort fallback for unusual addresses the first two miss.

A persistent **cache** (keyed on the normalized address) ensures each unique location is geocoded only once, ever. Rate-limited geocoders (Overpass, Nominatim) are throttled to respect their public usage policies. Results are tagged with which geocoder resolved them, so coordinate provenance is queryable.

### Storage (`store/`)

A common `IncidentStore` interface with two implementations:

- **`SqliteStore`** — zero-setup local development; the database is a single file under `data/`.
- **`PostgresStore`** — production storage on Neon, with `ON CONFLICT` upserts for efficient batch writes.

The runner selects the backend automatically from the `DATABASE_URL` environment variable: unset → SQLite (local), set → Postgres (cloud). The same is true for the geocoding cache. Nothing else in the codebase changes between environments.

Upserts are idempotent and dedup on `(source, source_incident_id)`. They backfill coordinates only when a stored record previously lacked them, and update a record's live `status` when it changes — which lays the groundwork for a real-time view of active calls.

### Runner (`runner.py`)

`run_source(name)` is the single orchestration path used by the CLI, local runs, and the Lambda handler alike. It resolves the adapter, fetches, normalizes, geocodes in parallel (a thread pool, with the rate-limited geocoders self-throttling), and upserts — returning a summary of inserted / updated / skipped counts.

---

## Project structure

```
.
├── adapters/
│   ├── base.py                 # IncidentSource interface + shared HTTP helpers
│   ├── lee_county.py           # Sheriff incidents adapter
│   └── lee_county_traffic.py   # Traffic crashes adapter
├── geocoding/
│   ├── base.py                 # Geocoder + GeocodeCache interfaces
│   ├── census.py               # Census Geocoder (standard addresses)
│   ├── overpass.py             # OpenStreetMap intersection geocoder
│   ├── nominatim.py            # Fuzzy fallback geocoder
│   ├── composite.py            # Chains geocoders; first hit wins
│   ├── postgres_cache.py       # PostgresCache
│   ├── sqlite_cache.py         # SqliteCache
│   └── service.py              # Cache-then-geocode service
├── store/
│   ├── base.py                 # IncidentStore interface
│   ├── sqlite.py               # Local file-based storage
│   └── postgres.py             # Neon / production storage
├── scripts/
│   ├── backfill_geocode.py     # Re-geocode records with missing coordinates
│   ├── migrate_to_postgres.py  # One-time SQLite → Neon migration
│   └── smoke.py                # Initial end-to-end sanity check
├── tests/
│   ├── test_lee_county.py      # Adapter normalization tests
│   └── fixtures/
│       └── lee_county_sample.json
├── data/                       # Local SQLite DBs (git-ignored)
├── models.py                   # NormalizedIncident canonical schema
├── runner.py                   # Orchestration + backend selection
├── paths.py                    # CWD-independent path anchoring
├── lambda_handler.py           # AWS Lambda entry point
├── pyproject.toml              # Source of truth for dependencies
├── uv.lock
└── README.md
```

---

## Data model

Each record is stored with the following fields:

| Field | Description |
|---|---|
| `source` | Which feed it came from (e.g. `lee_county`, `lee_county_traffic`) |
| `source_incident_id` | The source's own incident/call identifier |
| `occurred_at` | When the incident happened (stored in UTC) |
| `fetched_at` | When the pipeline retrieved it (UTC) |
| `lat`, `lon` | Coordinates (null if unresolvable) |
| `nature` | Call type, e.g. `CRASH`, `DISTURBANCE`, `SHOTS FIRED` |
| `disposition` | Outcome, where provided |
| `address`, `city` | Reported location |
| `geocoded_at` | When coordinates were derived (null = coords came from the source) |
| `geocode_quality` | Which geocoder resolved it and its confidence |
| `status` | Live dispatch status, e.g. `ASSIGNED`, `ARRIVED` (traffic feed) |
| `raw` | The complete original payload |

`(source, source_incident_id)` is the primary key. Indexes support time-range and geographic queries.

---

## Running locally

Requires [uv](https://github.com/astral-sh/uv) and Python 3.12+.

```bash
# Install dependencies
uv sync

# Run a single feed (writes to a local SQLite DB under data/ when DATABASE_URL is unset)
uv run python runner.py lee_county
uv run python runner.py lee_county_traffic

# Run against Postgres instead — just set the connection string
DATABASE_URL="postgresql://..." uv run python runner.py lee_county

# Run the tests
uv run pytest
```

Useful utilities in `scripts/`:

```bash
# Re-attempt geocoding for any stored records still missing coordinates
uv run python scripts/backfill_geocode.py 150

# Migrate a local SQLite database into Postgres (one-time)
PG_URL="postgresql://..." uv run python scripts/migrate_to_postgres.py
```

---

## Deployment

The pipeline runs serverlessly:

- **Compute** — a single AWS Lambda function (`lambda_handler.handler`) that dispatches on the `source` field of its event payload. The same function serves every feed.
- **Scheduling** — two Amazon EventBridge schedules invoke the Lambda with different payloads: `{"source": "lee_county"}` every 12 hours and `{"source": "lee_county_traffic"}` every 5 minutes.
- **Storage** — a Neon (serverless Postgres) database holds both the `incidents` and `geocode_cache` tables. The Lambda connects via Neon's pooled connection string, set as the `DATABASE_URL` environment variable.

Deployment artifact is a `.zip` built with Linux-targeted wheels so the compiled dependencies (`psycopg`, `pydantic-core`) run on Lambda's runtime:

```bash
uv pip install --python-platform x86_64-manylinux2014 --python-version 3.12 \
  --target build/package --only-binary :all: -r requirements.txt
cp -r adapters geocoding store build/package/
cp models.py runner.py paths.py lambda_handler.py build/package/
cd build/package && zip -rq ../lambda.zip . && cd ../..
```

---

## Data sources & design principles

All data is sourced exclusively from **official public APIs**. The Lee County Sheriff's Office publishes a public incidents API and a public active-traffic-calls endpoint; this pipeline consumes only those. No scraping of non-API sources is performed — a deliberate constraint that keeps the project on firm ethical and legal footing and reflects the broader goal of encouraging agencies to publish open data.

Lee County is currently the only Florida county with a suitable public API. The adapter architecture is built so that additional counties can be added trivially **if and when** they publish public endpoints — the limiting factor is data availability, not code.

All incident data is public record under Florida's Sunshine Laws (Chapter 119, Florida Statutes).

## Notable engineering

- **Resilience** — transient API failures are retried with exponential backoff; geocoding failures are non-fatal (a record is stored without coordinates rather than failing the whole batch); the scheduler and a dead-letter configuration provide an outer retry layer.
- **Idempotency** — every run is safe to repeat. Re-running never duplicates data; the dedup and cache layers make redundant work essentially free.
- **Cost-aware** — the geocoding cache, request throttling, and conservative scheduling keep the system comfortably within free-tier limits across AWS Lambda, Neon, and the public geocoders.
- **Environment parity** — a single environment variable switches the entire data layer between local SQLite and cloud Postgres, with no code changes.

## Known limitations

- A small, roughly constant set of addresses (highway mile markers, corrupted CAD entries, named landmarks) cannot be resolved by any free geocoder and are stored without coordinates. This is an inherent ceiling of free geocoding, not a defect — geocoded coverage sits in the mid-90% range, which is more than sufficient for density-based visualization and clustering.
- The sheriff API exposes only the most recent ~1,000 records and offers no historical pagination, so deep historical backfill depends on a public-records request rather than the API.

## Acknowledgments

Geocoding is powered by the [U.S. Census Geocoder](https://geocoding.geo.census.gov/), [OpenStreetMap](https://www.openstreetmap.org/) via the [Overpass API](https://overpass-api.de/), and [Nominatim](https://nominatim.org/). Built as part of a Senior Design capstone at the University of Central Florida.

## License

[MIT](LICENSE)