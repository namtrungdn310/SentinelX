# ADR-0002 — Modular Monolith Controller

## Status
Accepted

## Decision
Controller là Modular Monolith theo business capability.

Agent và Load Balancer là runtime process/service riêng.

Các module Controller giao tiếp qua public interface hoặc domain/application event phù hợp.

## Rationale
Tối ưu cho:
- nhóm 2 người;
- debug nhanh;
- demo ổn định;
- vẫn giữ boundary để mở rộng.
