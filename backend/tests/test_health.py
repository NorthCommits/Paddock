async def test_healthz_is_ok(fake_client):
    response = await fake_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_is_ready_when_database_answers(fake_client):
    response = await fake_client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readyz_reports_unavailable_when_database_fails(fake_client, fake_session):
    fake_session.fail = True
    response = await fake_client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


async def test_readyz_works_against_the_real_test_database(client):
    response = await client.get("/readyz")
    assert response.status_code == 200


async def test_every_response_has_a_request_id(fake_client):
    response = await fake_client.get("/healthz")
    assert response.headers["x-request-id"]


async def test_request_id_from_caller_is_kept(fake_client):
    response = await fake_client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assert response.headers["x-request-id"] == "abc123"


async def test_unknown_path_uses_the_error_shape(fake_client):
    response = await fake_client.get("/v1/nothing-here")
    body = response.json()
    assert response.status_code == 404
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"]
