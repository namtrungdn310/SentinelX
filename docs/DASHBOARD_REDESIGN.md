# SentinelX dashboard redesign

## 1. Milestone

Refinement of the existing F10 dashboard on the frozen F14 foundation.
This change implements no M1–M8 backend capabilities.

## 2. Scope

Included: the shared shell, Overview, Hosts, Telemetry, Events, onboarding,
host details, demo mode, filtering, responsive navigation and accessibility.
Excluded: new backend endpoints, authentication changes, detection, defense,
database migrations and deployment.

## 3. Repository inspection

The dashboard is a React 19 / Vite / TypeScript SPA using Lucide icons.
It already connects to REST and WebSocket endpoints and includes demo fixtures.
Controller project responses expose `project_id`; the UI normalizes this to `id`.
Resource metric queries return newest samples first.

## 4. Files and responsibilities

| Files | Action | Responsibility |
| --- | --- | --- |
| `dashboard/src/App.tsx`, `App.css`, `index.css` | Redesign | Shell, routes, scope filters, responsive layout and visual tokens |
| `dashboard/src/components/*.tsx` | Redesign / add | Panels, chart, host map, tables, events and accessible dialogs |
| `dashboard/src/useInfrastructure.ts` | Add | Separate demo and Controller snapshots, request races and telemetry history |
| `dashboard/src/useWebSocket.ts` | Update | Connection lifecycle and reconnect cleanup |
| `dashboard/src/presentation.ts` | Add | Consistent UI health labels, role grouping and byte formatting |
| `dashboard/src/api.ts` | Update | Normalize project IDs and bound read timeouts |
| `dashboard/vite.config.ts`, `.env.example` | Update / add | Configurable Controller target for development |
| `dashboard/scripts/check-ui.mjs` | Add | Render and contract smoke checks without additional packages |

## 5. Architecture notes

The existing modular monolith, REST contracts and database remain unchanged.
Presentation thresholds are UI summaries, not backend detection or policy.
Role groups retain the existing hostname inference; they are not server role metadata.
The Controller is reachable through a configurable Vite proxy. Agent enrollment
commands have a separately editable Controller URL for multi-host labs.

## 6. Implementation

