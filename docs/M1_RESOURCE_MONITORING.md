# M1 — Real Resource Monitoring: implementation and acceptance

Checkpoint: 04/11/2026. Resource corrections were merged via PR #13.
Linux deployment addition: `feat/m1-agent-linux-deployment`, based on `dev`
at `a261116`.

## 1. Status and scope

M1 code corrections, Agent deployment tooling and automated acceptance are complete.
The resource corrections below were the previous checkpoint; the 04/11 addition
completes standalone Linux installation and service operations. This covers real CPU,
RAM, disk and network byte deltas, Agent batching/retry, persistence, REST,
WebSocket, and truthful dashboard labels. No M2 packet capture, aggregation,
Scapy/libpcap, detection, firewall or recovery capability is implemented here.

Real Linux sampling and a live PostgreSQL round trip were exercised in a dedicated
Docker project with separate Agent, Controller and DB containers. This is a
single-host integration lab, not proof of deployment across two physical hosts/VMs.
The final LAN demonstration checklist below remains unverified.

Native service operations were also exercised on Ubuntu 22.04/WSL with systemd
249 and Agent Python 3.12.14, using a temporary non-root account/service and an
HTTP contract fixture. That fixture is not the real Controller. Actual Controller,
PostgreSQL and REST/WebSocket round trips passed separately in the Docker lab.
Boot enablement was checked; no machine reboot was performed.

The website-to-installation onboarding is not complete: no automated publication
or hosted download endpoint for the bundle is included, and the Add Host modal
still emits the older launch command instead of the new manage.py workflow.
Use the installation runbook with a trusted, manually transferred bundle today.
The implementation/automation results here must not be read as a completed
self-service SaaS onboarding experience.

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
| No standalone Linux deployment path | Build Agent/Common-only source bundle with hash-locked runtime requirements; uv installs Python 3.12 and an isolated venv on the target. |
| Daemon required manual foreground execution | Root-managed systemd unit runs a dedicated unprivileged account, starts on boot and restarts on crash. |
| Enrollment secret mixed with long-running config | One-time CLI enrollment via hidden prompt/private file/stdin; managed config does not retain the token. |
| Unsafe identity recovery semantics | Refuse damaged identity or configured node mismatch; never silently overwrite an existing identity. |
| No version lifecycle | Versioned releases, current/previous pointers, update, rollback, uninstall preserving identity and explicit purge. |
| Bootstrap failure could bypass HTTP cleanup | Daemon always closes owned client; cancellation stops and awaits sibling loops; SIGTERM/SIGINT stop the service cleanly. |
| Errors could print credentials from identity/remote responses | Suppress response/source bodies in enrollment errors and retry/identity logs. |

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
| `src/sentinelx_agent/cli.py`, `main.py` | Foreground run, local check and one-time enrollment CLI |
| `deploy/agent/manage.py`, `sentinelx-agent.service.in` | Privileged installation manager; unprivileged supervised daemon |
| `scripts/build_agent_bundle.py` | Reproducible content release IDs; export locked Agent-only runtime deps |
| `scripts/test_agent_systemd.py` | Opt-in Linux/root lifecycle acceptance with isolated service/account and cleanup |
| `tests/unit/agent/test_agent_cli.py`, `test_agent_bundle.py` | Secret handling, corrupt identity, cancellation, artifact tamper/path validation |
| `docs/AGENT_INSTALLATION.md`, multi-host env examples | Operator runbook and actual node-UUID/token placeholders |

Module boundaries, REST batching and configurable multi-host URLs remain in place.
The Agent does not import Controller ORM models.

## 5. Run and configure

For installation on a monitored Linux server, use the complete native runbook:
[AGENT_INSTALLATION.md](AGENT_INSTALLATION.md). Build on the development machine
with `uv run python scripts/build_agent_bundle.py`, then transfer the trusted
artifact. The target needs neither the repository nor Controller/DB dependencies.

