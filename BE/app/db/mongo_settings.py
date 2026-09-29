"""Mongo-backed editable configuration and reference data for the offer engine."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection

_BE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_BE_DIR / ".env", override=False)
_CONFIG_DIR = _BE_DIR / "app" / "config"
_FIXTURE_DIR = _BE_DIR / "app" / "integration" / "fixtures"
_KINDS = ("policy", "reference_data", "vehicles", "companies", "engine_inputs")
_client: MongoClient | None = None
_init_lock = Lock()
_initialized = False


def _json_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _seed_documents() -> dict[str, dict[str, Any]]:
    return {
        "policy": _json_file(_CONFIG_DIR / "de_pkw_v1.json"),
        "reference_data": _json_file(_CONFIG_DIR / "reference_data.json"),
        "vehicles": _json_file(_FIXTURE_DIR / "vehicles.json"),
        "companies": _json_file(_FIXTURE_DIR / "companies.json"),
        "engine_inputs": {
            "reference_rate_pct": "3.00",
            "reference_rate_source": "BUNDESBANK",
            "vat_pct": "19",
            "vat_source": "EU_TEDB",
            "asset_assessment_result": "PASS",
            "asset_assessment_detail": "representative MVP assessment (mock)",
        },
    }


def _fill_missing(target: dict[str, Any], defaults: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Backfill newly introduced defaults without replacing any value already edited in Mongo."""
    merged = dict(target)
    changed = False
    for key, value in defaults.items():
        if key not in merged:
            merged[key] = value
            changed = True
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            nested, nested_changed = _fill_missing(merged[key], value)
            merged[key] = nested
            changed = changed or nested_changed
    return merged, changed


def _mongo_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI is not configured")
        _client = MongoClient(uri, appname="leasedesk-settings", serverSelectionTimeoutMS=8000,
                              connectTimeoutMS=8000, retryWrites=True)
    return _client


def _collections() -> tuple[Collection, Collection]:
    client = _mongo_client()
    database_name = os.environ.get("MONGODB_DATABASE", "leasedesk")
    db = client[database_name]
    return db["system_settings"], db["system_settings_history"]


