# Architecture Review: CCWAP Dashboard UI Refactor

**Date**: 2026-02-08
**Author**: Sr. Architect Review (Claude Opus 4.6)
**Status**: Proposed
**Scope**: 16 critical bugs + frontend enhancements across FastAPI + React + SQLite stack

---

## 1. Executive Summary

The CCWAP dashboard has 16 confirmed bugs, 11 of which stem from a single root cause: inconsistent date/time handling across the ETL, SQLite, FastAPI, and React layers. The ETL stores timestamps as UTC ISO-8601 strings, but the query layer uses `date.today()` (local server time) and the frontend uses `toISOString().slice(0,10)` (UTC), creating a systematic timezone mismatch that affects every date-filtered endpoint and the daily_summaries materialized view.

The recommended architectural direction is **"Local Time at the Edges, UTC in Storage."** The ETL continues to store raw UTC timestamps in sessions/turns/tool_calls. All SQLite `date()` calls that feed user-visible grouping or filtering apply `'localtime'` conversion. The frontend computes date strings using local time exclusively. The daily_summaries table is rebuilt using `date(timestamp, 'localtime')` grouping. This approach requires zero schema changes, no ETL modifications, and concentrates fixes in the query and frontend layers.

The remaining 5 calculation/data bugs and 6 frontend display bugs are isolated fixes that do not require architectural changes. The proposed enhancements (custom date ranges, drill-down, lazy charts, export) are feature additions that slot cleanly into the existing component architecture. The total refactor is estimated at 3 phases over approximately 4-5 implementation sessions, with the date/time fixes being the critical path.

---

## 2. Requirements Analysis

### 2.1 Functional Requirements (Prioritized)

**Must-Have (Phase 1 -- Date/Time Foundation):**
- FR-1: All date-filtered endpoints must respect the `from`/`to` query parameters (Bugs 1, 2, 7)
- FR-2: "Today" calculations must use local time, not UTC (Bug 3)
- FR-3: Daily summaries must group by local date (Bug 4)
- FR-4: Frontend date strings must represent local dates (Bugs 8, 9)
- FR-5: Period-over-period deltas must use consistent date arithmetic (Bugs 5, 6)
- FR-6: Cost summary "This Week" must use consistent Monday-start (Bug 11)

**Must-Have (Phase 2 -- Data Correctness):**
- FR-7: Agent spawns metric must count actual spawns (sessions with `is_agent=1`), not turns in agent sessions (Bug 12)
- FR-8: Model selection in recent sessions must use most recent by timestamp, not MAX() (Bug 13)
- FR-9: Agent tree builder must handle orphaned parent nodes and avoid dict mutation during iteration (Bug 14)
- FR-10: Explorer filter options date logic must be corrected (Bug 10)
- FR-11: Thinking trend must be sorted by date in query (Bug 16)
- FR-12: Model queries filtering by `s.first_timestamp` vs tool_calls dates must be consistent (Bug 15)

**Must-Have (Phase 3 -- Frontend Display):**
- FR-13: Dashboard heatmap tooltip must show day name, not row index (Bug 17)
- FR-14: CostPage anomaly formatters must handle undefined values (Bug 18)
- FR-15: ProductivityPage must show both `loc_written` and `loc_delivered` (Bug 19)
- FR-16: ModelComparison radar normalization must use min-max 0-100 (Bug 20)
- FR-17: WorkflowPage pie labels must include percentages (Bug 21)
- FR-18: SessionsPage must replace cryptic "u" notation (Bug 22)

**Should-Have (Enhancements):**
- FR-19: Custom date range inputs (native `<input type="date">`)
- FR-20: "Last 7 Days" and "Last 14 Days" presets
- FR-21: Disable chart animations for >200 data points
- FR-22: `staleTime` tuning per query type
- FR-23: DateRangeParams Pydantic model with validation
- FR-24: Logging in global exception handler

**Could-Have (Future):**
- FR-25: Drill-down from charts to session lists
- FR-26: Aggregation option toggle (daily/weekly/monthly)
- FR-27: CSV/JSON export from all pages
- FR-28: Lazy chart rendering (intersection observer)

### 2.2 Non-Functional Requirements

| NFR | Target | Current State |
|-----|--------|--------------|
| Query latency (p95) | <200ms for all endpoints | Unknown, likely met (SQLite WAL + single user) |
| Frontend bundle size | <500KB gzipped | Current unknown, lazy loading in place |
| Test coverage | Maintain 703+ tests, add date-specific tests | 703 passing |
| Zero downtime | N/A (desktop app, no deployment) | Met |
| Data integrity | Daily summaries must match raw table aggregates | Broken (UTC vs local mismatch) |

### 2.3 Constraints and Assumptions

**Constraints:**
- C-1: Zero-dependency CLI constraint for core Python (stdlib only). Web deps in `requirements-web.txt`.
- C-2: SQLite single-file database. No migration to Postgres/other DB.
- C-3: Schema version is 3. No schema changes permitted for this refactor (per established Phase 2 pattern).
- C-4: Single shared aiosqlite connection (single-user desktop).
- C-5: Tailwind CSS 4 with CSS-first config. Shadcn/ui compatibility TBD.
- C-6: Recharts 3.7 strict typing constraints (Formatter<number, NameType>).

**Assumptions:**
- A-1: The user operates in a single timezone throughout the tool's lifecycle. Multi-timezone support is not required.
- A-2: Claude Code JSONL files contain UTC timestamps (confirmed from ETL loader: `.isoformat()` on datetime objects).
- A-3: All existing tests pass and must continue to pass after refactor.
- A-4: The `daily_summaries` table can be fully rebuilt (INSERT OR REPLACE) without user-visible downtime.
- A-5: The `date.today()` calls in Python return the same timezone as the user expects to see in the dashboard.

### 2.4 Gaps and Clarifications Needed

- **GAP-1**: How does the ETL parse timestamps from JSONL? Are they always UTC? Need to verify `ccwap/etl/extractor.py` to confirm source timezone. **Assumption: UTC based on `.isoformat()` usage in loader.**
- **GAP-2**: Does the user ever change timezones (e.g., traveling)? If so, daily_summaries would need a rebuild trigger. **Assumption: No, single timezone.**
- **GAP-3**: Is there an existing rebuild/re-ETL command? Needed for daily_summaries fix. **Assumption: Yes, ETL has a `--rebuild` or similar mechanism based on `materialize_daily_summaries(conn, affected_dates=None)` which recomputes all dates.**

---

## 3. Architecture Decisions

### ADR-001: Date/Time Strategy -- Local Time at the Edges

- **Context**: 11 of 16 bugs trace to timezone mismatch. ETL stores UTC ISO-8601 timestamps. SQLite `date('now')` returns UTC. Python `date.today()` returns local time. JavaScript `toISOString()` returns UTC. These four layers disagree on what "today" means, causing daily_summaries to group by UTC date while the user thinks in local date.

