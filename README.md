# Task Manager API

REST API for a simple task manager, built with **FastAPI** and **SQLite**.
Includes the bonus features: JWT user authentication (register/login) and an All / Completed / Pending filter.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

- Interactive docs (Swagger UI): http://127.0.0.1:8000/docs
- Click **Authorize** in Swagger, enter your email as `username` plus your password, and you can try every endpoint.
- The SQLite file `tasks.db` is created automatically on first start.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | random per start | JWT signing key. **Set this in production**, otherwise logins reset on every restart. |
| `DATABASE_PATH` | `tasks.db` | SQLite file location |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token lifetime |
| `CORS_ORIGINS` | `*` | Comma-separated frontend origins, e.g. `http://localhost:3000` |

## Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/auth/register` | Create account (`email`, `password` min 8 chars) -> 201 | no |
| POST | `/auth/login` | **Form data** `username` (email) + `password` -> `{access_token, token_type}` | no |
| GET | `/auth/me` | Current user | yes |
| GET | `/tasks` | List tasks. Query: `status=all\|completed\|pending`, `search`, `limit` (1-100, default 50), `offset`. Total count in `X-Total-Count` header | yes |
| POST | `/tasks` | Create task -> 201 | yes |
| GET | `/tasks/{id}` | Get one task | yes |
| PUT | `/tasks/{id}` | Full update (title required; omitted description is cleared) | yes |
| PATCH | `/tasks/{id}` | Partial update, e.g. `{"completed": true}` | yes |
| DELETE | `/tasks/{id}` | Delete -> 204 | yes |
| GET | `/health` | Health check | no |

Send the token as `Authorization: Bearer <token>`.

### Example

```bash
curl -X POST localhost:8000/auth/register -H "Content-Type: application/json" \
     -d '{"email":"me@example.com","password":"password123"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login \
     -d "username=me@example.com&password=password123" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -X POST localhost:8000/tasks -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"title":"Write README"}'

curl -X PATCH localhost:8000/tasks/1 -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"completed":true}'

curl "localhost:8000/tasks?status=pending" -H "Authorization: Bearer $TOKEN"
```

### Task object

```json
{"id": 1, "title": "Write README", "description": null, "completed": true,
 "created_at": "2026-11-07T07:30:00+00:00", "updated_at": "2026-11-07T07:31:00+00:00"}
```

## Error handling

All errors return `{"detail": ...}`.

| Status | When |
|---|---|
| 401 | Missing/invalid/expired token, wrong login |
| 404 | Task doesn't exist **or belongs to another user** |
| 409 | Email already registered |
| 422 | Validation failure (blank title, bad email, short password, bad filter value, empty PATCH body...) |
| 500 | Unexpected error: logged server-side, generic message to the client |

## Design notes

- **Per-user data:** every query is scoped by `owner_id`, so users can never read or change each other's tasks.
- **Passwords** are hashed with scrypt (salted); login uses a constant-time comparison and a dummy hash for unknown emails.
- **SQL** is fully parameterized; dynamic UPDATE column names come from a fixed whitelist.
- Plain `sqlite3` is used (no ORM) to keep the project small and dependency-light.

## Project structure

```
app/
  main.py        app setup, CORS, global error handler
  config.py      env settings
  database.py    SQLite connection + schema
  schemas.py     Pydantic request/response models
  crud.py        DB operations
  security.py    password hashing + JWT
  deps.py        DB + current-user dependencies
  routers/       auth.py, tasks.py
tests/
  test_core.py   security, schemas, CRUD (no web framework needed)
  test_api.py    full HTTP tests via TestClient
```

## Tests

```bash
python -m pytest -v
```

## Deploying (e.g. Render / Railway)

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Set `SECRET_KEY` and `CORS_ORIGINS` (your frontend URL).
- SQLite lives on local disk, which is wiped on redeploy on most free tiers. Attach a persistent disk and point `DATABASE_PATH` at it, or move to PostgreSQL.
