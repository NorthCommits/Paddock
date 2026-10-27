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


async def test_every_response_reports_how_long_it_took(fake_client):
    response = await fake_client.get("/healthz")
    assert response.headers["server-timing"].startswith("app;dur=")


async def test_warmz_wakes_the_database_and_returns_quickly(fake_client, monkeypatch):
    from app.api import health

    monkeypatch.setattr(health, "_last_poke", 0.0)
    monkeypatch.setattr(health, "_content_answers", lambda: "ready")
    response = await fake_client.get("/warmz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "content": "checking"}


async def test_warmz_reports_database_trouble(fake_client, fake_session):
    fake_session.fail = True
    response = await fake_client.get("/warmz")
    assert response.status_code == 503


async def test_warmz_wait_answers_once_content_is_awake(fake_client, monkeypatch):
    from app.api import health

    answers = iter(["waking", "waking", "ready"])
    paused = []

    async def no_pause():
        paused.append(1)

    monkeypatch.setattr(health, "_content_answers", lambda: next(answers))
    monkeypatch.setattr(health, "_pause", no_pause)
    response = await fake_client.get("/warmz?wait=content")
    assert response.json() == {"status": "ok", "content": "ready"}
    assert len(paused) == 2


async def test_warmz_wait_gives_up_when_nothing_listens(fake_client, monkeypatch):
    from app.api import health

    monkeypatch.setattr(health, "_content_answers", lambda: "down")
    response = await fake_client.get("/warmz?wait=content")
    assert response.json()["content"] == "down"


async def test_warmz_wait_stops_waiting_after_the_limit(fake_client, monkeypatch):
    from app.api import health

    async def no_pause():
        pass

    monkeypatch.setattr(health, "WAIT_SECONDS", 0)
    monkeypatch.setattr(health, "_content_answers", lambda: "waking")
    monkeypatch.setattr(health, "_pause", no_pause)
    response = await fake_client.get("/warmz?wait=content")
    assert response.json()["content"] == "waking"
