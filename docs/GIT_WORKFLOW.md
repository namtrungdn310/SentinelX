# SentinelX — Git & Branching Workflow

Quy chuẩn cộng tác Git và quản lý nhánh dành cho nhóm phát triển SentinelX.

---

## 1. Cấu trúc các nhánh (Branch Hierarchy)

```text
       (Feature/Milestone Branch)
          feat/f2-config-logging
                 |
                 v (Pull Request + Review)
               [ dev ]  <--- Nhánh tích hợp chính (Active Integration)
                 |
                 v (Pull Request + Final Verification)
              [ main ]  <--- Nhánh ổn định / Release chính thức
```

### 1.1 `main` (Production / Stable Release)
- Nhánh ổn định nhất của dự án.
- **Không bao giờ commit trực tiếp lên `main`**.
- Chỉ nhận code thông qua Pull Request từ nhánh `dev` sau khi toàn bộ milestone đã được kiểm thử ổn định và review đầy đủ.

### 1.2 `dev` (Active Integration)
- Nhánh tích hợp làm việc hàng ngày của nhóm 2 thành viên.
- **Không commit trực tiếp lên `dev`**.
- Mọi tính năng, milestone, hoặc bugfix đều phải xuất phát từ nhánh riêng và tạo Pull Request (PR) vào `dev`.
- Cần có review phê duyệt trước khi merge vào `dev`.

### 1.3 `feat/*`, `fix/*`, `milestone/*` (Working Branches)
- Mỗi khi code tính năng mới, milestone mới hoặc fix bug, **bắt buộc tạo nhánh riêng từ `dev`**.

---

## 2. Quy tắc đặt tên nhánh (Branch Naming Conventions)

- **Theo Milestone**: `milestone/f2-controller-skeleton`, `milestone/f3-shared-contracts`, v.v.
- **Tính năng mới**: `feat/agent-heartbeat`, `feat/dashboard-nodes-view`, v.v.
- **Sửa lỗi**: `fix/db-connection-retry`, `fix/metric-batch-validation`, v.v.
- **Tài liệu / Refactor**: `docs/update-architecture`, `refactor/telemetry-buffer`, v.v.

---

## 3. Quy trình làm việc hàng ngày (Daily Developer Workflow)

### Bước 1: Đồng bộ nhánh `dev` mới nhất
Trước khi bắt đầu làm bất kỳ việc gì:
```bash
git checkout dev
git pull origin dev
```

### Bước 2: Tạo nhánh riêng từ `dev`
```bash
git checkout -b feat/ten-tinh-nang-moi
```

### Bước 3: Code và kiểm tra Quality Gate cục bộ
Trước khi commit và push, luôn đảm bảo Quality Gate PASS:
```bash
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
```

### Bước 4: Commit và Push nhánh làm việc lên GitHub
```bash
git add .
git commit -m "feat: mo ta ngan gon thay doi"
git push -u origin feat/ten-tinh-nang-moi
```

### Bước 5: Tạo Pull Request (PR) vào nhánh `dev`
1. Truy cập GitHub repository: [https://github.com/namtrungdn310/SentinelX](https://github.com/namtrungdn310/SentinelX)
2. Tạo Pull Request:
   - **Base branch**: `dev`
   - **Compare branch**: `feat/ten-tinh-nang-moi`
3. Gán Reviewer để review code.
4. Sau khi review OK và CI pass $\rightarrow$ Tiến hành **Merge vào `dev`**.
5. Xóa nhánh làm việc trên GitHub và local sau khi merge:
   ```bash
   git checkout dev
   git pull origin dev
   git branch -d feat/ten-tinh-nang-moi
   ```

### Bước 6: Merge từ `dev` vào `main` (Release Milestone)
Khi một milestone hoặc tập tính năng đã hoàn chỉnh trên `dev`:
1. Tạo Pull Request từ `dev` $\rightarrow$ `main`.
2. Kiểm tra toàn bộ checklist, review lần cuối và merge vào `main`.

---

## 4. Hướng dẫn thiết lập Branch Protection trên GitHub (Khuyến nghị)

Để bắt buộc quy tắc này và tránh lỡ tay push nhầm lên `dev` hoặc `main`:
1. Vào GitHub repo: `Settings` $\rightarrow$ `Branches` $\rightarrow$ `Add branch protection rule`.
2. **Rule 1: Áp dụng cho nhánh `main`**:
   - Branch name pattern: `main`
   - Tích chọn: **Require a pull request before merging**
   - Tích chọn: **Require approvals** (số lượng: 1)
   - Lưu rule.
3. **Rule 2: Áp dụng cho nhánh `dev`**:
   - Branch name pattern: `dev`
   - Tích chọn: **Require a pull request before merging**
   - Tích chọn: **Require approvals** (số lượng: 1)
   - Lưu rule.
