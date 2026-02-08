# CCWAP Phase 2 Architecture Review

## 1. Executive Summary

This document covers the comprehensive architecture plan for CCWAP Phase 2: a 13-feature expansion of the existing Python CLI + FastAPI + React/TypeScript web dashboard that analyzes Claude Code usage from JSONL logs. The existing codebase follows well-established conventions -- two-query SQL pattern, lazy-loaded React pages, URL-param date filtering, Pydantic v2 response models, and TanStack React Query v5 with query key factories.

Phase 2 adds 3 new pages (Hourly Heatmap, Model Comparison, User Types/Workflow), 1 new project detail sub-page, and significant enhancements to all 10 existing pages. The changes span roughly 25 new backend query functions, 15 new API endpoints, 4 new frontend pages/sub-pages, 8 modified pages, 12+ new shared components, 6 new React hooks, and 1 new npm dependency (cmdk for Cmd+K search).

The architecture strategy is: **no schema changes** (the existing 7-table schema already contains all needed data), **no new backend dependencies**, **one new frontend dependency** (cmdk ~7KB), and strict adherence to existing conventions (two-query pattern, Pydantic response models, query key factories, lazy-loaded pages, CSS-variable-based theming). All new features are additive; no breaking changes to existing API contracts or routes.

Implementation is organized into 6 ordered phases over approximately 18-22 implementation sessions, with infrastructure/shared components first, then page enhancements in dependency order.

---

## 2. Requirements Analysis

### 2.1 Functional Requirements (Prioritized)

**Must-Have (P0)**
- F4: Analytics page visualization replacement (replaces generic DictTable with real charts)
- F5: Dashboard delta badges and activity calendar
- F6: Session Detail token waterfall and tool timeline
- F13: Cmd+K global search, keyboard shortcuts, data freshness indicator

**Should-Have (P1)**
- F1: Experiments page project dropdown and multi-tag comparison
- F2: Hourly Activity Heatmap page (new)
- F3: Model Comparison page (new)
- F7: Projects drill-down page
- F9: Cost page budget tracking and anomaly detection

**Could-Have (P2)**
- F8: User Types/Workflow Analysis page (new)
- F10: Productivity page enhancements
- F11: Live Monitor enhancements
- F12: Settings export and custom presets

### 2.2 Non-Functional Requirements

| NFR | Threshold |
|-----|-----------|
| Page load (data fetch) | < 500ms for date ranges under 90 days |
| SQLite query time | < 200ms per query on 100K+ turn databases |
| Frontend bundle | New pages add < 30KB gzipped total |
| WebSocket reconnection | Exponential backoff, max 30s (already implemented) |
| Accessibility | All interactive elements keyboard-navigable |
| Theme support | Light + dark mode via existing CSS variable system |
| Browser support | Chrome/Edge/Firefox last 2 versions |

### 2.3 Constraints & Assumptions

**Constraints**
- SQLite single-file database (no schema version bump required -- all data already exists)
- Zero new Python backend dependencies (all queries are pure SQL)
- Single aiosqlite connection shared across all endpoints
- Existing two-query pattern must be followed for all new queries
- Windows file paths in project_path (backslashes, colons) -- must be URL-encoded in route params

**Assumptions**
- daily_summaries table is populated by ETL (verified -- existing ETL handles this)
- The user_type column in turns table is populated (used for human vs agent breakdown)
- parent_session_id in sessions is populated for agent-spawned sessions
- Tool call timestamps are reliable for timeline visualizations
- The existing `color-mix(in srgb, ...)` pattern works in target browsers (verified in SessionDetailPage)

### 2.4 Gaps & Clarifications Needed

1. **Workflow Patterns (F8)**: "Common tool sequences" is underspecified. Architecture assumes: query last N tool calls per session, find repeated 2-3 tool sequences via sliding window, present top-10 patterns. This is compute-intensive; may need caching or a materialized table if slow.
2. **Cost Anomaly Detection (F9)**: "2 sigma days" assumes normal distribution. With limited data points (e.g., 30 days), Z-score approach is fragile. Architecture uses IQR-based outlier detection as fallback.
3. **What-If Cache Calculator (F9)**: Requires per-model pricing data to be available in the frontend. Currently pricing is server-side only. Architecture adds a pricing summary to the cost API response.
4. **File Churn Treemap (F10)**: Recharts Treemap requires hierarchical data. Architecture maps file_path to directory hierarchy.

---

## 3. Architecture Decisions

### ADR-001: No Database Schema Changes

- **Context**: All 13 features require data already present in the existing 7-table schema. Adding new tables or columns would require a schema migration (v3->v4), ETL changes, and potential re-processing.
- **Decision**: No schema changes. All new features are served by new SQL queries against existing tables.
- **Status**: Accepted
- **Consequences**:
  - (+) Zero migration risk, no ETL changes, no re-processing
  - (+) Existing CLI reports continue working unchanged
  - (-) Some queries (workflow patterns, hourly heatmap) will be slightly more complex SQL
  - (-) daily_summaries does not have hourly granularity; hourly heatmap must query turns directly
- **Alternatives Considered**: Adding an hourly_summaries materialized table. Rejected because the turns table with the idx_turns_timestamp index is sufficient, and adding a table requires ETL changes.

### ADR-002: Single New Frontend Dependency (cmdk)

- **Context**: Cmd+K global search requires a command palette component. Options: build from scratch, use cmdk, use kbar.
- **Decision**: Add cmdk (~7KB gzipped). It is unstyled (composable with Tailwind), accessible, and provides fuzzy search out of the box.
- **Status**: Accepted
- **Consequences**:
  - (+) Accessible, keyboard-driven, well-tested
  - (+) Unstyled -- integrates with existing Tailwind/CSS variable theming
  - (+) Tiny bundle impact
  - (-) One more dependency to maintain
- **Alternatives Considered**: kbar (heavier, more opinionated styling), building from scratch (2-3 days of work, less accessible).

### ADR-003: CSS Grid Heatmap (No Chart Library)

- **Context**: Heatmaps are not supported by Recharts. Options: add d3-heatmap, add nivo, or build with pure CSS Grid.
- **Decision**: Build the 7x24 heatmap (168 cells) with CSS Grid and `color-mix()` for intensity. This matches the existing pattern in SessionDetailPage's TurnBlock component.
- **Status**: Accepted
- **Consequences**:
  - (+) Zero additional dependencies
  - (+) Full control over styling, theme-aware via CSS variables
  - (+) Matches existing codebase pattern
  - (-) No built-in tooltip; must implement custom tooltip positioning

### ADR-004: Custom SVG for Tool Call Timeline (Gantt)

