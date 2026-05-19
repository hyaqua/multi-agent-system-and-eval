from __future__ import annotations

import logging
from functools import partial

from langgraph.graph import StateGraph, END

from state import AgentState, Phase
from agents.planner import planner_node
from agents.coder import coder_node
from agents.tester import tester_node
from agents.reviewer import reviewer_node
from config import Config

logger = logging.getLogger(__name__)


def _should_continue(state: dict, config: Config) -> str:
    s = AgentState(**state)

    if s.phase == Phase.DONE:
        logger.info("Reviewer approved. Finishing.")
        return "done"

    if s.iteration >= config.agent.max_iterations:
        logger.info(f"Max iterations ({config.agent.max_iterations}) reached. Stopping.")
        return "done"

    if s.total_tokens_used >= config.agent.max_total_tokens:
        logger.info(f"Token budget ({config.agent.max_total_tokens}) exceeded. Stopping.")
        return "done"

    return "revise"


def _increment_iteration(state: dict) -> dict:
    s = AgentState(**state)
    return {"iteration": s.iteration + 1}


def build_graph(config: Config, llm_client, sandbox) -> StateGraph:
    # Bind dependencies to node functions via partial
    plan = partial(planner_node, llm_client=llm_client, sandbox=sandbox)
    code = partial(coder_node, llm_client=llm_client, sandbox=sandbox)
    test = partial(tester_node, llm_client=llm_client, sandbox=sandbox)
    review = partial(reviewer_node, llm_client=llm_client, sandbox=sandbox)
    should_continue = partial(_should_continue, config=config)

    # Build the graph
    graph = StateGraph(dict)

    # Add nodes
    graph.add_node("planner", plan)
    graph.add_node("coder", code)
    graph.add_node("tester", test)
    graph.add_node("reviewer", review)
    graph.add_node("increment", _increment_iteration)

    # Set entry point
    graph.set_entry_point("planner")

    # Linear flow: plan -> code -> test -> review
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "tester")
    graph.add_edge("tester", "reviewer")

    # Conditional: review -> done or review -> increment -> plan
    graph.add_conditional_edges(
        "reviewer",
        should_continue,
        {
            "done": END,
            "revise": "increment",
        },
    )
    graph.add_edge("increment", "planner")

    return graph.compile()