- **Decision**: Adopt "Local Time at the Edges, UTC in Storage."
  1. **ETL/Storage (no change)**: Continue storing raw UTC timestamps in `sessions.first_timestamp`, `turns.timestamp`, and `tool_calls.timestamp`. These are immutable audit data.
  2. **SQLite Queries (change)**: All `date(timestamp)` calls that produce user-visible dates or filter by user-supplied dates must become `date(timestamp, 'localtime')`. All `date('now')` calls must become `date('now', 'localtime')`.
  3. **Python Query Layer (change)**: Replace `date.today().isoformat()` with a helper function that is explicit about localtime intent. All "today" references use this helper.
  4. **Daily Summaries Materialization (change)**: `materialize_daily_summaries()` must group by `date(t.timestamp, 'localtime')` instead of `date(t.timestamp)`. Requires a one-time full rebuild.
  5. **Frontend (change)**: Replace all `toISOString().slice(0,10)` with `toLocaleDateString()` formatted as YYYY-MM-DD. Replace `new Date("YYYY-MM-DD")` with `new Date("YYYY-MM-DDT00:00:00")` to force local interpretation.

- **Status**: Accepted

- **Consequences**:
  - **Positive**: All layers agree on what "today" and "this date" mean. Zero schema changes. ETL untouched. Fixes Bugs 1-9, 11.
  - **Positive**: SQLite's `'localtime'` uses the OS timezone, which matches `date.today()` in Python and local Date in JS.
  - **Negative**: If the user changes OS timezone, daily_summaries become stale and need a rebuild. Acceptable for single-user desktop.
  - **Negative**: `date(timestamp, 'localtime')` is slightly slower than `date(timestamp)` due to timezone conversion. Negligible for SQLite on local disk.

- **Alternatives Considered**:
  1. **UTC everywhere**: Would require converting the user's local date range to UTC in the frontend before sending API calls. Complex for edge cases (midnight transitions), and the user conceptually thinks in local time ("what did I do today").
  2. **Store local time in ETL**: Would require ETL changes and re-processing all JSONL files. Destructive to audit trail. Rejected.
  3. **Store timezone offset per session**: Overengineered for single-user desktop. Would require schema change. Rejected.

---

### ADR-002: Query Layer Date Filtering -- Shared Helper Module

- **Context**: Every query module independently constructs date filter clauses. There are 15 query modules with ~50+ date filter constructions, each slightly different (some use `date(t.timestamp)`, some use `date(s.first_timestamp)`, some use `date >= ?` on daily_summaries). This inconsistency is the mechanism through which most date bugs manifest.

- **Decision**: Create a shared `ccwap/server/queries/date_helpers.py` module with:
  1. `local_today() -> str` -- Returns `date.today().isoformat()`, explicitly documented as local time.
  2. `build_date_filter(col: str, date_from: Optional[str], date_to: Optional[str], params: list) -> str` -- Builds `AND date(col, 'localtime') >= ? AND date(col, 'localtime') <= ?` clauses, appending to params.
  3. `build_daily_summary_filter(date_from: Optional[str], date_to: Optional[str], params: list) -> str` -- Builds `AND date >= ? AND date <= ?` for the daily_summaries table (already stored as local dates after ADR-001 rebuild).

  All 15 query modules refactored to use these helpers. No raw `date()` or `date.today()` calls outside this module.

- **Status**: Accepted

- **Consequences**:
  - **Positive**: Single point of truth for date filtering. Adding `'localtime'` conversion requires changing one function, not 50+ query strings.
  - **Positive**: Consistent behavior across all endpoints.
  - **Negative**: Slightly more verbose imports in each query module. Minor.

- **Alternatives Considered**:
  1. **Find-and-replace `date(` with `date(xxx, 'localtime')` inline**: Error-prone, no enforcement, easy to regress. Rejected.
  2. **SQLite custom function**: Would need to register a custom `localdate()` function. Adds complexity to connection setup. Rejected as overengineering.

---

### ADR-003: Vitals and Sparkline -- Accept Date Range Parameters

- **Context**: `get_vitals_today()` ignores `date_from`/`date_to` and always queries "today." `get_sparkline_7d()` always shows the last 7 days. The dashboard route passes date range to `get_top_projects` and `get_cost_trend` but not to vitals or sparkline (Bug 1, Bug 2). The recent_sessions query also ignores date range.

- **Decision**:
  1. Rename `get_vitals_today()` to `get_vitals()` and add `date_from`/`date_to` parameters. When no range is provided, default to local today.
  2. Rename `get_sparkline_7d()` to `get_sparkline()` and add `date_from`/`date_to` parameters. When a range is provided, show daily cost for that range. When no range, default to last 7 days.
  3. Add `date_from`/`date_to` to `get_recent_sessions()`.
  4. Add `date_from`/`date_to` to `get_activity_calendar()`.
  5. Update the dashboard route to pass date range to all query functions.

- **Status**: Accepted

- **Consequences**:
  - **Positive**: All dashboard widgets respect the user's date range selection. This is the core UX expectation.
  - **Positive**: No API contract change needed (same response shape, just filtered differently).
  - **Negative**: Sparkline becomes redundant with cost_trend when a date range is selected. Consider hiding sparkline when explicit range is active, or keeping it as a "trailing 7 days" mini-view. Recommend: keep sparkline as "trailing 7 from end of range."

- **Alternatives Considered**:
  1. **Keep vitals as "today only" and add a separate date-range vitals endpoint**: Adds unnecessary API surface. The frontend already sends date range params to the dashboard endpoint. Rejected.

---

### ADR-004: Frontend Date String Computation -- toLocaleDateStr Helper

- **Context**: The `useDateRange.ts` hook computes date strings using `toISOString().split('T')[0]` in 6 places (lines 13, 14, 24, 30, 31, 35, 43). `toISOString()` converts to UTC, so at 11:30 PM ET on Feb 8, it returns "2026-02-09" -- a full day off. The `buildCalendarHeatmap` function uses `cellDate.toISOString().slice(0, 10)` (line 68) causing the same issue. `new Date("YYYY-MM-DD")` (line 89) parses as UTC midnight, also causing off-by-one for negative UTC offsets.

- **Decision**:
  1. Add a `toDateStr(date: Date): string` utility to `lib/utils.ts` that formats as `YYYY-MM-DD` using local getFullYear/getMonth/getDate.
  2. Replace all `toISOString().split('T')[0]` and `toISOString().slice(0,10)` with `toDateStr()`.
  3. Replace all `new Date("YYYY-MM-DD")` with `new Date("YYYY-MM-DDT00:00:00")` (or a `parseDateStr()` helper).
  4. Add `toDateStr` and `parseDateStr` to the existing `utils.ts`.

