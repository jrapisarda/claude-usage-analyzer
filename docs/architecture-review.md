# CCWAP Frontend Architecture Review

**Version:** 1.0
**Date:** 2026-02-05
**Author:** Senior Solutions Architect (Claude Opus 4.6)
**Status:** Proposed

---

## 1. Executive Summary

CCWAP Frontend is a local-first web dashboard that extends the existing CCWAP CLI tool with an interactive 8-page React SPA served by a FastAPI backend. The architecture is a monolith-in-a-process: a single `ccwap serve` command starts a FastAPI server that serves pre-aggregated REST endpoints, a WebSocket live monitoring channel, and the production React build as static files -- all from one uvicorn process reading from the existing SQLite database. This is the proven pattern used by Jupyter, MLflow, Grafana, and similar developer tools.

The architecture prioritizes three principles: (1) zero-configuration deployment (one command, one process, no Docker, no cloud), (2) data accuracy parity with the existing CLI (every number in the dashboard must match the CLI output for the same query), and (3) performance through pre-aggregation (the backend does all computation; the frontend renders pre-computed results).

The highest-risk component is the Session Timeline Scrubber -- a fully custom horizontally-scrollable virtualized timeline with synchronized SVG overlay. No off-the-shelf solution exists. The highest-priority prerequisite is populating the `daily_summaries` table, without which the dashboard, trend charts, and cost analysis pages have no performant data source. Both of these must be addressed in the earliest implementation phases.

---

## 2. Requirements Analysis

### 2.1 Functional Requirements (Prioritized -- MoSCoW)

**Must-Have (MVP)**

| ID | Requirement | Notes |
|----|-------------|-------|
| F-01 | Dashboard page with vitals strip, top-10 projects, 30-day cost chart, activity feed | Landing page; zero-click answers |
| F-02 | Global date range picker with presets and custom range | Filters all pages; URL-persisted |
| F-03 | Projects page with 30+ metrics, sortable columns, expandable rows, server-side pagination | Core analytics table |
| F-04 | Session Detail with Timeline Scrubber replay | Flagship feature; highest competitive differentiator |
| F-05 | Cost Analysis page (token type, model, trend, forecast, cache savings) | Core cost visibility |
| F-06 | Productivity page (LOC, languages, tools, errors, file hotspots) | Core productivity visibility |
| F-07 | Deep Analytics page (thinking, truncation, sidechains, cache tiers, branches, versions, skills) | Power user analytics |
| F-08 | Experiments page (tag CRUD, session assignment, side-by-side comparison) | Workflow optimization feature |
| F-09 | Live Monitor via WebSocket (cost ticker, token accumulator, burn rate, sparkline) | Real-time differentiator |
| F-10 | Settings page (pricing editor, display prefs, ETL status, rebuild trigger) | Configuration management |
| F-11 | Export system (CSV, JSON on every page; PNG for charts) | Data portability |
| F-12 | Dark mode default with light mode toggle | Developer-tool aesthetic |
| F-13 | `ccwap serve` CLI command integrating with existing CLI | Single entry point |

**Should-Have**

| ID | Requirement | Notes |
|----|-------------|-------|
| F-14 | Drill-down navigation with prefetch on hover | Performance optimization |
| F-15 | Chart auto-granularity (daily/weekly/monthly) | Large date range handling |
| F-16 | Virtual scrolling for 200+ turn sessions | Performance for large sessions |
| F-17 | Column preference persistence in localStorage | UX convenience |

**Could-Have**

| ID | Requirement | Notes |
|----|-------------|-------|
| F-18 | Multi-session switcher in Live Monitor | Deferred per requirements |
| F-19 | Trend chart with tag annotation markers | Visual experiment timeline |

**Won't-Have (Explicit)**

| ID | Requirement | Notes |
|----|-------------|-------|
| F-20 | Multi-user, auth, team features | Out of scope |
| F-21 | Cloud/SaaS deployment | Out of scope |
| F-22 | Mobile responsive design | Desktop-only |
| F-23 | License key validation | Out of scope for v1 |

### 2.2 Non-Functional Requirements

| Category | Requirement | Threshold |
|----------|-------------|-----------|
| Performance | Dashboard initial load | < 1 second (warm SQLite) |
| Performance | SPA page navigation | < 300ms |
| Performance | API response time (aggregated) | < 200ms |
| Performance | API response time (session replay) | < 500ms for < 200 turns |
| Performance | WebSocket update latency | < 2 seconds end-to-end |
| Performance | Initial SPA bundle | < 500KB gzipped |
| Performance | Browser memory | < 100MB typical usage |
| Security | Scope | Localhost only, no auth, no telemetry |
| Reliability | Recovery | User restarts server; frontend auto-reconnects |
| Scalability | Design target | 10x current (1500 sessions, 50K turns) |
| Compatibility | Browser | Chromium-based (Chrome, Edge) |
| Compatibility | OS | Windows, macOS, Linux |

### 2.3 Constraints and Assumptions

**Hard Constraints**

1. **Zero-dependency for end users** -- No Node.js required at runtime. React build is pre-compiled and bundled into the Python package.
2. **Existing schema is immutable for reads** -- The 7-table SQLite schema is fixed. New tables or columns may be added, but existing columns must not be altered (CLI compatibility).
3. **Single-process deployment** -- One `ccwap serve` command starts everything. No separate frontend server, no Docker, no process manager.
4. **Python 3.10+ minimum** -- Matches existing CCWAP CLI requirement.
5. **Pricing accuracy** -- All cost calculations must use per-model, per-token-type pricing. Never flat-rate. Must match CLI output.

**Assumptions**

1. `daily_summaries` table will be populated by an updated ETL pipeline BEFORE frontend development begins.
2. Users have a Chromium-based browser.
3. SQLite WAL mode provides sufficient concurrency for simultaneous ETL writes and server reads.
4. Dataset sizes will stay within the 10x design target (1500 sessions, 50K turns, 10B tokens).
5. The pre-built React SPA can be bundled within a 5MB Python package size budget.

### 2.4 Gaps and Clarifications Needed

| Gap | Impact | Assumption Made |
|-----|--------|-----------------|
| `daily_summaries` is unpopulated | Critical -- blocks all trend/chart endpoints | ETL update is a Phase 0 prerequisite; architecture proceeds assuming it will exist |
| No specification for per-project daily summaries | Medium -- project-level trend charts must query `turns` directly | Backend will compute project-level trends via filtered aggregation on `turns` table; if performance is insufficient, a `project_daily_summaries` table will be added |
| Session replay `user_prompt_preview` not stored in DB | Medium -- turn detail panel needs user prompt text | Add `user_prompt_preview` column to `turns` table during ETL, or extract from JSONL at query time |
| Export server-side vs client-side ambiguity | Low -- requirements say client-side for CSV/JSON but API contract shows `/api/export` | CSV/JSON export will be client-side (from TanStack Query cache). The `/api/export` endpoint will exist as a fallback for server-rendered exports |
| Recharts 3.x + recharts-to-png compatibility | Medium -- PNG export may not work | Plan SVG serialization as primary PNG strategy; test recharts-to-png as stretch |
| `loc_delivered` computation for daily_summaries | Low -- needs clarification on calculation | Use `SUM(lines_added) - SUM(lines_deleted)` per the appendix specification |

---

## 3. Architecture Decisions

### ADR-001: Monolith Backend Serving API + Static SPA

- **Context**: The product needs a web dashboard. Deployment must be a single command (`ccwap serve`). End users should not need Node.js, Docker, or any infrastructure beyond Python.
- **Decision**: FastAPI serves both REST API routes (under `/api/`) and the production React build as static files (at `/`). A single uvicorn process handles everything.
- **Status**: Accepted
- **Consequences**:
  - Positive: One-command deployment. No CORS issues in production. Simple packaging (Python wheel includes pre-built JS).
  - Positive: Matches the proven pattern of Jupyter, MLflow, Grafana.
  - Negative: Development requires running two processes (Vite dev server + FastAPI) with proxy configuration.
  - Negative: Frontend build step adds complexity to the release pipeline.
- **Alternatives Considered**:
  - *Separate frontend server (nginx/caddy)*: Rejected -- adds deployment complexity for a localhost tool.
  - *Server-side rendering (Next.js)*: Rejected -- requires Node.js at runtime, violating the zero-Node constraint.
  - *Flask instead of FastAPI*: Rejected -- no native async, no native WebSocket, no Pydantic integration, no auto-generated OpenAPI docs.

