# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm: AIDoCode
- Thành viên: xem `TEAM.md`
- Commit chốt (trùng `report/team/decision_adr.md`): `39a3eb3`

## 2. Mục tiêu và cách tiếp cận

Nhóm hiểu bài toán là cài **cùng một quy trình** xử lý claim hoàn phí vận chuyển theo bốn mức tự chủ (A workflow, B single, C orchestrator, D swarm có sẵn), rồi dựa vào số đo để chọn kiến trúc ít tự chủ nhất mà vẫn làm được việc. Ranh giới cố định ở mọi shape: số tiền do `compute_compensation` tính, approval, trần theo đơn và idempotency do host (`durability.issue_refund`) quyết. Model chỉ đọc dữ liệu và soạn chữ. Chữ trong ticket là dữ liệu, không phải lệnh.

Cách chia việc theo gợi ý cho nhóm 4 người: mỗi shape một người, nhóm trưởng lo integration, ledger/crash và evaluation (chi tiết ở `TEAM.md`). Thứ tự làm:

1. CP1: cả nhóm cài môi trường, chạy smoke và đọc `business_rules.md`, `contracts.md`, `swarm_reference.py`.
2. CP2: ba người viết song song ba shape trên ba file riêng (ba nhánh, merge qua pull request). Workflow xong trước và làm mẫu cho cách gọi `finish()` và ghi trace.
3. CP3–CP4: kiểm `crash_at` và handoff, chạy crash suite, rà các nhánh approval và quét trace.
4. CP5: benchmark, tự kiểm hidden, ADR, research card và báo cáo.

## 3. Giải pháp

Cả ba shape giữ chữ ký `run_claim(claim_id, *, seed, store_path, crash_at=None) -> RunResult`, đọc claim qua `get_claim_view` (4 cột allowlist, không `SELECT *`), và mọi nhánh return đều đi qua `finish()`. Nhờ vậy nhánh nào cũng ghi trace đúng contract v1, và `refund_effects` cùng `committed_audit_count` được lấy từ ledger chứ không tự khai.

| Shape | Đọc gì | Quyết định gì | Gọi host |
| --- | --- | --- | --- |
| A `workflow` | claim view, `lookup_order` theo `principal_id`, `compute_compensation` | Các bước Python cố định: không có claim → `failed`; thiếu `order_id` → `needs_info`; không thấy đơn → `escalated`; quote 0 → `denied` | Quote > 0: truyền quote đầy đủ và `crash_at`. MockLLM chỉ gọi 1 lần để soạn chữ, prompt chỉ có `status=...` |
| B `single` | Vòng ReAct (`run_react`, tối đa 8 bước) chọn trong các tool đọc: `lookup_order`, `lookup_refund_history`, `compute_compensation` | Agent chỉ chọn tool đọc hoặc kết thúc. Chạm trần bước → `failed`. Số tiền lấy từ kết quả tool, không từ model hay ticket | Sau vòng lặp, code gọi host với quote đầy đủ và `crash_at` |
| C `orchestrator` | Investigator (`run_readonly_investigators`) chạy 4 tool đọc theo handoff | Orchestrator dựng handoff bằng `make_handoff` với `facts={}` và chỉ tool đọc; đơn không thấy → `escalated` | Orchestrator gọi host; investigator không có tool ghi |

**Ranh giới code / model.** Không shape nào cho model quyết định số tiền, approval hay việc ghi ledger. Quote luôn được truyền **đầy đủ** cho host; host tự trừ phần đã hoàn (T13: denied với `order_already_refunded`; T14: quote 150.000, ledger 120.000). Khi shape tự trả `denied` vì quote = 0 thì không có audit `policy_denied`, vì host không được gọi. Audit đó chỉ có khi quote > 0 và host từ chối.

**Crash và idempotency.** Cả ba shape truyền `crash_at` xuống host. Khi gặp `InjectedCrash`, shape chỉ ghi event `crash`, gọi `trace.write()` rồi ném lại lỗi, không nuốt. Chạy lại thì host trả `idempotent_replay` theo khóa `refund:{claim_id}`, nên vẫn chỉ có một refund và một audit `refund_committed`.

**Handoff.** Handoff của orchestrator đi qua allowlist của `make_handoff`, không mang ticket, `parent_secret`, `raw_headers` hay dòng claim thô. Trace ghi handoff đã sanitize, không ghi parent context. Nhóm không dùng tóm tắt bằng LLM làm bước lọc.

**Trace.** Event chung là `claim`, `quote`, `host`/`issue_refund`, `decision` và `crash` (nếu có). Ngoài ra workflow có `lookup_order` (order đã lọc qua `ORDER_FIELDS`), single có `react_step` (chỉ tên tool hoặc status, không có args), orchestrator có `handoff` và `investigator`. Trace không bao giờ ghi ticket, secret, SĐT, địa chỉ, ghi chú nội bộ hay tên hàng.

## 4. Kết quả

**Benchmark public** (`src/reports/benchmark.json`): 14 claim × seed `11,22,33,44,55` = 70 trial mỗi shape, MockLLM, giá mô phỏng, `as_of` 2026-11-15, SQLite mới cho mỗi trial.

| Shape | Pass rate | Pass^5 | Seed min–max | Variance | Cost/success (VND, mô phỏng) | Mean steps | P95 steps | Model calls / trial | Tool calls / trial |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| workflow | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 28.80 | 5.07 | 6 | 1.00 | 2.79 |
| single | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 45.20 | 7.14 | 8 | 3.64 | 4.29 |
| orchestrator | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 57.08 | 6.00 | 7 | 1.93 | 5.57 |
| swarm | 0.986 | 0.929 | 0.929–1.000 | 0.000816 | 49.57 | 2.80 | 3 | 3.00 | 4.66 |