- **Status**: Accepted

- **Consequences**:
  - **Positive**: Eliminates UTC-shift bugs in the frontend (Bugs 8, 9). All date strings now match the user's wall clock.
  - **Positive**: Small, testable utility functions.
  - **Negative**: Need to audit all Date construction and formatting in every page/component. There are ~15 pages. Manageable.

- **Alternatives Considered**:
  1. **Use date-fns or dayjs library**: Adds a dependency. The needed functions are trivial (4 lines each). Rejected per zero-unnecessary-deps philosophy.
  2. **Use Intl.DateTimeFormat**: More correct but verbose. The manual approach (padStart) is simpler and sufficient. Rejected for simplicity.

---

### ADR-005: Query Architecture -- When to Use Two-Query vs CTE vs Correlated Subquery

- **Context**: The codebase uses three query patterns inconsistently:
  - **Two-query pattern** (dashboard_queries.py, session_queries.py): Separate queries for turns and tool_calls, merged in Python. Correct for avoiding cross-product inflation.
  - **CTE / subquery pre-aggregation** (workflow_queries.py lines 26-36): `LEFT JOIN (SELECT session_id, SUM(cost) as cost FROM turns GROUP BY session_id) turn_agg`. Correct but potentially slower for large datasets as the subquery isn't filtered.
  - **Correlated subqueries** (project_detail_queries.py lines 35-43, model_queries.py scatter): `COALESCE((SELECT SUM(t.cost) FROM turns t WHERE t.session_id = s.session_id), 0)`. Correct but O(N) per session.

- **Decision**: Standardize on these rules:
  1. **Two-query pattern**: Use when the result needs aggregates from BOTH turns and tool_calls for the same grouping dimension (e.g., per-project cost + LOC). This is the PRIMARY pattern.
  2. **CTE pre-aggregation**: Use when joining sessions with a SINGLE aggregate table (turns OR tool_calls, not both) and the aggregate needs to be filtered. Always apply date filters inside the CTE.
  3. **Correlated subqueries**: Use ONLY for small result sets (<50 rows, e.g., project detail sessions list) where the outer query already limits results. Replace with CTE for larger scans.
  4. **Direct aggregation**: Use when querying a single table (e.g., tool_calls grouped by tool_name, daily_summaries).

  Specifically:
  - `project_detail_queries.py get_project_detail`: Replace correlated subqueries with a CTE pre-aggregated JOIN. The current query runs N correlated subqueries per session.
  - `model_queries.py get_model_scatter`: Replace correlated subqueries with two-query pattern (turns agg per session + tool_calls agg per session, merge in Python).
  - `workflow_queries.py get_user_type_breakdown/trend`: Add date filter inside the CTE subquery (currently the `LEFT JOIN (SELECT ... FROM turns GROUP BY session_id)` scans ALL turns regardless of date range).
  - `analytics_queries.py get_branch_analytics/get_version_impact`: These JOIN sessions with turns directly. They work because there is no tool_calls in the equation, but should use CTE pattern for consistency and to apply date filters on turns inside the CTE.

- **Status**: Accepted

- **Consequences**:
  - **Positive**: Consistent, predictable query performance. No cross-product inflation. Date filters always pushed down.
  - **Positive**: Eliminates Bug 15 (model_queries filter mismatch) by establishing a clear rule: filter turns by `date(t.timestamp, 'localtime')`, not by `date(s.first_timestamp)`.
  - **Negative**: More code in some query modules (two queries instead of one). Acceptable for correctness.

- **Alternatives Considered**:
  1. **Always use two-query pattern everywhere**: Would be overkill for single-table queries. Rejected.
  2. **Use SQL views for pre-aggregation**: SQLite views are just syntax sugar with no materialization. No performance benefit. Rejected.

---

### ADR-006: API Contract -- DateRangeParams and Response Metadata

- **Context**: Every route independently declares `date_from: Optional[str] = Query(None, alias="from")` and `date_to: Optional[str] = Query(None, alias="to")`. There is no validation (invalid dates pass through to SQLite). The global exception handler swallows errors silently with no logging.

- **Decision**:
  1. Create a `DateRangeParams` Pydantic model as a FastAPI dependency:
     ```python
     class DateRangeParams:
         date_from: Optional[str] = Query(None, alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$")
         date_to: Optional[str] = Query(None, alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$")
     ```
  2. Use `Depends(DateRangeParams)` in all routes that accept date ranges.
  3. Do NOT add response metadata (timezone, effective date range) to every endpoint. This is a single-user desktop app; the overhead of response wrapping is not justified. The frontend already knows what it sent.
  4. Add `logging.exception()` to the global exception handler.

- **Status**: Accepted

- **Consequences**:
  - **Positive**: Invalid date formats caught early with 422 error. Single definition of date params.
  - **Positive**: Error logging aids debugging.
  - **Negative**: Slight refactor of all 15 route files to use dependency injection. Mechanical change.

- **Alternatives Considered**:
  1. **Response envelope with metadata**: `{ "data": {...}, "meta": {"timezone": "America/New_York", "range": {...}} }`. Too heavy for a desktop app. Would break all frontend type definitions. Rejected.
  2. **Custom middleware for date validation**: Possible but FastAPI's dependency injection is more idiomatic. Rejected.

---

### ADR-007: Frontend State Architecture -- Keep Hooks-Only, No DateContext

- **Context**: The current architecture uses `useDateRange()` hook backed by URL search params. Each page calls the hook independently. The question is whether to add a React Context for date range state.

- **Decision**: Keep the hooks-only approach. Do NOT add a DateContext.

  Rationale:
  1. URL search params are already a global store. `useSearchParams()` is effectively a context.
  2. All pages already call `useDateRange()` and it works correctly (aside from the UTC bug, fixed by ADR-004).
  3. React Query cache keys already include `dateRange.from` and `dateRange.to`, providing correct cache isolation.
  4. Adding a Context would create a second source of truth alongside the URL, inviting sync bugs.

  Enhancements to the existing pattern:
  1. Add `'last-7-days'` and `'last-14-days'` presets to `useDateRange.ts`.
  2. Add custom date range inputs to `DateRangePicker.tsx` (native `<input type="date">`).
  3. Add `staleTime` configuration per query category (see ADR-008).

- **Status**: Accepted

- **Consequences**:
  - **Positive**: No additional state management complexity. URL-driven state enables deep linking and browser back/forward.
  - **Positive**: Minimal change to existing architecture.
  - **Negative**: Each page must independently call `useDateRange()`. This is already the pattern and costs one line per page. Acceptable.

