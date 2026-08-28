# SentinelX — Security & Safety Guardrails

## 1. Principle

SentinelX có khả năng can thiệp Linux/network nên safety quan trọng hơn feature count.

---

## 2. Defense Boundary

Controller:
- evaluates policy;
- creates authorized DefenseAction;
- tracks audit.

Agent:
- receives command;
- re-validates command locally;
- executes only allowed action;
- returns acknowledgement/result.

---

## 3. Protected Targets

Agent không bao giờ block:
- localhost / loopback;
- Controller IP;
- management IP;
- node's own IP;
- required infrastructure addresses;
- explicit whitelist;
- protected CIDR.

Safety validation phải có cả Controller và Agent.

---

## 4. Action Safety

Bắt buộc cho automated defense:
- maximum block duration;
- cooldown;
- duplicate prevention;
- action ID/idempotency;
- manual override;
- rollback/unblock path;
- audit log;
- expiry.

---

## 5. Privilege

Controller không chạy root nếu không cần.

Agent dùng least privilege.

Packet capture/firewall milestone phải nghiên cứu Linux capability phù hợp thay vì mặc định full privileged/root.

---

## 6. PBL Attack Simulation

Chỉ target:
- Docker lab;
- localhost/private isolated environment được kiểm soát.

Không:
- scan public IP;
- SYN flood Internet;
- thử firewall trên production/customer system.

---

## 7. Secrets

Không commit:
- enrollment token;
- node credential;
- password;
- secret keys;
- `.env`.

Logs không được chứa credentials.

---

## 8. Safe Modes

Trước khi defense thật ổn định phải hỗ trợ:
- `alert_only`;
- `noop` executor;
- simulated action.

Self-healing trước khi ổn định phải có:
- maximum retry;
- cooldown;
- loop prevention.

---

## 9. Network Data

CORE không lưu packet payload đại trà.

Ưu tiên:
- metadata;
- aggregated network features.

Giảm:
- privacy risk;
- storage;
- CPU/memory pressure.
