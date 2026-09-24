"""LangGraph state for the offer workflow (hybrid model).

The `offer` field is the WORKING COPY of the Offer as a JSON-safe dict (so the PostgresSaver
checkpointer can serialise it). Nodes reconstruct the pydantic Offer, mutate it, persist it via the
single projection writer (repository.upsert_offer), and write the dict back to state.

The intake is a conversational loop (understand → clarify/correct → confirm): `messages` is the
chat transcript, `pending` carries the latest user turn from an interrupt resume, and
`intake_ready` signals the loop to proceed to pricing.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional

from typing_extensions import TypedDict


class OfferState(TypedDict, total=False):
    offer: dict[str, Any]                       # serialized Offer (working copy)
    nl_request: Optional[str]                   # initial free-text intake
    messages: Annotated[list[dict], operator.add]  # chat transcript [{role, content}]
    pending: Optional[dict]                     # latest intake resume payload {message?, confirm?, overrides?}
    intake_confirmed_initial: bool             # true for structured (non-conversational) creation
    intake_ready: bool                         # intake complete + confirmed -> proceed to pricing
    # Phase 2: stepped selection hierarchy (distinct confirm interrupt per step).
    step: Optional[str]                        # current wizard step: channel/partner/product/asset/commercial
    step_ok: bool                              # last step confirmed & valid -> advance to the next step
    goto_step: Optional[str]                   # jump back to edit an earlier step (controlled iteration)
    gate_action: Optional[str]                 # "select" / "generate" / "adjust" (workspace gate)
    finalize: bool                             # true when the salesperson requested generation