- **Alternatives Considered**:
  1. **DateContext provider wrapping all routes**: Would duplicate URL state. Rejected.
  2. **Zustand/Jotai store**: Overkill for a single piece of state that's already in the URL. Rejected.

---

### ADR-008: React Query Caching Strategy

- **Context**: Current `staleTime` is 30 seconds globally. For a single-user desktop app analyzing historical data, this is too aggressive -- it causes unnecessary refetches of data that cannot change (past dates).

- **Decision**: Implement tiered staleTime:
  1. **Historical data** (date range that does not include today): `staleTime: Infinity`. Past data never changes.
  2. **"Today" or "current" data** (date range includes today): `staleTime: 2 * 60 * 1000` (2 minutes). May change as sessions are added.
  3. **Session replay** (individual session): `staleTime: Infinity`. Individual sessions are immutable once written.
  4. **Settings/config**: `staleTime: Infinity` until mutated (use `invalidateQueries`).
  5. **Global default**: Keep `refetchOnWindowFocus: false` (already set). Keep `gcTime: 300_000`.

  Implementation: Each API hook (e.g., `useDashboard`, `useCostAnalysis`) checks whether `dateRange.to === toDateStr(new Date())` and sets staleTime accordingly.

- **Status**: Accepted

- **Consequences**:
  - **Positive**: Dramatically reduces unnecessary network requests. Instant page switches for historical data.
  - **Positive**: Simple implementation -- conditional in each hook's config.
  - **Negative**: If background ETL adds data for past dates (re-processing), the cache would be stale. Acceptable risk for desktop app; user can hard-refresh.

- **Alternatives Considered**:
  1. **WebSocket-driven cache invalidation**: The WebSocket already exists for live monitoring. Could push invalidation events. Overengineered for the benefit. Rejected for now.

---

### ADR-009: Daily Summaries Migration Strategy

- **Context**: The `daily_summaries` table is a materialized view keyed by `date TEXT PRIMARY KEY`. Currently, dates are computed as `date(t.timestamp)` (UTC). After ADR-001, they must be `date(t.timestamp, 'localtime')`. This means existing rows have wrong date keys.

- **Decision**: Full rebuild, not incremental migration.
  1. `DELETE FROM daily_summaries` (clear all rows).
  2. Run `materialize_daily_summaries(conn, affected_dates=None)` with the updated query (using `'localtime'`).
  3. This is a one-time operation triggered during the first ETL run after the code update.
  4. Add a migration flag: bump the materialization version or add a `localtime_rebuilt` flag to `etl_state`.
  5. Do NOT change the schema. The `date TEXT PRIMARY KEY` column is fine -- it will just contain local dates instead of UTC dates.

- **Status**: Accepted

- **Consequences**:
  - **Positive**: Clean slate. No mixed UTC/local dates in the table.
  - **Positive**: `materialize_daily_summaries()` already supports full rebuild (pass `affected_dates=None`).
  - **Negative**: One-time rebuild may take a few seconds for large databases. Acceptable for desktop.
  - **Negative**: If user downgrades code, daily_summaries would have local dates but queries would use UTC. Low risk for a development tool.

- **Alternatives Considered**:
  1. **Add a `date_local` column alongside `date`**: Doubles the table width. Schema change. Rejected per C-3.
  2. **Incremental migration (shift dates by timezone offset)**: Error-prone for DST transitions. Rejected.

---

### ADR-010: New Shared Components

- **Context**: Several frontend display bugs and enhancements suggest the need for shared utilities and components.

- **Decision**: Create the following shared modules:

  1. **`lib/utils.ts` additions** (not new files):
     - `toDateStr(date: Date): string` -- local YYYY-MM-DD
     - `parseDateStr(str: string): Date` -- parse as local midnight
     - `isToday(dateStr: string): boolean` -- compare with local today

  2. **`lib/chartConfig.ts` additions**:
     - `getStaleTime(dateRange: DateRange): number` -- returns Infinity for historical, 120000 for today
     - `shouldAnimate(dataLength: number): boolean` -- returns `dataLength < 200`

  3. **`components/DateRangePicker.tsx` enhancement** (existing file):
     - Add two `<input type="date">` fields for custom range
     - Add "Last 7 Days" and "Last 14 Days" preset buttons
     - Keep existing preset buttons

  4. **No new chart wrapper component**. Each page's chart has unique enough configuration that a generic wrapper would be a leaky abstraction. Instead, use the existing `TOOLTIP_STYLE` and `AXIS_STYLE` constants from `chartConfig.ts` consistently.

- **Status**: Accepted

- **Consequences**:
  - **Positive**: Minimal new files. Enhances existing modules.
  - **Positive**: `toDateStr` becomes the single correct way to format dates.
  - **Negative**: Each page still manages its own chart configuration. This is acceptable given the variety of chart types.

- **Alternatives Considered**:
  1. **Generic ChartWrapper component**: Would need to handle AreaChart, BarChart, PieChart, ScatterChart, RadarChart with different props. Abstraction leaks immediately. Rejected.
  2. **Separate `dateUtils.ts` file**: Not worth a new file for 3 small functions. Add to existing `utils.ts`. Rejected.

---

## 4. Technical Architecture Overview

### 4.1 System Decomposition

```
[User's Browser]
    |
    |-- React SPA (15 lazy-loaded pages)
    |     |-- useDateRange() hook (URL search params)
    |     |-- useQuery() hooks (TanStack Query v5)
    |     |-- lib/utils.ts (toDateStr, parseDateStr, formatters)
    |     |-- lib/chartConfig.ts (staleTime, animation, styles)
    |     |-- components/DateRangePicker.tsx (presets + custom)
    |
    v
[FastAPI Server]
    |-- routes/*.py (15 routers, Depends(DateRangeParams))
    |-- queries/date_helpers.py (NEW: local_today, build_date_filter)
    |-- queries/*.py (15 modules, all using date_helpers)
    |
    v
[SQLite WAL mode]
    |-- sessions, turns, tool_calls (UTC timestamps)
    |-- daily_summaries (local-date keys after rebuild)
    |-- etl_state, experiment_tags, snapshots
    |
    ^
[ETL Pipeline] (unchanged)
    |-- extractor.py -> loader.py -> materialize_daily_summaries()
```

### 4.2 Data Architecture

**Timestamp Flow:**
```
JSONL files (UTC ISO-8601)
  --> ETL extractor (parse as datetime)
  --> ETL loader (store as .isoformat() strings = UTC)
  --> SQLite turns.timestamp = "2026-02-08T03:15:22.000000"
  --> Query: date(timestamp, 'localtime') = "2026-02-07" (for EST/UTC-5)
  --> Daily summaries keyed by local date: "2026-02-07"
  --> API response: { "date": "2026-02-07" }
  --> Frontend: parseDateStr("2026-02-07") = local Feb 7 midnight
```

