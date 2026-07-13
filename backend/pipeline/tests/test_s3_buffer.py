def test_put_list_get_delete_round_trip(buffer, fake_s3):
    records = [
        {"source": "lee_county", "source_incident_id": "A-1"},
        {"source": "lee_county", "source_incident_id": "A-2"},
    ]

    key = buffer.put("lee_county", records)
    assert key.startswith("pending/lee_county/")
    assert buffer.list_pending() == [key]
    assert buffer.get(key) == records

    buffer.delete([key])
    assert buffer.list_pending() == []
    assert fake_s3.objects == {}


def test_put_empty_batch_writes_nothing(buffer, fake_s3):
    assert buffer.put("lee_county", []) is None
    assert fake_s3.objects == {}
    assert buffer.list_pending() == []
