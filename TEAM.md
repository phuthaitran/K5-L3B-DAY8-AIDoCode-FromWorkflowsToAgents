# Team

## Thông tin nhóm

- Tên nhóm: AIDoCode
- Lớp: L3B
- Repo nhóm: `K5-L3B-DAY08-AIDoCode-FromWorkflowsToAgents` (xem [SUBMISSION.md](SUBMISSION.md))
- URL repo, nhánh nộp, commit chốt: https://github.com/phuthaitran/K5-L3B-DAY8-AIDoCode-FromWorkflowsToAgents

## Thành viên

| STT | Họ tên | MSSV | Email | GitHub | Vai trò |
| --: | ------ | ---- | ----- | ------ | ------- |
|   1 | Trần Phú Thái | 2A202604001 | 26ai.thaitp@vinuni.edu.vn | phuthaitran | Nhóm trưởng, intergration, ledger + evaluation |
|   2 | Nguyễn Lương Nguyên | 2A202604005 | nglngnguyen@gmail.com | nglngnguyen-gh | Shape A Workflow |
|   3 | Cao Trung Hiếu | 2A202603993 | 26ai.hieuct@vinuni.edu.vn | HieuCaoTlu | Shape B Single Agent |
|   4 | Giang Thái Sơn | 2A202603964 | giangson309@gmail.com | son309 | Shape C Orchestrator + Handoff |

## Bảng đóng góp

`python -m lab8.check_submission` đọc bảng này bằng máy: giữ nguyên tiêu đề `## Bảng đóng góp` và các cột. Mỗi người một dòng: commit có nội dung và ít nhất một test đã thêm hoặc sửa.

| Người | Vai | Commit | Test đã thêm hoặc sửa |
| --- | --- | --- | --- |
| Trần Phú Thái | Nhóm trưởng, integration, ledger + evaluation | `2032079`, `069d64c` | `src/tests/test_shape_crash_and_approval.py` (12 test: crash 2 điểm, approval mượn/thu hồi qua 3 shape) |
| Nguyễn Lương Nguyên | Shape A workflow | `38221da` | `src/tests/test_workflow_shape.py` (38 test) |
| Cao Trung Hiếu | Shape B single agent | `b1ee347` | `src/tests/test_single_shape.py` (3 test) |
| Giang Thái Sơn | Shape C orchestrator + handoff | `763284a` | `src/tests/test_orchestrator_handoff.py` (2 test) |

## Cá nhân

Mỗi thành viên đồng thời tạo một báo cáo riêng trong `report/` theo dạng:

```text
report/team/MSSV_HoTen.md
```

Ví dụ: `report/team/20241234_NguyenVanAn.md`.

Sao chép mục dưới đây cho từng thành viên.

## 2A202604001_TranPhuThai

### Phần việc phụ trách

- Nhóm trưởng, integration (merge PR, giữ cổng host xanh), ledger/crash (CP3–CP4), evaluation và báo cáo (CP5).

### Đóng góp cụ thể

- Test crash và approval chạy qua 3 shape; `crash.json`; benchmark, hidden self-check, ablation R4; ADR, research card, báo cáo nhóm.

### Bằng chứng

- Commit `2032079`, `069d64c`; [report/team/2A202604001_TranPhuThai.md](report/team/2A202604001_TranPhuThai.md)

## 2A202604005_NguyenLuongNguyen

### Phần việc phụ trách

- Shape A `workflow` (CP2 và phần `crash_at` của CP3).

### Đóng góp cụ thể

- `src/lab8/shapes/workflow.py`; 38 test trong `src/tests/test_workflow_shape.py`.

### Bằng chứng

- Commit `38221da`; [report/team/2A202604005_NguyenLuongNguyen.md](report/team/2A202604005_NguyenLuongNguyen.md)

## 2A202603993_CaoTrungHieu

### Phần việc phụ trách

- Shape B `single` (vòng ReAct ≤ 8 bước, có xử lý crash); sơ đồ luồng và demo.

### Đóng góp cụ thể

- `src/lab8/shapes/single.py`; 3 test trong `src/tests/test_single_shape.py`; `report/team/images/single_money_flow.svg`, `report/team/demo/single_agent_chat.html`.

### Bằng chứng

- Commit `b1ee347`; [report/team/2A202603993_CaoTrungHieu.md](report/team/2A202603993_CaoTrungHieu.md)

## 2A202603964_GiangThaiSon

### Phần việc phụ trách

- Shape C `orchestrator` và handoff với investigator chỉ đọc.

### Đóng góp cụ thể

- `src/lab8/shapes/orchestrator.py`; 2 test trong `src/tests/test_orchestrator_handoff.py`.

### Bằng chứng

- Commit `763284a`; [report/team/2A202603964_GiangThaiSon.md](report/team/2A202603964_GiangThaiSon.md)