**Date Range Flow:**
```
User clicks "Last 30 Days" preset in DateRangePicker
  --> useDateRange() computes: { from: toDateStr(30_days_ago), to: toDateStr(today) }
  --> URL: ?preset=last-30-days
  --> API call: /api/dashboard?from=2026-01-09&to=2026-02-08
  --> FastAPI DateRangeParams validates YYYY-MM-DD format
  --> Query: date_helpers.build_date_filter("t.timestamp", "2026-01-09", "2026-02-08", params)
  --> SQL: AND date(t.timestamp, 'localtime') >= '2026-01-09'
           AND date(t.timestamp, 'localtime') <= '2026-02-08'
```

### 4.3 Integration Architecture

No external integrations affected. The WebSocket live monitor, file watcher, and cost broadcaster are not impacted by the date/time refactor.

### 4.4 Security Architecture

No security changes needed. The desktop app runs on localhost. The date validation (regex pattern on DateRangeParams) prevents SQL injection via malformed date strings (defense in depth -- parameterized queries already prevent injection).

### 4.5 Infrastructure and Deployment

No infrastructure changes. The app is a local Python process serving a built React SPA from `ccwap/static/`. The Vite build process is unchanged.

### 4.6 Observability

- Add `logging.exception("Unhandled error", exc_info=exc)` to the global exception handler in `app.py`.
- No other observability changes needed for a desktop app.

---

## 5. Technology Stack Recommendations

No stack changes. The existing stack is correct for the use case:

| Layer | Technology | Status |
|-------|-----------|--------|
| Backend | FastAPI + aiosqlite | Keep |
| Frontend | React 19 + TypeScript + Vite | Keep |
| Charts | Recharts 3.7 | Keep |
| State | TanStack Query v5 + URL params | Keep |
| Styling | Tailwind CSS 4 | Keep |
| Database | SQLite WAL mode | Keep |
| Testing | pytest (Python) + vitest (Frontend) | Keep |

No new dependencies recommended. The date utilities are trivial to implement without libraries.

---

## 6. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R-1 | `date(timestamp, 'localtime')` produces wrong results on Windows when OS timezone is misconfigured | Low | High | Document requirement for correct OS timezone. Add a `/api/health` field showing server timezone. |
| R-2 | Daily summaries rebuild takes too long on large databases (>100K turns) | Low | Medium | `materialize_daily_summaries(affected_dates=None)` is a single pass. Benchmark on largest known DB. If >10s, add progress logging. |
| R-3 | Changing `date()` to `date(..., 'localtime')` in 50+ query locations introduces typos/regressions | Medium | High | Use `date_helpers.build_date_filter()` everywhere. Grep for raw `date(` in queries after refactor to verify none remain. Add unit tests for the helper. |
| R-4 | Frontend `toDateStr()` change breaks edge cases (midnight, DST transition) | Low | Medium | Test `toDateStr(new Date(2026, 2, 9, 2, 0))` (spring forward) and `new Date(2026, 10, 2, 1, 0)` (fall back). The function uses getFullYear/getMonth/getDate which are always local, so DST doesn't affect date computation. |
| R-5 | Agent tree dict mutation bug (Bug 14) causes data corruption | Medium | Low | The bug is a Python dict mutation during iteration (`.pop()` inside a loop over `nodes.items()`). Fix: iterate a copy or use a separate pass. Isolated fix, low blast radius. |
| R-6 | Recharts formatter type errors from stricter handling of `undefined` | Medium | Low | Use explicit type guards `(v: any) => v != null ? formatCurrency(v) : ''` in all Tooltip formatters. Already done in DashboardPage; replicate to CostPage. |
| R-7 | Test suite breaks due to date-dependent assertions | Medium | Medium | Tests that assert specific dates should use `freezegun` (Python) or mock `Date` (JS). Add a note to CLAUDE.md about test date mocking patterns. |
| R-8 | Explorer filter_options query has broken date filter logic (Bug 10) | High | Medium | The `date_filter_sessions` variable is constructed but the SQL template uses a replacement that double-applies the filter. Fix: use `date_helpers` and remove the broken `.replace()` call on line 371. |

---

## 7. Implementation Guidance for Orchestrator

### 7.1 Recommended Phase Breakdown

**Phase 1: Date/Time Foundation (Critical Path -- Do First)**
Estimated: 1-2 sessions. All other phases depend on this.

1. Create `ccwap/server/queries/date_helpers.py` with `local_today()`, `build_date_filter()`, `build_daily_summary_filter()`.
2. Update `ccwap/etl/loader.py` `materialize_daily_summaries()` to use `date(t.timestamp, 'localtime')` and `date(tc.timestamp, 'localtime')` and `date(s.first_timestamp, 'localtime')`.
3. Add daily_summaries rebuild trigger (check a version flag in etl_state or just always rebuild on first run after code change).
4. Update `ccwap/server/queries/dashboard_queries.py`:
   - `get_vitals_today()` -> `get_vitals(db, date_from, date_to)` using `date_helpers`.
   - `get_sparkline_7d()` -> `get_sparkline(db, date_from, date_to)` using `date_helpers`.
   - `get_activity_calendar()` -> add `'localtime'` to `date('now', ?)`.
   - `get_period_deltas()` -> use `date_helpers` for date arithmetic.
   - `get_recent_sessions()` -> add date_from/date_to.
5. Update `ccwap/server/routes/dashboard.py` to pass date_from/date_to to all query functions.
6. Update `ccwap/server/queries/cost_queries.py`:
   - `get_cost_summary()` -> use `date_helpers.local_today()` for "today", "this week", "this month".
   - All `date(timestamp)` -> `date(timestamp, 'localtime')`.
7. Add `toDateStr()` and `parseDateStr()` to `ccwap/frontend/src/lib/utils.ts`.
8. Update `ccwap/frontend/src/hooks/useDateRange.ts`:
   - Replace all `toISOString().split('T')[0]` with `toDateStr()`.
   - Replace `new Date(dateRange.from)` with `parseDateStr(dateRange.from)`.
   - Fix granularity calc (line 90): use `parseDateStr` instead of `new Date`.
   - Add `'last-7-days'` and `'last-14-days'` presets.
9. Update `ccwap/frontend/src/pages/DashboardPage.tsx`:
   - `buildCalendarHeatmap()` line 68: replace `toISOString().slice(0, 10)` with `toDateStr()`.
   - Line 29: `new Date(sorted[0].date + 'T00:00:00')` already correct.
10. Run full test suite.

**Phase 2: Query Correctness Fixes (Parallelizable per module)**
Estimated: 1-2 sessions.

