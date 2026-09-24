"""Fixture loader shared by the MOCK adapters."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DIR = Path(__file__).resolve().parent / "fixtures"


@lru_cache(maxsize=16)
def load(name: str) -> dict[str, Any]:
    with (_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)
