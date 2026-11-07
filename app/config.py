"""Application settings, read from environment variables."""
import os
import secrets

# Set SECRET_KEY in production; a random key means tokens die on every restart.
SECRET_KEY: str = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Comma-separated list of allowed frontend origins, e.g. "http://localhost:3000,https://myapp.com"
CORS_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
]
