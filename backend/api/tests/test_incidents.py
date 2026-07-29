def get(client, query=""):
    response = client.get(f"/api/v1/incidents?limit=500&{query}")
    assert response.status_code == 200, response.json
    return response.json["incidents"]


def ids(incidents):
    return {(i["source"], i["source_incident_id"]) for i in incidents}


def one(incidents, source_incident_id):
    matches = [i for i in incidents if i["source_incident_id"] == source_incident_id]
    assert len(matches) == 1, f"expected exactly one {source_incident_id}, got {len(matches)}"
    return matches[0]


def test_a_ccm_duplicate_is_dropped(client):
    found = get(client)
    assert ("community_crime_map", "25-001") not in ids(found)
    assert ("lee_county", "25-001") in ids(found)


def test_a_ccm_only_incident_is_kept(client):
    assert ("community_crime_map", "25-002") in ids(get(client))


def test_ccm_coordinates_rescue_a_row_with_no_pin(client):
    row = one(get(client), "25-003")
    assert row["source"] == "lee_county"
    assert (row["lat"], row["lon"]) == (26.70, -81.90)


def test_ccm_coordinates_replace_an_untrusted_pin(client):
    row = one(get(client), "25-004")
    assert (row["lat"], row["lon"]) == (26.44, -81.81)


def test_a_trusted_pin_is_not_replaced_by_ccm(client):
    row = one(get(client), "25-005")
    assert (row["lat"], row["lon"]) == (26.45, -82.02)


def test_an_unmapped_nature_reads_as_other(client):
    assert one(get(client), "25-006")["category"] == "OTHER"


def test_a_known_nature_reads_as_its_category(client):
    assert one(get(client), "25-001")["category"] == "VIOLENT"


def test_city_is_canonicalized(client):
    assert one(get(client), "25-003")["city"] == "NORTH FORT MYERS"


def test_category_filter(client):
    found = get(client, "category=BURGLARY")
    assert {i["source_incident_id"] for i in found} == {"25-003"}


def test_other_category_includes_unmapped_natures(client):
    assert "25-006" in {i["source_incident_id"] for i in get(client, "category=OTHER")}


def test_city_filter_matches_alias_spellings(client):
    found = get(client, "city=NORTH FORT MYERS")
    assert {i["source_incident_id"] for i in found} == {"25-003"}


def test_source_filter(client):
    found = get(client, "source=lee_county_traffic")
    assert {i["source_incident_id"] for i in found} == {"T-001"}


def test_mapped_only_excludes_an_out_of_county_pin(client):
    assert "25-007" in {i["source_incident_id"] for i in get(client)}
    assert "25-007" not in {i["source_incident_id"] for i in get(client, "mapped=true")}


def test_mapped_only_keeps_a_row_rescued_by_ccm(client):
    assert "25-003" in {i["source_incident_id"] for i in get(client, "mapped=true")}


def test_bbox_filter(client):
    found = get(client, "bbox=-82.10,26.40,-82.00,26.50")
    assert {i["source_incident_id"] for i in found} == {"25-005"}


def test_date_range_filter(client):
    found = get(client, "from=2026-06-15&to=2026-06-15")
    assert {i["source_incident_id"] for i in found} == {"25-006"}


def test_results_are_newest_first(client):
    times = [i["occurred_at"] for i in get(client)]
    assert times == sorted(times, reverse=True)


def test_pagination_returns_every_row_exactly_once_across_tied_timestamps(client):
    seen, cursor, pages = [], None, 0
    while True:
        url = "/api/v1/incidents?limit=2" + (f"&cursor={cursor}" if cursor else "")
        body = client.get(url).json
        seen += [(i["source"], i["source_incident_id"]) for i in body["incidents"]]
        cursor = body["next_cursor"]
        pages += 1
        if not cursor or pages > 50:
            break
    assert len(seen) == len(set(seen))
    assert set(seen) == ids(get(client))


def test_an_invalid_filter_explains_itself(client):
    response = client.get("/api/v1/incidents?days=nope")
    assert response.status_code == 400
    assert "days" in response.json["error"]


def test_a_tampered_cursor_is_rejected(client):
    response = client.get("/api/v1/incidents?cursor=notbase64!!")
    assert response.status_code == 400
