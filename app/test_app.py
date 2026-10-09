from app import app


def test_health():
    r = app.test_client().get("/health")
    assert r.status_code == 200
    assert r.json["status"] == "ok"


def test_home_has_version():
    r = app.test_client().get("/")
    assert r.status_code == 200
    assert "version" in r.json