- **Context**: Session Detail needs a Gantt-style tool call timeline. Options: add a Gantt library, use Recharts (not suitable), build custom SVG.
- **Decision**: Build custom SVG component. The codebase already has the CostOverlayLine custom SVG component in SessionDetailPage, establishing this pattern.
- **Status**: Accepted
- **Consequences**:
  - (+) Zero dependencies, full control
  - (+) Follows established pattern
  - (-) More implementation effort (~2 hours)

### ADR-005: Project Path Encoding Strategy

- **Context**: Project paths contain backslashes and colons (e.g., `C:\testprojects\foo`). These break URL routing if used raw in `/projects/:path`.
- **Decision**: Base64url-encode project paths in URL parameters. The frontend encodes with `btoa()` and the backend decodes. Query parameters use standard URL encoding.
- **Status**: Accepted
- **Consequences**:
  - (+) Safe for all path characters
  - (+) Deterministic, reversible
  - (-) URLs are not human-readable for the path segment

### ADR-006: localStorage for All User Preferences

- **Context**: Multiple features require persisting user preferences (dashboard vitals config, cost budget, custom date presets, notification thresholds).
- **Decision**: Use localStorage with a `ccwap:` prefix for all user preferences. No backend storage needed.
- **Status**: Accepted
- **Consequences**:
  - (+) Zero backend changes
  - (+) Instant read/write, no network latency
  - (+) Per-browser personalization
  - (-) Not synced across browsers/devices (acceptable for a local analytics tool)

### ADR-007: Multi-Tag Comparison Architecture

- **Context**: Current experiments API only supports comparing 2 tags. Feature requires 3-4 tag comparison.
- **Decision**: Extend the `/api/experiments/compare` endpoint to accept a `tags` query parameter (comma-separated list, 2-4 tags). Return a ComparisonMatrixResponse with metrics per tag.
- **Status**: Accepted
- **Consequences**:
  - (+) Single endpoint, single request for all tags
  - (+) Backend can parallelize per-tag metric computation
  - (-) Existing `tag_a`/`tag_b` params become deprecated (maintain backward compatibility)

### ADR-008: Search API Architecture

- **Context**: Cmd+K search needs to search across pages, projects, sessions, models, branches, and tags.
- **Decision**: Single `/api/search` endpoint with `q` parameter. Returns categorized results from multiple table queries (sessions, projects via DISTINCT project_path, experiment_tags via DISTINCT tag_name). Limited to top 5 per category.
- **Status**: Accepted
- **Consequences**:
  - (+) Single round-trip for all search results
  - (+) Server-side search is fast with existing indexes
  - (-) No full-text search index; uses LIKE '%query%' which does not use indexes for leading wildcards. Acceptable because datasets are small (< 1M rows).

---

## 4. Technical Architecture Overview

### 4.1 System Decomposition

The architecture remains a monolithic FastAPI application with a React SPA frontend. No microservices, no external databases. The decomposition is:

```
ccwap/
  server/
    routes/        # 12 route modules (9 existing + 3 new)
    queries/       # 12 query modules (9 existing + 3 new)
    models/        # 12 Pydantic model modules (9 existing + 3 new)
    app.py         # App factory (unchanged)
    dependencies.py # DI (unchanged)
    websocket.py   # WS manager (minor extension)
    file_watcher.py # File watcher (minor extension)

  frontend/src/
    pages/         # 14 pages (10 existing + 4 new)
    components/    # Shared components (7 existing + 12 new)
    components/ui/ # UI primitives (4 existing + 5 new)
    hooks/         # React hooks (4 existing + 6 new)
    api/           # API clients (10 existing + 4 new)
    lib/           # Utilities (1 existing, extended)
```

### 4.2 Data Architecture

**No schema changes.** All 7 tables remain as-is. New queries derive all needed data from existing columns:

| Feature | Primary Tables | Key Columns |
|---------|---------------|-------------|
| Hourly Heatmap | turns, tool_calls, sessions | timestamp (extract hour, day-of-week) |
| Model Comparison | turns, tool_calls, sessions | model, cost, tokens, thinking_chars |
| User Types | sessions, turns | is_agent, parent_session_id, user_type |
| Workflow Patterns | tool_calls, sessions | tool_name, session_id, timestamp ordering |
| Budget Tracking | (frontend-only) | localStorage |
| Cost Anomaly | daily_summaries | cost, date |
| Cache Calculator | turns | cache_read_tokens, input_tokens, cost |
| Activity Calendar | daily_summaries | date, cost/sessions/loc_written |

### 4.3 Integration Architecture

**API Layer**: REST over HTTP (existing pattern). No new protocols.

**WebSocket**: Extended with 2 new message types:
1. `active_session` -- broadcasts when file watcher detects an active session
2. `daily_cost_update` -- periodic broadcast of today's running cost total

**Data Flow**: All pages follow the established pattern:
```
Page Component
  -> useDateRange() hook (URL params)
  -> useXxxData(dateRange) hook (TanStack Query)
  -> apiFetch('/api/xxx?from=...&to=...')
  -> FastAPI route handler
  -> query function (2-query pattern)
  -> aiosqlite -> SQLite
```

### 4.4 Security Architecture

No changes needed. The application is a local-only dashboard:
- No authentication (local tool, single user)
- CSV export sanitization (prefix cells starting with `=`, `+`, `-`, `@` with a tab character) -- already partially addressed in useExport, needs hardening
- No user input reaches SQL without parameterized queries (existing pattern, enforced in all new queries)

### 4.5 Infrastructure & Deployment

No changes. The build process remains:
```
cd frontend && npm run build   # outputs to ccwap/static/
python -m ccwap web            # starts FastAPI + serves SPA
```

### 4.6 Observability

No changes. The existing pattern (console logging, WebSocket event broadcasting) continues.

---

## 5. Technology Stack Recommendations

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Charts | Recharts 3.7 (existing) | Handles all new chart types: RadarChart, Treemap, ScatterChart, stacked AreaChart, grouped BarChart, Pie with innerRadius (donut) |
| Heatmap | Pure CSS Grid + color-mix() | No library needed; 168 cells, matches existing pattern |
| Gantt Timeline | Custom SVG | Follows CostOverlayLine pattern already in codebase |
| Command Palette | cmdk ~7KB (new) | Unstyled, accessible, fuzzy search |
| Agent Tree | Pure CSS/HTML | Start simple; react-d3-tree (~25KB) only if pure CSS proves inadequate |
| State: User Prefs | localStorage | Zero backend, instant, prefix `ccwap:` |
| State: Filter Params | URL search params | Existing pattern via useDateRange |

**No new backend dependencies.** All new backend code is pure Python + aiosqlite + Pydantic.

---

