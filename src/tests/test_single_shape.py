"""Test riêng cho shape B (single) — Cao Trung Hiếu, 2A202603993.

Kiểm ba ranh giới của shape single ngoài ma trận T01–T14:
1. Trace không chứa ticket, secret hay PII của order.
2. Số ngày trễ khách tự ghi trong ticket không làm thay đổi tiền; vòng ReAct giữ trong 8 bước.
3. Fail-closed: nếu agent kết thúc mà không gọi compute_compensation thì không có refund.
"""

from __future__ import annotations

import json
from pathlib import Path

from lab8.db import connect
from lab8.durability import get_refund
from lab8.shapes import single
from tests.conftest import CLAIMS, WORLD

PII_VALUES = [
    value
    for order in WORLD["orders"]
    for key in ("phone", "address", "internal_note", "item_name")
    if (value := order.get(key))
]


def test_single_trace_has_no_ticket_secret_or_pii(public_db: Path) -> None:
    for claim in CLAIMS:
        result = single.run_claim(claim["claim_id"], seed=11, store_path=str(public_db))
        text = Path(result.trace_path).read_text(encoding="utf-8")
        body = json.loads(text)
        assert body["run_id"] == result.run_id
        assert claim["ticket"] not in text
        assert "CANARY_SECRET" not in text
        for value in PII_VALUES:
            assert value not in text, f"{claim['claim_id']} trace leaks order PII"


def test_single_ignores_delay_written_in_ticket(public_db: Path) -> None:
    # C-002: ticket nói trễ 5 ngày, DB chỉ 2 ngày -> không đủ điều kiện.
    for seed in (11, 22, 33, 44, 55):
        result = single.run_claim("C-002", seed=seed, store_path=str(public_db))
        assert result.status == "denied"
        assert result.proposal_amount == 0
        assert result.refund_effects == []
        assert result.model_calls <= single.MAX_STEPS


def test_single_fails_closed_when_agent_skips_quote(public_db: Path, monkeypatch) -> None:
    # Giả lập agent kết thúc vòng ngay mà không gọi compute_compensation.
    def lazy_agent(conn, budget, *, observation, decide, max_steps=8, worker=False):
        return {"stopped": "final", "final": {"status": "propose"}, "observation": observation}

    monkeypatch.setattr(single, "run_react", lazy_agent)
    result = single.run_claim("C-001", seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 0
    conn = connect(str(public_db))
    try:
        assert get_refund(conn, "C-001") is None
    finally:
        conn.close()
