from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

SOURCES = ("lee_county", "lee_county_traffic", "community_crime_map")
DEFAULT_LIMIT = 100
MAX_LIMIT = 500
MAX_DAYS = 3660


@dataclass(frozen=True)
class Filters:
    start: datetime | None = None
    end: datetime | None = None
    categories: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    bbox: tuple[float, float, float, float] | None = None
    mapped_only: bool = False


def _csv(args, name: str) -> tuple[str, ...]:
    raw = args.get(name)
    if not raw:
        return ()
    return tuple(dict.fromkeys(v.strip().upper() for v in raw.split(",") if v.strip()))


def _eastern_midnight(value: str, name: str) -> datetime:
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{name} must be a date like 2026-07-01") from None
    return datetime(day.year, day.month, day.day, tzinfo=EASTERN).astimezone(UTC)


def _bbox(raw: str) -> tuple[float, float, float, float]:
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError("bbox must be west,south,east,north")
    try:
        west, south, east, north = (float(p) for p in parts)
    except ValueError:
        raise ValueError("bbox values must be numbers") from None
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError("bbox longitudes must be between -180 and 180")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError("bbox latitudes must be between -90 and 90")
    if west >= east or south >= north:
        raise ValueError("bbox must be west,south,east,north with west < east and south < north")
    return west, south, east, north


def parse(args) -> Filters:
    start = end = None

    if "days" in args:
        if "from" in args or "to" in args:
            raise ValueError("use either days or from/to, not both")
        try:
            days = int(args["days"])
        except ValueError:
            raise ValueError("days must be a whole number") from None
        if not 1 <= days <= MAX_DAYS:
            raise ValueError(f"days must be between 1 and {MAX_DAYS}")
        start = datetime.now(UTC) - timedelta(days=days)
    else:
        if "from" in args:
            start = _eastern_midnight(args["from"], "from")
        if "to" in args:
            end = _eastern_midnight(args["to"], "to") + timedelta(days=1)
    if start and end and start >= end:
        raise ValueError("from must be earlier than to")

    sources = _csv(args, "source")
    sources = tuple(s.lower() for s in sources)
    unknown = [s for s in sources if s not in SOURCES]
    if unknown:
        raise ValueError(f"unknown source {unknown[0]}; valid values are {', '.join(SOURCES)}")

    bbox = _bbox(args["bbox"]) if args.get("bbox") else None

    mapped = args.get("mapped", "").lower()
    if mapped not in ("", "true", "false"):
        raise ValueError("mapped must be true or false")

    return Filters(
        start=start,
        end=end,
        categories=_csv(args, "category"),
        cities=_csv(args, "city"),
        sources=sources,
        bbox=bbox,
        mapped_only=mapped == "true",
    )


def parse_limit(args) -> int:
    raw = args.get("limit")
    if raw is None:
        return DEFAULT_LIMIT
    try:
        limit = int(raw)
    except ValueError:
        raise ValueError("limit must be a whole number") from None
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    return limit
