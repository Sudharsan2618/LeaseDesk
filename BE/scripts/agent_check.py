"""Verify the OpenRouter LLM is wired (run AFTER adding OPENROUTER_API_KEY + OPENROUTER_MODEL to .env).

    python -m scripts.agent_check

Exercises the two LLM jobs: understand (NL -> structured) and explain (grounded). Prints whether the
explanation passed the grounding check.
"""
from __future__ import annotations

from decimal import Decimal

from app.agent import explain, llm
from app.agent.extract import understand
from app.engine.orchestrator import run_pipeline
from app.integration.base import AdapterMode, build_default_registry
from app.service.offer_factory import build_b2b_offer


def main():
    if not llm.llm_available():
        print("No OPENROUTER_API_KEY in .env (or AGENT_DISABLE_LLM set). Add the key and retry.")
        return
    print("LLM configured. Model:", llm._model())

    print("\n[understand] NL -> structured:")
    intent = understand("Lease a BMW X1 for 36 months, roughly 20k km a year, for Musterlogistik, "
                        "keep the monthly as low as possible")
    print("  ", intent.model_dump() if intent else "None (extraction failed)")

    reg = build_default_registry(AdapterMode.MOCK)
    offer = build_b2b_offer(reg, vehicle_key="bmw-x1-sdrive18i", register_number="HRB-1001",
                            term_months=36, annual_mileage_km=20000,
                            special_payment_eur=Decimal("0"))
    run_pipeline(offer, reg)
    text = explain.explain_pricing(offer)
    grounded = explain.grounding_check(text, explain._allowed_numbers(offer))
    print("\n[explain] grounded pricing explanation (passed grounding =", grounded, "):")
    print("  ", text)


if __name__ == "__main__":
    main()