### ADR-002: Fat Pre-Aggregated API Endpoints

- **Context**: The frontend needs data for 8 pages with dozens of charts and tables. Raw data queries to SQLite could be slow, and aggregation logic in JavaScript would duplicate Python business logic.
- **Decision**: Every API endpoint returns pre-aggregated, ready-to-render data. The backend performs all SQL aggregation, cost calculation, and metric derivation. The frontend does zero computation beyond formatting.
- **Status**: Accepted
- **Consequences**:
  - Positive: Single source of truth for business logic (Python). Frontend is a pure rendering layer.
  - Positive: API responses are small (pre-aggregated), reducing transfer overhead.
  - Positive: Easier to maintain data accuracy parity with CLI output.
  - Negative: More backend code. Each page needs dedicated endpoint(s) and query module(s).
  - Negative: Less flexibility for ad-hoc frontend explorations.
- **Alternatives Considered**:
  - *GraphQL*: Rejected -- over-engineering for a single-client application with well-defined pages.
  - *Generic query endpoint*: Rejected -- SQL injection risk, impossible to optimize, business logic leaks to frontend.
  - *Thin API + frontend aggregation*: Rejected -- duplicates pricing logic in TypeScript, harder to guarantee CLI parity.

### ADR-003: TanStack Query for All Server State Management

- **Context**: The SPA needs to fetch, cache, invalidate, and refetch data from ~30 API endpoints across 8 pages. Date range changes must trigger coordinated cache invalidation.
- **Decision**: TanStack Query (React Query) v5 manages all server state. No Redux, no Zustand, no global state store for API data. React Context is used ONLY for client-side UI state (theme, date range, sidebar collapse).
- **Status**: Accepted
- **Consequences**:
  - Positive: Built-in caching, stale-while-revalidate, loading/error states, background refetching.
  - Positive: Query key factory pattern enables clean cache invalidation when date range changes.
  - Positive: `prefetchQuery` on hover enables instant drill-down navigation.
  - Negative: Learning curve for developers unfamiliar with TanStack Query's cache model.
  - Negative: Debugging cache invalidation issues requires understanding query key structure.
- **Alternatives Considered**:
  - *Redux Toolkit Query*: Rejected -- heavier, more boilerplate, team not using Redux elsewhere.
  - *SWR*: Rejected -- less feature-rich than TanStack Query (no mutations, no devtools, weaker cache control).
  - *Plain fetch + useState*: Rejected -- massive boilerplate for loading/error/caching across 30 endpoints.

### ADR-004: Separate Queries for Turns and Tool Calls (Cross-Product JOIN Mitigation)

- **Context**: The existing codebase has a documented bug where JOINing sessions + turns + tool_calls produces inflated aggregates (N turns * M tool_calls per session). This is explicitly noted in the project memory and has been fixed in several CLI reports by using separate queries.
- **Decision**: ALL backend query modules MUST use the two-query pattern: (1) query sessions/turns for token/cost aggregates, (2) query tool_calls separately for LOC/error/tool aggregates. Results are merged in Python. No query may JOIN all three tables for aggregation.
- **Status**: Accepted (mandatory)
- **Consequences**:
  - Positive: Eliminates the cross-product inflation bug systematically.
  - Positive: Each query is simpler and more optimizable.
  - Negative: Slightly more Python code to merge results.
  - Negative: Two database round-trips instead of one (negligible for localhost SQLite).
- **Alternatives Considered**:
  - *CTEs with pre-aggregated subqueries*: Viable but fragile -- easy to accidentally re-introduce the bug in complex queries. SQLite also materializes CTEs, reducing optimizer flexibility.
  - *Denormalized views*: Rejected -- adds schema maintenance burden, same root cause risk.

### ADR-005: aiosqlite Singleton Connection with FastAPI Lifespan

- **Context**: FastAPI is async, but SQLite is inherently single-threaded. We need non-blocking database access without connection pool overhead for a file-based database.
- **Decision**: A single `aiosqlite` connection is created in FastAPI's `lifespan` async context manager, stored in `app.state.db`, and shared across all request handlers. WAL mode PRAGMAs are set at connection init.
- **Status**: Accepted
- **Consequences**:
  - Positive: Zero connection overhead per request. WAL mode allows concurrent reads.
  - Positive: Consistent PRAGMA configuration (journal_mode, synchronous, cache_size, mmap_size, busy_timeout).
  - Positive: Clean shutdown via lifespan exit.
  - Negative: Single-writer bottleneck (acceptable for read-heavy workload; only Settings writes through the API).
  - Negative: If the connection fails, all requests fail until server restart.
- **Alternatives Considered**:
  - *Connection per request*: Rejected -- unnecessary overhead, PRAGMA setup on every request.
  - *Connection pool (e.g., databases library)*: Rejected -- over-engineering for SQLite. Connection pools are for network databases.
  - *Synchronous sqlite3 with run_in_executor*: Viable but aiosqlite is the established pattern for FastAPI + SQLite.

### ADR-006: Session Timeline Scrubber as Custom TanStack Virtual Component

- **Context**: The Timeline Scrubber is the flagship feature -- a horizontally-scrollable strip where each turn is a block (width proportional to tokens, color intensity proportional to cost) with a synchronized cumulative cost SVG polyline overlay. No off-the-shelf component exists.
- **Decision**: Build as a custom React component using TanStack Virtual for horizontal virtualization. Turn blocks are rendered in a virtualized horizontal container. The cumulative cost line is an absolutely-positioned SVG polyline that scroll-synchronizes via an `onScroll` handler updating `translateX`. Turn detail is shown in a side panel (not inline expansion) to avoid TanStack Virtual bug #656.
- **Status**: Accepted (Spike recommended for scroll sync)
- **Consequences**:
  - Positive: Handles 500+ turn sessions performantly via virtualization.
  - Positive: Side panel avoids the known scroll-to-top bug with expandable rows.
  - Positive: Full control over visual design (block width/color mapping).
  - Negative: Highest implementation risk. Scroll synchronization between HTML blocks and SVG overlay requires careful engineering.
  - Negative: Cumulative cost line requires loading all turns (cannot virtualize the data, only the rendering).
  - Negative: Touch/trackpad horizontal scrolling behavior varies across OS/browser.
- **Alternatives Considered**:
  - *Canvas rendering*: Rejected -- harder to make interactive (click handlers, tooltips), worse accessibility.
  - *D3.js timeline*: Rejected -- heavy dependency, React integration is awkward, not worth the complexity.
  - *Simple vertical list of turns*: Rejected -- does not meet the flagship feature specification.
  - *Inline expandable rows*: Rejected -- triggers TanStack Virtual bug #656 (scroll-to-top on expand).

### ADR-007: WebSocket Live Monitoring via Existing FileWatcher

- **Context**: The Live Monitor page needs real-time updates when new JSONL data is written by Claude Code. The existing `FileWatcher` class in `ccwap/etl/watcher.py` already implements cross-platform polling-based file change detection.
- **Decision**: Wrap the existing `FileWatcher` in `asyncio.to_thread()` to run its polling loop in a background thread. File change events are passed to the main async event loop via an `asyncio.Queue`. A `ConnectionManager` class manages WebSocket connections and broadcasts updates from the queue to all connected clients.
- **Status**: Accepted
- **Consequences**:
  - Positive: Reuses existing, tested file watching code. No new dependency (no watchdog).
  - Positive: Cross-platform compatibility maintained (polling works on Windows, macOS, Linux).
  - Negative: Polling-based -- 2-5 second latency is inherent. The 2-second requirement is achievable with a 2-second poll interval.
  - Negative: Thread-to-async bridge adds complexity (must not share sqlite3 connections across threads).
- **Alternatives Considered**:
  - *watchdog library*: Rejected -- adds a dependency, and the existing FileWatcher already handles all platforms.
  - *inotify (Linux only)*: Rejected -- not cross-platform.
  - *Direct JSONL parsing in async loop*: Rejected -- duplicates existing ETL logic.

### ADR-008: Tailwind v4 with shadcn/ui for Component Library

