# ADR-0001 — Python as Primary CORE Language

## Status
Accepted

## Context
SentinelX cần Linux monitoring, network programming, asynchronous I/O, statistical detection và khả năng mở rộng ML; nhóm chỉ có 2 sinh viên.

## Decision
Python 3.12 là ngôn ngữ CORE chính.

## Consequences
Positive:
- development speed;
- Linux monitoring ecosystem;
- FastAPI/asyncio;
- Scapy/psutil;
- ML extensibility.

Trade-offs:
- raw performance thấp hơn C++;
- CPU-heavy workloads phải tránh block event loop.