Design direction revised on 2026-10-22: an operational observability console.
The interface uses graphite surfaces, compact section headers, thin dividers,
monospaced resource values, and semantic colors for metrics and host health.
The readability pass uses a neutral near-black canvas (#080808), black/gray
panel surfaces, brighter text and separators, a 14px base font, 32px primary
metric values, and slightly larger controls and table rows. Chart margins and
mobile axis labels are enlarged so labels remain legible as the SVG scales.

The rounded-layout refinement uses shared 10px control, 18px panel/card and 24px
modal radii across all views. KPI cards are independent elevated surfaces with
16px gaps, complete borders, restrained metric accents and inset progress bars,
not cells of a joined strip. Overview sections stack at full width on every
screen: fleet health, attention, projects and resource ranking each have their
own row, separated by 24px. Internal status tiles adapt from four columns to two;
KPI cards wrap from five columns to three, then two on smaller viewports.
Tables, chart panels, host tiles, filters, forms and dialogs share the same
rounded visual language; dark operational styling and route responsibilities
remain unchanged.
Marketing headlines, sidebar slogans, pastel KPI tiles, decorative graphics,
and brand copy in the footer have been removed.

The user-approved SentinelX logo concept is integrated as a clean, code-native
SVG adaptation at `dashboard/public/sentinelx-mark-v1.svg`. It replaces the
generic sidebar shield and the previous favicon references. The sidebar retains
an accessible link label and explicit image dimensions, including its collapsed
layout. A 32px PNG favicon is rendered from the SVG as a fallback. Both asset
references honor Vite's base path, and versioned filenames avoid the old favicon
cache. Previous favicon files and the approved concept PNG are preserved.
The concept was generated with imagegen; its prompt remains in
`output/imagegen/sentinelx-logo-concept-v1.prompt.md`. Raster background-removal
trials were not used in the application because their cutouts contained noise.

Overview and Telemetry have separate responsibilities:

- Overview summarizes the fleet: aggregate counters, health distribution,
  attention items, per-project totals, the top five hosts by CPU or RAM, and a
  preview of five recent non-metric events. Status counts open filtered host
  inventory; project rows open the corresponding project; ranked hosts open
  their Telemetry view. Overview contains no single-host time-series chart.
- Hosts provides the full searchable, sortable inventory and enrollment details.
- Telemetry analyzes one selected host: explicit host selection, CPU/RAM history,
  sample-count controls, exact sample data, disk usage and cumulative RX/TX.
  The full history is fetched only when this view is active.
- Events provides the complete buffered event stream with filtering and pause.

Twenty non-metric events are retained separately in UI memory so frequent metric
messages cannot immediately displace the overview's status/event preview.
Attention items use existing status and UI resource thresholds, including
pending enrollment; they do not invent backend incidents or detection results.

UI UX Pro Max informed the dashboard layout, visual hierarchy, readable type,
semantic status labels, reduced motion, keyboard interactions and dialog focus.
The implementation uses existing React / Lucide dependencies and SVG charts.
There are no new production dependencies.

- Routes: `#overview`, `#hosts`, `#metrics`, `#events`.
- Search accepts hostname, IP, `host:` and `ip:` queries.
- Project, status and role filters scope the KPI cards, map, table and events.
- CPU / RAM history is sorted by observation time and limited to 30 / 60 / 120 samples.
- Legends toggle series; keyboard arrows inspect points; a table exposes exact values.
- Host tables sort by hostname, CPU and RAM; missing metrics remain unavailable.
- Network byte counters are labeled cumulative bytes, not fabricated throughput.
- Pausing events freezes a snapshot; resume restores the current feed.
- Demo never issues real enrollment tokens or mixes Controller events with fixtures.
- Dialogs handle focus, Tab containment, Escape and focus restoration.
- Mobile uses labeled bottom navigation and larger controls.

## 7. Commands

From the repository root:

```powershell
uv sync --all-extras
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
cd dashboard
npm.cmd run build
npm.cmd run lint
npm.cmd run test:ui
npm.cmd run dev -- --port 5174
# In a second terminal, while Vite is running:
npm.cmd run test:dev
```

## 8. Expected result

The workspace opens at `http://localhost:5174`. With no Controller available,
it identifies simulated data and offers connection retry. With a reachable
Controller, actual projects and nodes replace demo fixtures, then WebSocket
messages update the displayed resources and events.

## 9. Troubleshooting

- Windows PowerShell execution policy may block `npm.ps1`; use `npm.cmd`.
- Set `SENTINELX_CONTROLLER_PROXY_TARGET` in `dashboard/.env.local` for a remote
  Controller, then restart Vite.
- Set `VITE_AGENT_CONTROLLER_URL` or edit the enrollment form's URL when Agents
  reach the Controller by a different host or port.
- An empty project list is a legitimate connected state; create a project through
  the existing Controller API before enrolling a host.
- The UI smoke checks render components and validate data conventions. They do
  not replace browser layout and interaction testing.
- UI smoke checks use a unique temporary cache with client dependency discovery
  disabled. They must never share `node_modules/.vite` with the running dev server.
- For a blank dev page, `npm.cmd run test:dev` checks every static module import,
  including optimized React files. HTML HTTP 200 alone does not prove startup.

## 10. Checkpoint

Verified on this branch:

- PASS: TypeScript and Vite production build.
- PASS: Oxlint with warnings treated as errors.
- PASS: 14 UI rendering / contract smoke checks, including route separation.
- PASS: Ruff and mypy (110 Python source files).
- PASS: 137 Python tests. Pytest reports three existing FastAPI / Starlette
  deprecation warnings; these are separate from lint results.
- PASS: dev server and current dashboard module return HTTP 200 at port 5174.
- Blank-page regression: missing optimized React files returned HTTP 404 after
  render checks reused the active dev cache. The checks now have a separate
  temporary cache; restart Vite with `npm.cmd run dev -- --force` to regenerate
  a cache already affected by the previous version.
- NOT VERIFIED: browser screenshots, visual layout and full browser interactions.
  The Browser runtime reported no available browser in this session.

## 11. Stop

The implementation stops at the dashboard redesign. No subsequent milestone
or production deployment is included. Publication uses a feature-branch commit
and a pull request into dev; merging requires the repository's review approval.

## 12. Handoff

Working branch: `feat/dashboard-observability-redesign`.
Review the running dashboard and this branch's diff before integrating into dev.
Unrelated local Python dependency changes in `pyproject.toml` and `uv.lock`
are excluded from the dashboard publication.