- **Context**: The UI needs a consistent design system with dark/light mode support, accessible components, and developer-tool aesthetic. The team needs to move fast.
- **Decision**: Use Tailwind CSS v4 (CSS-first configuration with `@theme` directive and OKLCH colors) combined with shadcn/ui components (Radix UI primitives + Tailwind styling). Chart components use shadcn/ui's built-in Chart wrapper around Recharts 3, which provides CSS variable-based theming that auto-adapts to dark/light mode.
- **Status**: Accepted
- **Consequences**:
  - Positive: shadcn/ui is copy-paste, not a dependency -- full control over component code.
  - Positive: Radix UI provides accessibility (ARIA) out of the box.
  - Positive: CSS variable theming means charts adapt to dark/light mode without code changes.
  - Positive: Tailwind v4 eliminates `tailwind.config.js` -- all config is in CSS.
  - Negative: Tailwind v4 is a major version upgrade from v3 (specified in requirements). CSS-first config syntax is different. Some shadcn/ui documentation may still reference v3.
  - Negative: OKLCH colors may require adjustment for WCAG contrast compliance.
- **Alternatives Considered**:
  - *Tailwind v3 (as specified)*: Rejected in favor of v4 because v4 is current stable, avoids using an already-outdated major version, and the CSS-first approach is cleaner.
  - *MUI (Material UI)*: Rejected -- heavy bundle size, opinionated design that doesn't match the developer-tool aesthetic.
  - *Ant Design*: Rejected -- heavy, enterprise-oriented, theming is complex.

### ADR-009: Client-Side Export with Server Fallback

- **Context**: Every page needs CSV, JSON, and PNG export. The requirements specify client-side generation for CSV/JSON (no server round-trip), but also define a `/api/export` endpoint.
- **Decision**: CSV and JSON exports are generated client-side from TanStack Query cache data using Blob URLs. PNG export uses SVG serialization of Recharts chart elements (not recharts-to-png, which is unverified with Recharts 3.x). The `/api/export/:page` server endpoint exists as a fallback for cases where client-side data is insufficient (e.g., exporting all pages of a paginated table).
- **Status**: Accepted
- **Consequences**:
  - Positive: Instant client-side export -- no server round-trip.
  - Positive: SVG serialization is a reliable PNG strategy (controlled rendering, 2x resolution via viewBox scaling).
  - Positive: Server fallback handles edge cases (full dataset export beyond current page).
  - Negative: Client-side CSV must include BOM prefix for Windows Excel compatibility.
  - Negative: SVG-to-PNG requires converting SVG to canvas then to PNG blob -- more code than recharts-to-png would be.
- **Alternatives Considered**:
  - *recharts-to-png*: Not rejected, but deprioritized. Compatibility with Recharts 3.x is unverified. If it works, it can replace SVG serialization as a simpler approach. Test during implementation.
  - *Server-only export*: Rejected -- adds latency, and the frontend already has the data in cache.
  - *html2canvas*: Rejected -- captures CSS-rendered HTML which can have visual artifacts (especially with dark mode, scrolled containers).

### ADR-010: React Router v7 with URL-Persisted Date Range

- **Context**: The global date range must persist across page navigation and be bookmark-shareable. Page-level state (sort order, search term, active tab) should also survive browser refresh.
- **Decision**: React Router v7 manages client-side routing. The global date range is stored as URL search parameters (`?from=YYYY-MM-DD&to=YYYY-MM-DD` or `?preset=last-30-days`). A `useDateRange` hook reads from URL params, provides setter functions, and is consumed by all API query hooks to include date range in query keys.
- **Status**: Accepted
- **Consequences**:
  - Positive: URL is the single source of truth for date range. Bookmarks and sharing work.
  - Positive: Date range in query keys means TanStack Query cache invalidates automatically when range changes.
  - Positive: Browser back/forward navigation restores previous date range.
  - Negative: URL can become long with many parameters. Mitigated by using presets where possible.
  - Negative: React Router v7 has different API from v6 (which the requirements specified). The migration is small since v7 is an evolution of v6.
- **Alternatives Considered**:
  - *React Context only*: Rejected -- loses date range on page refresh, not bookmark-shareable.
  - *localStorage only*: Rejected -- not reflected in URL, not shareable, back button doesn't work.
  - *React Router v6*: Rejected -- v7 is current stable; using v6 would mean starting with an already-outdated version.

### ADR-011: Vite 7 Build with Route-Based Code Splitting

- **Context**: The SPA bundle must be under 500KB gzipped. The application has 8+ pages with heavy charting dependencies.
- **Decision**: Vite 7 is the build tool. Each page component uses `React.lazy()` for route-based code splitting. Manual chunk configuration separates vendor libraries: `react-vendor` (React, React DOM, React Router), `chart-vendor` (Recharts), `ui-vendor` (Radix UI primitives), `query-vendor` (TanStack Query). Target: ~250-350KB gzipped total across all chunks.
- **Status**: Accepted
- **Consequences**:
  - Positive: Initial page load only downloads the chunk for the landing page (~100-150KB).
  - Positive: Subsequent page navigations load small incremental chunks.
  - Positive: Vendor chunks are long-term cacheable (they change rarely).
  - Negative: Slightly more complex build configuration.
  - Negative: Code splitting introduces loading states during navigation (mitigated by Suspense boundaries with skeleton UI).
- **Alternatives Considered**:
  - *No code splitting*: Rejected -- would likely exceed the 500KB budget with all chart dependencies.
  - *Webpack*: Rejected -- Vite is faster for development (HMR) and simpler to configure.

---

## 4. Technical Architecture Overview

### 4.1 System Decomposition

```
+------------------------------------------------------------------+
|                    User's Machine (localhost)                      |
|                                                                    |
|  +------------------+       +--------------------------------+    |
|  | Claude Code      |       | Browser (Chromium)             |    |
|  | (writes JSONL)   |       |                                |    |
|  +--------+---------+       |  +---------------------------+ |    |
|           |                 |  | React SPA                  | |    |
|           | filesystem      |  |                            | |    |
|           v                 |  |  [TanStack Query Cache]   | |    |
|  +------------------+       |  |  [React Router]           | |    |
|  | JSONL Files      |       |  |  [Recharts Charts]        | |    |
|  | ~/.claude/       |       |  |  [WebSocket Client]       | |    |
|  | projects/        |       |  |  [localStorage Prefs]     | |    |
|  +--------+---------+       |  +-------------+-------------+ |    |
|           |                 |                |                |    |
|           |                 +----------------+----------------+    |
|           |                                  |                     |
|           |              HTTP REST (/api/*), |                     |
|           |              WebSocket (/ws/*),  |                     |
|           |              Static Files (/)    |                     |
|           |                                  |                     |
|  +--------+---------+      +----------------+----------------+    |
|  |                  |      |                                 |    |
|  |  FileWatcher     +----->|  FastAPI Backend (uvicorn)      |    |
|  |  (bg thread)     | Queue|                                 |    |
|  |                  |      |  +------------+  +-----------+  |    |
|  +------------------+      |  | API Router |  | WS Manager|  |    |
|                            |  | /api/*     |  | /ws/live  |  |    |
|                            |  +------+-----+  +-----+-----+  |    |
|                            |         |               |        |    |
|                            |  +------+---------------+-----+  |    |
|                            |  |   Query Modules             |  |    |
|                            |  |   (SQL + Python aggregation)|  |    |
|                            |  +------+----------------------+  |    |
|                            |         |                        |    |
|                            +---------+------------------------+    |
|                                      |                             |
|                            +---------v----------+                  |
|                            | SQLite Database     |                  |
|                            | ~/.ccwap/           |                  |
|                            | analytics.db (WAL)  |                  |
|                            +----+----------------+                  |
|                                 |                                   |
|                            +----v---------+                         |
|                            | config.json  |                         |
|                            | ~/.ccwap/    |                         |
|                            +--------------+                         |
+------------------------------------------------------------------+
```

**Component Responsibilities:**

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| React SPA | Rendering, routing, client state, chart display, export generation | React 19, React Router 7, TanStack Query 5, Recharts 3, shadcn/ui, Tailwind v4 |
| FastAPI Backend | REST API, WebSocket server, static file serving, SQL queries, business logic | FastAPI, Pydantic v2, aiosqlite |
| Query Modules | SQL queries with cross-product JOIN prevention, result merging | Pure Python + SQL |
| ConnectionManager | WebSocket lifecycle, client tracking, broadcast | FastAPI WebSocket, asyncio |
| FileWatcher (bg thread) | JSONL file change detection, incremental ETL | Existing `ccwap.etl.watcher.FileWatcher`, asyncio.to_thread |
| SQLite Database | Persistent storage, WAL concurrent access | SQLite 3 (aiosqlite wrapper) |
| Config System | Pricing tables, server settings, display preferences | JSON file, existing `ccwap.config.loader` |

