"""CP3/CP4 cho ba shape nhóm viết: crash vẫn để lại trace sạch, approval mượn bị host chặn.

Bổ sung cho ma trận student (T11, T12) và test host (test_order_cap_and_approval_binding):
- Crash ở cả hai điểm: InjectedCrash phải bay ra, trace ghi trước khi bay có event `crash`,
  đúng run_id, không chứa secret; chạy lại thì đúng một refund và một audit `refund_committed`.
- Approval mượn của claim khác / bị thu hồi: đi qua shape (không gọi thẳng host) vẫn `denied`,
  không ghi ledger, có audit `policy_denied` đúng lý do.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8.db import connect
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.schemas import make_run_id
from lab8.shapes import orchestrator, single, workflow

SHAPES = {
    "workflow": workflow.run_claim,
    "single": single.run_claim,
    "orchestrator": orchestrator.run_claim,
}
CRASH_POINTS = ["before_effect", "after_effect_before_checkpoint"]
LEAK_MARKERS = ("CANARY_SECRET_", "CANARY_INTERNAL_", "parent_secret", "raw_headers", "Bearer ")


def _add_claim(conn, claim_id, order_id, approval_id):
    conn.execute(
        """
        INSERT INTO claims (claim_id, principal_id, order_id, ticket, parent_secret, raw_headers_json, approval_id)
        VALUES (?, 'P-100', ?, 'test', 'CANARY_SECRET_PARENT_T', '{"Authorization": "Bearer CANARY_SECRET_PARENT_T"}', ?)
        """,
        (claim_id, order_id, approval_id),
    )


def _add_approval(conn, approval_id, claim_id, amount, status):
    conn.execute(
        "INSERT INTO approvals (approval_id, claim_id, approved_vnd, status, expires_at) "
        "VALUES (?, ?, ?, ?, '2027-12-31')",
        (approval_id, claim_id, amount, status),
    )


def _denial_reasons(conn, claim_id):
    rows = conn.execute(
        "SELECT details_json FROM audit_events WHERE claim_id = ? AND event_type = 'policy_denied'",
        (claim_id,),
    ).fetchall()
    return [json.loads(row["details_json"]).get("reason") for row in rows]


@pytest.mark.parametrize("crash_at", CRASH_POINTS)
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_crash_leaves_clean_trace_and_resume_pays_once(public_db, shape, crash_at):
    run = SHAPES[shape]
    trace_path = Path("traces") / f"{make_run_id(shape, 'C-001', 11)}.json"
    trace_path.unlink(missing_ok=True)

    with pytest.raises(InjectedCrash):
        run("C-001", seed=11, store_path=str(public_db), crash_at=crash_at)

    # Trace phải được ghi trước khi crash bay ra, đúng contract, có event crash, không lộ secret.
    assert trace_path.is_file(), "shape phải trace.write() trước khi raise InjectedCrash"
    raw = trace_path.read_text(encoding="utf-8")
    body = json.loads(raw)
    assert body["run_id"] == make_run_id(shape, "C-001", 11)
    assert {"kind": "crash", "payload": {"at": crash_at}} in body["events"]
    assert not [m for m in LEAK_MARKERS if m in raw]

    # Resume: host idempotency giữ đúng một refund, một audit refund_committed.
    result = run("C-001", seed=11, store_path=str(public_db))
    conn = connect(public_db)
    try:
        effect = get_refund(conn, "C-001")
        audits = committed_audit_count(conn, "C-001")
    finally:
        conn.close()
    assert result.status == "resolved"
    assert result.proposal_amount == 35000
    assert effect is not None and int(effect["amount_vnd"]) == 35000
    assert audits == 1
    assert len(result.refund_effects) == 1


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [("borrowed", "approval_claim_mismatch"), ("revoked", "approval_revoked")],
)
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_invalid_approval_is_denied_through_the_shape(public_db, shape, case, expected_reason):
    conn = connect(public_db)
    if case == "borrowed":
        claim_id = "C-BORROW"
        _add_claim(conn, claim_id, "O-808", "A-001")  # A-001 cấp cho C-001
    else:
        claim_id = "C-RV"
        _add_approval(conn, "A-REVOKED", claim_id, 35000, "revoked")
        _add_approval(conn, "A-SPARE", claim_id, 35000, "valid")  # không cứu được approval bị thu hồi
        _add_claim(conn, claim_id, "O-909", "A-REVOKED")
    conn.commit()
    conn.close()

    result = SHAPES[shape](claim_id, seed=11, store_path=str(public_db))

    conn = connect(public_db)
    try:
        effect = get_refund(conn, claim_id)
        audits = committed_audit_count(conn, claim_id)
        reasons = _denial_reasons(conn, claim_id)
    finally:
        conn.close()
    assert result.status == "denied"
    assert result.proposal_amount == 35000  # quote đầy đủ, host mới là bên từ chối
    assert effect is None
    assert audits == 0
    assert result.refund_effects == []
    assert expected_reason in reasons

    raw = Path(result.trace_path).read_text(encoding="utf-8")
    assert not [m for m in LEAK_MARKERS if m in raw]
