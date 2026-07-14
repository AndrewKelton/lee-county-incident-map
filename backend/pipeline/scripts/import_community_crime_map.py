"""One time import of the CommunityCrimeMap export into incidents.

CommunityCrimeMap (a LexisNexis product) publishes the same Lee County Sheriff
incidents the pipeline already fetches, but as a complete date range sweep back to
2015 rather than an address driven crawl. The two are complementary: 80% of our
post-2015 lee_county rows are not in CCM, and CCM has 137k incidents we have never
seen. It also carries crime types the Sheriff's public API does not publish at all,
including sexual offences, arson, DUI and weapons violations.

This is a one time thing. The export was pulled by hand on 2026-06-15 with a
short lived browser token, and there is no ongoing feed. Nothing schedules this.

Run it once, against a database that is already at migration 0011:

    uv run python scripts/import_community_crime_map.py /path/to/lee_crime.csv

Idempotent. FETCHED_AT is a constant, and the upsert only accepts a row whose
fetched_at is strictly newer than the stored last_changed, so a second run is a
no-op rather than a duplicate or an error.

Three things worth knowing about the data.

The rows arrive already geocoded, 100% of them, and far more accurately than our
own geocoder manages: one row out of 158,131 falls outside Lee County, against 510
of our 103,378. So the geocode worker must never touch these. It claims rows where
lat IS NULL, and these have lat, so it will skip them on its own. Do not "fix" that.

The street numbers are anonymized to the block (8XX RIDGEWAY DR), which is why the
coordinates are block centres and why no geocoder could ever re-resolve them.

About 10% of the rows carry a timestamp of exactly midnight. That is roughly ten
times what chance would give you, so it means "time not recorded", not "happened at
midnight". Any hour of day analysis has to exclude occurred_at::time = '00:00:00'
or it will invent a spike.

The same incident can exist under lee_county and under community_crime_map, keyed
by the same Sheriff incident number, because both sources report it. That is
intentional and both rows are kept. The crawler is still running and will keep
creating more of them, so deduplication has to happen on read, in the API, not here.
"""

from __future__ import annotations

import argparse
import collections
import csv
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv

from leecad.models import NormalizedIncident
from leecad.store.postgres import PostgresStore

SOURCE = "community_crime_map"
EASTERN = ZoneInfo("America/New_York")

# The date the export was pulled. A constant, not now(), so re-running is a no-op.
FETCHED_AT = datetime(2026, 6, 15, tzinfo=timezone.utc)

# Block level. The coordinates are real, they are just the centre of the block.
GEOCODE_QUALITY = "community_crime_map:block"

BATCH = 5000

# CCM's Crime field has 454 values and is a mess of statute fragments. Its Class field has
# 26 and is clean, and Crime -> Class is 1:1 in the data. So the whole nature mapping comes
# from this one table.
#
# Where a nature already exists in nature_categories, the Sheriff's meaning wins and this is
# not applied. CCM classes DISTURBANCE as an assault and ANIMAL as non-criminal; we disagree.
CLASS_TO_CATEGORY = {
    "Assault - Simple": "VIOLENT",
    "Assault - Aggravated": "VIOLENT",
    "Robbery - Individual": "VIOLENT",
    "Robbery - Commercial": "VIOLENT",
    "Attempted Homicide": "VIOLENT",
    "Homicide / Manslaughter": "VIOLENT",
    "Weapons Violation": "FIREARM",
    "Burglary - Residential": "BURGLARY",
    "Burglary - Commercial": "BURGLARY",
    "Burglary from Motor Vehicle": "BURGLARY",
    "Theft": "THEFT",
    "Theft - Other": "THEFT",
    "Shoplifting": "THEFT",
    "Vandalism": "THEFT",
    "Arson": "THEFT",
    "Motor Vehicle Theft": "VEHICLE",
    "Fraud / Forgery": "FRAUD",
    "Drugs / Narcotics Violation": "DRUGS",
    "Sexual Assault": "SEX_OFFENSE",
    "Sexual Offense": "SEX_OFFENSE",
    "Death Investigation": "DEATH",
    "Traffic Incident": "TRAFFIC",
    "Driving Under the Influence (DUI)": "TRAFFIC",
    "Disorderly Conduct": "DISTURBANCE",
    "All Other - Non-Criminal": "NON_CRIMINAL",
    "All Other - Criminal": "OTHER",
}

# Real places in and around Lee County, plus the directional forms CCM uses for Fort Myers
# neighbourhoods. Curated on purpose. Learning this list from the data instead pulls in junk:
# CCM's own addresses yield 'FLORIDA FT', 'FL FT FORT MYERS' and 'ACRES' often enough to look
# like real city names.
PLACES = [
    "NORTH FORT MYERS", "FORT MYERS BEACH", "SAINT JAMES CITY", "BONITA SPRINGS",
    "LEHIGH ACRES", "UPPER CAPTIVA", "PUNTA GORDA", "BOCA GRANDE", "CAPE CORAL",
    "FORT MYERS", "ST JAMES CITY", "MATLACHA", "BOKEELIA", "CAPTIVA", "SANIBEL",
    "ESTERO", "NAPLES", "PLACIDA", "ALVA",
    "E FORT MYERS", "S FORT MYERS", "N FORT MYERS", "NORTH FORT MYER",
    "FORT MYERS BEAC", "N FT MYERS", "NORTH FT MYERS", "FT MYERS",
]