### 4.2 Data Architecture

#### 4.2.1 Storage

The system uses the existing 7-table SQLite schema without modification. The only prerequisite is populating `daily_summaries`.

**Read Paths by Page:**

| Page | Primary Table(s) | Query Strategy |
|------|-------------------|----------------|
| Dashboard vitals | `turns`, `tool_calls` (today only) | Direct aggregation on today's data (small dataset) |
| Dashboard cost chart | `daily_summaries` | Date range filter on pre-aggregated table |
| Dashboard activity feed | `sessions` | ORDER BY first_timestamp DESC LIMIT 10 |
| Dashboard top projects | `sessions` + `turns` | Aggregation with date filter |
| Projects | `sessions` + `turns` (query 1), `tool_calls` (query 2) | Two-query pattern, merged in Python |
| Session Replay | `turns` (query 1), `tool_calls` (query 2) | Two-query pattern for single session |
| Cost Analysis | `daily_summaries` (trends), `turns` (breakdowns) | Summaries for trends, turns grouped by model for breakdowns |
| Productivity | `tool_calls` + `sessions` | Direct aggregation on tool_calls |
| Deep Analytics | `turns` (various filters) | Specialized queries per panel |
| Experiments | `experiment_tags` + `sessions` + `turns`/`tool_calls` | Tag lookup then metric aggregation |
| Live Monitor | N/A (WebSocket) | Real-time from FileWatcher |
| Settings | `etl_state`, config.json | Direct reads |

#### 4.2.2 Data Flow: API Request

```
Browser                    FastAPI                     SQLite
  |                          |                           |
  |  GET /api/projects       |                           |
  |  ?from=...&to=...        |                           |
  |  &sort=cost&page=1       |                           |
  |------------------------->|                           |
  |                          |  Validate params          |
  |                          |  (Pydantic Query model)   |
  |                          |                           |
  |                          |  Query 1: sessions+turns  |
  |                          |-------------------------->|
  |                          |  (token/cost aggregates)  |
  |                          |<--------------------------|
  |                          |                           |
  |                          |  Query 2: tool_calls      |
  |                          |-------------------------->|
  |                          |  (LOC/error aggregates)   |
  |                          |<--------------------------|
  |                          |                           |
  |                          |  Merge results in Python  |
  |                          |  Calculate derived metrics|
  |                          |  Build Pydantic response  |
  |                          |                           |
  |  200 OK (JSON)           |                           |
  |<-------------------------|                           |
```

#### 4.2.3 Data Flow: WebSocket Live Monitor

```
Claude Code        FileWatcher         asyncio.Queue     ConnectionManager    Browser
    |              (bg thread)              |                   |                |
    |  writes      |                        |                   |                |
    |  JSONL       |                        |                   |                |
    |              |  poll detects          |                   |                |
    |              |  file change           |                   |                |
    |              |                        |                   |                |
    |              |  parse new entries     |                   |                |
    |              |  compute incremental   |                   |                |
    |              |  cost                  |                   |                |
    |              |                        |                   |                |
    |              |  queue.put(event)      |                   |                |
    |              |----------------------->|                   |                |
    |              |                        |                   |                |
    |              |                        |  broadcast_loop   |                |
    |              |                        |  queue.get()      |                |
    |              |                        |------------------>|                |
    |              |                        |                   |                |
    |              |                        |                   |  ws.send_json  |
    |              |                        |                   |--------------->|
    |              |                        |                   |                |
    |              |                        |                   |                |  render
    |              |                        |                   |                |  update
```

#### 4.2.4 Data Flow: Global Date Range Change

```
User clicks         useDateRange        URL Params         TanStack Query        API
"Last 7 Days"       hook                                   Cache
    |                   |                   |                   |                |
    |  select preset    |                   |                   |                |
    |------------------>|                   |                   |                |
    |                   |  setSearchParams  |                   |                |
    |                   |------------------>|                   |                |
    |                   |                   |                   |                |
    |                   |  URL changes      |                   |                |
    |                   |  triggers re-render|                  |                |
    |                   |                   |                   |                |
    |                   |  new from/to      |                   |                |
    |                   |  values flow to   |                   |                |
    |                   |  useQuery hooks   |                   |                |
    |                   |                   |                   |                |
    |                   |                   |  query keys now   |                |
    |                   |                   |  include new range|                |
    |                   |                   |                   |                |
    |                   |                   |  cache miss       |                |
    |                   |                   |  (new key)        |                |
    |                   |                   |------------------>|  GET /api/...  |
    |                   |                   |                   |  ?from=&to=    |
    |                   |                   |                   |--------------->|
    |                   |                   |                   |                |
    |                   |                   |  cache populated  |                |
    |                   |                   |<------------------|  200 OK        |
    |                   |                   |                   |<---------------|
    |  re-render with   |                   |                   |                |
    |  new data         |                   |                   |                |
    |<------------------|                   |                   |                |
```

### 4.3 Integration Architecture

#### 4.3.1 REST API Organization

All API routes are organized under `/api/` prefix and grouped by domain:

```
/api/
  /health                          GET    -- Health check + uptime
  /dashboard                       GET    -- Dashboard page data (vitals, projects, chart, feed)

  /projects                        GET    -- Paginated project list with metrics
  /projects/:path                  GET    -- Single project detail

  /sessions                        GET    -- Paginated session list
  /sessions/:id                    GET    -- Session summary
  /sessions/:id/replay             GET    -- Full session replay with all turns

  /cost/summary                    GET    -- Cost summary cards
  /cost/by-token-type              GET    -- Token type breakdown
  /cost/by-model                   GET    -- Model cost breakdown
  /cost/trend                      GET    -- Cost time series
  /cost/by-project                 GET    -- Top projects by cost
  /cost/forecast                   GET    -- Spend forecast

  /productivity/summary            GET    -- Efficiency cards
  /productivity/loc-trend          GET    -- LOC time series
  /productivity/languages          GET    -- Language distribution
  /productivity/tools              GET    -- Tool usage table
  /productivity/errors             GET    -- Error analysis
  /productivity/files              GET    -- File hotspots

  /analytics/thinking              GET    -- Extended thinking analysis
  /analytics/truncation            GET    -- Truncation/stop-reason analysis
  /analytics/sidechains            GET    -- Sidechain metrics
  /analytics/cache-tiers           GET    -- Ephemeral cache tier breakdown
  /analytics/branches              GET    -- Git branch metrics
  /analytics/versions              GET    -- CC version comparison
  /analytics/skills                GET    -- Skill/agent usage

  /experiments/tags                GET    -- List all tags with counts
  /experiments/tags                POST   -- Create a tag
  /experiments/tags/:name          DELETE -- Delete a tag
  /experiments/assign              POST   -- Assign tag to sessions
  /experiments/compare             GET    -- Compare two tags

  /settings/pricing                GET    -- Current pricing table
  /settings/pricing                PUT    -- Update pricing table
  /settings/etl-status             GET    -- ETL state info
  /settings/rebuild                POST   -- Trigger full ETL rebuild
  /settings/db-stats               GET    -- Database statistics

  /export/:page                    GET    -- Server-side export fallback

/ws/
  /ws/live                                -- WebSocket for live monitoring
```

**Common Query Parameters (all GET endpoints):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `from` | date (YYYY-MM-DD) | 30 days ago | Start of date range |
| `to` | date (YYYY-MM-DD) | today | End of date range |

**Pagination Parameters (list endpoints):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `limit` | int | 50 | Items per page (max 200) |
| `sort` | string | varies | Sort field |
| `order` | asc/desc | desc | Sort direction |

#### 4.3.2 WebSocket Protocol

The WebSocket at `/ws/live` follows a simple subscribe-broadcast pattern:

1. Client connects and sends `{"type": "subscribe"}`
2. Server acknowledges with current state or `{"type": "no_active_session"}`
3. Server sends `{"type": "heartbeat"}` every 30 seconds
4. On file change detection, server sends `{"type": "session_update", ...}` with cumulative and incremental data
5. Client sends `{"type": "ping"}` to keep connection alive
6. On disconnect, client reconnects with exponential backoff (1s, 2s, 4s, 8s, 16s, 30s cap)

