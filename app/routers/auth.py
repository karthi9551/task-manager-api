import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from .. import crud, security
from ..deps import Conn, CurrentUser
from ..schemas import Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, conn: Conn):
    conflict = HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if crud.get_user_by_email(conn, payload.email):
        raise conflict
    try:
        return crud.create_user(conn, payload.email, security.hash_password(payload.password))
    except sqlite3.IntegrityError:  # two simultaneous registrations
        raise conflict


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], conn: Conn):
    """OAuth2 password flow: send form fields `username` (the email) and `password`."""
    user = crud.get_user_by_email(conn, form.username.strip().lower())
    stored = user["hashed_password"] if user else security.DUMMY_HASH
    password_ok = security.verify_password(form.password, stored)
    if user is None or not password_ok:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=security.create_access_token(user["id"]))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
