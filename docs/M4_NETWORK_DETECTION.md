# M4 — Network Detection

## 1. Milestone và Scope

Milestone M4 bổ sung tầng phát hiện tấn công và bất thường mạng (Network Anomaly & Attack Detection) trên Controller, phân tích dữ liệu tổng hợp `NetworkFeature` và `NetworkWindow` thu thập từ Agent (M2), bóc tách danh tính IP kẻ tấn công (`attacker_ip`), và kích hoạt chuỗi xử lý sự cố (Incident) cùng thẩm định chính sách (Policy Engine) của Milestone M5.

### In Scope
- Mở rộng Wire Contracts: Thêm `NetworkAnomalyDetail`, enum `DetectorType` mạng (`syn_flood_detector`, `port_scan_detector`, `traffic_spike_detector`).
- Các bộ dò mạng chuyên dụng:
  - `SynFloodDetector`: Phát hiện tấn công TCP SYN Flood dựa trên độ lệch tỷ lệ cờ SYN/ACK và ngưỡng tối thiểu.
  - `PortScanDetector`: Phát hiện rà quét cổng do thám (Horizontal / Vertical Port Scan) dựa trên số lượng cổng đích phân biệt và cờ cắt ngắn (`ports_truncated`).
  - `TrafficSpikeDetector`: Phát hiện bão gói tin / UDP Flooding.
- Động cơ phát hiện mạng (`NetworkDetectionEngine` trong `DetectionEngine`):
  - Phân tích đa IP trong cùng một cửa sổ quan sát.
  - Quản lý trạng thái và hạ nhiệt (Cooldown) phân lập theo khóa `(node_id, detector_name, attacker_ip)`.
  - Cơ chế vượt cooldown khi mức độ nghiêm trọng leo thang từ `HIGH` lên `CRITICAL`.
- Đấu nối luồng Ingestion (`NetworkTelemetryService.ingest`):
  - Gói tin mạng từ Agent $\rightarrow$ M4 Detectors $\rightarrow$ `detection_events` $\rightarrow$ M5 `incidents` $\rightarrow$ M5 `PolicyEngine` (thẩm định IP Whitelist / Loopback / Cooldown).

### Out of Scope
- Không sửa mã nguồn Agent (Agent ở M2 đã hoàn tất thu thập `NetworkFeature`).
- Không thực thi firewall hay can thiệp `nftables` trực tiếp (dành cho Milestone M6 và M7).
- Không tạo bảng cơ sở dữ liệu mới (tận dụng bảng `detection_events` và `detection_states` từ M3).

---

## 2. Luồng thực thi chi tiết (Execution Pipeline)

```text
Agent Batch Push (POST /api/v1/telemetry/network-features)
           ↓
NetworkTelemetryService: Xác minh node/agent & lưu windows vào DB
           ↓
DetectionService.evaluate_network_windows():
   ├── SynFloodDetector (TCP flag asymmetry & volume)
   ├── PortScanDetector (Distinct destination ports >= 15 or truncated)
   └── TrafficSpikeDetector (UDP flooding >= 300 or Volumetric >= 1000 pkts)
           ↓
DetectionEngine: Lọc Cooldown per (node, detector, attacker_ip) & Lưu state
           ↓
PostgreSQL: Lưu detection_events (có attacker_ip & details JSONB)
           ↓
WebSocket Hub: Phát Realtime DETECTION_ALERT
           ↓
IncidentService.correlate_events() (M5):
   Gom các sự kiện cùng node/project vào Incident & phát INCIDENT_ALERT
           ↓
PolicyService.evaluate_event() (M5):
   Đối soát attacker_ip với ip_whitelist, loopback, controller IP & cooldown
           ↓
Trả về kết quả thẩm định phòng thủ (Authorized Action Intent) sẵn sàng cho M6
```

---

## 3. Lệnh tái lập kiểm thử (Reproducible Commands)

```bash
# Kiểm tra định dạng và linter
uv run ruff check src tests

# Kiểm tra tĩnh kiểu dữ liệu (Strict Type Check)
uv run mypy src tests

# Chạy riêng bộ kiểm thử đơn vị M4
uv run pytest tests/unit/controller/detection/test_network_detectors.py -v

# Chạy kiểm thử tích hợp End-to-End M4 -> M5
uv run pytest tests/integration/controller/test_m4_end_to_end.py -v

# Chạy toàn bộ test suite dự án
uv run pytest -q
```