### 4.4 Security Architecture

Security is minimal by design -- this is a localhost-only, single-user tool.

| Concern | Approach |
|---------|----------|
| Authentication | None. Bind to 127.0.0.1 only (default). |
| Authorization | None. All data is the user's own. |
| CORS | Not needed in production (same origin). Dev proxy eliminates it in development. |
| Input validation | Pydantic v2 models validate all request parameters. |
| SQL injection | Parameterized queries only. No string interpolation in SQL. |
| Data at rest | SQLite on local filesystem. No encryption (user's responsibility). |
| Data in transit | Localhost only. No HTTPS needed. |
| Network exposure | `--host 0.0.0.0` is an advanced flag with warning in documentation. Default is 127.0.0.1. |

### 4.5 Infrastructure and Deployment

#### 4.5.1 Production Deployment (End User)

```
pip install ccwap          # Installs Python package with bundled React SPA
ccwap serve                # Starts uvicorn + opens browser
```

The `ccwap serve` command:
1. Runs incremental ETL (processes new JSONL files)
2. Starts FastAPI/uvicorn on configured port (default 8080)
3. Opens default browser to `http://localhost:8080`
4. Prints server URL and Ctrl+C instruction

**Package Structure:**

```
ccwap/                     # Python package
  server/                  # FastAPI backend
  static/                  # Pre-built React SPA (copied from frontend/dist at build time)
  ...                      # Existing CLI modules
```

#### 4.5.2 Development Environment

Two processes during development:

| Process | Command | Port | Purpose |
|---------|---------|------|---------|
| FastAPI | `uvicorn ccwap.server.app:create_app --factory --reload --port 8080` | 8080 | Backend API + WebSocket |
| Vite | `cd frontend && npm run dev` | 5173 | React dev server with HMR |

Vite dev server proxies `/api/*` and `/ws/*` to FastAPI at localhost:8080:

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true
      }
    }
  }
})
```

#### 4.5.3 Build Pipeline

```
1. cd frontend && npm run build     # Produces frontend/dist/
2. cp -r frontend/dist/* ccwap/static/   # Bundle into Python package
3. python -m build                  # Build wheel/sdist
4. twine upload dist/*              # Publish to PyPI
```

No Node.js is required on the end user's machine.

### 4.6 Observability

| Aspect | Implementation |
|--------|---------------|
| Health check | `GET /api/health` returns `{"status": "ok", "uptime_seconds": N, "database": "ok"/"error", "version": "X.Y.Z"}` |
| API logging | FastAPI middleware logs request method, path, status code, duration to stderr |
| Error handling | Global exception handler returns structured JSON `{"error": "message", "detail": "..."}`, never stack traces |
| WebSocket status | Connection status indicator in UI (green/yellow/red) |
| Performance | API response time logged per request; slow queries (>200ms) logged as warnings |
| Bundle size | `vite-bundle-visualizer` in development; CI check that total gzipped < 500KB |

---

## 5. Technology Stack Recommendations

### 5.1 Backend

| Technology | Version | Rationale |
|------------|---------|-----------|
| Python | 3.10+ | Matches existing CCWAP CLI requirement |
| FastAPI | 0.126+ (latest) | Async REST + native WebSocket + Pydantic + OpenAPI auto-docs |
| uvicorn | 0.40+ (latest) | Production ASGI server, reload mode for development |
| Pydantic | v2.7+ | Request/response validation, serialization, OpenAPI schema generation |
| aiosqlite | 0.22+ | Async SQLite wrapper (note: 0.22.0 has breaking changes in connection API) |

**New Python Dependencies:**

```
fastapi>=0.126
uvicorn[standard]>=0.40
pydantic>=2.7
aiosqlite>=0.22
```

These are the ONLY new runtime dependencies. The existing zero-dependency CLI continues to work independently.

### 5.2 Frontend

| Technology | Version | Rationale |
|------------|---------|-----------|
| React | 19 | Current stable. Concurrent features, improved Suspense. |
| TypeScript | 5.x | Type safety, API contract enforcement |
| Vite | 7 | Current stable. Fast HMR, ESM-native, excellent build optimization. |
| React Router | 7 | Current stable. URL-based state management. |
| TanStack Query | 5 | Server state cache, loading/error states, background refetch |
| Recharts | 3 | React-native composable charts. shadcn/ui integration. |
| Tailwind CSS | 4 | Current stable. CSS-first config, OKLCH colors, dark mode. |
| shadcn/ui | latest | Copy-paste accessible components. Radix UI + Tailwind. |
| TanStack Virtual | 3 | Virtualized rendering for Timeline Scrubber and long lists |
| react-day-picker | latest | Date range picker (used by shadcn/ui DatePicker) |

**NOT included (and why):**

| Technology | Reason for Exclusion |
|------------|---------------------|
| Redux/Zustand | TanStack Query handles server state; React Context handles UI state. No global state store needed. |
| Axios | Native fetch is sufficient. TanStack Query provides the abstraction layer. |
| D3.js | Over-powered for this use case. Recharts handles all chart types needed. |
| recharts-to-png | Unverified with Recharts 3.x. SVG serialization is the primary PNG strategy. |
| Storybook | Over-engineering for a single-developer project. |

---

## 6. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | `daily_summaries` not populated before frontend development | High (known gap) | Critical | **Prerequisite gate**: ETL update must merge to main before any frontend work begins. Add integration test that verifies `daily_summaries` has data. |
| R2 | Timeline Scrubber scroll sync between HTML and SVG breaks | Medium | High | Spike/POC in Phase 1. If sync proves unreliable, fall back to single-container approach where cost line is rendered as CSS-positioned divs within the same scroll container. |
| R3 | Cross-product JOIN bug re-introduced in new API queries | Medium | High | Mandatory code review checklist item. No PR may merge a query that JOINs sessions+turns+tool_calls for aggregation. Add a lint rule or test that scans SQL strings. |
| R4 | aiosqlite 0.22 breaking changes cause runtime errors | Low | High | Pin to specific version. Test all PRAGMA setup in integration tests. |
| R5 | Recharts 3 + shadcn/ui Chart wrapper has undocumented API changes | Medium | Medium | Test early in Phase 2 (chart foundation). If wrapper is broken, fall back to direct Recharts usage with manual CSS variable theming. |
| R6 | Tailwind v4 CSS-first config incompatible with some shadcn/ui components | Medium | Medium | Test during project scaffolding. shadcn/ui CLI generates Tailwind config -- verify it works with v4 syntax. Fall back to v3 if blocking. |
| R7 | WebSocket reliability on Windows (file polling latency) | Medium | Medium | Set poll interval to 2 seconds on Windows. Document that live monitor has 2-5 second latency. |
| R8 | React production bundle exceeds 500KB gzipped | Low | Medium | Monitor with vite-bundle-visualizer. Route-based splitting keeps initial load small. If exceeded, evaluate tree-shaking and dependency audit. |
| R9 | Session replay for 500+ turn sessions causes browser memory pressure | Low | Medium | TanStack Virtual renders only visible turns. Cumulative cost data is a flat array (small). Turn detail loaded on demand. |
| R10 | `user_prompt_preview` field missing from database | Medium | Low | Add to ETL extraction (store first 500 chars of user prompt). For existing data, show "Prompt not available" in turn detail. |

---

## 7. Implementation Guidance for Orchestrator

### 7.1 Recommended Phase Breakdown

#### Phase 0: Prerequisites (must complete before any frontend work)

**Goal**: Ensure data infrastructure is ready.

| Task | Description | Est. Effort |
|------|-------------|-------------|
| P0-1 | Update ETL to populate `daily_summaries` on every run (incremental and rebuild) | 4-6 hours |
| P0-2 | Add `user_prompt_preview` column to `turns` table (migration v2->v3) | 2-3 hours |
| P0-3 | Write integration tests verifying `daily_summaries` accuracy | 2-3 hours |
| P0-4 | Verify existing test suite still passes (231 tests) | 30 min |

**Deliverable**: Merged PR with ETL updates. `daily_summaries` table populated. All tests green.

#### Phase 1: Backend Foundation + Spike

**Goal**: FastAPI app scaffold, database layer, core API endpoints, Timeline Scrubber spike.

| Task | Description | Est. Effort |
|------|-------------|-------------|
| P1-1 | FastAPI app factory with lifespan, aiosqlite connection, PRAGMA setup | 3-4 hours |
| P1-2 | Pydantic models for common types (pagination, date range, error responses) | 2-3 hours |
| P1-3 | Query module for dashboard (dashboard_queries.py) | 3-4 hours |
| P1-4 | Query module for projects (project_queries.py) -- two-query pattern | 4-5 hours |
| P1-5 | Query module for sessions/replay (session_queries.py) -- two-query pattern | 4-5 hours |
| P1-6 | Route handlers for `/api/dashboard`, `/api/projects`, `/api/sessions` | 3-4 hours |
| P1-7 | `/api/health` endpoint | 30 min |
| P1-8 | Backend test infrastructure (conftest.py, test SQLite with deterministic data) | 3-4 hours |
| P1-9 | **SPIKE**: Timeline Scrubber scroll sync POC (HTML + SVG in shared scroll container) | 4-6 hours |
| P1-10 | Static file mounting for SPA serving | 1-2 hours |

**Deliverable**: Working `/api/dashboard`, `/api/projects`, `/api/sessions/:id/replay` endpoints with tests. Timeline Scrubber spike report.

#### Phase 2: Frontend Foundation

**Goal**: React app scaffold, routing, layout, theme, date picker, chart foundation.

| Task | Description | Est. Effort |
|------|-------------|-------------|
| P2-1 | Vite + React + TypeScript + Tailwind v4 + shadcn/ui scaffold | 2-3 hours |
| P2-2 | App.tsx: React Router setup, QueryClientProvider, ThemeProvider, Suspense boundaries | 2-3 hours |
| P2-3 | Layout components: Sidebar, TopBar, PageLayout | 3-4 hours |
| P2-4 | `useDateRange` hook (URL params, presets, custom range) | 3-4 hours |
| P2-5 | DateRangePicker component (shadcn/ui DatePicker + presets) | 3-4 hours |
| P2-6 | `useTheme` hook + ThemeToggle component | 1-2 hours |
| P2-7 | API client layer (`api/client.ts`, typed fetch wrapper) | 2-3 hours |
| P2-8 | Chart foundation: test shadcn/ui Chart wrapper + Recharts 3 + dark mode | 2-3 hours |
| P2-9 | Common components: MetricCard, EmptyState, LoadingState, ErrorState | 2-3 hours |
| P2-10 | Vite proxy configuration for development | 30 min |

**Deliverable**: Working SPA shell with sidebar navigation, date picker, theme toggle, and chart rendering verified.

#### Phase 3: Core Pages (Backend + Frontend in Parallel)

**Goal**: Dashboard, Projects, Session Detail -- the core drill-down flow.

| Task | Description | Est. Effort |
|------|-------------|-------------|
| P3-1 | Dashboard page: VitalsStrip, ProjectGrid, CostAreaChart, ActivityFeed | 6-8 hours |
| P3-2 | Projects page: DataTable, ColumnSelector, ExpandableRow, server-side sort/paginate | 8-10 hours |
| P3-3 | Session Detail: SessionHeader, SessionStats sidebar, TurnDetail panel | 4-6 hours |
| P3-4 | **Timeline Scrubber** (flagship): implement based on Phase 1 spike results | 10-14 hours |
| P3-5 | Drill-down navigation: Dashboard -> Project -> Session with prefetch on hover | 3-4 hours |
| P3-6 | Backend: remaining query modules for cost, productivity, analytics, experiments | 10-14 hours |
| P3-7 | Backend: route handlers for all remaining endpoints | 6-8 hours |
| P3-8 | Backend: Pydantic response models for all endpoints | 4-6 hours |

**Deliverable**: Complete drill-down flow from Dashboard to Session Detail with Timeline Scrubber.

#### Phase 4: Remaining Pages

**Goal**: Cost Analysis, Productivity, Deep Analytics, Experiments, Settings.

| Task | Description | Est. Effort |
|------|-------------|-------------|
| P4-1 | Cost Analysis page (6 chart/card components) | 6-8 hours |
| P4-2 | Productivity page (6 components) | 6-8 hours |
| P4-3 | Deep Analytics page (7 panel components) | 8-10 hours |
| P4-4 | Experiments page (TagManager, TagAssignment, ComparisonBuilder, ComparisonResults) | 6-8 hours |
| P4-5 | Settings page (pricing editor, ETL status, rebuild trigger) | 4-6 hours |

**Deliverable**: All 8 pages functional.

#### Phase 5: WebSocket Live Monitor

**Goal**: Real-time session monitoring.

| Task | Description | Est. Effort |
|------|-------------|-------------|
| P5-1 | Backend: ConnectionManager, FileWatcher async wrapper, broadcast loop | 4-6 hours |
| P5-2 | Backend: WebSocket route handler with heartbeat | 2-3 hours |
| P5-3 | Frontend: `useWebSocket` hook with reconnect, Page Visibility buffering | 4-6 hours |
| P5-4 | Frontend: LiveMonitor page (CostTicker, TokenAccumulator, BurnRate, Sparkline, ConnectionStatus) | 6-8 hours |
| P5-5 | Integration testing: file write -> WebSocket update within 2 seconds | 2-3 hours |

**Deliverable**: Working live monitor that updates within 2 seconds of new JSONL data.

#### Phase 6: Export, Polish, and Testing

**Goal**: Export system, error handling, performance optimization, test coverage.

| Task | Description | Est. Effort |
|------|-------------|-------------|
| P6-1 | Export system: CSV (with BOM), JSON (with metadata), PNG (SVG serialization) | 6-8 hours |
| P6-2 | ChartExportWrapper HOC for PNG export on all charts | 3-4 hours |
| P6-3 | Error handling: global error boundary, API error states, empty states | 3-4 hours |
| P6-4 | Performance: virtual scrolling for long session turn lists | 3-4 hours |
| P6-5 | Backend test coverage to 90% | 6-8 hours |
| P6-6 | Frontend component tests (70% on key components) | 6-8 hours |
| P6-7 | E2E tests for critical paths | 4-6 hours |
| P6-8 | Bundle size audit and optimization | 2-3 hours |

**Deliverable**: Ship-ready product.

#### Phase 7: Integration and Launch

**Goal**: CLI integration, packaging, documentation.

| Task | Description | Est. Effort |
|------|-------------|-------------|
| P7-1 | `ccwap serve` CLI command (ETL, start server, open browser) | 3-4 hours |
| P7-2 | Build pipeline: `npm run build` -> copy to `ccwap/static/` -> Python package | 2-3 hours |
| P7-3 | README.md updates | 2-3 hours |
| P7-4 | ARCHITECTURE.md documentation | 2-3 hours |
| P7-5 | Final QA against production database | 2-3 hours |

**Deliverable**: Publishable `ccwap` package with web dashboard.

### 7.2 Critical Path Dependencies

```
Phase 0 (ETL prerequisite)
    |
    v
Phase 1 (Backend foundation + Timeline spike)
    |
    +---> Phase 2 (Frontend foundation)  [can start when P1-1 through P1-7 are done]
    |         |
    |         v
    +---> Phase 3 (Core pages)  [requires P1 backend + P2 frontend foundation]
              |
              v
         Phase 4 (Remaining pages)  [requires P3 backend endpoints]
              |
              v
         Phase 5 (WebSocket)  [independent of P4, but after P1 backend]
              |
              v
         Phase 6 (Export + Testing)  [after P4 and P5]
              |
              v
         Phase 7 (Integration + Launch)
```

**The critical path is**: Phase 0 -> Phase 1 -> Phase 3 (Timeline Scrubber at 10-14 hours is the longest single task) -> Phase 4 -> Phase 6 -> Phase 7.

Phase 2 can run in parallel with Phase 1 backend work (after the initial app scaffold is done).
Phase 5 (WebSocket) is semi-independent and can start alongside Phase 4.

### 7.3 Spike/POC Requirements

| Spike | Priority | Purpose | Timebox |
|-------|----------|---------|---------|
| S1: Timeline Scrubber scroll sync | Critical | Validate that HTML turn blocks and SVG cost overlay can stay synchronized during horizontal scroll. Test with 200+ blocks. | 4-6 hours |
| S2: Recharts 3 + shadcn/ui Chart | High | Verify that shadcn/ui's Chart component works with Recharts 3 and CSS variable theming in dark/light mode. | 2-3 hours |
| S3: recharts-to-png + Recharts 3 | Medium | Test if recharts-to-png works with Recharts 3. If yes, use it for PNG export. If no, confirm SVG serialization approach. | 1-2 hours |
| S4: Tailwind v4 + shadcn/ui compatibility | High | Run `npx shadcn@latest init` and verify all base components work with Tailwind v4 CSS-first config. | 1-2 hours |
| S5: aiosqlite 0.22 PRAGMA setup | Medium | Verify that aiosqlite 0.22+ correctly handles all PRAGMAs (journal_mode, synchronous, cache_size, mmap_size, busy_timeout). | 1 hour |

### 7.4 Key Patterns and Conventions to Follow

#### Backend Conventions

**1. Query Module Pattern**

Every API domain has a dedicated query module in `ccwap/server/queries/`. Each function takes an `aiosqlite.Connection` and returns typed data:

```python
# ccwap/server/queries/project_queries.py

async def get_projects(
    db: aiosqlite.Connection,
    date_from: date,
    date_to: date,
    sort: str,
    order: str,
    page: int,
    limit: int,
    search: Optional[str] = None
) -> tuple[list[dict], int]:
    """
    Returns (projects_list, total_count).
    Uses TWO-QUERY pattern: sessions+turns, then tool_calls separately.
    """
    # Query 1: token/cost aggregates from sessions + turns
    # Query 2: LOC/error aggregates from tool_calls + sessions
    # Merge in Python
    ...
```

**2. Pydantic Response Model Pattern**

Every endpoint has a typed Pydantic response model:

```python
# ccwap/server/models/projects.py
from pydantic import BaseModel

class ProjectMetrics(BaseModel):
    project_path: str
    project_display: str
    sessions: int
    turns: int
    cost: float
    # ... all 30+ fields

class ProjectsResponse(BaseModel):
    projects: list[ProjectMetrics]
    totals: dict[str, float]
    pagination: PaginationMeta
```

**3. Router Pattern**

```python
# ccwap/server/routes/projects.py
from fastapi import APIRouter, Depends, Query
from ccwap.server.dependencies import get_db

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", response_model=ProjectsResponse)
async def list_projects(
    db=Depends(get_db),
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    sort: str = "cost",
    order: str = "desc",
    page: int = 1,
    limit: int = Query(50, le=200),
    search: Optional[str] = None,
):
    ...
```

**4. Two-Query Mandate**

NEVER write a query like this:

```sql
-- FORBIDDEN: Cross-product JOIN
SELECT ... FROM sessions s
JOIN turns t ON t.session_id = s.session_id
JOIN tool_calls tc ON tc.turn_id = t.id
GROUP BY s.project_path
```

ALWAYS use this pattern:

```python
# Query 1: sessions + turns (token/cost aggregates)
q1 = await db.execute("""
    SELECT s.project_path, SUM(t.cost) as cost, ...
    FROM sessions s JOIN turns t ON t.session_id = s.session_id
    WHERE ...
    GROUP BY s.project_path
""")

# Query 2: tool_calls (LOC/error aggregates)
q2 = await db.execute("""
    SELECT s.project_path, SUM(tc.loc_written) as loc, ...
    FROM tool_calls tc JOIN sessions s ON s.session_id = tc.session_id
    WHERE ...
    GROUP BY s.project_path
""")

# Merge in Python
results = merge_project_data(q1_rows, q2_rows)
```

#### Frontend Conventions

**1. Query Key Factory Pattern**

```typescript
// api/keys.ts
export const projectKeys = {
  all: ['projects'] as const,
  lists: () => [...projectKeys.all, 'list'] as const,
  list: (filters: ProjectFilters) => [...projectKeys.lists(), filters] as const,
  details: () => [...projectKeys.all, 'detail'] as const,
  detail: (path: string) => [...projectKeys.details(), path] as const,
}
```

**2. API Hook Pattern**

```typescript
// api/projects.ts
export function useProjects(filters: ProjectFilters) {
  const { dateRange } = useDateRange()
  return useQuery({
    queryKey: projectKeys.list({ ...filters, ...dateRange }),
    queryFn: () => fetchProjects({ ...filters, ...dateRange }),
    staleTime: 30_000,  // 30 seconds
  })
}
```

**3. Page Component Pattern**

```typescript
// pages/ProjectsPage.tsx
const ProjectsPage = () => {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useProjects({ ...dateRange })

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />
  if (!data?.projects.length) return <EmptyState message="No projects found" />

  return (
    <PageLayout title="Projects" exportData={data}>
      <DataTable data={data.projects} ... />
    </PageLayout>
  )
}

export default ProjectsPage  // default export for React.lazy()
```

**4. Chart Component Pattern (shadcn/ui wrapper)**

```typescript
// components/charts/CostAreaChart.tsx
import { ChartContainer, ChartTooltip } from "@/components/ui/chart"
import { AreaChart, Area, XAxis, YAxis } from "recharts"

const chartConfig = {
  cost: { label: "Cost", color: "var(--chart-1)" },
}

export function CostAreaChart({ data }: { data: CostTrendPoint[] }) {
  return (
    <ChartContainer config={chartConfig}>
      <AreaChart data={data}>
        <XAxis dataKey="date" />
        <YAxis />
        <ChartTooltip />
        <Area dataKey="cost" fill="var(--chart-1)" fillOpacity={0.3} />
      </AreaChart>
    </ChartContainer>
  )
}
```

**5. TanStack Query Stale Time Strategy**

| Data Type | staleTime | Rationale |
|-----------|-----------|-----------|
| Dashboard data | 30s | Frequently visited, should feel fresh |
| Historical analytics | 60s | Data doesn't change often |
| Session replay | Infinity | Immutable once session is complete |
| Live monitor | 0 (WebSocket) | Real-time updates bypass query cache |
| Settings/config | 300s | Rarely changes |

### 7.5 Handoff Notes (Specific Instructions for Implementation Agents)

**For the Backend Implementation Agent:**

1. Start by reading `C:\testprojects\claude-usage-analyzer\ccwap\models\schema.py` to understand the exact database schema. All column names must match exactly.

2. Read `C:\testprojects\claude-usage-analyzer\ccwap\cost\pricing.py` and `C:\testprojects\claude-usage-analyzer\ccwap\config\loader.py` to understand how pricing lookups work. The backend API must use the same `get_pricing_for_model()` function for cost calculations.

3. Read `C:\testprojects\claude-usage-analyzer\ccwap\reports\projects.py` (specifically `_get_tool_stats_by_project`) as the reference implementation for the two-query pattern. Your query modules must follow the same approach.

4. The `FileWatcher` at `C:\testprojects\claude-usage-analyzer\ccwap\etl\watcher.py` uses synchronous `sqlite3`. When wrapping in `asyncio.to_thread()`, give the watcher thread its own `sqlite3.Connection` -- do NOT share the `aiosqlite` connection across threads.

5. PRAGMAs to set on the `aiosqlite` connection at startup:
   ```sql
   PRAGMA journal_mode=WAL;
   PRAGMA synchronous=NORMAL;
   PRAGMA cache_size=-64000;
   PRAGMA mmap_size=268435456;
   PRAGMA busy_timeout=5000;
   PRAGMA temp_store=MEMORY;
   PRAGMA foreign_keys=ON;
   ```

6. For the `ccwap serve` command, add it to the existing CLI at `C:\testprojects\claude-usage-analyzer\ccwap\ccwap.py`. Run ETL first (call `run_etl()`), then start uvicorn.

7. Mount StaticFiles LAST, after all API routes and WebSocket routes. Use `html=True` for SPA fallback:
   ```python
   app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
   ```

**For the Frontend Implementation Agent:**

1. Use `npx shadcn@latest init` to scaffold the project. Select Tailwind v4 configuration. If the init fails with v4, fall back to v3 and document the issue.

2. The global date range hook must read and write URL search params. Use `useSearchParams` from React Router 7. The query key for every API hook must include `dateFrom` and `dateTo`.

3. For the Timeline Scrubber, load ALL turns in a single API call (`/api/sessions/:id/replay`). The cumulative cost line needs the full dataset. Virtualize only the rendering, not the data fetching.

4. Token type colors are consistent across the entire application:
   - Input: blue-500
   - Output: green-500
   - Cache Read: purple-500
   - Cache Write: orange-500

5. CSV export must include UTF-8 BOM (`\uFEFF`) prefix for Windows Excel compatibility. This is a known issue from the existing CLI.

6. Dark mode is the DEFAULT. Set `dark` class on `<html>` element. Do NOT use OS detection -- dark is always the first-visit default.

7. For PNG chart export, the primary strategy is SVG serialization:
   ```typescript
   // Get SVG element from Recharts
   const svg = chartRef.current?.querySelector('svg')
   // Serialize to string
   const svgData = new XMLSerializer().serializeToString(svg)
   // Create canvas at 2x resolution
   const canvas = document.createElement('canvas')
   // ... draw SVG to canvas, export as PNG blob
   ```

8. The `useWebSocket` hook must implement Page Visibility API buffering:
   ```typescript
   document.addEventListener('visibilitychange', () => {
     if (document.visibilityState === 'hidden') {
       // Start buffering messages
     } else {
       // Flush buffer, render latest state
     }
   })
   ```

---

## Appendix A: Backend Directory Structure (Detailed)

```
ccwap/server/
  __init__.py
  app.py                    # create_app() factory, lifespan, middleware, router includes, static mount
  dependencies.py           # get_db() dependency, get_config() dependency
  websocket.py              # ConnectionManager class, broadcast loop
  file_watcher.py           # Async wrapper around existing FileWatcher

  routes/
    __init__.py             # Includes all routers
    dashboard.py            # GET /api/dashboard
    projects.py             # GET /api/projects, GET /api/projects/:path
    sessions.py             # GET /api/sessions, GET /api/sessions/:id, GET /api/sessions/:id/replay
    cost.py                 # GET /api/cost/{summary,by-token-type,by-model,trend,by-project,forecast}
    productivity.py         # GET /api/productivity/{summary,loc-trend,languages,tools,errors,files}
    analytics.py            # GET /api/analytics/{thinking,truncation,sidechains,cache-tiers,branches,versions,skills}
    experiments.py          # CRUD /api/experiments/tags, POST assign, GET compare
    settings.py             # GET/PUT /api/settings/pricing, GET etl-status, POST rebuild, GET db-stats
    health.py               # GET /api/health

  models/
    __init__.py
    common.py               # PaginationMeta, DateRangeParams, ErrorResponse
    dashboard.py            # DashboardResponse, VitalsData, CostTrendPoint, ActivityFeedItem
    projects.py             # ProjectMetrics, ProjectsResponse
    sessions.py             # SessionSummary, SessionReplay, TurnDetail, ToolCallDetail
    cost.py                 # CostSummary, TokenTypeBreakdown, ModelBreakdown, CostForecast
    productivity.py         # EfficiencySummary, LanguageBreakdown, ToolUsage, ErrorAnalysis, FileHotspot
    analytics.py            # ThinkingAnalysis, TruncationAnalysis, SidechainMetrics, CacheTierBreakdown, etc.
    experiments.py          # Tag, TagComparison, ComparisonMetric

  queries/
    __init__.py
    dashboard_queries.py    # get_vitals_today, get_cost_trend, get_top_projects, get_recent_sessions
    project_queries.py      # get_projects (two-query), get_project_detail
    session_queries.py      # get_sessions, get_session_replay (two-query)
    cost_queries.py         # get_cost_summary, get_by_token_type, get_by_model, get_trend, get_forecast
    productivity_queries.py # get_efficiency, get_loc_trend, get_languages, get_tools, get_errors, get_files
    analytics_queries.py    # get_thinking, get_truncation, get_sidechains, get_cache_tiers, etc.
    experiment_queries.py   # get_tags, create_tag, delete_tag, assign_tag, compare_tags
```

## Appendix B: Frontend Directory Structure (Detailed)

```
ccwap/frontend/
  package.json
  vite.config.ts
  tsconfig.json
  index.html

  src/
    main.tsx                # React entry point, render to #root
    App.tsx                 # Router, QueryClientProvider, ThemeProvider, Suspense boundaries

    api/
      client.ts             # Typed fetch wrapper, base URL, error handling
      keys.ts               # Query key factories for all domains
      dashboard.ts           # useDashboard() hook
      projects.ts            # useProjects(), useProject(path) hooks
      sessions.ts            # useSessions(), useSessionReplay(id) hooks
      cost.ts                # useCostSummary(), useCostTrend(), etc.
      productivity.ts        # useEfficiency(), useLanguages(), etc.
      analytics.ts           # useThinking(), useTruncation(), etc.
      experiments.ts         # useTags(), useComparison(), mutation hooks
      settings.ts            # useSettings(), usePricingMutation(), etc.

    hooks/
      useDateRange.ts        # URL param read/write, presets, computed granularity
      useTheme.ts            # localStorage + <html> class toggle
      useWebSocket.ts        # Connect, reconnect, buffering, heartbeat
      useExport.ts           # CSV/JSON/PNG generation and download
      useLocalStorage.ts     # Type-safe localStorage hook
      useColumnPrefs.ts      # Column visibility persistence

    components/
      ui/                    # shadcn/ui generated components (Button, Card, Table, Dialog, etc.)
      layout/
        Sidebar.tsx          # Navigation links, active state
        TopBar.tsx           # DateRangePicker, ThemeToggle, ExportDropdown
        PageLayout.tsx       # Title, export button slot, content area
      charts/
        CostAreaChart.tsx
        TokenBreakdownChart.tsx
        ModelCostChart.tsx
        LanguageChart.tsx
        ErrorCategoryChart.tsx
        LiveSparkline.tsx
        ChartExportWrapper.tsx  # HOC: wraps any chart, adds PNG export button
      tables/
        DataTable.tsx         # Generic: sort, paginate, column visibility, expandable rows
        ColumnSelector.tsx
      dashboard/
        VitalsStrip.tsx
        ProjectGrid.tsx
        ActivityFeed.tsx
      session/
        TimelineScrubber.tsx  # Flagship component
        TurnBlock.tsx         # Single block in timeline
        TurnDetailPanel.tsx   # Side panel with turn details
        SessionHeader.tsx
        SessionStats.tsx
      live/
        CostTicker.tsx
        TokenAccumulator.tsx
        BurnRate.tsx
        ConnectionStatus.tsx
      experiments/
        TagManager.tsx
        TagAssignment.tsx
        ComparisonBuilder.tsx
        ComparisonResults.tsx
      common/
        DateRangePicker.tsx
        ThemeToggle.tsx
        ExportDropdown.tsx
        EmptyState.tsx
        LoadingState.tsx
        ErrorState.tsx
        MetricCard.tsx

    pages/
      DashboardPage.tsx       # Default export for React.lazy()
      ProjectsPage.tsx
      ProjectDetailPage.tsx
      SessionDetailPage.tsx
      CostAnalysisPage.tsx
      ProductivityPage.tsx
      DeepAnalyticsPage.tsx
      ExperimentsPage.tsx
      LiveMonitorPage.tsx
      SettingsPage.tsx

    lib/
      utils.ts               # formatCurrency, formatTokens, formatDuration, formatPercentage
      constants.ts            # TOKEN_TYPE_COLORS, CHART_CONFIG, DATE_PRESETS
      types.ts                # Shared TypeScript interfaces matching Pydantic models
      export-utils.ts         # CSV/JSON/PNG generation helpers

    styles/
      globals.css             # @import "tailwindcss", @theme directive, custom properties, chart vars
```

## Appendix C: Quality Checklist Verification

- [x] Every requirement has been addressed or explicitly deferred with justification
- [x] Every ADR includes alternatives considered
- [x] No technology choice is made without stated rationale
- [x] Risks have been identified for each major architectural component
- [x] The implementation guidance section is actionable enough for downstream agents
- [x] Assumptions are clearly documented
- [x] The architecture supports the stated NFRs (performance, security, scalability)
- [x] Cross-cutting concerns (logging, error handling, auth) are addressed
- [x] Cross-product JOIN bug is addressed as a mandatory pattern
- [x] daily_summaries prerequisite is gated as Phase 0
- [x] recharts-to-png uncertainty is mitigated with SVG serialization fallback
- [x] Performance strategy for large datasets uses virtualization + pre-aggregation

---

**End of Architecture Review Document**