def initialize_settings() -> None:
    """Create indexes and seed only missing documents; existing Mongo edits are never overwritten."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        settings, history = _collections()
        _mongo_client().admin.command("ping")
        history.create_index([("kind", 1), ("revision", -1)])
        history.create_index("saved_at")
        now = datetime.now(timezone.utc)
        defaults = _seed_documents()
        for kind, data in defaults.items():
            settings.update_one(
                {"_id": kind},
                {"$setOnInsert": {"data": data, "revision": 1, "updated_at": now,
                                  "updated_by": "seed"}},
                upsert=True,
            )
            current = settings.find_one({"_id": kind})
            merged, changed = _fill_missing(current["data"], data)
            if changed:
                now = datetime.now(timezone.utc)
                previous_revision = current["revision"]
                updated = settings.find_one_and_update(
                    {"_id": kind, "revision": previous_revision},
                    {"$set": {"data": merged, "updated_at": now,
                              "updated_by": "system-migration"},
                     "$inc": {"revision": 1}},
                    return_document=ReturnDocument.AFTER,
                )
                if updated:
                    history.insert_one({"kind": kind, "revision": previous_revision,
                                        "data": current["data"], "saved_at": now,
                                        "saved_by": "system-migration"})
        _initialized = True


def get_setting(kind: str) -> dict[str, Any] | None:
    if kind not in _KINDS:
        raise KeyError(kind)
    if not os.environ.get("MONGODB_URI"):
        return None
    initialize_settings()
    settings, _ = _collections()
    row = settings.find_one({"_id": kind})
    return row


def list_settings() -> list[dict[str, Any]]:
    initialize_settings()
    settings, _ = _collections()
    rows = settings.find({"_id": {"$in": list(_KINDS)}})
    by_kind = {row["_id"]: row for row in rows}
    return [by_kind[kind] for kind in _KINDS if kind in by_kind]


def save_setting(kind: str, data: dict[str, Any], *, expected_revision: int,
                 updated_by: str = "settings-ui") -> dict[str, Any] | None:
    if kind not in _KINDS:
        raise KeyError(kind)
    validate_setting(kind, data)
    initialize_settings()
    settings, history = _collections()
    current = settings.find_one({"_id": kind})
    if current is None or current.get("revision") != expected_revision:
        return None
    if kind == "policy" and data.get("policy_id") != current["data"].get("policy_id"):
        raise ValueError("policy_id is fixed; edit policy values without changing its identifier")

    now = datetime.now(timezone.utc)
    row = settings.find_one_and_update(
        {"_id": kind, "revision": expected_revision},
        {"$set": {"data": data, "revision": expected_revision + 1,
                  "updated_at": now, "updated_by": updated_by}},
        return_document=ReturnDocument.AFTER,
    )
    if row is None:
        return None
    history.insert_one({"kind": kind, "revision": current["revision"], "data": current["data"],
                        "saved_at": now, "saved_by": updated_by})
    return row


def _validate_policy(raw: dict[str, Any]) -> None:
    from app.core.policy import Policy

    policy = Policy(raw)
    if not raw.get("policy_id") or not raw.get("currency"):
        raise ValueError("policy_id and currency are required")
    if policy.term_min <= 0 or policy.term_max < policy.term_min or policy.term_step <= 0:
        raise ValueError("term limits and step must be positive and ordered")
    if not policy.term_preferred or any(t < policy.term_min or t > policy.term_max
                                        for t in policy.term_preferred):
        raise ValueError("preferred terms must fall inside the allowed term range")
    if not (0 < policy.mileage_min <= policy.mileage_baseline <= policy.mileage_max):
        raise ValueError("mileage limits must satisfy min ≤ baseline ≤ max")
    if int(raw["mileage"]["step_km"]) <= 0:
        raise ValueError("mileage step_km must be positive")
    if not (0 < policy.quantity_min <= policy.quantity_max):
        raise ValueError("quantity limits must satisfy 0 < min ≤ max")
    weights = policy.risk_weights("B2B")
    if not weights or abs(sum(weights.values()) - Decimal("1")) > Decimal("0.0001"):
        raise ValueError("B2B risk weights must sum to 1")
    if not (Decimal("0") <= policy.risk_yellow_min <= policy.risk_green_min <= Decimal("100")):
        raise ValueError("risk thresholds must be ordered between 0 and 100")
    if not (Decimal("0") <= policy.vat_fallback_pct <= Decimal("100")):
        raise ValueError("VAT fallback must be between 0 and 100")
    # Force evaluation of all policy sections used by calculation, eligibility and approval.
    policy.term_spread_pp(policy.term_min)
    policy.asset_uncertainty_spread_pp("HIGH")
    policy.base_term_rv_pct(policy.term_min)
    policy.margin_base_pp
    policy.margin_floor_pp
    policy.margin_cap_pp
    policy.approval_limits
    policy.scoring_automatic_envelope
    policy.eligibility_vehicle
    residual = raw["residual"]
    confidence = residual["confidence"]
    if int(confidence["low_if_used_age_over_years"]) < 0 or int(confidence["high_max_term_months"]) <= 0:
        raise ValueError("residual confidence age and term thresholds are invalid")
    if int(confidence["low_if_annual_mileage_over_km"]) <= 0 or int(confidence["high_max_annual_mileage_km"]) <= 0:
        raise ValueError("residual confidence mileage thresholds must be positive")
    if Decimal(str(residual["used_vehicle_age_penalty_pp_per_year"])) < 0:
        raise ValueError("used vehicle age penalty must be non-negative")
    value_thresholds = raw["mileage_settlement"]["vehicle_value_thresholds_eur"]
    if Decimal(str(value_thresholds["lower"])) <= 0 or Decimal(str(value_thresholds["upper"])) <= Decimal(str(value_thresholds["lower"])):
        raise ValueError("mileage settlement vehicle value thresholds must be positive and ordered")


def validate_setting(kind: str, data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("settings value must be a JSON object")
    if kind == "policy":
        _validate_policy(data)
        return
    if kind == "reference_data":
        from app.domain.reference import ReferenceData
        reference = ReferenceData.model_validate({k: v for k, v in data.items() if k != "_note"})
        if not reference.business_lines or not reference.leasing_products or not reference.channels:
            raise ValueError("reference data must include business lines, products, and channels")
        return
    if kind == "vehicles":
        rows = data.get("vehicles")
        if not isinstance(rows, list) or not rows:
            raise ValueError("vehicle catalogue must contain at least one vehicle")
        keys: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("each vehicle must be a JSON object")
            key = row.get("key")
            if not key or key in keys:
                raise ValueError("vehicle keys must be present and unique")
            keys.add(key)
            if not all(row.get(field) not in (None, "") for field in
                       ("make", "commercial_name", "variant", "vehicle_category", "list_price_net")):
                raise ValueError(f"vehicle {key} is missing a required identity or price field")
            if Decimal(str(row["list_price_net"])) <= 0:
                raise ValueError(f"vehicle {key} list_price_net must be positive")
        return
    if kind == "companies":
        companies = data.get("companies")
        if not isinstance(companies, dict) or not companies:
            raise ValueError("customer directory must contain at least one company")
        defaults = data.get("_defaults") or {}
        if defaults.get("recommended_customer") and defaults["recommended_customer"] not in companies:
            raise ValueError("recommended_customer must reference a customer in the directory")
        for register, company in companies.items():
            if not company.get("legal_name"):
                raise ValueError(f"customer {register} is missing legal_name")
            for section in ("credit", "kyc", "sanctions"):
                if not isinstance(company.get(section), dict):
                    raise ValueError(f"customer {register} is missing {section} data")
        return
    if kind == "engine_inputs":
        try:
            reference_rate = Decimal(str(data["reference_rate_pct"]))
            vat_pct = Decimal(str(data["vat_pct"]))
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("engine inputs require numeric reference_rate_pct and vat_pct") from exc
        if reference_rate < 0 or not Decimal("0") <= vat_pct <= Decimal("100"):
            raise ValueError("reference rate must be non-negative and VAT must be between 0 and 100")
        if data.get("asset_assessment_result") not in ("PASS", "CONCERNS"):
            raise ValueError("asset_assessment_result must be PASS or CONCERNS")
        if not data.get("reference_rate_source") or not data.get("vat_source"):
            raise ValueError("reference-rate and VAT sources are required")

