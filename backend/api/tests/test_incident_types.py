def types(client):
    response = client.get("/api/v1/incident-types")
    assert response.status_code == 200, response.json
    return response.json["types"]


def by_code(client):
    return {t["code"]: t for t in types(client)}


def test_every_category_is_listed(client):
    codes = by_code(client)
    assert "OTHER" in codes
    assert "VIOLENT" in codes
    assert len(codes) > 10


def test_a_category_with_no_incidents_still_appears(client):
    assert by_code(client)["DEATH"]["incident_count"] == 0


def test_counts_exclude_ccm_duplicates(client):
    from conftest import CCM, ROWS

    assault = [r for r in ROWS if r[3] == "ASSAULT"]
    duplicated = [r for r in assault if r[0] == CCM]
    assert len(assault) == 9 and len(duplicated) == 2
    assert by_code(client)["VIOLENT"]["incident_count"] == len(assault) - len(duplicated)


def test_an_unmapped_nature_counts_as_other(client):
    assert by_code(client)["OTHER"]["incident_count"] == 1


def test_results_are_sorted_for_display(client):
    orders = [t["sort_order"] for t in types(client)]
    assert orders == sorted(orders)


def test_each_entry_has_what_a_dropdown_needs(client):
    entry = by_code(client)["VIOLENT"]
    assert entry["label"]
    assert isinstance(entry["incident_count"], int)


def test_new_incidents_change_the_counts(client, seeded):
    import psycopg

    before = by_code(client)["BURGLARY"]["incident_count"]
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("""
            INSERT INTO incidents (source, source_incident_id, occurred_at, fetched_at,
                                   last_changed, nature, raw)
            VALUES ('lee_county', 'cache-check', now(), now(), now(), 'BURGLARY', '{}'::jsonb)
        """)
    assert by_code(client)["BURGLARY"]["incident_count"] == before + 1