## 6. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Hourly heatmap query slow on large DBs (no hourly index) | Medium | Medium | Add covering index `idx_turns_timestamp_hour` on `strftime('%H', timestamp)` if needed. Or pre-compute via daily_summaries enhancement. |
| R2 | Workflow pattern detection (sliding window on tool sequences) is O(n) per session | Medium | Medium | Limit to sessions within date range. Cache results. Cap at 1000 sessions per query. |
| R3 | Multi-tag comparison with 4 tags = 4x query load | Low | Low | Each tag query is lightweight (IN-clause on session_ids). 4 parallel calls still < 100ms. |
| R4 | Recharts Treemap for file churn renders poorly with > 200 nodes | Medium | Low | Cap at top 50 files. Group remaining into "Other" bucket. |
| R5 | CSS Grid heatmap tooltip positioning breaks on small viewports | Low | Low | Use fixed position tooltip anchored to cursor. Tested pattern. |
| R6 | Base64-encoded project paths create ugly URLs | Low | Low | Acceptable trade-off. Users rarely share/bookmark project detail URLs. |
| R7 | cmdk version compatibility with React 19 | Low | Medium | cmdk 1.x is React 18/19 compatible. Pin to tested version. |
| R8 | Gradient ID collisions across multiple charts on same page | Medium | Low | Use unique gradient IDs per chart section (prefix with chart name). Research findings flagged this. |
| R9 | WebSocket message flood from frequent ETL updates | Low | Medium | 1-second debounce on broadcast (already partially in place). Add throttle wrapper. |
| R10 | Stacked charts fail when some keys have no data for a date | Medium | Low | Fill zeros for missing keys in query results. Research findings flagged this. |

---

## 7. New API Endpoints

### 7.1 Search

```
GET /api/search?q={query}&limit={5}
```

Response:
```python
class SearchResult(BaseModel):
    category: str          # "page" | "project" | "session" | "model" | "branch" | "tag"
    label: str             # Display text
    sublabel: str = ""     # Secondary text
    url: str               # Frontend route to navigate to

class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
```

### 7.2 Heatmap

```
GET /api/heatmap?from={date}&to={date}&metric={sessions|cost|loc|tool_calls}
```

Response:
```python
class HeatmapCell(BaseModel):
    day: int        # 0=Monday, 6=Sunday
    hour: int       # 0-23
    value: float
    count: int      # number of data points contributing

class HeatmapResponse(BaseModel):
    cells: List[HeatmapCell]
    max_value: float
    metric: str
```

### 7.3 Model Comparison

```
GET /api/models?from={date}&to={date}
```

Response:
```python
class ModelMetrics(BaseModel):
    model: str
    turns: int = 0
    cost: float = 0.0
    avg_cost_per_turn: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    avg_tokens_per_turn: float = 0.0
    thinking_rate: float = 0.0
    error_rate: float = 0.0
    cache_hit_rate: float = 0.0
    loc_written: int = 0

class ModelUsageTrend(BaseModel):
    date: str
    model_counts: Dict[str, int]    # model -> turn count for that date

class ModelScatterPoint(BaseModel):
    model: str
    session_id: str
    cost: float
    loc: int

class ModelComparisonResponse(BaseModel):
    models: List[ModelMetrics]
    usage_trend: List[ModelUsageTrend]
    scatter: List[ModelScatterPoint]
```

### 7.4 User Types / Workflow

```
GET /api/workflows?from={date}&to={date}
```

Response:
```python
class UserTypeBreakdown(BaseModel):
    human_sessions: int = 0
    agent_sessions: int = 0
    human_cost: float = 0.0
    agent_cost: float = 0.0
    trend: List[Dict]      # [{date, human, agent}, ...]

class AgentTree(BaseModel):
    session_id: str
    project_display: str
    cost: float
    turns: int
    children: List['AgentTree'] = []

class ToolSequence(BaseModel):
    sequence: List[str]     # e.g., ["Read", "Edit", "Bash"]
    count: int
    avg_cost: float

class WorkflowResponse(BaseModel):
    user_types: UserTypeBreakdown
    agent_trees: List[AgentTree]       # Top-level parent sessions
    tool_sequences: List[ToolSequence]  # Top 10 patterns
```

### 7.5 Project Detail

```
GET /api/projects/{encoded_path}/detail?from={date}&to={date}
```

Response:
```python
class ProjectCostTrend(BaseModel):
    date: str
    cost: float

class ProjectLanguage(BaseModel):
    language: str
    loc: int
    percentage: float

class ProjectTool(BaseModel):
    tool_name: str
    calls: int
    success_rate: float

class ProjectBranch(BaseModel):
    branch: str
    sessions: int
    cost: float

class ProjectSession(BaseModel):
    session_id: str
    first_timestamp: str
    cost: float
    turns: int
    model: str

class ProjectDetailResponse(BaseModel):
    project_path: str
    project_display: str
    cost_trend: List[ProjectCostTrend]
    languages: List[ProjectLanguage]
    tools: List[ProjectTool]
    branches: List[ProjectBranch]
    sessions: List[ProjectSession]
    total_cost: float
    total_sessions: int
    total_loc: int
```

### 7.6 Extended Analytics Endpoints

```
GET /api/analytics/thinking-trend?from={date}&to={date}
```
Returns `List[{date, model, thinking_chars}]` for sparkline trend.

```
GET /api/analytics/cache-trend?from={date}&to={date}
```
Returns `List[{date, ephemeral_5m, ephemeral_1h, standard_cache}]` for stacked area chart.

### 7.7 Extended Cost Endpoints

```
GET /api/cost/anomalies?from={date}&to={date}
```
Returns `List[{date, cost, zscore, is_anomaly}]` for anomaly highlighting.

```
GET /api/cost/cumulative?from={date}&to={date}
```
Returns `List[{date, daily_cost, cumulative_cost}]` for running total chart.

```
GET /api/cost/cache-simulation?cache_hit_rate={0.0-1.0}
```
Returns `{actual_cost, simulated_cost, savings, savings_pct}` for what-if calculator.

### 7.8 Extended Productivity Endpoints

```
GET /api/productivity/efficiency-trend?from={date}&to={date}
```
Returns `List[{date, cost_per_kloc}]` for LOC efficiency trend.

```
GET /api/productivity/language-trend?from={date}&to={date}
```
Returns `List[{date, language, loc}]` for stacked area chart.

```
GET /api/productivity/tool-success-trend?from={date}&to={date}
```
Returns `List[{date, tool_name, success_rate}]` for line chart.

```
GET /api/productivity/file-churn?from={date}&to={date}&limit={50}
```
Returns `List[{file_path, directory, edit_count, loc_written, language}]` for treemap.

### 7.9 Extended Experiments Endpoints