1. Refactor ALL 15 query modules to use `date_helpers.build_date_filter()` instead of inline date filter construction. Files:
   - `analytics_queries.py` (8 functions)
   - `cost_queries.py` (9 functions)
   - `dashboard_queries.py` (done in Phase 1)
   - `experiment_queries.py`
   - `explorer_queries.py` (update `_build_date_filter` to use localtime, fix `get_filter_options` Bug 10)
   - `heatmap_queries.py` (add localtime)
   - `model_queries.py` (fix Bug 13: MAX() -> ORDER BY timestamp DESC LIMIT 1; fix Bug 15: consistent date filtering)
   - `productivity_queries.py`
   - `project_detail_queries.py` (replace correlated subqueries with CTE per ADR-005)
   - `project_queries.py`
   - `search_queries.py`
   - `session_queries.py` (fix model selection Bug 13)
   - `settings_queries.py` (no date filtering, skip)
   - `workflow_queries.py` (fix Bug 14: agent tree dict mutation; fix agent spawns Bug 12; add date filter inside CTE subqueries)
2. Fix Bug 16: `analytics_queries.py get_thinking_trend()` -- the ORDER BY already uses `date(timestamp)` but should ensure it sorts correctly. Verify the `ORDER BY date(timestamp)` is not sorting by the aliased column name. (Line 365: `ORDER BY date(timestamp)` -- this is correct SQL, the alias `date` in the SELECT would shadow it. Rename the alias to `dt` or use positional ordering.)
3. Create `DateRangeParams` Pydantic model in `ccwap/server/models/common.py`.
4. Update all route files to use `Depends(DateRangeParams)`.
5. Add logging to global exception handler.
6. Run full test suite.

**Phase 3: Frontend Display Fixes and Enhancements**
Estimated: 1 session.

1. Bug 17: `DashboardPage.tsx` heatmap tooltip -- the `formatTooltip` callback on line 168-170 already receives `row` (which is the string label "Mon", "Tue", etc.) correctly from `HeatmapGrid`. However, the **heatmap page** (`HeatmapPage.tsx`) likely passes numeric `row` index. Verify and fix by ensuring row labels are always strings.
2. Bug 18: `CostPage.tsx` -- add `v != null` guards to all Tooltip formatters.
3. Bug 19: `ProductivityPage.tsx` -- the LOC trend query already returns `loc_delivered` (confirmed in `productivity_queries.py` line 67). The issue is the frontend chart only renders `loc_written`. Add a second `<Area>` for `loc_delivered`.
4. Bug 20: `ModelComparisonPage.tsx` -- normalize radar axes to 0-100 using min-max normalization.
5. Bug 21: `WorkflowPage.tsx` -- add percentage labels to pie chart (use `label={({ percent }) => ...}`).
6. Bug 22: `SessionsPage.tsx` -- replace "u" with "user turns" or a tooltip explaining it.
7. Enhancement: Update `DateRangePicker.tsx` with custom date inputs.
8. Enhancement: Add `staleTime` logic per ADR-008 to each API hook.
9. Enhancement: Add `shouldAnimate()` check to all chart `isAnimationActive` props.
10. Run frontend test suite.

### 7.2 Critical Path Dependencies

```
Phase 1 (Date/Time Foundation)
    |
    +--> Phase 2 (Query Correctness)  -- depends on date_helpers.py existing
    |         |
    |         +--> Phase 3 (Frontend Fixes) -- can start after Phase 1, overlap with Phase 2
    |
    [Daily summaries rebuild must happen before any query testing]
```

Phase 2 and Phase 3 can be partially parallelized (Phase 3 frontend fixes are independent of Phase 2 query refactors, except they share the `toDateStr()` utility from Phase 1).

### 7.3 Spike/POC Requirements

No spikes needed. All changes are well-understood transformations:
- `date(x, 'localtime')` is a documented SQLite feature
- `toLocaleDateString()` date formatting is standard JS
- Pydantic `Query(pattern=...)` is documented FastAPI

### 7.4 Key Patterns and Conventions to Follow

**Python Query Functions:**
```python
# Every query function that accepts date params follows this signature:
async def get_xxx(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    # ...other params...
) -> ReturnType:
    params: list = []
    filters = build_date_filter("t.timestamp", date_from, date_to, params)
    # ... use filters in SQL ...
```

**Frontend Date Handling:**
```typescript
// ALWAYS use these for date string operations:
import { toDateStr, parseDateStr } from '@/lib/utils'

// NEVER use:
// date.toISOString().slice(0, 10)     -- UTC shift bug
// new Date("2026-02-08")              -- UTC midnight bug
// date.toISOString().split('T')[0]    -- UTC shift bug
```

**React Query Hook Pattern:**
```typescript
export function useXxx(dateRange: DateRange) {
  return useQuery({
    queryKey: xxxKeys.data(dateRange),
    queryFn: () => apiFetch<XxxData>(`/xxx${buildQuery({...})}`),
    staleTime: getStaleTime(dateRange),
  })
}
```

**Chart Pattern:**
```tsx
<SomeChart>
  <Tooltip
    contentStyle={TOOLTIP_STYLE}
    formatter={(v: any) => v != null ? formatCurrency(v) : ''}
  />
  <Area
    isAnimationActive={shouldAnimate(data.length)}
  />
</SomeChart>
```

### 7.5 Handoff Notes for Implementation Agents

1. **When modifying `materialize_daily_summaries()`**, the function is in `ccwap/etl/loader.py` at line 191. Change three places: the turns query (line 233), the tool_calls query (line 264), and the agent/skill queries (lines 288, 305). Add `'localtime'` to all `date()` calls.

2. **The explorer_queries.py `get_filter_options()` bug (Bug 10)** is on line 371: `date_filter_sessions.replace('t.timestamp', 's.first_timestamp')`. This replace is conditional on `date_filter_sessions` being truthy, but the replacement modifies a filter that was already correctly constructed for sessions. The fix is to remove the `.replace()` call and use the `date_filter_sessions` variable directly, since it already references `s.first_timestamp`.

3. **The agent tree dict mutation bug (Bug 14)** is in `workflow_queries.py` lines 137-142. The `.pop("parent_session_id")` on line 138 mutates the dict while iterating `nodes.items()`. Fix: collect parent info in a separate dict or iterate `list(nodes.items())`.

4. **The model selection bug (Bug 13)** appears in two places: `dashboard_queries.py` line 205 (`MAX(CASE WHEN ... THEN t.model END)`) and `session_queries.py` line 59 (same pattern). Replace with a correlated subquery: `(SELECT t.model FROM turns t WHERE t.session_id = s.session_id AND t.model IS NOT NULL AND t.model NOT LIKE '<%' ORDER BY t.timestamp DESC LIMIT 1)`.

