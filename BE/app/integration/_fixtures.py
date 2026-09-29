"""Fixture loader shared by the MOCK adapters."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DIR = Path(__file__).resolve().parent / "fixtures"


def load(name: str) -> dict[str, Any]:
    from app.db.mongo_settings import get_setting

    kind = {"vehicles.json": "vehicles", "companies.json": "companies"}.get(name)
    configured = get_setting(kind) if kind else None
    if configured:
        return configured["data"]
    with (_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)