```
GET /api/experiments/compare-multi?tags={tag1,tag2,tag3}&from={date}&to={date}
```
Returns multi-tag comparison matrix.

```
GET /api/experiments/tag/{tag_name}/sessions?from={date}&to={date}
```
Returns list of sessions for a specific tag (for drill-down).

### 7.10 Extended Dashboard Endpoint

```
GET /api/dashboard/activity-calendar?days={90}
```
Returns `List[{date, value}]` for GitHub-style heatmap (90 days).

```
GET /api/dashboard/deltas
```
Returns `{sessions_delta, cost_delta, loc_delta, error_rate_delta}` comparing current period to previous period.

### 7.11 Settings Export

```
GET /api/settings/export?format={csv|json}
```
Returns a ZIP file containing all table data.

---

## 8. New Database Queries

All queries follow the established two-query pattern. Here are the key new query functions:

### 8.1 Heatmap Query Module (`ccwap/server/queries/heatmap_queries.py`)

```python
async def get_heatmap_data(
    db: aiosqlite.Connection,
    date_from: Optional[str],
    date_to: Optional[str],
    metric: str = "sessions",
) -> Dict[str, Any]:
    """
    Hourly activity heatmap. Groups by day-of-week (0-6) and hour (0-23).

    For 'sessions' and 'cost': query turns table (strftime on timestamp).
    For 'loc' and 'tool_calls': query tool_calls table.
    """
```

Key SQL (sessions metric):
```sql
SELECT
    CAST(strftime('%w', timestamp) AS INTEGER) as dow,
    CAST(strftime('%H', timestamp) AS INTEGER) as hour,
    COUNT(DISTINCT session_id) as value
FROM turns
WHERE timestamp IS NOT NULL
  AND date(timestamp) >= ? AND date(timestamp) <= ?
GROUP BY dow, hour
```

Note: SQLite `strftime('%w', ...)` returns 0=Sunday. Remap in Python to 0=Monday.

### 8.2 Model Comparison Query Module (`ccwap/server/queries/model_queries.py`)

```python
async def get_model_metrics(db, date_from, date_to) -> List[Dict]:
    """Model comparison metrics. Two-query pattern."""
    # Q1: turns aggregates grouped by model
    # Q2: tool_calls aggregates grouped by model (via JOIN on session_id -> turns.model)

async def get_model_usage_trend(db, date_from, date_to) -> List[Dict]:
    """Daily model usage counts for stacked area chart."""

async def get_model_scatter(db, date_from, date_to) -> List[Dict]:
    """Per-session cost vs LOC by model. Two-query pattern."""
```

### 8.3 Workflow Query Module (`ccwap/server/queries/workflow_queries.py`)

```python
async def get_user_type_breakdown(db, date_from, date_to) -> Dict:
    """Human vs Agent session counts and costs."""
    # Uses sessions.is_agent

async def get_agent_trees(db, date_from, date_to) -> List[Dict]:
    """Agent session parent-child trees."""
    # Uses sessions.parent_session_id
    # Recursive CTE or iterative Python assembly

async def get_tool_sequences(db, date_from, date_to, window_size=3) -> List[Dict]:
    """Common tool call sequences. Sliding window analysis."""
    # Fetches tool_calls ordered by session_id, timestamp
    # Python-side sliding window to find patterns
```

### 8.4 Project Detail Query Module (`ccwap/server/queries/project_detail_queries.py`)

```python
async def get_project_detail(db, project_path, date_from, date_to) -> Dict:
    """Full project detail. Two-query pattern plus sub-queries."""
    # Q1: turns -> cost trend, model breakdown
    # Q2: tool_calls -> language breakdown, tool usage, file hotspots
    # Q3: sessions -> session timeline, branch comparison
```

### 8.5 Search Query Module (`ccwap/server/queries/search_queries.py`)

```python
async def search_all(db, query: str, limit: int = 5) -> List[Dict]:
    """Cross-entity search for Cmd+K."""
    # Parallel LIKE queries on:
    # - sessions.project_display, sessions.session_id
    # - DISTINCT project_path from sessions
    # - DISTINCT tag_name from experiment_tags
    # - DISTINCT model from turns
    # - DISTINCT git_branch from sessions
    # Static page matches from hardcoded list
```

### 8.6 Extended Analytics Queries (add to `analytics_queries.py`)

```python
async def get_thinking_trend(db, date_from, date_to) -> List[Dict]:
    """Daily thinking chars by model for sparkline."""

async def get_cache_trend(db, date_from, date_to) -> List[Dict]:
    """Daily cache tier breakdown for stacked area."""
```

### 8.7 Extended Cost Queries (add to `cost_queries.py`)

```python
async def get_cost_anomalies(db, date_from, date_to) -> List[Dict]:
    """Days with cost > 2 sigma from mean. Uses IQR fallback."""

async def get_cumulative_cost(db, date_from, date_to) -> List[Dict]:
    """Running cumulative cost total per day."""

async def get_cache_simulation(db, target_hit_rate: float) -> Dict:
    """What-if cache calculator."""
```

### 8.8 Extended Productivity Queries (add to `productivity_queries.py`)

```python
async def get_efficiency_trend(db, date_from, date_to) -> List[Dict]:
    """Daily cost/kLOC trend."""

async def get_language_trend(db, date_from, date_to) -> List[Dict]:
    """Daily language mix for stacked area."""

async def get_tool_success_trend(db, date_from, date_to) -> List[Dict]:
    """Daily tool success rates for line chart."""

async def get_file_churn(db, date_from, date_to, limit=50) -> List[Dict]:
    """Top files by edit count for treemap."""
```

---

## 9. New Frontend Pages

### 9.1 Hourly Activity Heatmap (`/heatmap`)

**Route**: `/heatmap`
**File**: `ccwap/frontend/src/pages/HeatmapPage.tsx`
**Data**: `useHeatmap(dateRange, metric)` hook via `/api/heatmap`

**Components**:
- `HeatmapGrid` -- 7 rows x 24 columns CSS Grid with intensity coloring
- `HeatmapCell` -- individual cell with tooltip on hover
- Metric toggle (sessions | cost | LOC | tool_calls)
- Color legend bar

**Layout**: PageLayout + DateRangePicker + metric toggle + full-width grid

### 9.2 Model Comparison (`/models`)

**Route**: `/models`
**File**: `ccwap/frontend/src/pages/ModelComparisonPage.tsx`
**Data**: `useModelComparison(dateRange)` hook via `/api/models`

**Components**:
- Side-by-side metric cards per model
- Recharts `RadarChart` for multi-metric comparison
- Recharts stacked `AreaChart` for usage over time
- Recharts `ScatterChart` for cost vs LOC

### 9.3 User Types / Workflow (`/workflows`)