5. **Test considerations**: The `materialize_daily_summaries` function is tested. After adding `'localtime'`, tests that check specific date values will need to either mock the timezone or use dates that are the same in UTC and local (e.g., noon UTC timestamps which are the same local date for all Western Hemisphere timezones).

6. **The `HeatmapPage.tsx` vs `DashboardPage.tsx` tooltip bug (Bug 17)**: The Dashboard heatmap uses `formatTooltip={(row, col, value) => ...}` which receives string labels. Check `HeatmapPage.tsx` -- it likely uses the heatmap API endpoint which returns `{ day: number, hour: number, value: number }` where `day` is a numeric index (0-6). The tooltip needs to map this back to a day name. The `HeatmapGrid` component receives `rowLabels` and uses the string label, so the bug is that the heatmap API data's `day` field is used as a row index into `rowLabels`. Verify the mapping is correct (0=Mon in both the query and the labels array).

7. **File list for Phase 1 changes** (ordered by dependency):
   - NEW: `ccwap/server/queries/date_helpers.py`
   - MODIFY: `ccwap/etl/loader.py` (materialize_daily_summaries)
   - MODIFY: `ccwap/server/queries/dashboard_queries.py` (all 6 functions)
   - MODIFY: `ccwap/server/routes/dashboard.py` (pass date params)
   - MODIFY: `ccwap/server/queries/cost_queries.py` (get_cost_summary + all date() calls)
   - MODIFY: `ccwap/frontend/src/lib/utils.ts` (add toDateStr, parseDateStr)
   - MODIFY: `ccwap/frontend/src/hooks/useDateRange.ts` (fix UTC bug + add presets)
   - MODIFY: `ccwap/frontend/src/pages/DashboardPage.tsx` (fix heatmap date)

8. **File list for Phase 2 changes** (can be done in any order):
   - MODIFY: `ccwap/server/models/common.py` (add DateRangeParams)
   - MODIFY: `ccwap/server/queries/analytics_queries.py`
   - MODIFY: `ccwap/server/queries/explorer_queries.py` (fix Bug 10)
   - MODIFY: `ccwap/server/queries/heatmap_queries.py`
   - MODIFY: `ccwap/server/queries/model_queries.py` (fix Bugs 13, 15)
   - MODIFY: `ccwap/server/queries/productivity_queries.py`
   - MODIFY: `ccwap/server/queries/project_detail_queries.py` (CTE refactor)
   - MODIFY: `ccwap/server/queries/project_queries.py`
   - MODIFY: `ccwap/server/queries/search_queries.py`
   - MODIFY: `ccwap/server/queries/session_queries.py` (fix Bug 13)
   - MODIFY: `ccwap/server/queries/workflow_queries.py` (fix Bugs 12, 14, CTE filters)
   - MODIFY: `ccwap/server/queries/experiment_queries.py`
   - MODIFY: All `ccwap/server/routes/*.py` (DateRangeParams dependency)
   - MODIFY: `ccwap/server/app.py` (add logging to exception handler)

9. **File list for Phase 3 changes** (can be done in any order):
   - MODIFY: `ccwap/frontend/src/pages/CostPage.tsx` (Bug 18)
   - MODIFY: `ccwap/frontend/src/pages/ProductivityPage.tsx` (Bug 19)
   - MODIFY: `ccwap/frontend/src/pages/ModelComparisonPage.tsx` (Bug 20)
   - MODIFY: `ccwap/frontend/src/pages/WorkflowPage.tsx` (Bug 21)
   - MODIFY: `ccwap/frontend/src/pages/SessionsPage.tsx` (Bug 22)
   - MODIFY: `ccwap/frontend/src/pages/HeatmapPage.tsx` (Bug 17 verification)
   - MODIFY: `ccwap/frontend/src/components/DateRangePicker.tsx` (custom date inputs)
   - MODIFY: `ccwap/frontend/src/lib/chartConfig.ts` (staleTime helper, animation helper)
   - MODIFY: All `ccwap/frontend/src/api/*.ts` (add staleTime per ADR-008)

---

## Appendix A: Bug-to-ADR Mapping

| Bug # | Description | ADR | Phase |
|-------|-------------|-----|-------|
| 1 | Vitals ignores date params | ADR-003 | 1 |
| 2 | Sparkline ignores date params | ADR-003 | 1 |
| 3 | date.today() timezone mismatch | ADR-001 | 1 |
| 4 | Daily summaries UTC dates | ADR-001, ADR-009 | 1 |
| 5 | Granularity off-by-one | ADR-004 | 1 |
| 6 | Period deltas naive datetime | ADR-002 | 1 |
| 7 | Activity calendar hardcoded date('now') | ADR-001 | 1 |
| 8 | Heatmap DOW wrong from Date parsing | ADR-004 | 1 |
| 9 | toISOString UTC shift | ADR-004 | 1 |
| 10 | Explorer filter date logic backwards | ADR-002 | 2 |
| 11 | Cost week start locale | ADR-001 | 1 |
| 12 | Agent spawns counts wrong metric | -- (isolated fix) | 2 |
| 13 | Model MAX() not most recent | -- (isolated fix) | 2 |
| 14 | Agent tree dict mutation | -- (isolated fix) | 2 |
| 15 | Model queries date filter mismatch | ADR-005 | 2 |
| 16 | Thinking trend not sorted | -- (isolated fix) | 2 |
| 17 | Heatmap tooltip shows index | -- (isolated fix) | 3 |
| 18 | CostPage formatters undefined | -- (isolated fix) | 3 |
| 19 | ProductivityPage missing loc_delivered | -- (isolated fix) | 3 |
| 20 | Radar normalization inconsistent | -- (isolated fix) | 3 |
| 21 | Pie labels missing percentages | -- (isolated fix) | 3 |
| 22 | Cryptic "u" notation | -- (isolated fix) | 3 |

## Appendix B: Component Dependency Diagram

