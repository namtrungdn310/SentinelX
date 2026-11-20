# Core M1–M8 hardening — implementation checklist

Scope authorized 13/11/2026: complete the core audit fixes in one continuous
implementation. No UI changes, no M9 tenancy, no new infrastructure dependencies.
Working branch: `fix/core-m1-m8-hardening`, base `1b67632`.

- [x] Typed commands, expiry, authenticated/fenced ACK, legal transitions.
- [x] Leased command delivery, bounded retries, durable Agent command/ACK journal.
- [x] Independent Agent command worker; truthful real/simulated/noop outcomes.
- [x] YAML/env executor configuration, protected addresses, duration limits.
- [x] Transactional persistent policy cooldown, pure dry-run, per-node isolation.
- [x] Policy decision audit and supported-action validation.
- [x] Unified execution duration/expiry; serialized recovery and retry budgets.
- [x] Recovery ownership and quiet-observation requirements for incident resolution.
- [x] Network time/order/rate checks, bounded state and observation direction.
- [x] nftables JSON schema checks and idempotent reconciliation.
- [x] Incident severity/correlation/count queries and public module boundaries.
- [x] Bounded retention maintenance, operational constraints and deployment lab.
- [x] Migration acceptance through current head; PostgreSQL concurrency tests.
- [x] Isolated Linux nftables acceptance; full quality gates and handover report.

Existing uncommitted dashboard files are user-owned and must remain unchanged:
`AttentionPanel.tsx`, `TelemetryChart.tsx`, `presentation.ts`.

Final evidence: Windows 311 passed / 11 opt-in skips; Linux unit/integration
311 passed; separate live acceptance 9 + 2 passed. Ruff clean, mypy strict clean
(220 files), Docker builds and bundle manifest hashes verified. Five existing
Starlette deprecation warnings remain in pytest; no lint/type errors.
See `CORE_HARDENING_HANDOVER.md` for upgrade steps and explicit verification limits.