**Route**: `/workflows`
**File**: `ccwap/frontend/src/pages/WorkflowPage.tsx`
**Data**: `useWorkflows(dateRange)` hook via `/api/workflows`

**Components**:
- Recharts `PieChart` (human vs agent) + stacked `AreaChart` trend
- `AgentTreeView` -- CSS tree layout for parent-child sessions
- `ToolSequenceList` -- ranked list of common sequences with frequency bar

### 9.4 Project Detail (`/projects/:path`)

**Route**: `/projects/:path`
**File**: `ccwap/frontend/src/pages/ProjectDetailPage.tsx`
**Data**: `useProjectDetail(path, dateRange)` hook via `/api/projects/{path}/detail`

**Components**:
- Cost trend `AreaChart`
- Language breakdown `PieChart` (donut)
- Tool usage horizontal `BarChart`
- Branch comparison grouped `BarChart`
- Session timeline list with drill-down links

---

## 10. Modified Existing Pages

### 10.1 Dashboard (`/`)

**Changes**:
- Add configurable vitals strip (localStorage for selected metrics)
- Add 90-day activity calendar widget (GitHub-style heatmap, reuses HeatmapCell component)
- Add delta badges to MetricCard ("+12% vs last period")
- Add cost alert threshold indicator (localStorage-based)

**New hook**: `useLocalStorage(key, defaultValue)` for preferences
**New component**: `ActivityCalendar` (90-day mini heatmap)
**Modified component**: `MetricCard` -- add `delta` and `deltaLabel` props

### 10.2 Analytics (`/analytics`)

**Changes**:
- Replace all `DictTable` instances with proper Recharts visualizations:
  - Thinking by model: `BarChart` + sparkline trend
  - Truncation: `PieChart` (donut) of stop reasons
  - Sidechains: stacked `BarChart` by project
  - Cache tiers: stacked `AreaChart` over time
  - Branches: horizontal `BarChart`
  - Versions: `LineChart` of avg turn cost over versions

**New API calls**: `useThinkingTrend`, `useCacheTrend` (additional data for trends)

### 10.3 Experiments (`/experiments`)

**Changes**:
- Replace raw text input for project_path with project dropdown (fetch from `/api/projects`)
- Reuse DateRangePicker for date filtering in tag creation
- Multi-tag comparison (3-4 tags) with grouped `BarChart` + `RadarChart`
- Tag detail view (click tag -> see sessions list)

**New API hook**: `useMultiTagComparison(tags[])`
**New API hook**: `useTagSessions(tagName)`

### 10.4 Session Detail (`/sessions/:id`)

**Changes**:
- Add token waterfall chart (stacked `BarChart` per turn: input/output/cache_read/cache_write)
- Toggle cost view vs token view
- Add tool call timeline (custom SVG Gantt-style)
- Add thinking chars as secondary Y-axis on timeline scrubber

**New components**: `TokenWaterfall`, `ToolTimeline`
**New state**: `viewMode: 'cost' | 'tokens'` (useState)

### 10.5 Projects (`/projects`)

**Changes**:
- Add click-through to project detail page (`/projects/:path`)
- Add project comparison mode (select 2-3 projects, side-by-side)

**New component**: `ProjectComparisonPanel`
**New state**: `selectedProjects: string[]` (useState)

### 10.6 Cost (`/cost`)

**Changes**:
- Add budget tracking section (monthly budget input, progress bar, burn rate)
- Add cost anomaly detection (highlighted days on chart)
- Add cumulative cost chart
- Add "what-if" cache calculator (slider + simulated cost display)

**New hooks**: `useLocalStorage` (for budget), `useCostAnomalies`, `useCumulativeCost`, `useCacheSimulation`
**New components**: `BudgetTracker`, `CacheCalculator`, `AnomalyChart`

### 10.7 Productivity (`/productivity`)

**Changes**:
- Add LOC efficiency trend (cost/kLOC over time line chart)
- Add language trend (stacked area)
- Add tool success rate trend (line chart)
- Add file churn treemap

**New hooks**: `useEfficiencyTrend`, `useLanguageTrend`, `useToolSuccessTrend`, `useFileChurn`

### 10.8 Live Monitor (`/live`)

**Changes**:
- Add real-time cost ticker (animated counter using CSS transitions)
- Add active session indicator (project/branch badge from WebSocket)
- Add mini dashboard (live vitals for current day -- reuses dashboard API)

**New component**: `CostTicker`, `ActiveSessionBadge`
**WebSocket extension**: `active_session` message type

### 10.9 Settings (`/settings`)

**Changes**:
- Add full database export button (triggers `/api/settings/export`)
- Add custom date range presets editor (localStorage)
- Add notification thresholds editor (localStorage)

**New component**: `CustomPresetsEditor`, `ThresholdEditor`

---

## 11. New Shared Components

### 11.1 Components to Create

| Component | File | Purpose |
|-----------|------|---------|
| `CommandPalette` | `components/CommandPalette.tsx` | Cmd+K global search overlay (uses cmdk) |
| `HeatmapGrid` | `components/charts/HeatmapGrid.tsx` | Reusable CSS Grid heatmap (used by Heatmap page + Dashboard calendar) |
| `HeatmapCell` | `components/charts/HeatmapCell.tsx` | Single cell with tooltip |
| `ToolTimeline` | `components/charts/ToolTimeline.tsx` | Custom SVG Gantt-style tool call timeline |
| `TokenWaterfall` | `components/charts/TokenWaterfall.tsx` | Stacked bar chart of token types per turn |
| `AgentTreeView` | `components/charts/AgentTreeView.tsx` | CSS tree layout for parent-child sessions |
| `BudgetTracker` | `components/BudgetTracker.tsx` | Progress bar + burn rate |
| `CacheCalculator` | `components/CacheCalculator.tsx` | Slider-based what-if cache simulation |
| `DeltaBadge` | `components/ui/DeltaBadge.tsx` | "+12%" style delta indicator |
| `CostTicker` | `components/ui/CostTicker.tsx` | Animated cost counter |
| `ActiveSessionBadge` | `components/ui/ActiveSessionBadge.tsx` | Real-time session indicator |
| `ChartCard` | `components/ui/ChartCard.tsx` | Standardized wrapper: title + chart + optional legend |

### 11.2 Components to Modify

| Component | Change |
|-----------|--------|
| `MetricCard` | Add `delta`, `deltaLabel`, `deltaDirection` props |
| `Sidebar` | Add 3 new nav items, data freshness indicator, keyboard shortcut hints |
| `TopBar` | Add Cmd+K trigger button |
| `DateRangePicker` | Add custom presets from localStorage |
| `ExportDropdown` | Add "Full Database Export" option on Settings page |

---

## 12. New React Hooks

