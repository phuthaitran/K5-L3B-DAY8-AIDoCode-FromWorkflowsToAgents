# Báo cáo cá nhân — Giang Thái Sơn (2A202603964)

## 1. Thông tin thành viên

- Họ tên: Giang Thái Sơn
- MSSV: 2A202603964
- Email: giangson309@gmail.com
- GitHub: son309

## 2. Phần việc phụ trách

- Triển khai `run_claim` của shape C tại [`src/lab8/shapes/orchestrator.py`](../../src/lab8/shapes/orchestrator.py), thay cho stub `not_implemented`.
- Ghép cơ chế handoff và investigator chỉ đọc có sẵn (`lab8.handoff.make_handoff`, `lab8.runtime.run_readonly_investigators`) vào luồng xử lý claim. Không sửa mã host, ledger, policy hoặc thư viện handoff.
- Bổ sung test tích hợp tại [`src/tests/test_orchestrator_handoff.py`](../../src/tests/test_orchestrator_handoff.py).

## 3. Đóng góp cụ thể

**Commit chính:** [`763284a`](https://github.com/phuthaitran/K5-L3B-DAY8-AIDoCode-FromWorkflowsToAgents/commit/763284acc22c91512679f8a394b8e3dbf4e24cf7) — `feat: implement orchestrator handoff and tests` trên nhánh `main`. Commit gồm hai file nêu trên.

**Luồng xử lý và quyết định kỹ thuật:**

1. Đọc claim qua `get_claim_view`; claim không tồn tại trả `failed`, thiếu `order_id` trả `needs_info` mà không giao việc hay ghi ledger.
2. Tạo handoff bằng `make_handoff` với `facts={}` và danh sách tool đọc: `lookup_order`, `lookup_policy`, `lookup_refund_history`, `compute_compensation`. Investigator không được nhận tool ghi `issue_refund`.
3. Gọi `run_readonly_investigators` để tra đơn theo phạm vi `principal_id`. Đơn không hiển thị trả `escalated`; số ngày trễ trong ticket không được dùng thay dữ liệu đơn.
4. Lấy quote từ `compute_compensation` trên dữ liệu đơn đã tra. Quote bằng 0 trả `denied` và không gọi host. Quote dương được truyền **đầy đủ** cho `durability.issue_refund`; host kiểm approval, trần hoàn theo đơn và idempotency. Shape không tự trừ khoản đã hoàn trước đó.
5. Truyền `crash_at` xuống host. Nếu xảy ra `InjectedCrash`, ghi trace rồi ném lại để test có thể chạy tiếp kịch bản resume. Các nhánh trả kết quả đều dùng `finish()` để lấy refund và audit từ ledger và ghi trace đúng contract.
6. Trace chỉ ghi handoff đã lọc, trạng thái, lý do và số tiền; không ghi ticket, claim/order thô, secret, header hoặc thông tin cá nhân. MockLLM chỉ dùng cho bước lập kế hoạch và soạn chữ bằng prompt cố định, không quyết định số tiền hay ghi refund.

**Test đã thêm:**

| Test | Điều được kiểm tra |
| --- | --- |
| `test_orchestrator_sends_only_read_tools_and_safe_handoff` | Claim C-001 được giải quyết; trace có handoff; handoff chỉ cấp tool đọc và không có facts thô; trace không chứa canary secret hoặc tên field PII. |
| `test_missing_order_never_handoffs_or_writes` | Claim C-004 thiếu mã đơn trả `needs_info`, không tạo handoff và không có dòng refund. |

## 4. Bằng chứng và kết quả kiểm tra

Các lệnh sau được chạy trong `src/` sau khi triển khai; kết quả là bằng chứng từ phiên kiểm tra, không phải số liệu benchmark nộp bài. Trong bảng, `python` là cách viết ngắn: phiên kiểm tra dùng Python 3.13 từ venv của một dự án khác vì Python mặc định trên máy thiếu `PyYAML` và mạng không cho tải gói.

| Kiểm tra | Kết quả |
| --- | --- |
| `python -m lab8.smoke` | `lab8.smoke pass` |
| `python -m pytest -q -m student -o addopts= -k orchestrator` | **64 passed**: 62 ca ma trận cho shape C và 2 test mới |
| `python -m pytest -q -m student -o addopts=` | **250 passed** cho toàn bộ ma trận student của repo |
| `python -m pytest -q` | **95 passed** cho cổng mặc định |
| `python -m lab8.crash_test --count 20 --out <file-tạm>` | `crash_safety 20/20`; file này chưa phải `src/reports/crash.json` để nộp |

`python -m lab8.check_submission` xác nhận shape orchestrator đúng format và **12/12 claim public pass ở seed 11**. Công cụ vẫn báo thiếu benchmark, crash report chính thức và các tài liệu nhóm; các việc đó thuộc bước tổng hợp CP4–CP5.

## 5. Công cụ AI đã dùng và cách kiểm tra

- **OpenAI Codex** hỗ trợ đọc contract, triển khai shape C, viết hai test và rà kết quả kiểm tra. Code của lab chỉ gọi `MockLLM`, không dùng model thật hay API key.
- Kết quả được kiểm bằng ma trận student, cổng test mặc định, crash suite và `check_submission`; đối chiếu nhánh `needs_info`, `escalated`, `denied`, `resolved` với [`docs/contracts.md`](../../docs/contracts.md) và kiểm tra handoff/trace không chứa secret.
- Không dùng AI để tạo số liệu benchmark, run id hoặc kết quả hidden. Các số kiểm tra ở mục 4 là output đã chạy thực tế.

## 6. Tự đánh giá theo bằng chứng hiện có

- Phần shape C và test riêng đã hoàn thành ở mức public: 64 test được chọn đều pass, crash suite toàn repo đạt 20/20, handoff chỉ cấp tool đọc và trace được kiểm không lộ secret ở test thêm.
- Chưa có kết quả hidden cho shape C; không thể khẳng định pass rate hidden đạt ngưỡng. Benchmark bốn shape và quyết định kiến trúc của nhóm chưa được ghi vào báo cáo chính thức, nên chưa kết luận orchestrator là shape nên chọn.
- Điều cần thành viên rà lại trước khi nộp: email, tài khoản GitHub cá nhân và phần tự đánh giá nếu muốn bổ sung trải nghiệm học tập của mình.
