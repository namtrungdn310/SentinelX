# SentinelX — Project Overview

## 1. Tên đề tài

**SentinelX — Nền tảng giám sát, phát hiện bất thường và tự động bảo vệ hạ tầng máy chủ**

Đây là dự án PBL4 thuộc lĩnh vực Hệ điều hành & Mạng máy tính.

Nhóm phát triển gồm 2 sinh viên.

---

## 2. Product Definition

SentinelX là một nền tảng tập trung để:

- onboard Linux nodes;
- thu thập telemetry;
- theo dõi trạng thái tài nguyên;
- thu thập network features;
- phát hiện bất thường;
- tạo incident;
- áp policy;
- điều phối automated defense;
- hỗ trợ recovery/self-healing;
- phân phối traffic qua custom load balancer;
- hiển thị toàn bộ trạng thái trên Web Management Dashboard.

SentinelX Agent chạy độc lập trên Linux OS và **không nhúng vào source code ứng dụng khách hàng**.

---

## 3. Người dùng chính

Người dùng của SentinelX là:

> Administrator / Infrastructure Operator

Không phải end-user của website khách hàng.

---

## 4. Các khái niệm

### Project / Infrastructure
Nhóm logic chứa các node/backend thuộc cùng một hệ thống khách hàng.

### Node
Một Linux server/VM/container được SentinelX quản lý.

### Agent
Daemon/service chạy trên node, có nhiệm vụ:
- identity/enrollment;
- heartbeat;
- telemetry collection;
- network feature collection;
- command execution;
- action acknowledgement.

### Controller
Control plane trung tâm:
- node registry;
- ingestion;
- storage;
- detection input;
- incidents;
- policy;
- defense coordination;
- realtime API;
- LB control information.

### Load Balancer
HTTP reverse proxy đứng trước backend pool:
- Round Robin;
- Least In-Flight;
- health checking;
- backend ejection;
- backend re-add.

### Dashboard
Web UI dành cho administrator:
- nodes;
- monitoring;
- network;
- alerts/incidents;
- load balancer;
- blocked IP;
- defense history;
- whitelist;
- settings.

---

## 5. Real-world deployment target

```text
Internet Users
      |
      v
Customer Domain
      |
      v
SentinelX Load Balancer
      |
  +---+---+
  |   |   |
  v   v   v
NodeA NodeB NodeC
Agent Agent Agent
  \    |    /
   \   |   /
    v  v  v
SentinelX Controller
      |
   PostgreSQL
      |
   Dashboard
```

---

## 6. Single-server case

SentinelX vẫn có giá trị với một server:

- monitoring;
- resource detection;
- network detection;
- alerts;
- defense;
- service health;
- một phần recovery.

Load Balancer không có nhiều ý nghĩa nếu chỉ có một backend instance.

---

## 7. PBL Lab

PBL chủ yếu dùng Docker để giả lập nhiều Linux backend node.

Mục tiêu demo:

1. Monitoring
2. CPU Overload
3. Backend Failure + LB failover
4. Port Scan/SYN simulation → Detection → Defense
5. Recovery/unblock/re-add

---

## 8. Nguyên tắc phạm vi

Ưu tiên:
- end-to-end core;
- integration;
- debug;
- demo reliability;
- Linux/network relevance.

Không ưu tiên:
- enterprise scale;
- distributed complexity;
- technology novelty.
