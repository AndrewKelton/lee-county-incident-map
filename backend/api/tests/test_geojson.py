def get(client, query=""):
    response = client.get(f"/api/v1/incidents?format=geojson&limit=500&{query}")
    assert response.status_code == 200, response.json
    return response.json


def feature(body, source_incident_id):
    matches = [f for f in body["features"]
               if f["properties"]["source_incident_id"] == source_incident_id]
    assert len(matches) == 1, f"expected one {source_incident_id}, got {len(matches)}"
    return matches[0]


def test_it_is_a_feature_collection(client):
    body = get(client)
    assert body["type"] == "FeatureCollection"
    assert all(f["type"] == "Feature" for f in body["features"])


def test_coordinates_are_longitude_then_latitude(client):
    lon, lat = feature(get(client), "25-001")["geometry"]["coordinates"]
    assert (lon, lat) == (-81.87, 26.64)


def test_feature_ids_are_unique_and_identify_the_incident(client):
    body = get(client)
    ids = [f["id"] for f in body["features"]]
    assert len(ids) == len(set(ids))
    assert feature(body, "25-001")["id"] == "lee_county:25-001"


def test_coordinates_are_not_duplicated_into_properties(client):
    props = feature(get(client), "25-001")["properties"]
    assert "lat" not in props and "lon" not in props


def test_geojson_hides_an_out_of_county_pin_by_default(client):
    ids = {f["properties"]["source_incident_id"] for f in get(client)["features"]}
    assert "25-007" not in ids


def test_mapped_false_shows_it_again(client):
    body = get(client, "mapped=false")
    ids = {f["properties"]["source_incident_id"] for f in body["features"]}
    assert "25-007" in ids


def test_a_row_without_coordinates_gets_null_geometry(client):
    body = get(client, "mapped=false&source=lee_county")
    unlocated = [f for f in body["features"] if f["geometry"] is None]
    assert unlocated, "expected at least one unlocated feature"
    assert all(f["properties"]["source_incident_id"] for f in unlocated)


def test_the_ccm_rescue_pin_is_used(client):
    lon, lat = feature(get(client), "25-003")["geometry"]["coordinates"]
    assert (lon, lat) == (-81.90, 26.70)


def test_duplicates_are_dropped_here_too(client):
    ids = [f["id"] for f in get(client)["features"]]
    assert "community_crime_map:25-001" not in ids
    assert "lee_county:25-001" in ids


def test_filters_still_apply(client):
    body = get(client, "category=BURGLARY")
    assert {f["properties"]["source_incident_id"] for f in body["features"]} == {"25-003"}


def test_pagination_metadata_is_present(client):
    body = client.get("/api/v1/incidents?format=geojson&limit=2").json
    assert body["next_cursor"]
    assert isinstance(body["dataset_revision"], int)


def test_an_unknown_format_is_rejected(client):
    response = client.get("/api/v1/incidents?format=kml")
    assert response.status_code == 400
    assert "format" in response.json["error"]
