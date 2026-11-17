"""Tests riêng cho shape A (workflow). Chạy trong cổng mặc định: python -m pytest -q

Bổ sung cho ma trận student T01–T14 ở những điểm workflow phải mạnh hơn swarm:
không tin số ngày trễ trong ticket, kết quả không đổi theo seed, trace không lộ
secret/PII, không ném exception, crash rồi resume vẫn một refund.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8.db import connect
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.shapes.workflow import run_claim
from tests.conftest import BY_ID, CLAIMS, WORLD

SEEDS = [11, 22, 33, 44, 55]

# Mọi chuỗi nhạy cảm có trong dữ liệu public: secret của claim, header, và các field
# của order bị loại khỏi allowlist (SĐT, địa chỉ, ghi chú nội bộ, tên hàng).
FORBIDDEN = sorted(
    {c["parent_secret"] for c in CLAIMS}
    | {v for c in CLAIMS for v in c["raw_headers"].values()}
    | {str(o[k]) for o in WORLD["orders"] for k in ("phone", "address", "internal_note", "item_name")}
)


def _ledger(store: Path, claim_id: str) -> tuple[dict | None, int]:
    conn = connect(store)
    try:
        return get_refund(conn, claim_id), committed_audit_count(conn, claim_id)
    finally:
        conn.close()


@pytest.mark.parametrize("seed", SEEDS)
def test_ticket_delay_is_ignored(public_db, seed):
    # C-002: ticket nói trễ 5 ngày, order thật trễ 2 ngày -> denied ở mọi seed.
    # Swarm fail đúng trial này ở seed 55; workflow không được fail.
    assert "5 ngày" in BY_ID["C-002"]["ticket"]
    result = run_claim("C-002", seed=seed, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
    assert _ledger(public_db, "C-002") == (None, 0)


@pytest.mark.parametrize("claim_id", sorted(BY_ID))
def test_result_does_not_depend_on_seed(tmp_path, claim_id):
    # Workflow không để model quyết gì, nên status và số tiền phải giống nhau ở mọi seed.
    from lab8.db import init_store

    outcomes = set()
    for seed in SEEDS:
        store = tmp_path / f"{claim_id}-{seed}.sqlite"
        init_store(store, WORLD, CLAIMS).close()
        result = run_claim(claim_id, seed=seed, store_path=str(store))
        refunded = sum(int(e["amount_vnd"]) for e in result.refund_effects)
        outcomes.add((result.status, result.proposal_amount, refunded))
    assert len(outcomes) == 1, outcomes


@pytest.mark.parametrize("claim_id", sorted(BY_ID))
def test_trace_has_no_secret_or_pii(public_db, claim_id):
    result = run_claim(claim_id, seed=11, store_path=str(public_db))
    body = Path(result.trace_path).read_text(encoding="utf-8")
    trace = json.loads(body)
    assert trace["run_id"] == result.run_id
    assert isinstance(trace["events"], list) and trace["events"]
    # Ticket là chữ người dùng: không được chép vào trace.
    assert BY_ID[claim_id]["ticket"] not in body
    leaked = [s for s in FORBIDDEN if s and s in body]
    assert leaked == []
    assert not any(s and s in json.dumps(result.as_dict(), ensure_ascii=False) for s in FORBIDDEN)


def test_unknown_claim_fails_without_exception(public_db):
    result = run_claim("C-DOES-NOT-EXIST", seed=11, store_path=str(public_db))
    assert result.status == "failed"
    assert result.error_reason == "unknown_claim"
    assert result.proposal_amount == 0
    assert Path(result.trace_path).exists()


@pytest.mark.parametrize("crash_at", ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"])
def test_crash_then_resume_pays_once(public_db, crash_at):
    # C-001 (T01): trễ 4 ngày, approval 35.000. Crash ở bất kỳ điểm nào rồi chạy lại
    # vẫn chỉ ra một dòng ledger và một audit refund_committed.
    with pytest.raises(InjectedCrash):
        run_claim("C-001", seed=11, store_path=str(public_db), crash_at=crash_at)
    result = run_claim("C-001", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.proposal_amount == 35000
    effect, audits = _ledger(public_db, "C-001")
    assert effect is not None and int(effect["amount_vnd"]) == 35000
    assert audits == 1


def test_full_quote_sent_when_order_partly_refunded(public_db):
    # C-014 (T14): đơn đã hoàn 30.000 ship, nay hỏng hàng đã verify (150.000).
    # proposal_amount là quote đầy đủ; ledger chỉ ghi phần chênh do host tính.
    result = run_claim("C-014", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.proposal_amount == 150000
    effect, audits = _ledger(public_db, "C-014")
    assert int(effect["amount_vnd"]) == 120000
    assert audits == 1
