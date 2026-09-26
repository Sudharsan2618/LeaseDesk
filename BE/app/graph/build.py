"""Graph definition (docs/06 + spec §3.3-3.6 as a LangGraph state machine), stepped agent-driven intake.

`builder` is exported UN-compiled so the server attaches the Postgres checkpointer.

    START -> understand            # extract initial NL, pre-fill every step (no interrupt)
                 | structured (intake_confirmed_initial) --> run_pipeline
                 | else
                 v
             select_channel(interrupt) -> select_partner(interrupt) -> select_product(interrupt)
                 -> select_asset(interrupt) -> select_commercial(interrupt) -> assemble
             (each select_* loops on itself until confirmed & valid — FR-16/BR-02)

             assemble -> run_pipeline -> explain_pricing -> (route)
                 |-- priced -----------------> scenarios -> explain_scenarios -> workspace_gate(interrupt)
                 |-- compliance-RED ---------> final_validation -> END (blocked)
                 |-- economic-RED/out-of-range -> select_asset   # reopen wizard to adjust, re-price
             workspace_gate (single actor, mutable):
                 |-- select   --> workspace_gate
                 |-- adjust   --> select_asset                     # reopen wizard, re-price
                 |-- generate --> human_review(interrupt)          # mandatory review gate (BR-15)
             human_review:
                 |-- confirm (& not blocked) --> final_validation -> generate_offer -> END (done)
                 |-- return / blocked --------> workspace_gate
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.agent_nodes import (
    agent_turn_node,
    assemble_node,
    explain_pricing_node,
    explain_scenarios_node,
    route_after_pipeline,
    route_after_turn,
    route_after_understand,
    understand_node,
)
from app.graph.nodes import (
    final_validation_node,
    generate_offer_node,
    human_review_node,
    route_after_final,
    route_after_gate,
    route_after_review,
    run_pipeline_node,
    scenarios_node,
    workspace_gate_node,
)
from app.graph.state import OfferState


def make_builder() -> StateGraph:
    b = StateGraph(OfferState)
    b.add_node("understand", understand_node)
    b.add_node("agent_turn", agent_turn_node)                # interrupt: one conversational intake turn
    b.add_node("assemble", assemble_node)
    b.add_node("run_pipeline", run_pipeline_node)
    b.add_node("explain_pricing", explain_pricing_node)
    b.add_node("scenarios", scenarios_node)
    b.add_node("explain_scenarios", explain_scenarios_node)
    b.add_node("workspace_gate", workspace_gate_node)        # interrupt: select / adjust / generate
    b.add_node("human_review", human_review_node)            # interrupt: confirm / return (BR-15)
    b.add_node("final_validation", final_validation_node)
    b.add_node("generate_offer", generate_offer_node)

    b.add_edge(START, "understand")
    b.add_conditional_edges("understand", route_after_understand,
                            {"run_pipeline": "run_pipeline", "agent_turn": "agent_turn"})
    # one conversational turn: loop until every required field is confirmed, then assemble
    b.add_conditional_edges("agent_turn", route_after_turn,
                            {"agent_turn": "agent_turn", "assemble": "assemble"})
    b.add_edge("assemble", "run_pipeline")
    b.add_edge("run_pipeline", "explain_pricing")
    b.add_conditional_edges("explain_pricing", route_after_pipeline,
                            {"scenarios": "scenarios", "final_validation": "final_validation",
                             "agent_turn": "agent_turn"})
    b.add_edge("scenarios", "explain_scenarios")
    b.add_edge("explain_scenarios", "workspace_gate")
    b.add_conditional_edges("workspace_gate", route_after_gate,
                            {"workspace_gate": "workspace_gate", "human_review": "human_review",
                             "agent_turn": "agent_turn"})
    b.add_conditional_edges("human_review", route_after_review,
                            {"final_validation": "final_validation", "workspace_gate": "workspace_gate"})
    b.add_conditional_edges("final_validation", route_after_final,
                            {"generate_offer": "generate_offer", "END": END})
    b.add_edge("generate_offer", END)   # generation is terminal — the offer is done, no re-prompt
    return b


builder = make_builder()