Trial fail duy nhất là `R-swarm-C-002-s55` (`status resolved != denied`): ở seed chia hết cho 5, swarm tin số ngày trễ ghi trong ticket (5 ngày) thay vì cột `delay_days` (2 ngày).

**Crash safety** (`src/reports/crash.json`): `20/20`. Ngoài ra T11 và T12 của ma trận student xanh trên cả ba shape nhóm viết, cùng 12 test bổ sung trong `src/tests/test_shape_crash_and_approval.py` (crash ở cả 2 điểm, approval mượn của claim khác, approval bị thu hồi). Cổng host `python -m pytest -q` có 107 test xanh, ma trận student có 250 test xanh.

**Tự kiểm trên `student_drop/`** (`src/reports/hidden_selfcheck.json`, 40 claim × 5 seed, không nhãn):

| Shape | Trial | Lỗi (`error`) | Nghi lộ secret | denied / resolved / escalated / needs_info | Mean steps | Tổng cost mô phỏng (VND) |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| workflow | 200 | 0 | 0 | 95 / 90 / 10 / 5 | 5.15 | 5988.3 |
| single | 200 | 0 | 0 | 95 / 90 / 10 / 5 | 7.38 | 9329.7 |
| orchestrator | 200 | 0 | 0 | 95 / 90 / 10 / 5 | 6.12 | 11928.0 |

Với mỗi claim hidden, cả ba shape cho cùng một status ở cả 5 seed. Đây không phải pass rate; điểm hidden chính thức do grader của giảng viên chấm.

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md` (chọn **workflow**: chất lượng bằng hai shape tự chủ hơn, cost/success thấp nhất, không có variance). Phiếu nghiên cứu và ablation: xem `report/team/research_card.md` (R4: đổi bộ seed sang các số chia hết cho 5 thì swarm có pass rate 0.929 với variance 0. Variance thấp không có nghĩa là đúng).

## 5. Khó khăn và cách xử lý

- **Môi trường Python khác nhau giữa các máy.** Một thành viên có Python mặc định thiếu `PyYAML` và không tải được gói, nên đã chạy kiểm tra bằng venv Python 3.13 khác (ghi trong báo cáo cá nhân). Nhóm thống nhất mọi lệnh chạy trong `src/` với venv riêng của repo.
- **Làm song song trên nhiều nhánh.** Ba shape nằm ở ba file riêng nên không bị xung đột code. Nhóm merge qua pull request (#1 workflow, #2 single, #3 báo cáo) và chạy lại cổng host sau mỗi lần merge.
- **Crash test cho từng shape.** `lab8.crash_test` chỉ chạy swarm tham chiếu, nên `crash.json` không chứng minh được gì cho shape của nhóm. Nhóm dựa vào T11, T12 và viết thêm test crash cho cả ba shape, kiểm trace được ghi trước khi lỗi bay ra và không lộ secret.
- **Các nhánh approval không có trong bộ public.** Bộ public không có claim mượn approval của claim khác. Test host chỉ gọi thẳng `issue_refund`, nên nhóm viết test chạy qua shape thật để chứng minh không có đường vòng qua cổng duyệt.
- **`check_submission` báo FAIL ở CP5** do thiếu `benchmark.json`, `crash.json`, ADR, research card và bảng đóng góp. Nhóm sinh report bằng đúng lệnh của lab, không sửa tay JSON, rồi điền tài liệu.

## 6. Tổng hợp đóng góp

Chi tiết đóng góp của từng thành viên nằm trong `TEAM.md` (bảng đóng góp) và báo cáo cá nhân `report/team/MSSV_HoTen.md`.

## 7. Hạn chế và hướng cải thiện

- MockLLM không phải model sản xuất; latency là `unavailable`; cost là giá mô phỏng. Ở cả ba shape, model không quyết định gì về tiền, và hàm `decide()` của single là luật cố định. Vì vậy pass rate 1.000 phản ánh logic code chứ không phản ánh khả năng một model thật hiểu ticket.
- Bộ public chỉ có 14 claim nên không phân biệt được ba shape về chất lượng; khác biệt đo được chỉ nằm ở cost và số bước. Hidden mới chỉ được tự kiểm (không nhãn).
- Single có p95 steps bằng 8, đúng trần ReAct. Nếu quy trình cần thêm một tool, single sẽ chạm trần và trả `failed`.
- Kết luận chọn workflow sẽ đổi nếu claim có ticket tự do mà luật cố định không phân loại được (pass rate workflow trên hidden tụt dưới mức của single hoặc orchestrator một cách ổn định), hoặc nếu cần tra nhiều nguồn độc lập song song đến mức chi phí điều phối là đáng giá (xem ADR).
- Hướng cải thiện: thêm claim có ticket mâu thuẫn với dữ liệu đơn vào bộ test; chạy benchmark với nhiều bộ seed (như ablation R4) trước khi so variance; nếu làm bonus thì gắn nhãn lỗi theo MAST cho các trial fail.

## 8. Tài liệu tham khảo

- Đề bài và tài liệu của lab: `README.md`, `CHECKPOINTS.md`, `RUBRIC.md`, `docs/business_rules.md`, `docs/contracts.md`, `docs/architecture.md`, `docs/metrics.md`.
- *Rethinking Evaluation of MAS Efficiency*, EMNLP 2026 (thư viện tham khảo của khóa, slide 44, 59) — dùng cho research card R4.
- Shape tham chiếu `src/lab8/shapes/swarm_reference.py`.
