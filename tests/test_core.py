"""Tests for the layers that don't need FastAPI: security, schemas, database/CRUD."""
import sqlite3
from datetime import timedelta

import pytest
from pydantic import ValidationError

from app import crud, database, security
from app.schemas import TaskCreate, TaskUpdate, UserCreate


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    database.init_db()
    c = database.get_connection()
    yield c
    c.close()


@pytest.fixture
def user(conn):
    return crud.create_user(conn, "a@example.com", security.hash_password("password123"))


# ---------- security ----------
def test_password_hash_roundtrip():
    h = security.hash_password("s3cret-pass")
    assert h != "s3cret-pass"
    assert security.verify_password("s3cret-pass", h)
    assert not security.verify_password("wrong", h)


def test_password_hashes_are_salted():
    assert security.hash_password("same") != security.hash_password("same")


def test_verify_rejects_malformed_hash():
    assert not security.verify_password("x", "garbage")
    assert not security.verify_password("x", "bcrypt$1$2$3$4$5")


def test_token_roundtrip_and_tamper():
    token = security.create_access_token(42)
    assert security.decode_access_token(token) == 42
    assert security.decode_access_token(token + "x") is None
    assert security.decode_access_token("not.a.token") is None


def test_expired_token_rejected():
    token = security.create_access_token(1, expires_delta=timedelta(seconds=-5))
    assert security.decode_access_token(token) is None


# ---------- schemas ----------
def test_task_title_is_trimmed_and_required():
    assert TaskCreate(title="  Buy milk  ").title == "Buy milk"
    for bad in ("", "   "):
        with pytest.raises(ValidationError):
            TaskCreate(title=bad)
    with pytest.raises(ValidationError):
        TaskCreate(title="x" * 201)


def test_patch_requires_a_field_and_rejects_null():
    with pytest.raises(ValidationError):
        TaskUpdate()
    with pytest.raises(ValidationError):
        TaskUpdate(title=None)
    with pytest.raises(ValidationError):
        TaskUpdate(completed=None)
    assert TaskUpdate(description=None).model_dump(exclude_unset=True) == {"description": None}


def test_user_validation():
    assert UserCreate(email="  Bob@Example.COM ", password="longenough").email == "bob@example.com"
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="longenough")
    with pytest.raises(ValidationError):
        UserCreate(email="b@example.com", password="short")


# ---------- crud: users ----------
def test_duplicate_email_raises(conn, user):
    with pytest.raises(sqlite3.IntegrityError):
        crud.create_user(conn, "a@example.com", "h")


# ---------- crud: tasks ----------
def test_create_get_update_delete(conn, user):
    t = crud.create_task(conn, user["id"], "Write tests", "cover crud")
    assert t["completed"] == 0 and t["description"] == "cover crud"

    assert crud.get_task(conn, t["id"], user["id"])["title"] == "Write tests"

    updated = crud.update_task(conn, t["id"], user["id"], {"completed": True, "title": "Done"})
    assert updated["completed"] == 1 and updated["title"] == "Done"
    assert updated["updated_at"] >= t["updated_at"]

    assert crud.delete_task(conn, t["id"], user["id"]) is True
    assert crud.get_task(conn, t["id"], user["id"]) is None
    assert crud.delete_task(conn, t["id"], user["id"]) is False


def test_update_missing_task_returns_none(conn, user):
    assert crud.update_task(conn, 999, user["id"], {"title": "x"}) is None


def test_update_ignores_unknown_columns(conn, user):
    t = crud.create_task(conn, user["id"], "keep")
    out = crud.update_task(conn, t["id"], user["id"], {"owner_id": 99, "id": 5, "title": "new"})
    assert out["owner_id"] == user["id"] and out["id"] == t["id"] and out["title"] == "new"


def test_status_filter(conn, user):
    crud.create_task(conn, user["id"], "open 1")
    crud.create_task(conn, user["id"], "open 2")
    crud.create_task(conn, user["id"], "closed", completed=True)

    assert crud.list_tasks(conn, user["id"], "all")[1] == 3
    pending, n_pending = crud.list_tasks(conn, user["id"], "pending")
    assert n_pending == 2 and all(t["completed"] == 0 for t in pending)
    done, n_done = crud.list_tasks(conn, user["id"], "completed")
    assert n_done == 1 and done[0]["title"] == "closed"


def test_pagination_and_total(conn, user):
    for i in range(5):
        crud.create_task(conn, user["id"], f"task {i}")
    page, total = crud.list_tasks(conn, user["id"], limit=2, offset=2)
    assert total == 5 and len(page) == 2
    assert [t["title"] for t in page] == ["task 2", "task 1"]  # newest first


def test_search_escapes_wildcards(conn, user):
    crud.create_task(conn, user["id"], "100% done")
    crud.create_task(conn, user["id"], "plain task")
    assert crud.list_tasks(conn, user["id"], search="%")[1] == 1
    assert crud.list_tasks(conn, user["id"], search="_")[1] == 0
    assert crud.list_tasks(conn, user["id"], search="PLAIN")[1] == 1


def test_users_cannot_touch_each_others_tasks(conn, user):
    other = crud.create_user(conn, "b@example.com", "h")
    t = crud.create_task(conn, user["id"], "private")
    assert crud.get_task(conn, t["id"], other["id"]) is None
    assert crud.update_task(conn, t["id"], other["id"], {"title": "hacked"}) is None
    assert crud.delete_task(conn, t["id"], other["id"]) is False
    assert crud.list_tasks(conn, other["id"])[1] == 0
    assert crud.get_task(conn, t["id"], user["id"])["title"] == "private"


def test_deleting_user_cascades_to_tasks(conn, user):
    crud.create_task(conn, user["id"], "orphan?")
    conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0
