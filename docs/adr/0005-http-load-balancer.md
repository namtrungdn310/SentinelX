# ADR-0005 — HTTP Reverse Proxy for CORE Load Balancer

## Status
Accepted

## Decision
SentinelX CORE xây custom HTTP reverse proxy/load balancer bằng Python + aiohttp.

Algorithms:
- Round Robin;
- Least In-Flight.

## Rationale
HTTP phù hợp PBL vì:
- request-level observability;
- dễ đo latency;
- dễ track in-flight;
- health endpoint rõ;
- demo dễ;
- mở đường Adaptive LB Phase 2.

Generic TCP proxy không thuộc CORE.
