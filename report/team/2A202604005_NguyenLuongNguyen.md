# Báo cáo cá nhân — 2A202604005_NguyenLuongNguyen

## 1. Thông tin thành viên

- Họ tên: Nguyễn Lương Nguyên
- MSSV: 2A202604005
- Email: nglngnguyen@gmail.com
- GitHub: nglngnguyen-gh

## 2. Phần việc phụ trách

- Shape A `workflow`: [`src/lab8/shapes/workflow.py`](../../src/lab8/shapes/workflow.py) (CP2 và phần `crash_at` của CP3).
- Test riêng cho workflow: [`src/tests/test_workflow_shape.py`](../../src/tests/test_workflow_shape.py).
- Cài môi trường và chạy tự kiểm CP1 trên máy cá nhân (Windows, Python 3.12.10).

## 3. Đóng góp cụ thể

**Commit chính:** `38221da` — `feat(workflow): implement shape A deterministic workflow + tests` (nhánh `feat/workflow-shape`).

**Luồng xử lý của workflow** (các bước Python cố định, model không quyết định gì):

1. Đọc claim qua `get_claim_view` (allowlist 4 field), không `SELECT *`. Claim không tồn tại → `failed`.
2. Thiếu `order_id` → `needs_info`. Không lấy mã đơn từ chữ trong ticket.
3. `lookup_order` theo `principal_id`. Không thấy đơn hoặc sai chủ → `escalated`.
4. Tính tiền bằng `compute_compensation` từ dòng order và policy hiện hành. Số ngày trễ trong ticket bị bỏ qua.
5. Quote = 0 → `denied`, không gọi host.
6. Quote > 0 → `durability.issue_refund(conn, claim_id, quote, crash_at=crash_at)`. Host từ chối → `denied` (host ghi `policy_denied`), xung đột số tiền → `failed`, chấp nhận → `resolved`.

**Quyết định kỹ thuật:**

- Truyền **quote đầy đủ** cho host, không tự trừ phần đã hoàn, để host tính trần theo đơn một lần (T13, T14).
- Mọi nhánh return đi qua một hàm `done()` gọi `finish()`, nên nhánh nào cũng ghi trace đúng contract v1 và lấy `refund_effects` / `committed_audit_count` từ ledger.
- Trace không chứa ticket và không chứa dòng claim/order thô. Chỉ ghi order đã lọc qua `ORDER_FIELDS`, quote và kết quả của host.
- MockLLM chỉ được gọi một lần (`draft`) để soạn câu trả lời; prompt chỉ có `status=...`, không có ticket hay dữ liệu đơn.
- Bắt `InjectedCrash` chỉ để ghi trace rồi `raise` lại, không nuốt lỗi; chạy lại dựa vào idempotency key `refund:{claim_id}` của host.

**Test đã thêm** (`src/tests/test_workflow_shape.py`, 38 test, chạy trong cổng mặc định):

| Test | Kiểm tra |
|---|---|
| `test_ticket_delay_is_ignored` | C-002: ticket ghi trễ 5 ngày, order trễ 2 ngày → `denied`, ledger trống ở cả 5 seed (swarm fail trial này ở seed 55) |
| `test_result_does_not_depend_on_seed` | 14 claim public: status, quote và số tiền hoàn giống nhau ở 5 seed |
| `test_trace_has_no_secret_or_pii` | Trace và kết quả không chứa ticket, `CANARY_SECRET_*`, header, SĐT, địa chỉ, ghi chú nội bộ, tên hàng |
| `test_unknown_claim_fails_without_exception` | Claim không tồn tại → `failed`, không ném exception, vẫn có trace |
| `test_crash_then_resume_pays_once` | Crash ở 3 điểm rồi chạy lại → một refund 35.000 và một audit `refund_committed` |
| `test_full_quote_sent_when_order_partly_refunded` | C-014: `proposal_amount` 150.000, ledger 120.000 |

## 4. Bằng chứng

- Commit: `38221da` trên nhánh `feat/workflow-shape` (link GitHub có sau khi push và merge; nếu PR được squash thì cập nhật hash mới).
- `python -m pytest -q -m student -o addopts= -k workflow` → `62 passed`.
- `python -m pytest -q tests/test_workflow_shape.py` → `38 passed`.
- `python -m pytest -q` (cổng host) → `92 passed` sau khi thêm test.
- Quét các file `src/traces/workflow*` không thấy `CANARY_SECRET`, `parent_secret`, `phone`, `address`.
- Run id của workflow trong benchmark: điền sau khi nhóm chạy `lab8.benchmark` ở CP5.

## 5. Công cụ AI đã dùng

- **Claude Code (Claude Opus 5.5) trong VS Code**, dùng để:
  - đọc đề và tóm tắt các checkpoint, luật nghiệp vụ, contract;
  - cài venv, chạy smoke và test tự kiểm CP1;
  - viết `workflow.py` theo docstring hướng dẫn, dựa trên mẫu `swarm_reference.py`;
  - viết bộ test `test_workflow_shape.py`.
- **Cách tự kiểm tra:**
  - chạy ma trận student của workflow (62 passed) và cổng host (xanh) sau mỗi thay đổi;
  - đối chiếu từng nhánh return trong code với bảng output contract trong `docs/contracts.md` và bảng luật trong `docs/business_rules.md`;
  - quét trace bằng tay tìm secret/PII;
  - test crash ở cả 3 điểm `crash_at` để chắc không hoàn hai lần.
- Không dùng AI để tạo số liệu benchmark, run id hay phần tự đánh giá.

## 6. Tự đánh giá
- Hoàn thành phần việc được giao (Shape workflow).
- Học được điểm khác biệt giữa các shapes, điểm mạnh và điểm yếu. Học được cách tạo ra shape workflow.
- Có kiểm tra lại những phần AI đã viết và kiến thức chung.