| Hook | File | Purpose |
|------|------|---------|
| `useLocalStorage<T>` | `hooks/useLocalStorage.ts` | Generic localStorage read/write with JSON serialization and SSR safety |
| `useKeyboardShortcuts` | `hooks/useKeyboardShortcuts.ts` | Register Alt+1-9 page navigation, Cmd+K for search |
| `useHeatmap` | `api/heatmap.ts` | Fetch heatmap data with metric param |
| `useModelComparison` | `api/models.ts` | Fetch model comparison data |
| `useWorkflows` | `api/workflows.ts` | Fetch workflow analysis data |
| `useProjectDetail` | `api/projects.ts` (extend) | Fetch project detail by encoded path |
| `useSearch` | `api/search.ts` | Fetch search results for Cmd+K (with 300ms debounce) |
| `useMultiTagComparison` | `api/experiments.ts` (extend) | Fetch multi-tag comparison |
| `useTagSessions` | `api/experiments.ts` (extend) | Fetch sessions for a specific tag |
| `useCostAnomalies` | `api/cost.ts` (extend) | Fetch anomaly data |
| `useCumulativeCost` | `api/cost.ts` (extend) | Fetch cumulative cost data |
| `useCacheSimulation` | `api/cost.ts` (extend) | Fetch cache simulation data |
| `useEfficiencyTrend` | `api/productivity.ts` (extend) | Fetch efficiency trend |
| `useLanguageTrend` | `api/productivity.ts` (extend) | Fetch language trend |
| `useToolSuccessTrend` | `api/productivity.ts` (extend) | Fetch tool success trend |
| `useFileChurn` | `api/productivity.ts` (extend) | Fetch file churn data |
| `useDashboardDeltas` | `api/dashboard.ts` (extend) | Fetch period-over-period deltas |
| `useActivityCalendar` | `api/dashboard.ts` (extend) | Fetch 90-day activity data |

---

## 13. WebSocket Extensions

### 13.1 New Message Types

**`active_session`** -- broadcast when file watcher detects changes in a specific session:
```json
{
  "type": "active_session",
  "timestamp": "2026-02-06T14:30:00",
  "session_id": "abc123",
  "project_display": "claude-usage-analyzer",
  "git_branch": "main"
}
```

**`daily_cost_update`** -- periodic broadcast (every 30s if clients connected) of today's running total:
```json
{
  "type": "daily_cost_update",
  "timestamp": "2026-02-06T14:30:00",
  "cost_today": 1.2345,
  "sessions_today": 5
}
```

### 13.2 Implementation

Extend `file_watcher.py`:
- After `etl_update` broadcast, also parse the session metadata to broadcast `active_session`
- Add a periodic (30s) task that queries `get_vitals_today()` and broadcasts `daily_cost_update`

Frontend: `useWebSocket` hook already handles arbitrary message types. The Live Monitor page filters by `msg.type`. New components subscribe to the same hook and filter for their message type.

---

## 14. Data Flow Diagrams

### 14.1 Cmd+K Search Flow

```
User types Cmd+K
  -> CommandPalette opens (cmdk)
  -> User types query text
  -> 300ms debounce
  -> useSearch(query) fires
  -> GET /api/search?q=...
  -> search_queries.search_all(db, query)
      -> LIKE '%query%' on sessions.project_display
      -> LIKE '%query%' on sessions.session_id
      -> LIKE '%query%' on experiment_tags.tag_name
      -> LIKE '%query%' on turns.model (DISTINCT)
      -> LIKE '%query%' on sessions.git_branch (DISTINCT)
      -> Static page name matching
  -> Returns categorized results
  -> User selects result
  -> react-router navigate(result.url)
  -> CommandPalette closes
```

### 14.2 Budget Tracking Flow (Client-Only)

```
User opens Cost page
  -> useLocalStorage('ccwap:budget', {monthly: 0, alert_pct: 80})
  -> useCost(dateRange) fetches cost data
  -> BudgetTracker renders:
      - Progress bar: cost_this_month / budget.monthly
      - Burn rate: cost_this_month / days_elapsed * 30
      - Alert: if cost_this_month > budget.monthly * alert_pct
  -> User edits budget via inline input
  -> useLocalStorage writes to localStorage
  -> Component re-renders
```

### 14.3 Heatmap Page Flow

```
User navigates to /heatmap
  -> useDateRange() reads URL params
  -> useState('sessions') for metric toggle
  -> useHeatmap(dateRange, metric) fires
  -> GET /api/heatmap?from=...&to=...&metric=sessions
  -> heatmap_queries.get_heatmap_data(db, ...)
      -> Query turns (for sessions/cost): GROUP BY dow, hour
      -> Query tool_calls (for loc/tool_calls): GROUP BY dow, hour
  -> Returns 168 cells + max_value
  -> HeatmapGrid renders CSS Grid
      - 7 rows (Mon-Sun), 24 columns (0h-23h)
      - Each cell colored via color-mix(in srgb, var(--color-chart-1) {pct}%, transparent)
      - Hover tooltip shows exact value
  -> User toggles metric -> triggers refetch with new metric
```

---

## 15. File Organization

### 15.1 New Backend Files

```
ccwap/server/
  routes/
    heatmap.py          # NEW - Heatmap endpoint
    models_route.py     # NEW - Model comparison endpoint (models.py conflicts with models/ dir)
    workflows.py        # NEW - User types / workflow endpoint
    search.py           # NEW - Search endpoint
  queries/
    heatmap_queries.py        # NEW
    model_queries.py          # NEW
    workflow_queries.py       # NEW
    search_queries.py         # NEW
    project_detail_queries.py # NEW
  models/
    heatmap.py          # NEW - Pydantic models
    model_comparison.py # NEW - Pydantic models
    workflows.py        # NEW - Pydantic models
    search.py           # NEW - Pydantic models
    project_detail.py   # NEW - Pydantic models
```

### 15.2 New Frontend Files

```
ccwap/frontend/src/
  pages/
    HeatmapPage.tsx           # NEW
    ModelComparisonPage.tsx    # NEW
    WorkflowPage.tsx           # NEW
    ProjectDetailPage.tsx      # NEW
  components/
    CommandPalette.tsx         # NEW
    BudgetTracker.tsx          # NEW
    CacheCalculator.tsx        # NEW
    charts/                    # NEW directory
      HeatmapGrid.tsx         # NEW
      HeatmapCell.tsx          # NEW
      ToolTimeline.tsx         # NEW
      TokenWaterfall.tsx       # NEW
      AgentTreeView.tsx        # NEW
    ui/
      DeltaBadge.tsx           # NEW
      CostTicker.tsx           # NEW
      ActiveSessionBadge.tsx   # NEW
      ChartCard.tsx            # NEW
  hooks/
    useLocalStorage.ts         # NEW
    useKeyboardShortcuts.ts    # NEW
  api/
    heatmap.ts                 # NEW
    models.ts                  # NEW
    workflows.ts               # NEW
    search.ts                  # NEW
```

