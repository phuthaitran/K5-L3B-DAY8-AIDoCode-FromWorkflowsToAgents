# Báo cáo cá nhân — 2A202604001_TranPhuThai

## 1. Thông tin thành viên

- Họ tên: Trần Phú Thái
- MSSV: 2A202604001
- Email: 26ai.thaitp@vinuni.edu.vn
- GitHub: phuthaitran

## 2. Phần việc phụ trách

- Nhóm trưởng và integration: tạo repo nhóm, review và merge pull request của các thành viên (#1 workflow, #2 single, #3 báo cáo), giữ cổng host `python -m pytest -q` xanh sau mỗi lần merge, điền `TEAM.md`.
- Ledger và durability (CP3–CP4): kiểm `crash_at` và `InjectedCrash` ở cả ba shape, chạy crash suite, rà các nhánh approval, quét trace và stdout tìm secret hay PII.
- Evaluation (CP5): chạy benchmark 4 shape × 5 seed và tự kiểm hidden, chạy ablation cho research card, viết `decision_adr.md`, `research_card.md` và `group_report.md`.

## 3. Đóng góp cụ thể

| Hạng mục | Nội dung | Commit |
| --- | --- | --- |
| Test | `src/tests/test_shape_crash_and_approval.py`: 12 test cho workflow, single và orchestrator | `2032079` |
| Report CP4 | `src/reports/crash.json` sinh bằng `python -m lab8.crash_test --count 20 --out reports/crash.json` | `2032079` |
| Thông tin nhóm | Thông tin nhóm trong `TEAM.md` và các báo cáo | `069d64c` |
| CP5 | `src/reports/benchmark.json`, `hidden_selfcheck.json`, `ablation_r4_seeds_mod5.json`; ADR, research card, báo cáo nhóm, bảng đóng góp | chưa commit (cập nhật hash sau khi nhóm chốt) |
| Integration | Merge PR #1, #2, #3 | `1300029`, `842aa1d`, `37e486c` |

**Test đã thêm** (`test_shape_crash_and_approval.py`, chạy trong cổng host):

| Test | Kiểm tra |
| --- | --- |
| `test_crash_leaves_clean_trace_and_resume_pays_once` (3 shape × 2 điểm crash) | `InjectedCrash` bay ra ngoài; trace được ghi **trước** khi lỗi bay ra, đúng `run_id`, có event `crash`, không chứa `CANARY_*`, `parent_secret`, `raw_headers` hay `Bearer`; chạy lại thì đúng 1 refund 35.000 và 1 audit `refund_committed` |
| `test_invalid_approval_is_denied_through_the_shape` (3 shape × 2 trường hợp) | Approval mượn của claim khác (`approval_claim_mismatch`) và approval bị thu hồi dù có approval hợp lệ dự phòng (`approval_revoked`): đi qua shape thật vẫn `denied`, `proposal_amount` vẫn là quote đầy đủ, không có dòng ledger, có audit `policy_denied` đúng lý do, trace không lộ secret |

**Quyết định kỹ thuật:**

- Viết thêm test approval chạy **qua shape** chứ không gọi thẳng host. Test host có sẵn (`test_order_cap_and_approval_binding.py`) chỉ chứng minh host chặn được, chưa chứng minh shape không có đường vòng nào qua cổng duyệt. Bộ public cũng không có claim mượn approval.
- Không dựa vào `crash.json` để chứng minh độ bền của shape nhóm, vì `lab8.crash_test` chỉ chạy swarm tham chiếu. Bằng chứng cho từng shape là T11, T12 và test crash ở trên.
- Đề xuất chọn **workflow** dựa trên số đo: cùng pass rate 1.000 và variance 0 với single và orchestrator, nhưng cost/success thấp nhất (28.80 so với 45.20 và 57.08 VND mô phỏng).
- Chọn R4 cho research card và thiết kế ablation chỉ đổi một biến là bộ seed, để chứng minh variance của swarm trên public phụ thuộc vào bộ seed được chọn.

## 4. Bằng chứng

- Commit: `2032079` (test và crash.json), `069d64c` (thông tin nhóm).
- `python -m pytest -q tests/test_shape_crash_and_approval.py` → `12 passed`.
- `python -m pytest -q` (cổng host) → `107 passed`; `python -m pytest -q -m student -o addopts=` → `250 passed`.
- `python -m lab8.crash_test --count 20 --out reports/crash.json` → `crash_safety 20/20`.
- `src/reports/benchmark.json`: workflow / single / orchestrator đạt pass rate 1.000, swarm 0.986 (trial fail duy nhất `R-swarm-C-002-s55`).
- `src/reports/hidden_selfcheck.json`: 600 trial, 0 lỗi, 0 nghi lộ secret.
- `src/reports/ablation_r4_seeds_mod5.json`: swarm 0.929 / variance 0 trên seed `10,20,30,40,50`.
- Quét thủ công (script tạm, không commit): 3 shape × 14 claim public × seed 11 và 55 không có chuỗi nào trong `forbid_substrings`, `CANARY_*`, `Bearer` hay SĐT trong trace, kết quả trả về và stdout; trace đạt contract v1 ở mọi nhánh.

## 5. Công cụ AI đã dùng

| Công cụ | Dùng vào việc gì | Cách tự kiểm tra |
| --- | --- | --- |
| Claude Code (VS Code) | Tóm tắt đề và gợi ý chia vai; rà CP3/CP4; viết `test_shape_crash_and_approval.py`; chạy benchmark và ablation; soạn nháp ADR, research card, báo cáo nhóm và bảng đóng góp | Chạy lại test, cổng host và ma trận student; đối chiếu từng số trong báo cáo với `src/reports/*.json` do công cụ của lab sinh ra; đối chiếu bảng đóng góp với `git log` và báo cáo cá nhân của từng thành viên |

Không dùng AI để tạo hay sửa số liệu benchmark: mọi file JSON trong `src/reports/` được sinh bằng lệnh của lab và không sửa tay.

## 6. Tự đánh giá

- Làm được: CP3–CP4 được kiểm có bằng chứng cho cả ba shape (crash, approval, secret). Phần evaluation CP5 có số liệu từ file report, có ablation chạy được, và quyết định kiến trúc có điều kiện đảo ngược rõ ràng.
- Học được: variance thấp hay pass rate cao trên một bộ seed không chứng minh shape đáng tin; phải cố định corpus, seed, giá và evaluator thì so sánh mới công bằng. Kiến trúc ít tự chủ có thể đạt cùng chất lượng với chi phí thấp hơn.
- Giới hạn: MockLLM không phải model thật nên số đo phản ánh logic code; chưa có pass rate hidden chính thức; chưa làm bonus.
