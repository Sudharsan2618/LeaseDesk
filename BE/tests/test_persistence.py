"""Live persistence round-trip (docs/07). Skips cleanly when the DB is unreachable so the core
engine suite still runs offline."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.policy import load_policy
from app.core.types import AssetAssessmentStatus, RiskBand
from app.domain.entities import Role
from app.engine.orchestrator import run_pipeline
from app.integration.base import AdapterMode, build_default_registry
from app.service.offer_factory import build_b2b_offer

psycopg = pytest.importorskip("psycopg")


@pytest.fixture(scope="module")
def conn():
    from app.db.connection import get_conn
    try:
        cm = get_conn()
        c = cm.__enter__()
    except Exception as e:  # no DB configured / unreachable
        pytest.skip(f"database unavailable: {e}")
    try:
        yield c
    finally:
        cm.__exit__(None, None, None)


def test_save_and_load_roundtrip(conn):
    from app.db import repository as repo

    policy = load_policy("DE_PKW_V1")
    reg = build_default_registry(AdapterMode.MOCK)
    repo.seed_policy(conn, policy.policy_id, policy.raw)
    sales = repo.ensure_user(conn, "pytest-sales@demo.local", Role.SALES)

    offer = build_b2b_offer(reg, vehicle_key="bmw-x1-sdrive18i", register_number="HRB-1001",
                            term_months=36, annual_mileage_km=20000)
    offer.created_by = sales
    run_pipeline(offer, reg, policy)
    oid = repo.save_offer(conn, offer)

    loaded = repo.load_offer(conn, oid)
    assert loaded.reference == offer.reference
    assert loaded.scoring.value.band is RiskBand.GREEN
    # §3.7 asset-assessment outcome round-trips through its own column (FR-19/54)
    assert loaded.asset_assessment is not None
    assert loaded.asset_assessment.value.status is AssetAssessmentStatus.AVAILABLE
    assert loaded.calculation.value.monthly_gross_eur == offer.calculation.value.monthly_gross_eur
    assert loaded.calculation.engine == "MVP_LEASE_CALC_V1"
    assert loaded.vehicle.list_price_net.value == Decimal("37800.00")
    assert any(ev["event"] == "OFFER_CREATED" for ev in repo.audit_trail(conn, oid))
