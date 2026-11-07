import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, database
from .routers import auth, tasks

logger = logging.getLogger("task_manager")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="Task Manager API",
    description="Simple task manager: JWT auth + CRUD over SQLite.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

app.include_router(auth.router)
app.include_router(tasks.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    # Log details server-side; never leak internals to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
