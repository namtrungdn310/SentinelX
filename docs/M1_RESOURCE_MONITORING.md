# M1 — Real Resource Monitoring: implementation and acceptance

Checkpoint: 02/11/2026. Working branch: `fix/m1-resource-monitoring-completion`,
based on `dev` at `d16d99f`.

## 1. Status and scope

M1 code corrections and automated acceptance are complete. This covers real CPU,
RAM, disk and network byte deltas, Agent batching/retry, persistence, REST,
WebSocket, and truthful dashboard labels. No M2 packet capture, aggregation,
Scapy/libpcap, detection, firewall or recovery capability is implemented here.

Real Linux sampling and a live PostgreSQL round trip were exercised in a dedicated
Docker project with separate Agent, Controller and DB containers. This is a
single-host integration lab, not proof of deployment across two physical hosts/VMs.
The final LAN demonstration checklist below remains unverified.

## 2. Corrections

| Problem | Implemented behavior |
|---|---|
| Disk read failure appeared as `0%` | Send `disk_percent=null`; show `—` and a missing-data label. A real zero remains zero. |
| Dashboard described RX/TX as cumulative | Label latest deltas as bytes between checks; never call them bytes/s or synchronized fleet throughput. |
| Missing network counters appeared as zero/boot totals | Send null, reset the baseline, then resume differences after two valid observations. Counter decreases clamp to zero and rebase. |
| CPU primed in one thread, sampled in another | Each call measures a bounded 100ms window inside `asyncio.to_thread`, independent of previous per-thread calls. |
| Temporary OS sampling error terminated telemetry | Log expected OS/psutil failures, skip the failed sample and retry at the next interval; heartbeat continues. |
| Failed batch was appended backwards | Requeue failed samples before newer ones in FIFO order, retain the sequence until acknowledged, and keep the newest samples on overflow. |
| Empty injected batcher silently replaced | Check `is not None`, preserving the provided buffer even when empty. |
| Unknown collector setting silently selected real | Validate collector type as `real` or `fake`. |
| Optional byte fields defaulted to zero in ORM | Remove client-side defaults; explicit null survives SQL, REST and WebSocket. |
| REST returned success before DB commit | Use `Depends(get_db_session, scope="function")` consistently in projects/nodes/telemetry; commit finishes before HTTP success. |
| Config example contained unused keys/M2 settings | Provide the actual supported Agent keys and a configurable remote Controller URL; supply enrollment credentials locally. |

The transaction race was reproduced against PostgreSQL: an immediate node/token
request could return 404 after the preceding create returned success. The final
live test uses immediate dependent requests without compensating polling for
project/node creation. Regression tests also check commit success/failure at the
HTTP response boundary.

## 3. Metric semantics

- `cpu_percent`: system-wide utilization during a 100ms measurement window.
  The configurable telemetry interval is the wait between collections; collection,
  HTTP dispatch and retry can lengthen the actual sample spacing.
- `memory_percent`: OS virtual-memory usage percentage.
- `disk_percent`: usage for `telemetry_disk_path` (default root mount); null if
  the path cannot be read. The Agent does not turn an unreadable disk into 0%.
- `network_rx_bytes` / `network_tx_bytes`: nonnegative differences between OS
  counter observations, including all interfaces returned by psutil. These are
  neither since-boot totals nor packet features for M2. Failure/rebaseline is null;
  a counter decrease produces zero for that direction and resets its baseline.
- `observed_at`: UTC timestamp at the end of collection.
- Fleet network summary: sum of latest valid samples for online hosts, whose
  intervals/timestamps may differ. Coverage text identifies partial data.

No field names or wire types changed. Existing SQL columns already allow NULL;
removing the ORM's Python zero defaults requires no schema migration. Older rows
that contain fabricated zero cannot be distinguished retrospectively from measured
zero, so no speculative backfill is performed.

