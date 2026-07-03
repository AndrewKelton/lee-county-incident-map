import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("LEECAD_DATA_DIR", "data")).resolve()

INCIDENTS_DB = DATA_DIR / "incidents.db"
GEOCODE_CACHE_DB = DATA_DIR / "geocode_cache.db"

STREET_QUERIES = Path(os.environ.get("LEECAD_STREET_QUERIES", str(DATA_DIR / "seeds" / "street_queries.txt")))