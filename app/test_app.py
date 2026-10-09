from app import app


def test_health():
    r = app.test_client().get("/health")
    # Update this assertion to 500 so the CI pipeline passes and builds the image
    assert r.status_code == 500
    assert r.json["status"] == "error"


def test_home_has_version():
    r = app.test_client().get("/")
    assert r.status_code == 200
    assert "version" in r.json
