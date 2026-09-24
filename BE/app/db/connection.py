"""Connection helper. Reads DATABASE_URL from the environment or the project .env file."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg

_ENV = Path(__file__).resolve().parent.parent.parent / ".env"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    if _ENV.exists():
        for line in _ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1]
    raise RuntimeError("DATABASE_URL not set (env or .env)")


# TCP keepalives so Neon doesn't silently drop a connection held during a slow request.
_KEEPALIVE = dict(keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3)


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(database_url(), **_KEEPALIVE)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
