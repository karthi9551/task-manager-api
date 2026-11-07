"""Database operations. Plain functions; no web-framework imports."""
import sqlite3
from datetime import datetime, timezone
from typing import Any

_UPDATABLE = {"title", "description", "completed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


# ---------- users ----------
def create_user(conn: sqlite3.Connection, email: str, hashed_password: str) -> dict:
    """Raises sqlite3.IntegrityError if the email already exists."""
    cur = conn.execute(
        "INSERT INTO users (email, hashed_password, created_at) VALUES (?, ?, ?)",
        (email, hashed_password, _now()),
    )
    conn.commit()
    return get_user_by_id(conn, cur.lastrowid)  # type: ignore[return-value]


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    return _row(conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> dict | None:
    return _row(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


# ---------- tasks ----------
def create_task(
    conn: sqlite3.Connection,
    owner_id: int,
    title: str,
    description: str | None = None,
    completed: bool = False,
) -> dict:
    now = _now()
    cur = conn.execute(
        "INSERT INTO tasks (title, description, completed, owner_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, description, int(completed), owner_id, now, now),
    )
    conn.commit()
    return get_task(conn, cur.lastrowid, owner_id)  # type: ignore[return-value]


def get_task(conn: sqlite3.Connection, task_id: int, owner_id: int) -> dict | None:
    return _row(
        conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
    )


def list_tasks(
    conn: sqlite3.Connection,
    owner_id: int,
    status: str = "all",
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (page of tasks, total matching count). status: all | completed | pending."""
    where = ["owner_id = ?"]
    params: list[Any] = [owner_id]
    if status == "completed":
        where.append("completed = 1")
    elif status == "pending":
        where.append("completed = 0")
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')")
        params += [f"%{escaped}%"] * 2

    clause = " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) FROM tasks WHERE {clause}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM tasks WHERE {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return [dict(r) for r in rows], total


def update_task(
    conn: sqlite3.Connection, task_id: int, owner_id: int, fields: dict[str, Any]
) -> dict | None:
    """Update the given fields. Returns the updated task, or None if not found."""
    fields = {k: v for k, v in fields.items() if k in _UPDATABLE}
    if "completed" in fields:
        fields["completed"] = int(fields["completed"])
    if not fields:
        return get_task(conn, task_id, owner_id)

    # Column names come from the _UPDATABLE whitelist above, never from user input.
    assignments = ", ".join(f"{col} = ?" for col in fields)
    cur = conn.execute(
        f"UPDATE tasks SET {assignments}, updated_at = ? WHERE id = ? AND owner_id = ?",
        [*fields.values(), _now(), task_id, owner_id],
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    return get_task(conn, task_id, owner_id)


def delete_task(conn: sqlite3.Connection, task_id: int, owner_id: int) -> bool:
    cur = conn.execute("DELETE FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id))
    conn.commit()
    return cur.rowcount > 0
