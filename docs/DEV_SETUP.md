# SentinelX — Hướng dẫn thiết lập môi trường phát triển (uv)

Tài liệu này hướng dẫn các thành viên trong nhóm thiết lập môi trường phát triển đồng bộ 100% bằng **`uv`**, đảm bảo không bao giờ bị xung đột (conflict) phiên bản package.

---

## 1. Cài đặt `uv` (Chỉ làm 1 lần trên mỗi máy)

### Trên Windows:
Mở PowerShell và chạy:
```powershell
pip install uv
# hoặc dùng winget:
# winget install --id=astral-sh.uv -e
```

### Trên Linux / macOS:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Kiểm tra cài đặt:
```bash
uv --version
```

---

## 2. Thiết lập môi trường dự án lần đầu

Sau khi clone repository về máy:

```bash
# 1. Chuyển vào thư mục dự án
cd code

# 2. Đồng bộ toàn bộ môi trường và công cụ phát triển (Ruff, Mypy, Pytest) từ uv.lock
uv sync --all-extras
```

Lệnh `uv sync --all-extras` sẽ tự động:
- Tạo thư mục ảo `.venv` chuẩn Python 3.12.
- Cài đặt chính xác các phiên bản thư viện được khóa trong file `uv.lock`.
- Cài đặt dự án ở chế độ editable.

---

## 3. Quy trình làm việc hàng ngày

### 3.1 Chạy lệnh kiểm tra / chạy server
Không cần kích hoạt virtual environment thủ công, `uv run` sẽ tự động chạy trong môi trường `.venv`:

- **Chạy toàn bộ Quality Gate**:
  ```bash
  uv run ruff check src tests
  uv run mypy src tests
  uv run pytest -v
  ```
  *(hoặc dùng lệnh `make check` nếu có Make)*

- **Format code tự động**:
  ```bash
  uv run ruff format src tests
  uv run ruff check --fix src tests
  ```

- **Chạy Controller server**:
  ```bash
  uv run python -m sentinelx_controller.main
  ```

---

## 4. Thêm thư viện mới (Add Dependency)

Khi cần thêm thư viện mới cho dự án:

- **Thư viện chạy thực tế (Production)**:
  ```bash
  uv add asyncpg
  ```
- **Thư viện phục vụ kiểm thử (Development/Dev)**:
  ```bash
  uv add --dev pytest-mock
  ```

Lệnh `uv add` sẽ tự động:
1. Cập nhật file `pyproject.toml`.
2. Cập nhật file khóa `uv.lock`.
3. Cài đặt ngay vào `.venv` của bạn.

> **QUY TẮC BẮT BUỘC KHI COMMIT**: Luôn commit cả 2 file `pyproject.toml` VÀ `uv.lock` lên Git khi thêm/xóa thư viện.

---

## 5. Khi teammate thêm thư viện mới (Pull code về)

Khi bạn kéo code mới từ GitHub về và thấy `uv.lock` hoặc `pyproject.toml` có thay đổi:

```bash
git pull origin dev
uv sync --all-extras
```

Lệnh `uv sync` sẽ cập nhật lại môi trường của bạn chỉ trong **1-2 giây**, đảm bảo 2 máy luôn luôn giống hệt nhau.
