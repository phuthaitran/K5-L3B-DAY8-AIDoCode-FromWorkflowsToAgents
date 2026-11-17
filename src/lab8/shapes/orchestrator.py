"""Shape C — orchestrator plus read-only investigators. Student work.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3

from lab8 import durability
from lab8.db import connect
from lab8.handoff import make_handoff
from lab8.mock_llm import complete
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        # The model drafts words only; neither ticket text nor private rows enter the prompt.
        complete(budget, seed=seed, purpose="draft", prompt=f"status={status}")
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim["found"]:
        trace.add("claim", {"found": False})
        return done("failed", 0, "unknown_claim")
    trace.add("claim", {"found": True, "has_order_id": bool(claim["order_id"])})
    if not claim["order_id"]:
        return done("needs_info", 0, "missing_order_id")

    # Only an allowlisted task and read tools cross the investigator boundary.
    complete(budget, seed=seed, purpose="plan", prompt="check_order_and_current_policy")
    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="check_order_and_current_policy",
        facts={},
        allowed_tools=["lookup_order", "lookup_policy", "lookup_refund_history", "compute_compensation"],
    )
    trace.add("handoff", handoff)
    investigated = run_readonly_investigators(conn, budget, handoff, claim["principal_id"])
    order_view = investigated["tools"]["lookup_order"]
    trace.add("investigator", {"order_visible": order_view["visible"], "reason": order_view["reason"]})
    if not order_view["visible"]:
        return done("escalated", 0, order_view["reason"])

    # The quote comes from the investigator's order view, never from the ticket.
    quote = investigated["tools"]["compute_compensation"]
    proposal = int(quote["amount_vnd"])
    trace.add("quote", {"amount_vnd": proposal, "reason": quote["reason"]})
    if proposal <= 0:
        return done("denied", 0, quote["reason"])

    # The host checks approval, order cap and idempotency. Pass the full quote.
    trace.add("issue_refund", {"proposed_vnd": proposal})
    try:
        outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except durability.InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    trace.add("host", {"ok": outcome["ok"], "reason": outcome["reason"]})
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal, None)
