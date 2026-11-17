# Research card

File này nằm cố định ở `report/team/research_card.md`; `python -m lab8.check_submission` đọc cột "Nhóm điền" bằng máy.

Phần này nối tiếp phần mini research ở buổi lý thuyết (slide 62–63). Chọn **một** câu R1–R4, điền 6 dòng, rồi biến nó thành **một ablation** chạy được trong lab: giữ nguyên model (MockLLM), tool, seed, corpus và giá, chỉ thay đổi một biến.

| Câu | Nguồn (thư viện tham khảo, slide 68–69) | Câu hỏi gợi ý cho lab |
| --- | --- | --- |
| R1 · Scaling | Google Research 2026, *Towards a Science of Scaling Agent Systems* | Task claims chủ yếu tuần tự hay song song được? Dự đoán thêm investigator sẽ làm pass rate và cost/success thay đổi thế nào. |
| R2 · Failure taxonomy | MAST, NeurIPS 2025, *Why Do Multi-Agent LLM Systems Fail?* | Các trial fail của swarm (seed 55) thuộc nhóm nào: lỗi giao việc, lệch mục tiêu, hay lỗi kiểm chứng? |
| R3 · Architecture choices | AgentArch, AACL 2026 | Nếu đổi topology mà giữ nguyên mọi thứ khác, biến nào phải cố định để kết luận còn đúng? |
| R4 · Evaluation confounders | EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* | Làm sao chứng minh chênh lệch giữa A/B/C/D là do topology, không phải do prompt, tool hay seed? |

## Phiếu của nhóm

Điền vào cột cuối. Không xóa hai cột đầu.

| Field | Hướng dẫn | Nhóm điền |
| --- | --- | --- |
| CÂU | R1 / R2 / R3 / R4 | R4 · Evaluation confounders |
| SOURCE | Paper/blog, năm, URL, loại bằng chứng (benchmark, production report, blog kinh nghiệm) | *Rethinking Evaluation of MAS Efficiency*, EMNLP 2026 (thư viện tham khảo của khóa, slide 44, 59); nhóm chưa có URL bản công bố. Loại bằng chứng: paper về phương pháp đánh giá hệ multi-agent |
| CLAIM | Một kết luận gốc của nguồn. Không viết rộng hơn phạm vi paper | Kết luận về hiệu năng của hệ multi-agent có thể đến từ cách đo (lựa chọn cấu hình đánh giá), không chỉ từ kiến trúc |
| BOUNDARY | Model / dataset / setup giới hạn kết luận đó | Nhóm chỉ dùng ý chính được tóm tắt ở slide của khóa, không đối chiếu model, dataset hay setup gốc của paper. Trong lab: MockLLM có seed, 14 claim public, giá mô phỏng; kết luận ablation chỉ áp dụng cho swarm tham chiếu của lab |
| HYPOTHESIS | Nếu đổi shape A→B (hoặc bật/tắt một thành phần), metric X sẽ đổi theo hướng nào, khoảng bao nhiêu | Variance khác 0 của swarm trên public (0.000816) là hệ quả của bộ seed chứ không phải độ ngẫu nhiên của topology. Nếu chỉ đổi bộ seed từ `11,22,33,44,55` (1/5 seed chia hết cho 5) sang `10,20,30,40,50` (5/5 seed chia hết cho 5): pass rate swarm giảm từ 0.986 xuống khoảng 0.929 (C-002 fail ở mọi seed), variance về 0, pass^5 giữ 0.929; workflow giữ 1.000 |
| METHOD | Biến giữ cố định: model, tools, seed, corpus, giá, evaluator. Biến duy nhất được thay đổi: … | Giữ cố định: MockLLM, tool, corpus `data/public_claims.jsonl`, bảng giá `config/pricing.yaml`, evaluator `lab8.benchmark`, `as_of` 2026-11-15, SQLite mới mỗi trial, code của hai shape `workflow` và `swarm`. Biến duy nhất được thay đổi: bộ seed |
| FAILURE / METRIC | Một lỗi dự kiến và cách đo nó: pass rate, pass^5, variance, cost/success, leak, bypass | Lỗi dự kiến: swarm tin số ngày trễ trong ticket thay vì `delay_days` của đơn, dẫn đến `status resolved != denied` ở C-002. Đo bằng pass rate, pass^5, seed variance, seed min–max và số trial fail theo `run_id` |

## Kết quả ablation

- Lệnh đã chạy (copy nguyên văn): `python -m lab8.benchmark --shapes workflow,swarm --cases data/public_claims.jsonl --seeds 10,20,30,40,50 --out reports/ablation_r4_seeds_mod5.json` (so với baseline `python -m lab8.benchmark --shapes workflow,single,orchestrator,swarm --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/benchmark.json`)
- Run id / file report: `src/reports/ablation_r4_seeds_mod5.json`; trial fail: R-swarm-C-002-s10, R-swarm-C-002-s20, R-swarm-C-002-s30, R-swarm-C-002-s40, R-swarm-C-002-s50. Baseline: `src/reports/benchmark.json`, trial fail duy nhất R-swarm-C-002-s55
- Kết quả so với hypothesis (đúng / sai / không kết luận được), kèm số liệu: **Đúng.** Swarm: pass rate 0.986 → 0.929, pass^5 0.929 → 0.929, variance 0.000816 → 0.000000, seed min–max 0.929–1.000 → 0.929–0.929, cost/success 49.57 → 53.23 VND (cost tổng gần như không đổi, nhưng chia cho ít trial pass hơn). Workflow giữ 1.000 / 1.000 / variance 0 / 28.80 VND ở cả hai bộ seed. Như vậy cùng một code swarm có thể trông "hơi dao động" hoặc "ổn định nhưng sai đều" tùy bộ seed. Variance thấp không chứng minh độ tin cậy. Muốn so topology công bằng thì phải cố định bộ seed (và báo pass^5 cùng số trial fail theo claim), không chỉ báo variance
- Giới hạn: MockLLM không phải model sản xuất, latency là `unavailable`. Điểm yếu `seed % 5 == 0` của swarm được cài sẵn để minh họa và quyết định theo luật, không phải hành vi ngẫu nhiên của một LLM thật. Corpus chỉ có 14 claim, và chỉ một claim (C-002) có ticket mâu thuẫn với dữ liệu đơn.

Muốn đi xa hơn một ablation để lấy điểm cộng thì xem [docs/bonus_topics.md](../../docs/bonus_topics.md).
