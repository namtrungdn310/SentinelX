# ADR-0004 — PostgreSQL as CORE Storage

## Status
Accepted

## Decision
CORE sử dụng PostgreSQL làm database chính.

## Rationale
Quy mô PBL 2–3 nodes không cần specialized TSDB.

PostgreSQL đủ cho:
- telemetry;
- health summaries;
- projects/nodes;
- incidents;
- policies;
- defense history;
- LB configuration/state records.

## Consequences
Không thêm TimescaleDB/InfluxDB trong CORE.
Supabase nếu dùng sau này chỉ là hosting option, không phải architectural dependency.
