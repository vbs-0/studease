"""API test fixtures: the injected starter dataset loaded into the test database, five demo logins, a test client.

`loaded` reloads before each test that asks for it (a few hundred ms), so tests that write never affect each other."""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.engine import detect, loader, users

PASSWORD = "a-long-demo-password-1"


@pytest.fixture(scope="session")
def client(db_engine):
    from app.main import app
    original = db.engine
    db.engine = db_engine                      # get_conn looks the engine up at call time
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    db.engine = original


@pytest.fixture
def loaded(db_engine, injected, client):
    ds, gt = injected
    loader.load(db_engine, ds, gt, detect.run(ds))
    seeded = users.seed_users(db_engine, PASSWORD)
    return {"ds": ds, "gt": gt, "users": {u["role"]: u for u in seeded}, "engine": db_engine}


class Session:
    """A signed-in caller: `s.get(...)`, `s.post(...)` carry the bearer token."""
    def __init__(self, client, role, env):
        self.client, self.role = client, role
        self.user = env["users"][role]
        res = client.post("/api/v1/auth/login", json={"email": self.user["email"], "password": PASSWORD})
        assert res.status_code == 200, res.text
        self.token = res.json()["token"]

    def headers(self, extra=None):
        return {"Authorization": f"Bearer {self.token}", **(extra or {})}

    def get(self, url, **kw):
        return self.client.get("/api/v1" + url, headers=self.headers(), **kw)

    def post(self, url, json=None, headers=None):
        return self.client.post("/api/v1" + url, json=json, headers=self.headers(headers))


@pytest.fixture
def as_role(client, loaded):
    def make(role):
        return Session(client, role, loaded)
    return make


def clean_students(env):
    """Students with no labelled anomaly, in id order: their books must reconcile exactly."""
    labelled = {g["student_id"] for g in env["gt"]}
    return [s["student_id"] for s in env["ds"]["student"] if s["student_id"] not in labelled]
