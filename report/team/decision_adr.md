# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: 
- Run id dẫn chứng: R-workflow-C-002-s55 (pass) đối chứng R-swarm-C-002-s55 (fail `status resolved != denied`); R-workflow-C-014-s11 (quote 150.000, ledger 120.000) — `src/reports/benchmark.json`
- Pass rate / pass^5 / seed min-max / variance: 1.000 / 1.000 / 1.000–1.000 / 0.000000 (70 trial = 14 claim public × seed 11,22,33,44,55, `src/reports/benchmark.json`)
- Cost per success (mô phỏng, VND): 28.80 (single 45.20, orchestrator 57.08, swarm 49.57; giá mô phỏng trong `config/pricing.yaml`, không phải hóa đơn API)
- Crash safety: 20/20 (`src/reports/crash.json`); T11, T12 xanh trên workflow, single, orchestrator
- Secret leak / approval bypass: 0 / 0 trên public (`benchmark.json`: 70/70 trial workflow pass, trong đó có kiểm chuỗi cấm và ledger khớp nhãn); hidden tự kiểm `leak_suspect_trials` = 0, `error_trials` = 0 (`src/reports/hidden_selfcheck.json`)

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Trên cùng corpus (14 claim public), cùng 5 seed `11,22,33,44,55`, cùng MockLLM, cùng bảng giá và cùng evaluator, cả ba shape nhóm viết đều đạt pass rate 1.000, pass^5 1.000 và variance 0. Chênh lệch nằm ở chi phí và độ phức tạp: workflow có cost/success 28.80 VND, mean steps 5.07 và p95 bằng 6, với 1 lần gọi model mỗi trial. Single tốn 45.20 VND (3.64 lần gọi model, p95 bằng 8, chạm sát trần 8 bước ReAct). Orchestrator tốn 57.08 VND (5.57 tool call vì investigator chạy cả bốn tool đọc). Khi chất lượng ngang nhau, nhóm chọn kiến trúc **ít tự chủ nhất**. Workflow rẻ nhất (bằng khoảng 64% single và 50% orchestrator), có ít điểm có thể hỏng nhất, và không có đường nào để model chạm vào số tiền. Trên bộ hidden tự kiểm (40 claim × 5 seed, không nhãn), ba shape cho phân bố status giống hệt nhau (95 denied, 90 resolved, 10 escalated, 5 needs_info), mọi claim có cùng status ở cả ba shape và cả 5 seed, không có trial lỗi hay nghi lộ secret. Điều đó cho thấy workflow không bỏ sót nhánh nào mà hai shape tự chủ hơn bắt được. Pass rate hidden chính thức do grader của giảng viên chấm.

## Có đáng đổi lấy multi-agent không

Không, với dữ liệu hiện có. Không shape tự chủ hơn nào có pass rate nhỉnh hơn: orchestrator bằng workflow nhưng cost cao gấp khoảng 2 lần, còn swarm vừa đắt hơn (49.57) vừa kém hơn (0.986, pass^5 0.929) vì ở seed 55 nó tin số ngày trễ trong ticket thay vì cột `delay_days` (R-swarm-C-002-s55). Ablation trong research card cho thấy trên các seed chia hết cho 5, swarm fail C-002 ở cả 5/5 seed. Lỗi này nằm ở cấu trúc, không phải nhiễu. Nếu một shape multi-agent chỉ nhỉnh hơn vài phần trăm pass mà cost và variance cao hơn, nhóm vẫn giữ workflow, vì ngưỡng hidden là 0.75 và quy trình claim chủ yếu tuần tự (đọc claim, đọc đơn, tính quote, gọi host). Quyết định sẽ đảo lại khi: (1) claim có ticket tự do mà luật cố định không phân loại được (ví dụ phải đọc ảnh, chứng từ hoặc hội thoại nhiều lượt), làm pass rate workflow trên hidden tụt dưới mức của single hoặc orchestrator một cách ổn định qua các seed; (2) cần tra nhiều nguồn độc lập song song (nhiều kho, nhiều hãng vận chuyển) đến mức các investigator chạy song song bù được chi phí; hoặc (3) bảng giá thay đổi khiến chi phí gọi model không còn đáng kể so với tool call. Ngay cả khi đó, tiền, approval và idempotency vẫn do host quyết.

## Trace và bằng chứng

Trace workflow (`src/traces/R-workflow-<claim>-s<seed>.json`, contract v1: `run_id`, `steps`, `events`) ghi các event: `claim` (claim_id, found, has_order_id), `lookup_order` (visible, reason, và order **đã lọc** qua `ORDER_FIELDS`: order_id, status, delay_days, phí ship, paid, damage_verified, carrier), `quote` (kết quả `compute_compensation`), `issue_refund` (số đề xuất), `host` (ok, reason), `decision` (status, proposal_amount, reason), và `crash` nếu có crash giả lập. Trace cố ý **không** ghi: ticket (chữ người dùng, có thể chứa PII hoặc prompt injection), `parent_secret` và `raw_headers` (là secret), SĐT, địa chỉ, ghi chú nội bộ, tên hàng của đơn, và prompt hay text của MockLLM. Claim được đọc qua `get_claim_view`, chỉ lấy 4 cột, không `SELECT *`. Mọi file trace nằm trong `src/traces/` và được đặt tên theo `<run_id>`, nên scanner của grader quét được toàn bộ. Nếu trace nằm ngoài chỗ scanner quét được, đội security không thể chứng minh bằng log tự khai. Lúc đó phải chứng minh bằng cấu trúc: code không bao giờ đọc cột secret (không `SELECT *`, view có allowlist), không có đường nào đưa secret vào prompt hay output, và chạy test canary (`CANARY_SECRET_*` trong dữ liệu, quét mọi output: `test_workflow_shape.py::test_trace_has_no_secret_or_pii`, `test_shape_crash_and_approval.py`). Grader vì vậy fail-closed khi gặp `missing_trace`, `stale_trace`, `invalid_trace` hay `trace_run_id_mismatch`.

## Giới hạn

MockLLM không phải model sản xuất. Ở workflow, model chỉ soạn chữ nên số đo phản ánh logic code, không phản ánh khả năng hiểu ticket của một model thật. Latency để `unavailable`. Cost là giá mô phỏng. Bộ public chỉ có 14 claim, nên pass rate 1.000 cho cả ba shape không phân biệt được chúng về chất lượng. Kết quả hidden ở đây chỉ là tự kiểm không nhãn, không phải pass rate. Không sửa JSON cho đủ 0.75: mọi số trong file này lấy từ `src/reports/benchmark.json`, `crash.json` và `hidden_selfcheck.json` do công cụ của lab sinh ra.
