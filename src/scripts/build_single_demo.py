"""Sinh trang demo HTML cho shape B (single): khung chat + các bước agent đã làm.

Chạy trong thư mục src/:
    python scripts/build_single_demo.py

Mỗi claim public chạy trên một store mới bằng chính `lab8.shapes.single.run_claim`.
Các bước hiển thị lấy từ trace của lần chạy đó; số liệu giải thích phép tính đọc bằng
tool allowlist (lookup_order, lookup_refund_history, lookup_policy) và lab8.policy.
Không đọc parent_secret, raw_headers, phone, address, internal_note, item_name.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))

from lab8 import policy, tools  # noqa: E402
from lab8.app import prepare_store  # noqa: E402
from lab8.compensation import ELIGIBLE_STATUSES, _clause_amount  # noqa: E402
from lab8.config_loader import as_of, repo_path  # noqa: E402
from lab8.db import connect, load_jsonl  # noqa: E402
from lab8.durability import InjectedCrash  # noqa: E402
from lab8.mock_llm import parse_delay_days  # noqa: E402
from lab8.shapes.single import run_claim  # noqa: E402

SEED = 11
OUT = SRC.parent / "report" / "team" / "demo" / "single_agent_chat.html"
TEMPLATE = Path(__file__).with_name("single_demo_template.html")

def vnd(n: int | None) -> str:
    return "—" if n is None else f"{int(n):,}".replace(",", ".") + " đ"


def calc(label: str, expr: str, ok: bool | None = None) -> dict:
    return {"label": label, "expr": expr, "ok": ok}


def explain_quote(order: dict, policies: list[dict]) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    amounts: list[str] = []
    if order["status"] not in ELIGIBLE_STATUSES:
        rows.append(calc("status", f"{order['status']} ∉ {{delivered, delivered_late}} → quote = 0", False))
        return rows, amounts
    today = as_of()
    for pol in policies:
        if not pol["is_current"] or str(pol["effective_date"]) > today:
            ids = ", ".join(c["clause_id"] for c in pol["clauses"])
            rows.append(calc(pol["policy_id"], f"is_current = {str(pol['is_current']).lower()} → bỏ qua ({ids})", False))
            continue
        for cl in pol["clauses"]:
            amt = _clause_amount(order, cl)
            if cl["kind"] == "late_delivery":
                ok = int(order["delay_days"]) >= int(cl["min_delay_days"])
                sign = "≥" if ok else "<"
                tail = f"→ shipping_fee_vnd = {vnd(amt)}" if ok else "→ 0"
                expr = f"delay_days {order['delay_days']} {sign} {cl['min_delay_days']} {tail}"
            else:
                if not order["damage_verified"]:
                    expr, ok = "damage_verified = false → 0", False
                else:
                    expr = f"min(max_refund {vnd(cl['max_refund_vnd'])}, paid {vnd(order['paid_vnd'])}) = {vnd(amt)}"
                    ok = True
            rows.append(calc(cl["clause_id"], expr, ok and amt > 0))
            amounts.append(vnd(amt))
    return rows, amounts


def approval_view(conn, claim_id: str) -> dict | None:
    row = conn.execute("SELECT approval_id FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if row is None or not row["approval_id"]:
        return None
    ap = conn.execute(
        "SELECT approval_id, claim_id, approved_vnd, status, expires_at FROM approvals WHERE approval_id = ?",
        (row["approval_id"],),
    ).fetchone()
    return dict(ap) if ap else {"approval_id": row["approval_id"], "missing": True}


def host_rows(claim_id: str, ap: dict | None, quote: int, paid: int, already: int, decision) -> list[dict]:
    today = as_of()
    rows: list[dict] = []
    if ap is None or ap.get("missing"):
        rows.append(calc("approval", "không có approval → từ chối (missing_approval)", False))
        return rows
    rows.append(calc("approval_id", f"{ap['approval_id']} cấp cho {ap['claim_id']}", ap["claim_id"] == claim_id))
    rows.append(calc("status", f"{ap['status']}", ap["status"] == "valid"))
    rows.append(calc("expires_at", f"{ap['expires_at']} ≥ hôm nay {today}", str(ap["expires_at"]) >= today))
    if not decision.ok and decision.reason not in ("order_already_refunded", "capped_to_zero"):
        return rows
    step1 = quote - already
    rows.append(calc("trần theo đơn", f"quote − đã hoàn bởi claim KHÁC = {vnd(quote)} − {vnd(already)} = {vnd(step1)}", step1 > 0))
    if step1 <= 0:
        return rows
    step2 = min(step1, int(ap["approved_vnd"]))
    rows.append(calc("trần approval", f"min({vnd(step1)}, approved {vnd(ap['approved_vnd'])}) = {vnd(step2)}", True))
    step3 = min(step2, paid - already)
    rows.append(calc("trần đã trả", f"min({vnd(step2)}, paid − đã hoàn = {vnd(paid - already)}) = {vnd(step3)}", True))
    return rows


def reply_text(status: str, reason: str | None, order_id: str | None, ledger: int | None) -> str:
    if status == "resolved":
        return f"LogiX đã hoàn {vnd(ledger)} cho đơn {order_id}. Tiền sẽ về tài khoản của bạn trong vài ngày."
    if status == "needs_info":
        return "Bạn vui lòng cung cấp mã đơn hàng để LogiX kiểm tra yêu cầu."
    if status == "escalated":
        return "LogiX không xác minh được đơn này thuộc tài khoản của bạn. Yêu cầu đã được chuyển cho nhân viên xử lý."
    if status == "denied":
        texts = {
            "no_entitlement": "đơn chưa đủ điều kiện hoàn theo chính sách hiện hành",
            "order_already_refunded": "đơn này đã được hoàn đủ trước đó",
            "approval_claim_mismatch": "phiếu duyệt không thuộc yêu cầu này",
            "missing_approval": "yêu cầu chưa có phiếu duyệt hợp lệ",
            "approval_expired": "phiếu duyệt đã hết hạn",
            "approval_revoked": "phiếu duyệt đã bị thu hồi",
        }
        why = texts.get(reason or "", reason or "không đủ điều kiện")
        if reason and reason.startswith("order_status_"):
            why = f"trạng thái đơn là {reason.removeprefix('order_status_')}"
        return f"Rất tiếc, LogiX chưa thể hoàn tiền: {why}."
    return f"Có lỗi khi xử lý yêu cầu ({reason}). Nhân viên sẽ kiểm tra lại."


def snapshot(store: str, cid: str) -> dict:
    """Đọc DB bằng tool allowlist + policy.authorize (chỉ đọc) để giải thích phép tính."""
    conn = connect(store)
    try:
        view = tools.get_claim_view(conn, cid)
        order_id, principal = view["order_id"], view["principal_id"]
        ov = tools.lookup_order(conn, order_id, principal) if order_id else None
        hist = tools.lookup_refund_history(conn, order_id, principal) if order_id else None
        ap = approval_view(conn, cid)
        host_pre = None
        if ov and ov["visible"]:
            q = tools.compute_compensation(conn, ov["order"])["amount_vnd"]
            already = policy.order_refunded_vnd(conn, order_id, exclude_claim_id=cid)
            paid = int(ov["order"]["paid_vnd"])
            decision = policy.authorize(conn, cid, q, paid_vnd=paid, already_refunded_vnd=already)
            host_pre = {"already": already, "paid": paid, "decision": decision}
        return {"view": view, "ov": ov, "hist": hist, "ap": ap, "host_pre": host_pre}
    finally:
        conn.close()


def build_case(claim: dict) -> dict:
    cid = claim["claim_id"]
    mid = claim["matrix_id"]
    with tempfile.TemporaryDirectory() as tmp:
        store = str(Path(tmp) / "demo.sqlite")
        prepare_store(store)
        runs = []
        if mid == "T12":
            try:
                run_claim(cid, seed=SEED, store_path=store, crash_at="after_effect_before_checkpoint")
            except InjectedCrash:
                runs.append({"label": "Lần 1 — crash giả sau khi ghi ledger", "crash": True})
        repeat = 2 if mid == "T11" else 1
        for i in range(repeat):
            snap = snapshot(store, cid)  # đọc lại DB ngay trước mỗi lần chạy
            res = run_claim(cid, seed=SEED, store_path=store)
            trace = json.loads(Path(res.trace_path).read_text(encoding="utf-8"))
            label = "Chạy lại (resume)" if mid == "T12" else (f"Lần {i + 1}" if repeat > 1 else "")
            runs.append({"label": label, "res": res, "trace": trace, "snap": snap})
        view = runs[-1]["snap"]["view"]
        order_id = view["order_id"]

        conn = connect(store)
        audits = [
            {"type": r["event_type"], "details": json.loads(r["details_json"] or "{}")}
            for r in conn.execute(
                "SELECT event_type, details_json FROM audit_events WHERE claim_id = ? ORDER BY rowid", (cid,)
            )
        ]
        ledger_rows = conn.execute(
            "SELECT amount_vnd FROM refund_ledger WHERE claim_id = ?", (cid,)
        ).fetchall()
        # Lấy toàn bộ policy (kể cả cũ) để giải thích vì sao policy cũ bị bỏ qua.
        policies_full = [tools._policy_dict(r) for r in conn.execute("SELECT * FROM policies")]
        conn.close()

    steps: list[dict] = []
    final = runs[-1]
    res = final["res"]
    for run in runs:
        if run.get("crash"):
            steps.append({"kind": "crash", "fn": "durability.issue_refund(..., crash_at=\"after_effect_before_checkpoint\")",
                          "title": run["label"], "rows": [calc("InjectedCrash", "đã ghi ledger, chưa kịp checkpoint → lỗi bay ra, shape không bắt", None)]})
            continue
        if run["label"]:
            steps.append({"kind": "divider", "title": run["label"]})
        s = run["snap"]
        steps.extend(steps_from_trace(run, claim, s["view"], s["ov"], s["hist"], policies_full, s["ap"], s["host_pre"]))

    ledger = int(ledger_rows[0]["amount_vnd"]) if ledger_rows else None
    steps.append({
        "kind": "result",
        "fn": "finish(...) → RunResult",
        "title": "Kết quả trả về",
        "rows": [
            calc("status", res.status, res.status == "resolved"),
            calc("proposal_amount", vnd(res.proposal_amount)),
            calc("ledger", f"{len(ledger_rows)} dòng · {vnd(ledger) if ledger else '0 đ'}"),
            calc("audit", ", ".join(a["type"] + (f" ({a['details'].get('reason')})" if a["details"].get("reason") else "") for a in audits) or "không có"),
            calc("budget", f"{res.model_calls} lần gọi model · {res.tool_calls} lần gọi tool · cost {res.cost_estimate:,.2f}"),
        ],
    })
    last_reason = res.error_reason
    host_called = any(s["kind"] in ("host", "crash") for s in steps)
    return {
        "id": cid,
        "matrix": mid,
        "ticket": view["ticket"],
        "status": res.status,
        "host_called": host_called,
        "pending": pending_text(res.status, last_reason, res.proposal_amount, order_id, host_called),
        "host_skip": None if host_called else skip_reason(res.status, last_reason),
        "reply": reply_text(res.status, last_reason, order_id, ledger),
        "steps": steps,
    }


def pending_text(status: str, reason: str | None, proposal: int, order_id: str | None, host_called: bool) -> str:
    """Tin nhắn agent gửi trước khi HOST duyệt."""
    if host_called:
        return f"Agent đề xuất hoàn {vnd(proposal)} cho đơn {order_id} (quote đầy đủ). Đang chờ HOST duyệt…"
    if status == "needs_info":
        return "Agent không thấy mã đơn trong claim nên chưa thể tính tiền. Đang chờ HOST xác nhận…"
    if status == "escalated":
        return "Agent không xác minh được đơn thuộc về người gửi. Đang chờ HOST xác nhận…"
    if status == "denied":
        return f"Agent tính quote = 0 đ ({reason}), không có khoản nào để đề xuất. Đang chờ HOST xác nhận…"
    return f"Agent dừng với lỗi ({reason}). Đang chờ HOST xác nhận…"


def skip_reason(status: str, reason: str | None) -> list[dict]:
    """Khi shape không gọi issue_refund: giải thích vì sao HOST không có gì để ghi."""
    why = {
        "needs_info": "thiếu order_id → shape trả needs_info, không gọi issue_refund",
        "escalated": f"đơn không xem được ({reason}) → shape trả escalated, không gọi issue_refund",
        "denied": "quote = 0 → shape tự trả denied, không gọi issue_refund (không có audit policy_denied)",
    }.get(status, f"shape dừng ({reason}), không gọi issue_refund")
    return [calc("issue_refund", "không được gọi", False), calc("lý do", why), calc("ledger", "không ghi dòng nào")]


def steps_from_trace(run, claim, view, ov, hist, policies, ap, host_pre) -> list[dict]:
    cid = claim["claim_id"]
    events = run["trace"]["events"]
    out: list[dict] = []
    agent_step = 0
    quote_amt = 0
    for ev in events:
        k, p = ev["kind"], ev["payload"]
        if k == "claim":
            rows = [calc("found", str(p["found"]).lower(), p["found"])]
            if p["found"]:
                rows.append(calc("order_id", view["order_id"] or "không có", bool(view["order_id"])))
                rows.append(calc("principal_id", view["principal_id"]))
            out.append({"kind": "code", "fn": f"get_claim_view(\"{cid}\")", "title": "Code đọc claim (chỉ cột an toàn)", "rows": rows})
        elif k == "react_step":
            agent_step += 1
            if "tool" in p:
                out.append({"kind": "agent", "fn": "MockLLM.complete(purpose=\"react\")",
                            "title": f"Agent bước {agent_step}: chọn tool → {p['tool']}", "rows": []})
                out.append(tool_step(p["tool"], view, ov, hist, policies))
            else:
                out.append({"kind": "agent", "fn": "MockLLM.complete(purpose=\"react\")",
                            "title": f"Agent bước {agent_step}: kết thúc vòng → {p['final']}", "rows": []})
        elif k == "quote":
            quote_amt = int(p["amount_vnd"])
            out.append({"kind": "code", "fn": "quote = memory[\"compute_compensation\"][\"amount_vnd\"]",
                        "title": "Code lấy quote từ kết quả tool, kiểm quote > 0",
                        "rows": [calc("quote > 0", f"{vnd(quote_amt)} > 0", quote_amt > 0)]})
        elif k == "issue_refund":
            hp = host_pre
            rows = host_rows(cid, ap, quote_amt, hp["paid"], hp["already"], hp["decision"])
            if not hp["decision"].ok:
                rows.append(calc("authorize()", f"từ chối: {hp['decision'].reason} → ghi audit policy_denied", False))
            else:
                rows.append(calc("authorize()", f"được ghi {vnd(hp['decision'].amount_vnd)}", True))
            rows.append(calc("host trả về", f"ok = {str(p['ok']).lower()} · reason = {p['reason']}", p["ok"]))
            out.append({"kind": "host", "fn": f"durability.issue_refund(\"{cid}\", {quote_amt}, crash_at)",
                        "title": "Host kiểm approval, tính trần, chống ghi trùng", "rows": rows})
    return out


def tool_step(name: str, view, ov, hist, policies) -> dict:
    if name == "lookup_order":
        rows = [calc("visible", f"{str(ov['visible']).lower()} ({ov['reason']})", ov["visible"])]
        if ov["visible"]:
            o = ov["order"]
            rows += [
                calc("status", o["status"]),
                calc("delay_days (DB)", str(o["delay_days"])),
                calc("shipping_fee_vnd", vnd(o["shipping_fee_vnd"])),
                calc("paid_vnd", vnd(o["paid_vnd"])),
                calc("damage_verified", str(o["damage_verified"]).lower()),
            ]
            said = parse_delay_days(view["ticket"])
            if said is not None and said != int(o["delay_days"]):
                rows.append(calc("ticket nói", f"trễ {said} ngày ≠ DB {o['delay_days']} ngày → dùng số trong DB", False))
        return {"kind": "tool", "fn": f"lookup_order(\"{view['order_id']}\", \"{view['principal_id']}\")",
                "title": "Tool đọc: tra đơn theo đúng chủ claim", "rows": rows}
    if name == "lookup_refund_history":
        rows = [calc("đã hoàn cho đơn", f"{hist['refund_count']} lần · {vnd(hist['refunded_vnd'])}")]
        rows.append(calc("ghi chú", "tính cả claim này; chỉ để biết, KHÔNG tự trừ — host tự trừ phần của claim khác"))
        return {"kind": "tool", "fn": f"lookup_refund_history(\"{view['order_id']}\", \"{view['principal_id']}\")",
                "title": "Tool đọc: lịch sử hoàn tiền của đơn", "rows": rows}
    if name == "compute_compensation":
        rows, amounts = explain_quote(ov["order"], policies)
        if amounts:
            best = max(_clause_amount(ov["order"], c) for p in policies if p["is_current"] for c in p["clauses"])
            rows.append(calc("quote", f"max({', '.join(amounts)}) = {vnd(best)}", best > 0))
        return {"kind": "tool", "fn": "compute_compensation(order) → compensation.quote()",
                "title": "Tool đọc: tính quote theo policy hiện hành", "rows": rows}
    return {"kind": "tool", "fn": name, "title": name, "rows": []}


def main() -> None:
    claims = load_jsonl(repo_path("data", "public_claims.jsonl"))
    cases = [build_case(c) for c in claims]
    payload = json.dumps({"seed": SEED, "as_of": as_of(), "cases": cases}, ensure_ascii=False, default=str)
    for bad in ("CANARY", "parent_secret", "Bearer", "phone", "address", "internal_note", "item_name"):
        if bad in payload:
            raise SystemExit(f"dữ liệu demo chứa '{bad}' — dừng, không ghi file")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload.replace("</", "<\\/"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(cases)} claims)")


if __name__ == "__main__":
    main()
