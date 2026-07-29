def stats(client, query=""):
    response = client.get(f"/api/v1/stats/summary?{query}")
    assert response.status_code == 200, response.json
    return response.json


def as_map(rows, key):
    return {r[key]: r["count"] for r in rows}


def test_total_matches_the_incident_list(client):
    listed = client.get("/api/v1/incidents?limit=500").json["incidents"]
    assert stats(client)["total"] == len(listed)


def test_totals_exclude_ccm_duplicates(client):
    from conftest import ROWS

    assert stats(client)["total"] < len(ROWS)


def test_category_breakdown_sums_to_the_total(client):
    body = stats(client)
    assert sum(r["count"] for r in body["by_category"]) == body["total"]


def test_category_breakdown_is_biggest_first(client):
    counts = [r["count"] for r in stats(client)["by_category"]]
    assert counts == sorted(counts, reverse=True)


def test_filters_apply_the_same_way_as_the_incident_list(client):
    body = stats(client, "category=BURGLARY")
    listed = client.get("/api/v1/incidents?limit=500&category=BURGLARY").json["incidents"]
    assert body["total"] == len(listed)
    assert as_map(body["by_category"], "category") == {"BURGLARY": len(listed)}


def test_days_are_grouped_in_local_time(client):
    # 25-006 is stored at 2026-06-15 12:00 UTC, which is the 15th in Florida too.
    days = as_map(stats(client, "category=OTHER")["by_day"], "date")
    assert days == {"2026-06-15": 1}


def test_a_late_evening_utc_incident_lands_on_the_previous_local_day(client, seeded):
    import psycopg

    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("""
            INSERT INTO incidents (source, source_incident_id, occurred_at, fetched_at,
                                   last_changed, nature, raw)
            VALUES ('lee_county', 'tz-check', '2026-06-20 02:30:00+00', now(), now(),
                    'NOT A REAL NATURE', '{}'::jsonb)
        """)
    days = as_map(stats(client, "category=OTHER")["by_day"], "date")
    assert "2026-06-19" in days, f"expected the 19th in local time, got {sorted(days)}"


def test_hours_exclude_exact_midnight(client, seeded):
    import psycopg

    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("""
            INSERT INTO incidents (source, source_incident_id, occurred_at, fetched_at,
                                   last_changed, nature, raw)
            VALUES ('community_crime_map', 'midnight', '2026-06-20 04:00:00+00', now(), now(),
                    'NOT A REAL NATURE', '{}'::jsonb)
        """)
    body = stats(client, "category=OTHER")
    assert body["excluded_from_by_hour"] == 1
    assert 0 not in as_map(body["by_hour"], "hour")


def test_weekdays_use_monday_as_one(client):
    weekdays = {r["weekday"] for r in stats(client)["by_weekday"]}
    assert weekdays and weekdays <= set(range(1, 8))


def test_an_empty_result_returns_zeros_not_nulls(client):
    body = stats(client, "from=1999-01-01&to=1999-01-02")
    assert body["total"] == 0
    assert body["by_category"] == []
    assert body["by_day"] == []
    assert body["by_hour"] == []


def test_a_bad_filter_is_rejected_here_too(client):
    assert client.get("/api/v1/stats/summary?days=nope").status_code == 400
