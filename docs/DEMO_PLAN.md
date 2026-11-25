# SentinelX — PBL Demo Plan

## 1. Demo Environment Strategy & Phased Deployment Roadmap

SentinelX triển khai theo 3 bước tuần tự từ test nội bộ tới demo từ xa:

### Phase 1 (Hiện tại — Mức 1): Docker Compose Lab trên 1 máy
Dùng [compose.yaml](../compose.yaml) trên máy dev trước để hoàn thiện và kiểm thử end-to-end toàn bộ luồng (`--profile core` → `--profile lab` → `--profile attack`).

Dùng cho:
- phát triển & kiểm thử tích hợp end-to-end;
- repeatability trước khi mang sang nhiều máy;
- fallback nếu network lab gặp sự cố.

### Phase 2 (Mục tiêu demo nhiều máy): PC/Laptop Windows + Nhiều VM/Laptop Từ xa
- **Laptop A (Windows — Control Plane & Gateway)**: bật cụm `--profile core` (`postgres_db`, `sentinelx_controller` kèm sẵn Agent Bundle download, `sentinelx_dashboard` Nginx SPA tại `:5174`) + chạy `sentinelx_lb` (`:8080`).
- **Nhiều laptop & VM từ xa** kết nối về Laptop A qua **Tailscale** (ưu tiên: giữ IP `100.x.y.z` cố định, chạy VMware `NAT` bình thường qua Wi-Fi trường hay 5G Hotspot iPhone, không đụng cấu hình lab môn học khác) hoặc **Cloudflare Tunnel** kèm lớp xác thực truy cập cho trình duyệt bên ngoài.

> Xem kế hoạch chi tiết 7 bước cho mô hình **2 Laptop + VMware Linked Clone + Tailscale** tại [LEVEL2_RUNBOOK.md](./LEVEL2_RUNBOOK.md).

### Phase 3 (Tùy chọn thực tế / Cloud VPS): Production Linux Hosts
Chuyển Control Plane lên Linux VPS chạy 24/7 (Nginx HTTPS + xác thực truy cập; tạo ≥ 2 GB Swap nếu dùng Droplet 1 GB RAM), cài `sentinelx-agent` làm `systemd` service trên từng Linux server và khai báo `protected_cidrs` trước khi bật `nftables` thật.

> Chi tiết tham chiếu kiến trúc mạng LAN đa máy xem thêm tại [MULTI_HOST_DEPLOYMENT.md](./MULTI_HOST_DEPLOYMENT.md) và runbook thực hành từng bước tại [LEVEL2_RUNBOOK.md](./LEVEL2_RUNBOOK.md).

### Final Network Profile (LAN / Multi-Host Chuẩn PBL4)
Multi-host qua LAN/IP hoặc Tailscale VPN.

Khuyến nghị:

```text
Machine A
├── Controller
├── Dashboard
└── Load Balancer

Machine B
├── Backend01
└── Agent01

Machine C (recommended)
├── Backend02
└── Agent02
```

---

## Demo 1 — Multi-Host Monitoring

```text
Remote Node
   ↓
Agent
   ↓ LAN / HTTP
Controller
   ↓
PostgreSQL
   ↓ WebSocket
Dashboard
```

Show:
- node identity;
- CPU;
- RAM;
- load;
- RX/TX;
- connections;
- last_seen;
- online/offline.

Acceptance:
- remote Agent không chạy cùng máy Controller;
- không sửa source code để chuyển local → LAN.

---

## Demo 2 — CPU Overload

```text
Generate CPU load on remote Node
 -> Agent metric
 -> Controller
 -> Resource Detector
 -> DetectionEvent
 -> Alert/Incident
 -> Dashboard
```

Foundation chỉ chuẩn bị pipeline; real detector triển khai sau Foundation Freeze.

---

## Demo 3 — Backend Failure + LB Failover

```text
Client
  ↓
LB on Machine A
  ↓
Remote Backend B/C
```

Stop one backend:

```text
health check failures
 -> UNHEALTHY
 -> EJECTED
 -> traffic continues to healthy backend
```

Recovery:

```text
backend starts again
 -> successful probes
 -> RECOVERING
 -> HEALTHY
 -> ENABLED
```

---

## Demo 4 — Port Scan / SYN Simulation

```text
Attack Simulator
 -> Target Linux Node
 -> Network Collection
 -> NetworkFeature
 -> Detection
 -> Policy
 -> DefenseAction
 -> Agent
 -> nftables / safe executor
 -> Dashboard
```

Attack chỉ chạy trong controlled PBL lab/private network.

---

## Demo 5 — Recovery

IP:

```text
temporary block
 -> expiry/cooldown
 -> automatic unblock
 -> audit/recovery event
```

Backend:

```text
unhealthy
 -> recover
 -> health verification
 -> re-add
```

---

## Demo Reliability Rules

- có `demo-reset.sh`;
- không phụ thuộc Internet;
- có Docker fallback;
- có known-good config;
- remote IP/port configurable;
- defense có safe/no-op fallback;
- attack target chỉ private/controlled host;
- trước bảo vệ phải chạy full rehearsal ít nhất một lần trên topology multi-host.