References used for the implementation:
[psutil CPU sampling](https://psutil.io/api/#psutil.cpu_percent) and
[FastAPI dependency scope](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope).
The FastAPI lower bound is now 0.121.0 for scoped dependencies; the existing locked
version 0.141.1 and all other resolved package versions remain unchanged. Existing
local `types-psutil` dependency-group changes were preserved.

## 4. Files and responsibilities

| Files | Responsibility |
|---|---|
| `src/sentinelx_agent/collectors/real.py` | CPU window, optional metrics, network baseline recovery |
| `src/sentinelx_agent/config.py`, `configs/agent.example.yaml` | Validated collector and usable config |
| `src/sentinelx_agent/daemon.py`, `telemetry.py` | Collection failure handling and ordered bounded retries |
| `src/sentinelx_common/contracts/telemetry.py` | Clarified existing nullable fields |
| Controller telemetry model and three router providers | Preserve NULL and commit before success |
| Dashboard App/KPI/host-detail components, demo polling | Correct labels, missing-state text, independent simulated deltas |
| Agent unit tests, realtime integration, transaction response tests | Regressions for failures, order, scope and serialization |
| `tests/e2e/test_m1_live.py`, `deploy/m1/` | Opt-in Linux/PostgreSQL acceptance |

Module boundaries, REST batching and configurable multi-host URLs remain in place.
The Agent does not import Controller ORM models.

## 5. Run and configure

```bash
uv sync --all-extras --frozen
```

Create a project and node on the target Controller, issue an enrollment token,
then set these environment variables on the managed Linux server:

```bash
export SENTINELX_CONTROLLER_URL=http://CONTROLLER_LAN_IP:8000
export SENTINELX_NODE_ID=NODE_UUID_FROM_CONTROLLER
export SENTINELX_ENROLLMENT_TOKEN=TOKEN_FROM_CONTROLLER
export SENTINELX_TELEMETRY_COLLECTOR_TYPE=real
export SENTINELX_TELEMETRY_DISK_PATH=/
export SENTINELX_TELEMETRY_INTERVAL=5
export SENTINELX_TELEMETRY_BATCH_SIZE=5
export SENTINELX_IDENTITY_PATH=data/agent_identity.json
uv run python -m sentinelx_agent.main
```

These are placeholders, not usable credentials. Keep real credentials out of Git,
screenshots and shared logs. Alternatively use a private copy of
`configs/agent.example.yaml` via `SENTINELX_AGENT_CONFIG`.

## 6. Automated checks and results

| Check | Verified result |
|---|---|
| Ruff | PASS |
| mypy strict | PASS, 112 source/test files |
| Full pytest, Windows Python 3.12.10 | 152 passed, 2 opt-in live tests skipped |
| Full pytest, Linux Python 3.12.15 | 152 passed, 2 opt-in live tests skipped |
| Live Linux Agent → Controller → PostgreSQL → REST/WS | 2 passed, including unavailable optional fields |
| Dashboard lint / production build | PASS |
| Dashboard smoke checks | 25 passed |
| `uv lock --check` | PASS |

The normal suites retain 3 existing Starlette deprecation warnings. The 2 skipped
tests are not missing acceptance: they passed separately in the opt-in live lab.
The live normal case uses actual Linux resources; its error case uses a real
missing disk path and injects unavailable network counters to verify PostgreSQL
NULL round trips. It also verifies enrollment identity, heartbeat `last_seen`,
two-sample batches, matching pushed/persisted values and UTC timestamps.

```bash
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
npm --prefix dashboard run lint
npm --prefix dashboard run test:ui
npm --prefix dashboard run build
```

If Windows cannot write the default pytest temp/cache location, pass a new,
unused workspace-local `--basetemp` and `-o cache_dir=...`; do not reuse a valuable
directory because pytest clears its base-temp target.

## 7. Reproduce isolated live acceptance

```bash
docker compose -p sentinelx-m1-acceptance -f deploy/m1/compose.acceptance.yaml up --build --abort-on-container-exit --exit-code-from agent-check
```

This creates a dedicated project, applies Alembic migrations, starts PostgreSQL
16 and the Controller, then executes the real Agent test from a different Linux
container over HTTP/WebSocket. No host ports, shared lab networks, host mounts,
firewall privileges or existing application containers are used. The database
credentials in that file are disposable test-only values.

The test writes disposable projects/nodes and must target a dedicated test DB.
`SENTINELX_M1_CONTROLLER_URL` opts in when running pytest outside Compose; do not
point it at customer/production data. Cleanup of this dedicated lab only:

```bash
docker compose -p sentinelx-m1-acceptance -f deploy/m1/compose.acceptance.yaml down --volumes
```

## 8. Troubleshooting and practical limits

- A missing disk mount should show `—`; verify the configured path/permissions.
- Network counters need a fresh baseline after unavailable observations. Null is
  expected until a second valid read, while real zero traffic is `0 B`.
- CPU is measured over 100ms, not an average of the entire telemetry interval.
- The in-memory buffer is bounded, drops oldest on overflow, and is not durable
  across process restarts. A lost HTTP acknowledgment can lead to duplicate stored
  samples; exactly-once delivery/idempotent ingestion is not claimed.
- Docker psutil metrics describe the container-visible OS/network namespace and
  mounts. This does not prove visibility of every physical host resource.
- WebSocket broadcast can occur before the POST transaction finishes; consumers
  must not treat broadcast alone as proof of durable commit. The REST success is
  emitted after commit. The acceptance query waits for the broadcast batch to persist.
- Current live acceptance does not exercise a browser connected to this isolated
  stack. UI labels/missing states are covered by render smoke tests; there is no
  claim of a new visual or screen-reader audit.

## 9. Final LAN demonstration (not verified in this run)

- [ ] Record Linux/VM host A (Controller/PostgreSQL/dashboard) and separate host B
  (Agent) addresses; configure Controller URL without source edits.
- [ ] Enroll host B using its node UUID/token; verify heartbeat and real OS samples.
- [ ] Compare CPU/RAM/disk with host B tools over comparable measurement windows.
- [ ] Verify latest RX/TX deltas, including a no-traffic sample; do not compare them
  directly with since-boot interface counters or call them bytes/s.
- [ ] Briefly interrupt only the controlled Agent–Controller lab connection;
  reconnect and verify heartbeat, ordered batching and dashboard recovery.
- [ ] Verify a deliberately missing disk path appears as missing through storage/UI.
- [ ] Capture sanitized evidence (no tokens) and record results/date/hosts here.

## 10. Checkpoint

Code and automated M1 acceptance PASS. This is the technical baseline for M2;
the final LAN checklist is explicitly open and must not be marked PASS based on
single-host Docker. README/roadmap link to this report instead of implying a
completed physical multi-host demonstration.

## 11. Stop

No M2 work is included. Changes remain on the M1 fix branch for review; no commit,
push or merge was performed as part of this correction task.
