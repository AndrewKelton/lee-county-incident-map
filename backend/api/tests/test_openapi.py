import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

SPEC = Path(__file__).resolve().parent.parent / "openapi.yaml"


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(SPEC.read_text())


def app_routes(app):
    routes = set()
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/api/") and "GET" in rule.methods:
            routes.add(re.sub(r"<(?:[^>:]+:)?([^>]+)>", r"{\1}", rule.rule))
    return routes


def spec_routes(spec):
    return set(spec["paths"])


def test_the_spec_documents_every_route(app_for_spec, spec):
    missing = app_routes(app_for_spec) - spec_routes(spec)
    assert not missing, f"routes missing from openapi.yaml: {sorted(missing)}"


def test_the_spec_has_no_routes_that_do_not_exist(app_for_spec, spec):
    extra = spec_routes(spec) - app_routes(app_for_spec)
    assert not extra, f"openapi.yaml documents routes the app does not serve: {sorted(extra)}"


def test_documented_query_parameters_are_real(spec):
    from leecad_api.filters import MAX_DAYS, MAX_LIMIT

    params = spec["components"]["parameters"]
    assert params["days"]["schema"]["maximum"] == MAX_DAYS
    assert params["limit"]["schema"]["maximum"] == MAX_LIMIT


def test_the_incident_schema_matches_what_the_api_returns(client, spec):
    documented = set(spec["components"]["schemas"]["Incident"]["properties"])
    returned = set(client.get("/api/v1/incidents?limit=1").json["incidents"][0])
    assert documented == returned
