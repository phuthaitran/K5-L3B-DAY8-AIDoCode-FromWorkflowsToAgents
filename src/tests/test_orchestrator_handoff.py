"""Shape C must keep the investigator boundary and trace safe."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8.db import connect
from lab8.handoff import READONLY_TOOLS
from lab8.shapes.orchestrator import run_claim


@pytest.mark.student
def test_orchestrator_sends_only_read_tools_and_safe_handoff(public_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = run_claim("C-001", seed=11, store_path=str(public_db))
    trace = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    handoffs = [event["payload"] for event in trace["events"] if event["kind"] == "handoff"]

    assert result.status == "resolved"
    assert trace["run_id"] == result.run_id
    assert len(handoffs) == 1
    assert set(handoffs[0]["allowed_tools"]) <= READONLY_TOOLS
    assert "lookup_order" in handoffs[0]["allowed_tools"]
    assert "compute_compensation" in handoffs[0]["allowed_tools"]
    assert handoffs[0]["facts"] == {}
    blob = json.dumps(trace, ensure_ascii=False)
    for forbidden in ("CANARY_SECRET_", "parent_secret", "raw_headers", "Authorization", "phone", "address", "internal_note", "item_name"):
        assert forbidden not in blob


@pytest.mark.student
def test_missing_order_never_handoffs_or_writes(public_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = run_claim("C-004", seed=11, store_path=str(public_db))
    trace = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    conn = connect(public_db)
    try:
        count = conn.execute("SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = 'C-004'").fetchone()["n"]
    finally:
        conn.close()

    assert result.status == "needs_info"
    assert result.proposal_amount == 0
    assert count == 0
    assert not any(event["kind"] == "handoff" for event in trace["events"])
