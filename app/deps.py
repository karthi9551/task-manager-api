"""FastAPI dependencies: DB connection and current user."""
import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from . import crud, database, security

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_db() -> Iterator[sqlite3.Connection]:
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], conn: Conn) -> dict:
    user_id = security.decode_access_token(token)
    user = crud.get_user_by_id(conn, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]
