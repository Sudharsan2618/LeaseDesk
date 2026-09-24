import os
import sys
from pathlib import Path

import pytest

# Ensure the project root (containing the `app` package) is importable when running pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Tests must be deterministic: force the agent layer to use its template fallbacks (no live LLM),
# even if an OPENROUTER_API_KEY is present in .env.
os.environ.setdefault("AGENT_DISABLE_LLM", "1")


@pytest.fixture(scope="session", autouse=True)
def _clean_test_offers():
    """Delete offers created by test personas after the run, so the shared Neon DB / inbox is never
    polluted by test data (tests use gtest-*/pytest-* emails; real app uses sales@/approver@)."""
    yield
    try:
        from app.db.connection import get_conn
        with get_conn() as conn:
            conn.execute("ALTER TABLE audit_events DISABLE TRIGGER audit_no_update")
            conn.execute(
                "DELETE FROM offers WHERE created_by IN "
                "(SELECT id FROM users WHERE email LIKE 'gtest-%' OR email LIKE 'pytest-%')")
            conn.execute("ALTER TABLE audit_events ENABLE TRIGGER audit_no_update")
    except Exception:
        pass