### 15.3 Modified Files

```
Backend:
  ccwap/server/app.py                          # Add 4 new routers
  ccwap/server/routes/analytics.py             # Add 2 new endpoints
  ccwap/server/routes/cost.py                  # Add 3 new endpoints
  ccwap/server/routes/productivity.py          # Add 4 new endpoints
  ccwap/server/routes/experiments.py           # Add 2 new endpoints
  ccwap/server/routes/dashboard.py             # Add 2 new endpoints
  ccwap/server/routes/projects.py              # Add 1 new endpoint
  ccwap/server/routes/settings.py              # Add 1 new endpoint
  ccwap/server/queries/analytics_queries.py    # Add 2 functions
  ccwap/server/queries/cost_queries.py         # Add 3 functions
  ccwap/server/queries/productivity_queries.py # Add 4 functions
  ccwap/server/queries/experiment_queries.py   # Add 2 functions
  ccwap/server/queries/dashboard_queries.py    # Add 2 functions
  ccwap/server/models/analytics.py             # Add trend models
  ccwap/server/models/cost.py                  # Add anomaly/cumulative models
  ccwap/server/models/productivity.py          # Add trend models
  ccwap/server/models/experiments.py           # Add multi-compare model
  ccwap/server/models/dashboard.py             # Add delta/calendar models
  ccwap/server/file_watcher.py                 # Add active_session + daily_cost broadcast
  ccwap/server/websocket.py                    # (no change -- broadcast() is generic)

Frontend:
  ccwap/frontend/src/App.tsx                   # Add 4 new lazy routes
  ccwap/frontend/src/components/Sidebar.tsx     # Add 3 nav items + freshness indicator
  ccwap/frontend/src/components/TopBar.tsx      # Add Cmd+K button
  ccwap/frontend/src/components/DateRangePicker.tsx  # Add custom presets
  ccwap/frontend/src/components/ui/MetricCard.tsx    # Add delta props
  ccwap/frontend/src/api/keys.ts               # Add 4+ new key factories
  ccwap/frontend/src/api/dashboard.ts          # Add delta + calendar hooks
  ccwap/frontend/src/api/cost.ts               # Add anomaly + cumulative + simulation hooks
  ccwap/frontend/src/api/productivity.ts       # Add 4 trend hooks
  ccwap/frontend/src/api/experiments.ts        # Add multi-compare + tag sessions hooks
  ccwap/frontend/src/api/projects.ts           # Add project detail hook
  ccwap/frontend/src/lib/utils.ts              # (may add formatDelta helper)
  ccwap/frontend/src/index.css                 # Add heatmap intensity variables
  ccwap/frontend/src/pages/DashboardPage.tsx   # Major enhancements
  ccwap/frontend/src/pages/AnalyticsPage.tsx   # Replace DictTable with charts
  ccwap/frontend/src/pages/ExperimentsPage.tsx # Project dropdown, multi-tag
  ccwap/frontend/src/pages/SessionDetailPage.tsx # Token waterfall, tool timeline
  ccwap/frontend/src/pages/ProjectsPage.tsx    # Drill-down links, comparison mode
  ccwap/frontend/src/pages/CostPage.tsx        # Budget, anomaly, cumulative, cache calc
  ccwap/frontend/src/pages/ProductivityPage.tsx # 4 new chart sections
  ccwap/frontend/src/pages/LiveMonitorPage.tsx  # Cost ticker, active session, mini dashboard
  ccwap/frontend/src/pages/SettingsPage.tsx     # Export, presets, thresholds
  ccwap/frontend/package.json                   # Add cmdk dependency
  ccwap/frontend/vite.config.ts                 # (no change unless chunking cmdk)
```

---

## 16. Migration / Schema Changes

**None required.** All features are served by existing schema. The schema version remains at 3.

If hourly heatmap queries prove slow on large databases (R1 in risk register), a future optimization would be:
```sql
CREATE INDEX IF NOT EXISTS idx_turns_dow_hour
ON turns(CAST(strftime('%w', timestamp) AS INTEGER), CAST(strftime('%H', timestamp) AS INTEGER));
```
This is a performance index only, not a schema change, and can be added via migration v3->v4 if needed.

---

## 17. Implementation Phases

### Phase 1: Shared Infrastructure (Sessions 1-3)

**Goal**: Build all shared components, hooks, and utilities that multiple features depend on.

1. `useLocalStorage` hook
2. `useKeyboardShortcuts` hook
3. `DeltaBadge` component
4. `ChartCard` component
5. `CommandPalette` component (install cmdk)
6. `HeatmapGrid` + `HeatmapCell` components
7. Extend `MetricCard` with delta props
8. Extend `Sidebar` with new nav items + freshness indicator
9. Extend `TopBar` with Cmd+K trigger
10. Add search backend: route, queries, models
11. Add query key factories for all new endpoints
12. Add shared chart constants (tooltip style, gradient IDs)

**Dependencies**: None. This is the foundation.

### Phase 2: Analytics + Dashboard Upgrades (Sessions 4-7)

**Goal**: Replace DictTable, add dashboard vitals config + calendar + deltas.

1. Backend: `get_thinking_trend`, `get_cache_trend` queries
2. Backend: `get_activity_calendar`, `get_deltas` queries
3. Backend: analytics trend endpoints, dashboard delta/calendar endpoints
4. Frontend: AnalyticsPage full chart replacement (6 sections)
5. Frontend: DashboardPage configurable vitals, activity calendar, delta badges, cost alert
6. Frontend: DateRangePicker custom presets (localStorage)

**Dependencies**: Phase 1 (DeltaBadge, HeatmapGrid, useLocalStorage, ChartCard)

### Phase 3: New Pages (Sessions 8-12)

**Goal**: Build all 4 new pages and their backend APIs.

1. Backend: heatmap route + queries + models
2. Frontend: HeatmapPage
3. Backend: model comparison route + queries + models
4. Frontend: ModelComparisonPage
5. Backend: workflow route + queries + models
6. Frontend: WorkflowPage (AgentTreeView component)
7. Backend: project detail route + queries + models
8. Frontend: ProjectDetailPage
9. Update App.tsx routes, Sidebar nav

**Dependencies**: Phase 1 (HeatmapGrid, ChartCard), Phase 2 (patterns established)

### Phase 4: Existing Page Enhancements (Sessions 13-16)

**Goal**: Enhance Cost, Productivity, Sessions, Experiments pages.

