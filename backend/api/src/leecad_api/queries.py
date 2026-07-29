import base64
from datetime import datetime

FROM_AND_JOINS = """
    FROM incidents i
    LEFT JOIN incidents twin
           ON i.source = 'lee_county'
          AND twin.source = 'community_crime_map'
          AND twin.source_incident_id = i.source_incident_id
          AND (i.lat IS NULL OR i.geocode_trusted IS false OR i.location_quality = 'out_of_county')
    LEFT JOIN nature_categories nc ON nc.nature = i.nature
    LEFT JOIN city_aliases ca ON ca.raw_city = i.city
"""

NOT_A_DUPLICATE = """
    NOT EXISTS (SELECT 1 FROM incidents lc
                 WHERE lc.source = 'lee_county'
                   AND lc.source_incident_id = i.source_incident_id
                   AND i.source = 'community_crime_map')
"""

COLUMNS = """
    SELECT i.source,
           i.source_incident_id,
           i.occurred_at,
           i.nature,
           COALESCE(nc.category_code, 'OTHER') AS category,
           i.address,
           CASE WHEN ca.raw_city IS NOT NULL THEN ca.canonical_city ELSE i.city END AS city,
           COALESCE(twin.lat, i.lat) AS lat,
           COALESCE(twin.lon, i.lon) AS lon,
           i.disposition,
           i.status
"""

ORDER = " ORDER BY i.occurred_at DESC, i.source DESC, i.source_incident_id DESC"


def encode_cursor(row: dict) -> str:
    raw = f"{row['occurred_at'].isoformat()}|{row['source']}|{row['source_incident_id']}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        occurred_at, source, source_incident_id = raw.split("|", 2)
        return datetime.fromisoformat(occurred_at), source, source_incident_id
    except (ValueError, UnicodeDecodeError):
        raise ValueError("cursor is not valid") from None


def _conditions(filters) -> tuple[list[str], list]:
    where = [NOT_A_DUPLICATE]
    params: list = []

    if filters.start:
        where.append("i.occurred_at >= %s")
        params.append(filters.start)
    if filters.end:
        where.append("i.occurred_at < %s")
        params.append(filters.end)

    if filters.sources:
        where.append("i.source = ANY(%s)")
        params.append(list(filters.sources))

    if filters.categories:
        clause = """(i.nature IN (SELECT nature FROM nature_categories
                                  WHERE category_code = ANY(%s))"""
        params.append(list(filters.categories))
        if "OTHER" in filters.categories:
            clause += """
                   OR i.nature IS NULL
                   OR i.nature NOT IN (SELECT nature FROM nature_categories)"""
        where.append(clause + ")")

    if filters.cities:
        where.append("""(i.city = ANY(%s)
                      OR i.city IN (SELECT raw_city FROM city_aliases
                                     WHERE canonical_city = ANY(%s)))""")
        params.append(list(filters.cities))
        params.append(list(filters.cities))

    if filters.bbox:
        where.append("i.geom && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), 26959)")
        params.extend(filters.bbox)

    if filters.mapped_only:
        where.append("""((i.location_quality = 'in_county' AND i.geocode_trusted)
                      OR twin.lat IS NOT NULL)""")

    return where, params


def incident_list(filters, limit: int, cursor: str | None) -> tuple[str, list]:
    where, params = _conditions(filters)

    if cursor:
        where.append("(i.occurred_at, i.source, i.source_incident_id) < (%s, %s, %s)")
        params.extend(decode_cursor(cursor))

    sql = COLUMNS + FROM_AND_JOINS + " WHERE " + " AND ".join(where) + ORDER + " LIMIT %s"
    params.append(limit + 1)
    return sql, params
