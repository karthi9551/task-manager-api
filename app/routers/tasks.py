from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, Response, status

from .. import crud
from ..deps import Conn, CurrentUser
from ..schemas import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

TaskId = Path(ge=1)
NOT_FOUND = "Task not found"


@router.get("", response_model=list[TaskOut])
def list_tasks(
    response: Response,
    conn: Conn,
    user: CurrentUser,
    status_filter: Literal["all", "completed", "pending"] = Query("all", alias="status"),
    search: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List your tasks. Filter with ?status=all|completed|pending. Total count is in the X-Total-Count header."""
    tasks, total = crud.list_tasks(conn, user["id"], status_filter, search, limit, offset)
    response.headers["X-Total-Count"] = str(total)
    return tasks


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, conn: Conn, user: CurrentUser):
    return crud.create_task(
        conn, user["id"], payload.title, payload.description, payload.completed
    )


@router.get("/{task_id}", response_model=TaskOut)
def get_task(conn: Conn, user: CurrentUser, task_id: int = TaskId):
    task = crud.get_task(conn, task_id, user["id"])
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return task


@router.put("/{task_id}", response_model=TaskOut)
def replace_task(payload: TaskCreate, conn: Conn, user: CurrentUser, task_id: int = TaskId):
    """Full update: title is required; omitted description is cleared."""
    task = crud.update_task(conn, task_id, user["id"], payload.model_dump())
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(payload: TaskUpdate, conn: Conn, user: CurrentUser, task_id: int = TaskId):
    """Partial update, e.g. {"completed": true} to mark a task done."""
    task = crud.update_task(conn, task_id, user["id"], payload.model_dump(exclude_unset=True))
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(conn: Conn, user: CurrentUser, task_id: int = TaskId):
    if not crud.delete_task(conn, task_id, user["id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
