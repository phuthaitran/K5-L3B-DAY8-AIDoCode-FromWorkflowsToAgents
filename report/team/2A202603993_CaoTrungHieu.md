# Báo cáo cá nhân — 2A202603993_CaoTrungHieu

## 1. Thông tin thành viên

- Họ tên: Cao Trung Hiếu
- MSSV: 2A202603993
- Email: 26ai.hieuct@vinuni.edu.vn
- GitHub: HieuCaoTlu

## 2. Phần việc phụ trách

- Shape B Single — ReAct agent, có check crash: [src/lab8/shapes/single.py](../../src/lab8/shapes/single.py) (xử lý crash tại [single.py:199-204](../../src/lab8/shapes/single.py#L199-L204))
- Làm phần test riêng cho Single agent: [src/tests/test_single_shape.py](../../src/tests/test_single_shape.py)
- Mô tả sơ đồ luồng Single: [images/single_money_flow.svg](images/single_money_flow.svg); làm demo tương tác: [demo/single_agent_chat.html](demo/single_agent_chat.html)

![Luồng xử lý của shape single](images/single_money_flow.svg)

## 3. Đóng góp cụ thể

| Hạng mục | Nội dung | Commit |
| --- | --- | --- |
| Code | `single.py`: vòng ReAct ≤ 8 bước, gọi host với quote đầy đủ + `crash_at` | <!-- TODO --> |
| Test | `test_single_shape.py`: 3 test | <!-- TODO --> |
| Sơ đồ / demo | `images/single_money_flow.svg`, `demo/single_agent_chat.html`, `src/scripts/build_single_demo.py` | <!-- TODO --> |

Quyết định kỹ thuật:

- Agent chỉ chọn tool đọc; số tiền lấy từ `compute_compensation`, không lấy từ model hay ticket.
- Truyền quote đầy đủ cho host, không tự trừ phần đã hoàn (T14: quote 150.000, host ghi 120.000).
- Agent không tính quote → quote = 0 → `denied`, không gọi host (fail-closed).
- Idempotency do host lo (khóa `refund:{claim_id}`); shape truyền `crash_at`, không bắt `InjectedCrash`, không tự ghi checkpoint. Chạy lại → `idempotent_replay`, vẫn 1 refund (T11, T12).
- Trace chỉ ghi tên tool, status, quote, lý do; không ghi ticket hay order row.

## 4. Bằng chứng

| Lệnh (trong `src/`) | Kết quả |
| --- | --- |
| `python -m pytest -q -m student -o addopts= -k "single and not workflow and not orchestrator and not swarm"` | **62 passed** (T01–T14) |
| `python -m pytest -q tests/test_single_shape.py` | **3 passed** |

Benchmark thử (14 claim public × 5 seed):

| Shape | Pass rate | pass^5 | Variance | Cost/success |
| --- | ---: | ---: | ---: | ---: |
| single | 1.000 | 1.000 | 0.000 | 45.20 |
| swarm | 0.986 | 0.929 | 0.0008 | 49.57 |

## 5. Công cụ AI đã dùng

| Công cụ | Dùng vào việc gì | Cách tự kiểm tra |
| --- | --- | --- |
| Claude Code | Tóm tắt đề, hỗ trợ code và test shape single, vẽ sơ đồ, làm demo | Chạy lại test (62/62, 3/3), đọc trace kiểm không lộ secret/PII, đối chiếu `docs/contracts.md` |

## 6. Tự đánh giá

- Làm được: shape single qua 62/62 test student, 3 test riêng, pass rate 1.000 / variance 0 trên public; sơ đồ + demo giải thích luồng.
- Giới hạn: decide() hiện là luật cố định, MockLLM chỉ để tính cost -> số liệu chưa phản ánh model thật hay quên bước; chưa chạy trên bộ hidden; chưa so với workflow/orchestrator vì hai shape đó chưa xong.
- Học được: một kiến trúc agent đơn giản nhưng cũng đủ để hoàn thành sơ bộ chức năng hoàn tiền, biết được trade-off khi lựa chọn các kiến trúc
- Điều làm tốt: hiểu được kiến trúc agent một cách cụ thể
- Điều chưa làm được / giới hạn: chưa thể code tay hoàn toàn