The foreground source workflow below remains available for development/labs.

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
| mypy strict | PASS, 115 source/test files; deployment/build/QA tools also checked for Linux |
| Full pytest, Windows Python 3.12.10 | 177 passed, 2 opt-in live tests skipped |
| Full pytest, Linux Python 3.12.15 | 177 passed, 2 opt-in live tests skipped |
| Live Linux Agent → Controller → PostgreSQL → REST/WS | 2 passed, including unavailable optional fields |
| Agent unit tests | 62 passed; 25 tests added beyond previous checkpoint |
| Native systemd lifecycle, Ubuntu 22.04 / systemd 249 | PASS; install, enroll, real samples, outage recovery, crash restart, stop/start, config exit 78, update, rollback, uninstall/reinstall, journal secret check, purge |
| Standalone bundle | Built and installed; only 18 Agent runtime packages, no FastAPI/SQLAlchemy/DB runtime |
| Dashboard lint / production build | PASS at previous checkpoint; UI unchanged in this addition |
| Dashboard smoke checks | 25 passed at previous checkpoint; UI unchanged |
| `uv lock --check` | PASS |

The normal suites retain 3 existing Starlette deprecation warnings. The 2 skipped
tests are not missing acceptance: they passed separately in the opt-in live lab.
The live normal case uses actual Linux resources; its error case uses a real
missing disk path and injects unavailable network counters to verify PostgreSQL
NULL round trips. It also verifies enrollment identity, heartbeat `last_seen`,
two-sample batches, matching pushed/persisted values and UTC timestamps.

The native test uses an actual systemd unit, not a mock systemctl. It creates a
unique `sentinelx-agent-qa-<suffix>` account/unit and purges its paths/account in
`finally`; no existing application service is touched. Release B differs only in
documentation to exercise version switching. This is not a compatibility claim
for arbitrary future Agent versions or distro package managers. An unrelated
installed snapd unit emits a systemd-analyze warning on Ubuntu 22.04; the SentinelX
unit verifies and runs. No reboot, production host install or physical LAN proof
is implied by these tests.

```bash
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
npm --prefix dashboard run lint
npm --prefix dashboard run test:ui
npm --prefix dashboard run build
```

Additional deployment checks:

```bash
uv run ruff check scripts/build_agent_bundle.py deploy/agent/manage.py
uv run ruff check --target-version py310 scripts/test_agent_systemd.py
uv run mypy --platform linux deploy/agent/manage.py scripts/build_agent_bundle.py scripts/test_agent_systemd.py
uv run python scripts/build_agent_bundle.py
# Linux lab only, from repository root, with a trusted extracted bundle:
sudo python3 scripts/test_agent_systemd.py /path/to/extracted-bundle --uv /absolute/path/to/uv
```

The lifecycle test deliberately kills/restarts its own temporary service and
downloads the managed Python/runtime dependencies. It does not reboot the host.

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
- [ ] Install native Agent on the separate Linux host using the runbook; reboot
  that authorized lab host and verify the service resumes with the same identity.

## 10. Checkpoint

Code and automated M1 acceptance PASS. This is the technical baseline for M2;
the final LAN checklist is explicitly open and must not be marked PASS based on
single-host Docker. README/roadmap link to this report instead of implying a
completed physical multi-host demonstration.

Native deployment is now implemented and lifecycle-tested, rather than left as
a later milestone. The built artifact is
`dist/agent/sentinelx-agent-0.1.0-14a099da6d8a.tar.gz` (ignored build output, rebuild
from source when needed). The operational runbook is the installation reference.
The existing local `pyproject.toml` / `uv.lock` dependency-group edits were retained;
this addition introduces no dependency/version change. No database migration is required.

## 11. Stop

No M2 work is included. Publish this addition through a pull request into dev;
the native installer checks do not close the website onboarding, reboot or LAN
acceptance items above.
