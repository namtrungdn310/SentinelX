# ADR-0003 — Agent Pushes Batched Telemetry

## Status
Accepted

## Decision
Agent chủ động push telemetry về Controller qua REST/JSON theo batch.

## Rationale
- không cần mở inbound Agent API cho telemetry;
- thuận lợi sau NAT/firewall;
- Controller topology đơn giản;
- giảm polling overhead;
- batch giảm HTTP/DB overhead.
