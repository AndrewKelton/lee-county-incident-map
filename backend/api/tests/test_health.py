def test_health_reports_the_dataset_revision(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert isinstance(response.json["dataset_revision"], int)


def test_health_reports_503_when_the_database_is_unreachable():
    from leecad_api.app import create_app

    client = create_app("postgresql://nobody@127.0.0.1:1/nowhere").test_client()
    response = client.get("/api/v1/health")
    assert response.status_code == 503
