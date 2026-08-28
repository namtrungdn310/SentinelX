# ADR-0006 — Controller Decides, Agent Executes Defense

## Status
Accepted

## Decision
Controller chịu trách nhiệm quyết định và persist DefenseAction.

Agent trên node chịu trách nhiệm:
- nhận command;
- safety validation cục bộ;
- thực thi local action;
- ACK/result.

Firewall CORE: nftables.

## Rationale
Controller không nên SSH trực tiếp vào node để thay firewall.
Local Agent hiểu local network/privilege context tốt hơn và giữ execution boundary rõ.
