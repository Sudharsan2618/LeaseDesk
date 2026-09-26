"""Conversational intake turn planner (docs/16).

Given the current field state + the controlled reference options + the salesperson's message, the LLM
returns a TURN PLAN: which field values to set, which fields the human confirmed, whether to proceed
to pricing, and a short natural-language reply (answers questions, lists requested options, states
what changed). This is what makes the chat agentic — it interprets intent, not just field values.

The LLM still only STRUCTURES intent and talks; it never prices, scores, approves, or invents
options/values. Without a key, callers fall back to deterministic affirmation detection.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.agent import llm

# proposed-keys the planner may set (whitelist; anything else is ignored)
SET_KEYS = {
    "channel", "leasing_product", "company_hint", "register_number", "make", "model", "colour",
    "vehicle_key", "term_months", "annual_mileage_km", "quantity", "special_payment_eur",
    "service_maintenance", "service_tyres", "insurance",
}
# field ids the planner may confirm
CONFIRM_FIELDS = {
    "channel", "customer", "product", "asset", "term", "mileage",
    "quantity", "special_payment", "maintenance", "tyres", "insurance",
}


class TurnPlan(BaseModel):
    set: dict = Field(default_factory=dict,
                      description="field values to change, using exact keys: channel, leasing_product, "
                                  "company_hint (customer name), make, model, colour, term_months, "
                                  "annual_mileage_km, quantity, special_payment_eur, service_maintenance, "
                                  "service_tyres, insurance")
    confirm: list[str] = Field(default_factory=list,
                               description="field ids the user explicitly confirmed/accepted: channel, "
                                           "customer, product, asset, term, mileage, quantity, "
                                           "special_payment, maintenance, tyres, insurance")
    confirm_all: bool = Field(False, description="true if the user accepts everything")
    proceed: bool = Field(False, description="true if the user wants to price / continue now")
    reply: str = Field("", description="a short, friendly reply: answer the user's question, list any "
                                       "options they asked for (from the provided options only), and say "
                                       "what you changed or confirmed")


_SYSTEM = (
    "You are the intake agent for a German B2B leasing workbench. You are given the current offer "
    "fields (with their confirm status), the controlled reference options, and one message from the "
    "salesperson. Interpret the message and return the structured turn plan:\n"
    "- put any values they state into `set` (exact keys given in the schema);\n"
    "- put any fields they explicitly accept into `confirm` (or set `confirm_all`);\n"
    "- set `proceed` when they want to price/continue;\n"
    "- write a concise `reply` that answers their question and, if they ask for options (e.g. channels "
    "or products), lists ONLY the provided options.\n"
    "Write `reply` in the SAME language the salesperson used in their message.\n"
    "Never invent option values or field values you were not given. You never price, score or approve."
)


def plan_turn(message: str, fields_summary: str, options_summary: str) -> Optional[TurnPlan]:
    if not llm.llm_available() or not (message or "").strip():
        return None
    user = (f"CURRENT FIELDS:\n{fields_summary}\n\n"
            f"REFERENCE OPTIONS:\n{options_summary}\n\n"
            f"SALESPERSON MESSAGE:\n{message}")
    try:
        return llm.extract_json(_SYSTEM, user, TurnPlan)
    except Exception:
        return None