# CCM's Address field sometimes carries a stray comma mid-name:
#   '147XX SIX MILE CYPRESS FORT, MYERS, FL 33912'
# Splitting on commas would call the city 'MYERS'. Allowing a comma between the words of a
# place name instead resolves it to FORT MYERS. This alone removes 1,800 phantom cities.
GAZETTEER = re.compile(
    r"^(?P<street>.*?)[\s,]+(?P<city>"
    + "|".join(
        r"[\s,]+".join(map(re.escape, place.split()))
        for place in sorted(PLACES, key=len, reverse=True)
    )
    + r")[\s,]*FL[\s,]*(?P<zip>\d{5})?$",
    re.I,
)

# '8XX RIDGEWAY DR, NORTH FORT MYERS, FL 33903'
CLEAN_ADDRESS = re.compile(r"^(?P<street>.+?),\s*(?P<city>[^,]+?),\s*FL\s*(?P<zip>\d{5})?$", re.I)


def parse_address(raw: str) -> tuple[str | None, str | None]:
    """Gazetteer first, so a real place name beats a naive comma split. Recovers a city on
    93% of rows. The rest genuinely have no city in them, just a street."""
    if not raw:
        return None, None
    for pattern in (GAZETTEER, CLEAN_ADDRESS):
        match = pattern.match(raw)
        if match:
            city = re.sub(r"[\s,]+", " ", match.group("city")).strip().upper()
            return match.group("street").strip(), city
    return raw.strip(), None          # a street with no city in it at all


def normalize(row: dict) -> NormalizedIncident:
    street, city = parse_address(row["Address"])
    naive = datetime.strptime(row["DateTime"][:19], "%Y-%m-%d %H:%M:%S")
    return NormalizedIncident(
        source=SOURCE,
        source_incident_id=row["IRNumber"],      # the Sheriff's own number, shared with lee_county
        occurred_at=naive.replace(tzinfo=EASTERN).astimezone(timezone.utc),
        fetched_at=FETCHED_AT,
        lat=float(row["Latitude"]),
        lon=float(row["Longitude"]),
        nature=row["Crime"],
        address=street,
        city=city,
        geocoded_at=FETCHED_AT,
        geocode_quality=GEOCODE_QUALITY,
        raw=row,
    )


def seed_natures(connection: psycopg.Connection, rows: list[dict]) -> int:
    """Map CCM's natures onto our categories. DO NOTHING on conflict, so anything migration
    0007 already mapped keeps the Sheriff's meaning."""
    by_crime: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for row in rows:
        by_crime[row["Crime"]][row["Class"]] += 1

    unknown = {c for counts in by_crime.values() for c in counts} - set(CLASS_TO_CATEGORY)
    if unknown:
        raise SystemExit(f"CCM has Class values this script does not map: {sorted(unknown)}")

    pairs = [
        (crime, CLASS_TO_CATEGORY[counts.most_common(1)[0][0]])
        for crime, counts in by_crime.items()
    ]
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO public.nature_categories (nature, category_code)
            VALUES (%s, %s) ON CONFLICT (nature) DO NOTHING
            """,
            pairs,
        )
        added = cursor.rowcount
    connection.commit()
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv_path")
    parser.add_argument("--dry-run", action="store_true", help="parse and report, write nothing")
    args = parser.parse_args()

    load_dotenv()   # does not override anything already exported, so a shell URL still wins
    url = os.environ.get("DATABASE_WRITE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("set DATABASE_WRITE_URL (or DATABASE_URL) to a writable database")

    # Say where this is going before writing 158k rows. The same shell usually has a
    # production URL in scope, and the two look alike until they don't.
    target = urlsplit(url)
    print(f"target: {target.hostname}/{target.path.lstrip('/')}")

    with open(args.csv_path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    print(f"read {len(rows):,} rows from {args.csv_path}")

    store = PostgresStore(url)
    try:
        incidents = [normalize(row) for row in rows]
        with_city = sum(1 for i in incidents if i.city)
        print(f"parsed a city for {with_city:,} of {len(incidents):,} ({with_city/len(incidents):.1%})")

        if args.dry_run:
            print("dry run, nothing written")
            return

        added = seed_natures(store.conn, rows)
        print(f"nature_categories: {added} new mappings "
              f"(existing ones keep the Sheriff's meaning)")

        totals = collections.Counter()
        for start in range(0, len(incidents), BATCH):
            counts = store.upsert(incidents[start:start + BATCH])
            totals.update(counts)
            done = min(start + BATCH, len(incidents))
            print(f"  {done:>7,} / {len(incidents):,}   {dict(totals)}", end="\r", flush=True)
        print()
        print(f"done: {dict(totals)}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