```
App.tsx
  |-- QueryClientProvider (staleTime config)
  |-- Sidebar.tsx
  |-- TopBar.tsx (onCommandK)
  |-- CommandPalette.tsx
  |-- ErrorBoundary.tsx
  |-- Routes
       |
       |-- DashboardPage.tsx
       |     |-- useDateRange() --> URL search params
       |     |-- useDashboard(dateRange) --> /api/dashboard?from=...&to=...
       |     |-- useDashboardDeltas(dateRange) --> /api/dashboard/deltas?from=...&to=...
       |     |-- useActivityCalendar(90) --> /api/dashboard/activity-calendar?days=90
       |     |-- MetricCard (x4)
       |     |-- HeatmapGrid (activity calendar)
       |     |-- AreaChart (sparkline, cost trend)
       |     |-- ExportDropdown
       |
       |-- CostPage.tsx
       |     |-- useDateRange()
       |     |-- useCostAnalysis(dateRange) --> /api/cost?from=...&to=...
       |     |-- useCostAnomalies(dateRange) --> /api/cost/anomalies?from=...&to=...
       |     |-- useCumulativeCost(dateRange) --> /api/cost/cumulative?from=...&to=...
       |     |-- MetricCard, AreaChart, BarChart, PieChart
       |     |-- BudgetTracker, CacheCalculator
       |
       |-- ProductivityPage.tsx
       |     |-- useDateRange()
       |     |-- useProductivityAnalysis(dateRange) --> /api/productivity?from=...&to=...
       |     |-- useEfficiencyTrend, useLanguageTrend, useToolSuccessTrend, useFileChurn
       |
       |-- AnalyticsPage.tsx
       |     |-- useDateRange()
       |     |-- useAnalytics(dateRange) --> /api/analytics?from=...&to=...
       |     |-- useThinkingTrend, useCacheTrend
       |
       |-- ModelComparisonPage.tsx
       |     |-- useDateRange()
       |     |-- useModelComparison(dateRange)
       |     |-- RadarChart, ScatterChart, BarChart
       |
       |-- WorkflowPage.tsx
       |     |-- useDateRange()
       |     |-- useWorkflows(dateRange)
       |     |-- PieChart, AreaChart, AgentTreeView
       |
       |-- HeatmapPage.tsx
       |     |-- useDateRange()
       |     |-- useHeatmap(dateRange, metric)
       |     |-- HeatmapGrid
       |
       |-- ExplorerPage.tsx
       |     |-- useDateRange() + local state (metric, group_by, split_by, filters)
       |     |-- useExplorerQuery, useFilterOptions
       |     |-- Dynamic chart rendering
       |
       |-- ProjectsPage.tsx, ProjectDetailPage.tsx
       |-- SessionsPage.tsx, SessionDetailPage.tsx
       |-- ExperimentsPage.tsx
       |-- LiveMonitorPage.tsx (WebSocket)
       |-- SettingsPage.tsx

Shared Components:
  |-- DateRangePicker.tsx (used in PageLayout via TopBar)
  |-- PageLayout.tsx (title, subtitle, actions slot)
  |-- MetricCard.tsx, ChartCard.tsx, DeltaBadge.tsx
  |-- HeatmapGrid.tsx, AgentTreeView.tsx, TokenWaterfall.tsx
  |-- LoadingState, ErrorState, EmptyState
  |-- ExportDropdown.tsx

Shared Hooks:
  |-- useDateRange.ts (URL state)
  |-- useExport.ts (CSV/JSON generation)
  |-- useWebSocket.ts (live monitor)
  |-- useTheme.ts (dark/light mode)
  |-- useLocalStorage.ts (user preferences)
  |-- useKeyboardShortcuts.ts (Cmd+K)

Shared Libraries:
  |-- lib/utils.ts (cn, formatCurrency, formatNumber, formatPercent, formatDuration, toDateStr*, parseDateStr*)
  |-- lib/chartConfig.ts (TOOLTIP_STYLE, AXIS_STYLE, CHART_COLORS, TOKEN_COLORS, fillZeros, getStaleTime*, shouldAnimate*)
  |-- api/client.ts (apiFetch, buildQuery, ApiError)
  |-- api/keys.ts (query key factories)

  * = new in this refactor
```

## Appendix C: Date/Time Data Flow Diagram

```
+------------------+     +------------------+     +-------------------+
| JSONL Files      |     | ETL (Python)     |     | SQLite Database   |
| UTC ISO-8601     | --> | Parse datetime   | --> | TEXT columns       |
| "2026-02-08T     |     | Store .isoformat |     | UTC ISO-8601      |
|  03:15:22Z"      |     | (no conversion)  |     | "2026-02-08T      |
+------------------+     +------------------+     |  03:15:22.000000" |
                                                  +-------------------+
                                                          |
                                    +---------------------+---------------------+
                                    |                                           |
                          +---------v-----------+                   +-----------v---------+
                          | Raw Queries         |                   | Materialization     |
                          | date(ts,'localtime')|                   | date(ts,'localtime')|
                          | = "2026-02-07"      |                   | = "2026-02-07"      |
                          | (EST = UTC-5)       |                   | Stored as PK in     |
                          +----------+----------+                   | daily_summaries     |
                                     |                              +----------+----------+
                                     |                                         |
                          +----------v----------+                   +----------v----------+
                          | FastAPI Response    |                   | daily_summaries     |
                          | {"date":"2026-02-07"|                   | date TEXT PK        |
                          |  "cost": 1.23}      |                   | = "2026-02-07"      |
                          +----------+----------+                   +---------------------+
                                     |
                          +----------v----------+
                          | React Frontend      |
                          | parseDateStr(       |
                          |  "2026-02-07")      |
                          | = new Date(         |
                          |   "2026-02-07T      |
                          |    00:00:00")       |
                          | = Feb 7 local       |
                          +---------------------+
                                     |
                          +----------v----------+
                          | User sees:          |
                          | "Feb 7" in chart    |
                          | Matches their       |
                          | wall clock date     |
                          +---------------------+

DATE RANGE FLOW (user action):
+---------------------+     +-----------------------+     +------------------+
| DateRangePicker     |     | useDateRange() hook   |     | URL Search Params|
| User clicks         | --> | toDateStr(new Date()) | --> | ?from=2026-01-09 |
| "Last 30 Days"      |     | = "2026-02-08" local  |     | &to=2026-02-08   |
+---------------------+     +-----------------------+     +--------+---------+
                                                                   |
                                                          +--------v---------+
                                                          | API Hook         |
                                                          | useQuery({       |
                                                          |   queryKey: [    |
                                                          |     "dashboard", |
                                                          |     "2026-01-09",|
                                                          |     "2026-02-08" |
                                                          |   ]})            |
                                                          +--------+---------+
                                                                   |
                                                          +--------v---------+
                                                          | HTTP GET         |
                                                          | /api/dashboard   |
                                                          |   ?from=2026-.. |
                                                          |   &to=2026-..   |
                                                          +--------+---------+
                                                                   |
                                                          +--------v---------+
                                                          | FastAPI Route    |
                                                          | DateRangeParams  |
                                                          | validates format |
                                                          +--------+---------+
                                                                   |
                                                          +--------v---------+
                                                          | Query Layer      |
                                                          | build_date_filter|
                                                          | ("t.timestamp",  |
                                                          |  "2026-01-09",   |
                                                          |  "2026-02-08",   |
                                                          |  params)         |
                                                          +--------+---------+
                                                                   |
                                                          +--------v---------+
                                                          | SQL              |
                                                          | WHERE date(      |
                                                          |   t.timestamp,   |
                                                          |   'localtime')   |
                                                          |  >= '2026-01-09' |
                                                          +------------------+
```