1. Backend: cost anomaly + cumulative + cache simulation endpoints
2. Frontend: CostPage (BudgetTracker, anomaly chart, cumulative chart, CacheCalculator)
3. Backend: productivity trend endpoints (4)
4. Frontend: ProductivityPage (4 new chart sections + Treemap)
5. Frontend: SessionDetailPage (TokenWaterfall, ToolTimeline, thinking secondary axis)
6. Frontend: ExperimentsPage (project dropdown, multi-tag, tag detail view)
7. Frontend: ProjectsPage (drill-down links, comparison mode)

**Dependencies**: Phase 1 (useLocalStorage), Phase 3 (ProjectDetailPage exists)

### Phase 5: Live Monitor + Settings (Sessions 17-18)

**Goal**: Enhance real-time features and settings.

1. Backend: extend file_watcher with active_session + daily_cost_update broadcasts
2. Frontend: LiveMonitorPage (CostTicker, ActiveSessionBadge, mini dashboard)
3. Backend: settings export endpoint
4. Frontend: SettingsPage (export button, custom presets editor, threshold editor)

**Dependencies**: Phase 1 (useLocalStorage, CostTicker)

### Phase 6: Polish & Testing (Sessions 19-22)

**Goal**: Integration testing, performance validation, edge cases.

1. Test all new endpoints with empty database
2. Test all new endpoints with large database (> 50K turns)
3. Test heatmap performance, add index if needed (R1)
4. Test workflow pattern detection performance (R2)
5. Verify gradient ID uniqueness across all pages (R8)
6. Verify stacked charts handle missing data correctly (R10)
7. CSV export sanitization hardening
8. Keyboard shortcut conflict testing
9. Dark mode testing for all new components
10. Mobile/responsive testing for new pages

---

## 18. Implementation Guidance for Orchestrator

### 18.1 Critical Path Dependencies

```
Phase 1 (shared infra)
  |
  +-> Phase 2 (analytics + dashboard)
  |     |
  +--+--+-> Phase 3 (new pages)
     |        |
     +--------+-> Phase 4 (page enhancements)
                    |
                    +-> Phase 5 (live + settings)
                          |
                          +-> Phase 6 (polish)
```

Phase 2 and Phase 3 can be partially parallelized if two implementation agents are available.

### 18.2 Spike / POC Requirements

1. **Workflow Pattern Detection**: Before Phase 3 Session 5, test the sliding window approach on real data. If session tool_call counts exceed 500 per session, the O(n) scan may be slow. Fallback: limit to 3-tool windows and top 100 sessions by tool_call count.

2. **Hourly Heatmap Performance**: Run `EXPLAIN QUERY PLAN` on the heatmap query against real data. If full table scan, add the computed index early.

### 18.3 Key Patterns & Conventions to Follow

**Backend**:
- Every route module: `router = APIRouter(prefix="/api", tags=["xxx"])`
- Every query function: `async def xxx(db: aiosqlite.Connection, date_from: Optional[str], date_to: Optional[str]) -> type`
- Date filtering: `AND date(t.timestamp) >= ?` with optional params
- Two-query pattern: Query 1 on turns, Query 2 on tool_calls, merge in Python
- Pydantic response models in `ccwap/server/models/xxx.py`
- Import and include router in `app.py:create_app()` BEFORE static mount

**Frontend**:
- Pages: `export default function XxxPage()` (default export for lazy loading)
- API hooks: `export function useXxx(dateRange: DateRange)` in `api/xxx.ts`
- Query keys: factory pattern in `api/keys.ts`
- Loading/Error/Empty: use `LoadingState` / `ErrorState` / `EmptyState` components
- Charts: use `ResponsiveContainer` wrapper, CSS variable colors, consistent tooltip styling
- Gradient IDs: unique per chart instance (e.g., `${pagePrefix}${chartName}Grad`)
- Card styling: `className="rounded-lg border border-border bg-card p-4"`
- Text styling: `text-sm text-muted-foreground` for labels, `font-mono` for numbers

### 18.4 Handoff Notes

1. **Install cmdk**: In Phase 1, run `npm install cmdk` in the frontend directory. No other npm installs needed.

2. **App.tsx Route Order**: New routes must be added in a specific order due to React Router matching. The `/projects/:path` route must come AFTER `/projects` with a different path structure. Use base64-encoded path to avoid conflicts.

3. **Gradient ID Convention**: Use the pattern `{pageName}-{chartName}-grad` for all linearGradient IDs. The existing codebase uses `sparkGrad`, `costGrad`, `liveGrad` -- these are already unique but the pattern should be formalized for new charts.

4. **Vite Chunking**: cmdk is small enough to go in the main bundle. If adding react-d3-tree later (for agent trees), add it to `manualChunks` in `vite.config.ts`.

5. **Backend Router Registration**: New routers in `app.py` should follow alphabetical order after the existing imports. All routers must be included BEFORE the static files mount and SPA fallback.

6. **Project Path Encoding**: Use `btoa(unescape(encodeURIComponent(path)))` on the frontend and `base64.urlsafe_b64decode(encoded).decode('utf-8')` on the backend. This handles Unicode and special characters in Windows paths.

7. **Testing**: All new backend query functions should have unit tests following the existing pattern in `ccwap/tests/`. Each test should use an in-memory SQLite database with test data.

8. **CSS Variables for Heatmap**: Add heatmap intensity levels to `index.css` under `@theme`:
   ```css
   --color-heatmap-0: transparent;
   --color-heatmap-1: color-mix(in srgb, var(--color-chart-1) 20%, transparent);
   --color-heatmap-2: color-mix(in srgb, var(--color-chart-1) 40%, transparent);
   --color-heatmap-3: color-mix(in srgb, var(--color-chart-1) 60%, transparent);
   --color-heatmap-4: color-mix(in srgb, var(--color-chart-1) 80%, transparent);
   --color-heatmap-5: var(--color-chart-1);
   ```
   Or compute dynamically with `color-mix()` in the component (preferred, as SessionDetailPage already does this).

9. **Stacked Chart Data Preparation**: All stacked chart data must have every key present in every data point, even if zero. Create a `fillZeros(data, keys)` utility in `lib/utils.ts`:
   ```typescript
   export function fillZeros<T extends Record<string, unknown>>(
     data: T[],
     keys: string[],
   ): T[] {
     return data.map(d => {
       const filled = { ...d }
       for (const k of keys) {
         if (filled[k] == null) (filled as Record<string, unknown>)[k] = 0
       }
       return filled as T
     })
   }
   ```

10. **CSV Export Sanitization**: Harden the `escapeCSV` function in `useExport.ts` to prefix cells starting with `=`, `+`, `-`, `@`, `\t`, `\r` with a tab character to prevent formula injection.
