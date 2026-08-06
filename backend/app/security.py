import hashlib
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import ApiKey

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
request_times: dict[int, deque[float]] = defaultdict(deque)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def enforce_rate_limit(key_id: int) -> None:
    now = time.monotonic()
    window = request_times[key_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    window.append(now)


def require_api_key(raw_key: str | None = Security(api_key_header)) -> None:
    if not settings.auth_enabled:
        return
    if raw_key is None:
        raise HTTPException(status_code=401, detail="Missing API key")

    with SessionLocal() as session:
        key = session.scalar(
            select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key))
        )
    if key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    enforce_rate_limit(key.id)
