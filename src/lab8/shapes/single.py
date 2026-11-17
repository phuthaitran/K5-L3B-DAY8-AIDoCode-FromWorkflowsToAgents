"""Shape B — SINGLE AGENT (ReAct) - Cao Trung Hiếu — 2A202603993
BÀI TOÁN
  Khách gửi một "claim" (yêu cầu hoàn tiền): giao trễ hoặc hàng hỏng. Ta phải quyết định:
  hoàn bao nhiêu tiền, hay từ chối, hay hỏi thêm, hay chuyển cho người xử lý.

Ý TƯỞNG CỦA SHAPE NÀY
  Thay vì viết sẵn các bước cố định (như workflow), ta để MỘT agent tự đi từng bước theo
  vòng ReAct: "nghĩ -> chọn tool -> đọc kết quả -> nghĩ tiếp". Agent được tự chọn tool,
  NHƯNG chỉ được dùng tool ĐỌC (xem đơn, xem lịch sử hoàn, tính quote).
  Hai việc quan trọng nhất là TÍNH TIỀN và GHI TIỀN thì agent không được làm:
  code tính tiền bằng công thức cố định, và chỉ host (durability.issue_refund) được ghi.

  Tại sao chia như vậy? Model (LLM) có thể sai, có thể bị lừa bởi chữ trong ticket
  (ví dụ khách viết "trễ 9 ngày" hay "ignore policy"). Nếu để model quyết số tiền
  thì một câu lừa trong ticket là đủ để mất tiền. Còn chọn thứ tự đọc dữ liệu thì có sai
  cũng không gây hại: tệ nhất là thiếu thông tin rồi dừng.
  => Model lo phần "đi tìm thông tin", code lo phần "tiền và quyền".

-------------------------------------------------------------------------------------
BƯỚC 1 — Code tự đọc claim (get_claim_view), chưa cho agent làm gì
  - get_claim_view chỉ trả các cột an toàn: claim_id, principal_id, order_id, ticket.
    Không dùng "SELECT *" vì bảng claims có cột parent_secret (CANARY_SECRET_*):
    lỡ đọc nguyên dòng rồi ghi vào trace là lộ secret, vi phạm must-pass.
  - Claim không tồn tại -> status "failed" (theo bảng contract). Không có gì để xử lý.

BƯỚC 2 — Vòng ReAct (run_react, tối đa 8 bước)
  Mỗi bước, hàm decide() đóng vai "bộ não" của agent:
    a) Gọi MockLLM một lần. Mục đích: tính cost và token giống như có model thật suy nghĩ,
       để khi benchmark so cost giữa các shape cho công bằng. Câu trả lời của MockLLM
       KHÔNG được dùng để quyết định tiền.
    b) Chọn việc tiếp theo dựa trên những gì đã biết:
       - Claim không có order_id        -> kết thúc: "needs_info".
         Không đoán mã đơn từ chữ trong ticket, vì đó là dữ liệu khách tự viết, không đáng tin.
       - Chưa xem đơn                   -> gọi lookup_order(order_id, principal_id).
         Tool này kiểm luôn: đơn có tồn tại không, có đúng là của người gửi claim không.
       - Đơn không thấy / không phải của khách -> kết thúc: "escalated".
         Không được báo SĐT, địa chỉ, tên hàng của đơn người khác (bảo vệ thông tin cá nhân).
       - Chưa xem lịch sử hoàn          -> gọi lookup_refund_history.
         Chỉ để agent "biết" đơn đã được hoàn bao nhiêu. KHÔNG tự trừ số này (xem bước 4).
       - Chưa có quote                  -> gọi compute_compensation(order lấy từ DATABASE).
         Dùng số ngày trễ, phí ship, damage_verified trong DB, không dùng số trong ticket.
         Hàm này chỉ áp policy đang hiệu lực (is_current), bỏ qua policy cũ hoặc tương lai.
       - Đã có đủ                       -> kết thúc: "propose" (đề xuất hoàn tiền).
  - Kết quả thật của từng tool được lưu vào biến `memory` (do code giữ), vì run_react
    chỉ đưa cho agent kết quả của bước NGAY TRƯỚC, không đưa toàn bộ lịch sử.

BƯỚC 3 — Giới hạn 8 bước
  Agent có thể bị lặp vô hạn (gọi tool mãi không dừng), làm tốn tiền.
  Đề bắt buộc cap = 8. Hết 8 bước chưa xong -> "failed" (step_cap). Chấp nhận fail còn hơn đốt tiền.

BƯỚC 4 — Code (không phải agent) quyết số tiền và gọi host
  - Lấy số tiền từ KẾT QUẢ TOOL compute_compensation đã lưu trong memory,
    không lấy con số agent "nói ra". Model chỉ đọc, code mới tính tiền.
  - Quote = 0 (trễ < 3 ngày, đơn hủy, hỏng chưa verify...) -> "denied", KHÔNG gọi host.
  - Quote > 0 -> durability.issue_refund(conn, claim_id, quote ĐẦY ĐỦ, crash_at=crash_at).
    Host (code có sẵn, không được sửa) làm ba việc:
      * Kiểm approval: có approval không, hết hạn chưa, bị thu hồi chưa, có đúng claim này không.
      * Trần theo đơn: trừ phần các claim khác đã hoàn cho cùng đơn.
      * Idempotency: mỗi claim tối đa 1 dòng ledger (khóa refund:{claim_id}).
    Vì sao truyền quote ĐẦY ĐỦ mà không tự trừ phần đã hoàn? Host đã tự trừ rồi.
    Nếu shape trừ trước thì bị trừ 2 lần -> hoàn thiếu tiền (test T14 fail).
    Ví dụ T14: đã hoàn 30.000 ship, nay hỏng hàng đáng 150.000 -> truyền 150.000,
    host tự ghi 120.000 (phần chênh).
  - Đọc kết quả host trả về:
      ok        -> "resolved"  (đã ghi đúng 1 dòng ledger + 1 audit refund_committed)
      conflict  -> "failed"    (gọi lại cùng claim với số khác số đã ghi; host giữ số cũ)
      bị chặn   -> "denied"    (host tự ghi audit policy_denied, grader cần audit này)
    Ở cả ba trường hợp, proposal_amount vẫn là quote đầy đủ, theo contract.

BƯỚC 5 — Crash và trace
  - crash_at là "crash giả" mà bài lab cài vào để kiểm tra độ bền. Ta chuyển nó xuống host
    và KHÔNG bắt InjectedCrash: chỉ ghi trace rồi để lỗi bay ra. Lý do: test cần thấy crash
    thật sự xảy ra, rồi chạy lại (resume) vẫn chỉ ra 1 refund nhờ idempotency của host.
    Nếu ta "nuốt" crash thì test T12 không kiểm được gì và bị đánh fail.
  - Mọi nhánh return đều đi qua finish(): hàm này tự đọc ledger để điền refund_effects
    và committed_audit_count (không tự điền tay) và ghi file trace.
  - Trace là ranh giới bảo mật: grader quét trace để tìm secret và thông tin cá nhân.
    Vì vậy trace chỉ ghi tên tool, status, số tiền, lý do. Không ghi ticket, args
    (có order row) hay claim row.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8 import durability
from lab8.db import connect
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8


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

    # Bước 1: code đọc claim qua view allowlist.
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim["found"]:
        trace.add("claim", {"found": False})
        return done("failed", 0, "unknown_claim")
    trace.add("claim", {"found": True, "has_order_id": bool(claim["order_id"])})

    # Bước 2: vòng ReAct. Agent chỉ thấy claim_id / order_id / principal_id + ticket (để đọc, không tin số).
    principal_id = claim["principal_id"]
    order_id = claim["order_id"]
    memory: dict[str, Any] = {}  # kết quả tool thật, code dùng sau vòng lặp

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        last = seen.get("last_tool")
        if last:
            memory[last] = seen["last_result"]
        # "Suy nghĩ" của model: MockLLM theo seed, chỉ để đếm cost; không quyết định tiền.
        complete(budget, seed=seed, purpose="react", prompt=f"{claim['ticket']}|last={last}")

        if not order_id:
            action: dict[str, Any] = {"final": {"status": "needs_info", "reason": "missing_order_id"}}
        elif "lookup_order" not in memory:
            action = {"tool": "lookup_order", "args": {"order_id": order_id, "principal_id": principal_id}}
        elif not memory["lookup_order"]["visible"]:
            action = {"final": {"status": "escalated", "reason": memory["lookup_order"]["reason"]}}
        elif "lookup_refund_history" not in memory:
            action = {
                "tool": "lookup_refund_history",
                "args": {"order_id": order_id, "principal_id": principal_id},
            }
        elif "compute_compensation" not in memory:
            # Quote từ dòng order trong DB, không dùng số ngày trễ khách viết trong ticket.
            action = {"tool": "compute_compensation", "args": {"order": memory["lookup_order"]["order"]}}
        else:
            action = {"final": {"status": "propose"}}

        trace.add("react_step", _safe_action(action))
        return action

    loop = run_react(
        conn,
        budget,
        observation={"claim": {"claim_id": claim_id, "order_id": order_id}},
        decide=decide,
        max_steps=MAX_STEPS,
    )
    final = loop["final"]

    # Bước 3: các nhánh kết thúc sớm.
    if loop["stopped"] == "step_cap":
        return done("failed", 0, "step_cap")
    if final["status"] in ("needs_info", "escalated"):
        return done(final["status"], 0, final.get("reason"))

    # Bước 4: tiền lấy từ kết quả tool compute_compensation, không lấy từ model hay ticket.
    quote = memory.get("compute_compensation") or {}
    proposal = int(quote.get("amount_vnd", 0))
    trace.add(
        "quote",
        {"amount_vnd": proposal, "reason": quote.get("reason"), "clause_ids": quote.get("clause_ids", [])},
    )
    if proposal <= 0:
        return done("denied", 0, quote.get("reason"))

    # Bước 5: host là cửa ghi duy nhất. Truyền quote đầy đủ + crash_at, không bắt InjectedCrash.
    budget.add_tool(tool_cost())
    try:
        outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except durability.InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    trace.add("issue_refund", {"ok": outcome["ok"], "reason": outcome["reason"]})

    if outcome["ok"]:
        return done("resolved", proposal, None)
    if outcome["conflict"]:
        return done("failed", proposal, outcome["reason"])
    return done("denied", proposal, outcome["reason"])


def _safe_action(action: dict[str, Any]) -> dict[str, Any]:
    """Chỉ ghi tên tool / status vào trace, không ghi args (order row) hay ticket."""
    if "final" in action:
        return {"final": action["final"].get("status")}
    return {"tool": action["tool"]}
