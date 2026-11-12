# Milestone M7 — Linux Agent nftables Defense Executor

## 1. Mục tiêu (Objective)
Triển khai bộ thực thi tường lửa **`NftablesDefenseExecutor`** chạy cục bộ trong tiến trình daemon của SentinelX Agent trên máy chủ Linux.
Bộ thực thi có trách nhiệm:
1. Đảm bảo cấu trúc bảng cô lập (`table inet sentinelx`), chains và sets cấm IP (`blocked_v4`, `blocked_v6`) được khởi tạo chuẩn xác, idempotent.
2. Thi hành lệnh `BLOCK_IP_NFTABLES` được Controller ủy quyền và gửi xuống Agent.
3. Hỗ trợ cơ chế tự động giải phóng phần tử qua cờ `flags timeout` của Linux Netfilter kernel.
4. Cách ly lỗi tuyệt đối: không để các lỗi quyền hạn (`Permission denied`), thiếu công cụ `nft`, hoặc timeout làm gián đoạn hay crash tiến trình Agent daemon.

---

## 2. Kiến trúc & Ranh giới (Architecture & Boundaries)

```text
+-----------------------+              Heartbeat Response
|  SentinelX Controller | ------------------------------------------+
+-----------------------+                                            |
                                                                     v
+---------------------------------------------------------------------------------+
| SentinelX Agent Host (Linux Server / Container)                                |
|                                                                                 |
|  +-----------------------+       Validate Target IP, Controller IP, Loopback    |
|  |  LocalSafetyValidator | <----------------------------------------------------+
|  +-----------------------+                                                      |
|              | PASS                                                             |
|              v                                                                  |
|  +---------------------------+    Async subprocess 'nft'                        |
|  |  NftablesDefenseExecutor  | -------------------------------+                 |
|  +---------------------------+                                |                 |
+---------------------------------------------------------------|-----------------+
                                                                v
                 +---------------------------------------------------------------+
                 | Linux Kernel Netfilter (nftables)                             |
                 |                                                               |
                 | table inet sentinelx {                                        |
                 |     set blocked_v4 { type ipv4_addr; flags timeout; }         |
                 |     set blocked_v6 { type ipv6_addr; flags timeout; }         |
                 |     chain input { hook input priority -100; policy accept; }  |
                 | }                                                             |
                 +---------------------------------------------------------------+
```

---

## 3. Cấu trúc nftables của SentinelX

Bảng được đặt tên là `sentinelx` thuộc family `inet` (hỗ trợ song song cả IPv4 và IPv6):

```nft
table inet sentinelx {
    set blocked_v4 {
        type ipv4_addr
        flags timeout
    }
    set blocked_v6 {
        type ipv6_addr
        flags timeout
    }
    chain input {
        type filter hook input priority -100; policy accept;
        ip saddr @blocked_v4 drop
        ip6 saddr @blocked_v6 drop
    }
}
```

* **Hook input priority -100**: Chạy trước chuỗi filter chuẩn (priority 0), lập tức loại bỏ (DROP) gói tin độc hại ngay tại cửa ngõ ingress của kernel, tiết kiệm CPU tối đa.
* **Sets `blocked_v4` & `blocked_v6`**: Tra cứu địa chỉ IP với độ phức tạp $O(1)$.
* **Cờ `flags timeout`**: Kernel tự động đếm lùi thời gian chặn (ví dụ: `1800s`). Khi hết hạn, kernel tự động giải phóng IP mà không cần thêm lệnh xóa thủ công, tránh rò rỉ bộ nhớ hoặc bảng luật bị phình to.

---

## 4. Đặc tả lệnh thực thi (Command Specification)

### 4.1 Khởi tạo schema (Idempotent Initialization)
Agent kiểm tra bảng bằng:
```bash
nft list table inet sentinelx
```
Nếu chưa tồn tại hoặc thiếu set, Agent nạp cấu hình nguyên tử qua stdin:
```bash
nft -f -
```

### 4.2 Chặn IP IPv4 có thời hạn
```bash
nft add element inet sentinelx blocked_v4 { 203.0.113.195 timeout 1800s }
```

### 4.3 Chặn IP IPv6 có thời hạn
```bash
nft add element inet sentinelx blocked_v6 { 2001:db8::1 timeout 1800s }
```

### 4.4 Chặn vĩnh viễn (khi duration <= 0)
```bash
nft add element inet sentinelx blocked_v4 { 203.0.113.195 }
```

### 4.5 Mở chặn IP (UNBLOCK)
```bash
nft delete element inet sentinelx blocked_v4 { 203.0.113.195 }
```
*(Nếu phần tử đã hết hạn hoặc không tồn tại, Executor xử lý an toàn và báo thành công mà không gây lỗi)*.

---

## 5. Quyền hạn Linux & Bảo mật (Least Privilege & Safety)

1. **Linux Capabilities**:
   - Agent **không cần chạy dưới user `root` tuyệt đối**. Chỉ cần cấp quyền `CAP_NET_ADMIN`.
   - Trong Docker:
     ```yaml
     cap_add:
       - NET_ADMIN
     ```
   - Trong systemd service:
     ```ini
     [Service]
     User=sentinelx
     CapabilityBoundingSet=CAP_NET_ADMIN
     AmbientCapabilities=CAP_NET_ADMIN
     ```

2. **Cách ly lỗi & Báo cáo ACK**:
   - Nếu lệnh `nft` trả về exit code khác 0 (ví dụ `Operation not permitted`), Executor bắt lỗi `stderr`, trả về `ExecutionResult(success=False, error_message=...)`.
   - `CommandProcessor` gửi ACK `status=FAILED` kèm thông báo lỗi chi tiết về Controller để lưu audit log và hiển thị trên Dashboard.
   - Tiến trình Agent daemon tuyệt đối không bị crash.

---

## 6. Hướng dẫn kiểm thử

```bash
# 1. Kiểm tra linter
uv run ruff check src tests

# 2. Kiểm tra type hint nghiêm ngặt
uv run mypy src tests

# 3. Chạy unit tests cho nftables executor và processor
uv run pytest -v tests/unit/agent/test_nftables_executor.py tests/unit/agent/test_command_processor.py

# 4. Chạy toàn bộ test suite
uv run pytest -q
```
