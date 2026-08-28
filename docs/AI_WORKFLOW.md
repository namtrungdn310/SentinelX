# SentinelX — AI Coding Workflow

## 1. Mục tiêu

Tài liệu này quy định quy trình làm việc chuẩn cho AI coding assistant khi thực hiện các task trong repository SentinelX, nhằm:
- Luôn giữ vững bối cảnh kiến trúc qua từng phiên làm việc (tránh tình trạng quên hoặc suy đoán);
- Tuân thủ kỷ luật phạm vi (Strict Scope Discipline) cho từng milestone;
- Bảo toàn tính tương thích multi-host và các ranh giới module (Domain Boundaries);
- Đảm bảo 100% code sinh ra đều đạt Quality Gate với `uv`.

---

## 2. Quy trình 8 bước bắt buộc cho mọi Task

```text
[Step 1: Re-read & Ground Context]
                │
                ▼
[Step 2: State Milestone & Scope]
                │
                ▼
[Step 3: Inspect Repository Filesystem]
                │
                ▼
[Step 4: Design Minimal Patch & Boundaries]
                │
                ▼
[Step 5: Implement Complete Code]
                │
                ▼
[Step 6: Validate Quality Gate via uv]
                │
                ▼
[Step 7: Report 11-Section Result]
                │
                ▼
[Step 8: Stop & Await Review]
```

### Step 1 — Classify Task & Selective Reading (Đọc chọn lọc theo Task)
Đầu mỗi task, AI phân loại nghiệp vụ và chỉ đọc chọn lọc các tài liệu liên quan theo bảng ma trận trong `AGENTS.md` (kèm base context) để tiết kiệm token tối đa mà vẫn nắm chính xác 100% ranh giới kỹ thuật.

### Step 2 — State Milestone & Scope
Xác định chính xác milestone đang làm:
- **In scope**: Những gì cần tạo/sửa trong milestone này.
- **Out of scope**: Những gì tuyệt đối chưa làm.

### Step 3 — Inspect Repository Filesystem
Khảo sát cây thư mục và đọc nội dung các file hiện có liên quan trước khi sửa đổi.

### Step 4 — Design Minimal Patch & Boundaries
Lập bảng danh sách file cần tạo/sửa đổi kèm phân tích ranh giới phụ thuộc (Dependency Direction).

### Step 5 — Implement
Viết code hoàn chỉnh, có type hints đầy đủ (Python 3.12), tuân thủ tiêu chuẩn kiến trúc, không dùng pseudo-code.

### Step 6 — Validate Quality Gate via `uv`
Chạy kiểm tra tự động:
```bash
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
```
Tất cả phải PASS 100%.

### Step 7 — Report
Trình bày kết quả theo đúng cấu trúc chuẩn 11 mục quy định.

### Step 8 — Stop
Dừng lại hoàn toàn. Tuyệt đối không tự ý làm trước milestone tiếp theo khi chưa có yêu cầu từ người dùng.

---

## 3. Các hành vi bị cấm (AI Prohibitions)

- **CẤM** tự ý thêm microservices, Kafka, RabbitMQ, Redis, Kubernetes, TimescaleDB, InfluxDB, eBPF, Isolation Forest, Adaptive LB.
- **CẤM** hard-code `localhost` làm giả định kiến trúc; mọi endpoint phải cấu hình được qua config/env.
- **CẤM** Agent import ORM model của Controller hoặc Controller import repository của module khác.
- **CẤM** Detector gọi trực tiếp firewall hoặc restart service.
- **CẤM** nhét mọi thứ vào `sentinelx_common`.
- **CẤM** xóa bỏ assertion hợp lệ để làm test pass giả tạo.
- **CẤM** sinh code mock/placeholder giả vờ là tính năng thật đã hoàn thành.

---

## 4. Xử lý khi thiếu thông tin hoặc phát sinh mơ hồ

- Nếu là chi tiết implementation cục bộ đơn giản: Chọn giải pháp đơn giản nhất phù hợp với kiến trúc và ghi rõ assumption.
- Nếu ảnh hưởng tới: API public contract, DB schema, security, multi-host deployment, tech stack $\rightarrow$ **Dừng lại và xin quyết định từ người dùng trước khi code**.
