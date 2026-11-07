"""End-to-end HTTP tests. Skipped automatically if fastapi/httpx aren't installed."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "api.db"))
    from app.main import app

    with TestClient(app) as c:  # context manager runs startup (creates tables)
        yield c


def register_and_login(client, email="u@example.com", password="password123"):
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_duplicate_and_validation(client):
    body = {"email": "u@example.com", "password": "password123"}
    assert client.post("/auth/register", json=body).status_code == 201
    assert client.post("/auth/register", json=body).status_code == 409
    assert client.post("/auth/register", json={"email": "bad", "password": "password123"}).status_code == 422
    assert client.post("/auth/register", json={"email": "x@y.com", "password": "short"}).status_code == 422


def test_register_response_hides_password(client):
    r = client.post("/auth/register", json={"email": "u@example.com", "password": "password123"})
    assert "password" not in r.text and "hashed" not in r.text


def test_login_failures(client):
    client.post("/auth/register", json={"email": "u@example.com", "password": "password123"})
    assert client.post("/auth/login", data={"username": "u@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", data={"username": "nobody@example.com", "password": "password123"}).status_code == 401


def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_full_task_lifecycle(client):
    h = register_and_login(client)

    r = client.post("/tasks", json={"title": "  Buy milk ", "description": "2 litres"}, headers=h)
    assert r.status_code == 201
    task = r.json()
    assert task["title"] == "Buy milk" and task["completed"] is False
    tid = task["id"]

    assert client.get(f"/tasks/{tid}", headers=h).json()["title"] == "Buy milk"

    r = client.patch(f"/tasks/{tid}", json={"completed": True}, headers=h)
    assert r.status_code == 200 and r.json()["completed"] is True and r.json()["title"] == "Buy milk"

    r = client.put(f"/tasks/{tid}", json={"title": "Buy bread"}, headers=h)
    assert r.json()["title"] == "Buy bread" and r.json()["description"] is None

    assert client.delete(f"/tasks/{tid}", headers=h).status_code == 204
    assert client.get(f"/tasks/{tid}", headers=h).status_code == 404
    assert client.delete(f"/tasks/{tid}", headers=h).status_code == 404


def test_filters_and_total_header(client):
    h = register_and_login(client)
    client.post("/tasks", json={"title": "a"}, headers=h)
    client.post("/tasks", json={"title": "b", "completed": True}, headers=h)
    client.post("/tasks", json={"title": "c"}, headers=h)

    r = client.get("/tasks", headers=h)
    assert len(r.json()) == 3 and r.headers["X-Total-Count"] == "3"
    assert len(client.get("/tasks?status=completed", headers=h).json()) == 1
    assert len(client.get("/tasks?status=pending", headers=h).json()) == 2
    assert client.get("/tasks?status=bogus", headers=h).status_code == 422

    r = client.get("/tasks?limit=1&offset=1", headers=h)
    assert len(r.json()) == 1 and r.headers["X-Total-Count"] == "3"


def test_validation_errors(client):
    h = register_and_login(client)
    assert client.post("/tasks", json={"title": "   "}, headers=h).status_code == 422
    assert client.post("/tasks", json={}, headers=h).status_code == 422
    tid = client.post("/tasks", json={"title": "t"}, headers=h).json()["id"]
    assert client.patch(f"/tasks/{tid}", json={}, headers=h).status_code == 422
    assert client.patch(f"/tasks/{tid}", json={"title": None}, headers=h).status_code == 422
    assert client.get("/tasks/0", headers=h).status_code == 422
    assert client.get("/tasks/abc", headers=h).status_code == 422
    assert client.get("/tasks?limit=1000", headers=h).status_code == 422


def test_isolation_between_users(client):
    h1 = register_and_login(client, "one@example.com")
    h2 = register_and_login(client, "two@example.com")
    tid = client.post("/tasks", json={"title": "mine"}, headers=h1).json()["id"]

    assert client.get(f"/tasks/{tid}", headers=h2).status_code == 404
    assert client.patch(f"/tasks/{tid}", json={"title": "x"}, headers=h2).status_code == 404
    assert client.delete(f"/tasks/{tid}", headers=h2).status_code == 404
    assert client.get("/tasks", headers=h2).json() == []
    assert client.get(f"/tasks/{tid}", headers=h1).status_code == 200
