# SentinelX — AI Coding Workflow

## 1. Mục tiêu

File này quy định cách sử dụng AI coding assistant để tránh:
- code quá nhiều một lần;
- drift khỏi architecture;
- sửa file ngoài scope;
- over-engineering;
- tạo code chưa test.

---

## 2. Mỗi session coding

### Step 1 — Read
AI đọc:
- `AGENTS.md`
- milestone hiện tại
- architecture/tech stack
- file liên quan.

### Step 2 — State scope
AI phải nói:
- đang làm F?;
- output của F?;
- không làm gì.

### Step 3 — Inspect repository
Nếu AI có tool:
- xem tree;
- đọc file hiện tại;
- không giả định file chưa đọc.

### Step 4 — Plan minimal patch
Liệt kê files create/modify.

### Step 5 — Implement
Code theo standards.

### Step 6 — Validate
Run:
```bash
ruff check src tests
mypy src
pytest -q
```

Thêm integration/smoke command nếu milestone yêu cầu.

### Step 7 — Report
AI báo:
- files changed;
- tests;
- known limitations;
- next checkpoint.

### Step 8 — Stop
Không tự làm milestone tiếp theo.

---

## 3. AI Must Not

- Rewrite whole repository vì "cleaner".
- Introduce new framework without approval.
- Bypass module boundary.
- Put everything in `common`.
- Generate placeholder business logic pretending to be implemented.
- Disable tests to make CI green.
- Add security-sensitive action before safe mode.
- Commit secrets.
- Add Phase 2 technology early.

---

## 4. Preferred AI behavior when uncertain

Nếu uncertainty nhỏ, local implementation detail:
- choose simplest reasonable option;
- document assumption.

Nếu uncertainty ảnh hưởng:
- public contract;
- DB schema;
- security;
- architecture;
- deployment boundary;
- tech stack;

AI phải dừng và xin quyết định.
