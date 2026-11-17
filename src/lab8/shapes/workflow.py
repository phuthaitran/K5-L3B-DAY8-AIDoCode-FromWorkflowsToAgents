"""Shape A — deterministic workflow. Student work.

Signature (do not change):

    run_claim(claim_id, *, seed, store_path, crash_at=None) -> RunResult

Suggested steps. Money stays in code (`lab8.tools.compute_compensation`).

1. Open the store. Read the claim through `get_claim_view` (not SELECT *).
2. Missing order_id -> status `needs_info`. Do not write the ledger.
3. `lookup_order`. If not visible -> `escalated`. Do not copy phone, address, item, internal note.
4. Quote from the order row. Ignore delay numbers written in the ticket.
5. Quote amount 0 -> `denied`. Do not call issue_refund.
6. Quote amount > 0 -> `durability.issue_refund(conn, claim_id, <full quote>)`.
   Pass the FULL quote. The host checks the claim's own approval and subtracts
   what earlier claims already got for the same order (T13, T14). Do not
   subtract it yourself or the host subtracts twice.
   Auth failure or order already refunded -> `denied` (the host writes `policy_denied`).
   `proposal_amount` stays the full quote. Amount conflict -> `failed`.
7. Success -> `resolved`. One ledger row, one `refund_committed` audit.
8. Use MockLLM only to draft the reply text, if you want a model call at all.

The model must not choose the refund amount and must not commit the refund.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3

from lab8 import durability
from lab8.db import connect
from lab8.mock_llm import complete
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, lookup_order, tool_cost
from lab8.trace import Trace

SHAPE = "workflow"


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
        # Model chỉ soạn chữ trả lời; prompt không chứa ticket hay dữ liệu đơn.
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

    # Bước 1: đọc claim qua view có allowlist, không SELECT *.
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim["found"]:
        trace.add("claim", {"claim_id": claim_id, "found": False})
        return done("failed", 0, "unknown_claim")
    # Không ghi ticket vào trace: ticket là chữ người dùng, có thể chứa PII.
    trace.add("claim", {"claim_id": claim_id, "found": True, "has_order_id": bool(claim["order_id"])})

    # Bước 2: thiếu order_id -> needs_info. Không đoán mã đơn từ ticket.
    if not claim["order_id"]:
        return done("needs_info", 0, "missing_order_id")

    # Bước 3: đọc đơn trong phạm vi principal. Không thấy -> escalated.
    budget.add_tool(tool_cost())
    order_view = lookup_order(conn, claim["order_id"], claim["principal_id"])
    if not order_view["visible"]:
        trace.add("lookup_order", {"visible": False, "reason": order_view["reason"]})
        return done("escalated", 0, order_view["reason"])
    order = order_view["order"]  # đã lọc theo ORDER_FIELDS, không có SĐT/địa chỉ
    trace.add("lookup_order", {"visible": True, "order": safe_dump(order)})

    # Bước 4: quote từ dòng order + policy hiện hành. Bỏ qua số ngày trễ trong ticket.
    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order)
    proposal = int(quote["amount_vnd"])
    trace.add("quote", safe_dump(quote))

    # Bước 5: quote = 0 -> denied, không gọi host.
    if proposal <= 0:
        return done("denied", 0, quote["reason"])

    # Bước 6: gửi QUOTE ĐẦY ĐỦ cho host. Host kiểm approval, trần theo đơn, idempotency.
    trace.add("issue_refund", {"proposed_vnd": proposal})
    try:
        outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except durability.InjectedCrash:
        # Chỉ ghi trace rồi ném lại: crash phải lộ ra cho harness (T12).
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    trace.add("host", {"ok": outcome["ok"], "reason": outcome["reason"]})

    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        return done(status, proposal, outcome["reason"])

    # Bước 7: thành công. proposal_amount là quote, số đã ghi lấy từ ledger qua finish().
    return done("resolved", proposal, None)
