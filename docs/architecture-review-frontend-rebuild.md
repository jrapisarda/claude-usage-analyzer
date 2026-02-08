# Architecture Review: CCWAP Frontend Production Rebuild

**Date**: 2026-02-08
**Author**: Sr. Architect Review (Claude Opus 4.6)
**Status**: Proposed
**Scope**: Full frontend rebuild with shadcn/ui, TanStack Table, production-quality component architecture

---

## 1. Executive Summary

The CCWAP frontend is a 15-page analytics dashboard built with React 19, Tailwind CSS 4, Recharts 3.7, and TanStack Query v5. The existing MVP demonstrates the correct data architecture -- 27 REST endpoints across 14 route modules, WebSocket live monitoring, and a well-structured API layer with typed hooks. However, the frontend suffers from three systemic issues: (1) monolithic page components that inline chart configuration, tooltip styling, and data transformation; (2) inconsistent UI patterns -- every page hand-rolls its own table, card grid, and chart wrapper markup; and (3) no shared component library, which means every new page duplicates 40-60 lines of boilerplate.

The recommended architectural direction is an **incremental adoption of shadcn/ui components** layered on top of the existing Tailwind v4 theme, combined with a **composable page architecture** that separates data transformation from presentation. The existing backend API is sufficient for the rebuild with minor additions (3 new endpoints). The frontend rebuild should follow a strict bottom-up approach: foundation layer first (shadcn/ui primitives + theme), then shared composite components (DataTable, ChartContainer, MetricCardGrid), then page-by-page rebuilds working from the simplest pages outward. This approach allows each phase to be deployed and validated independently.

The critical technical risk is **shadcn/ui compatibility with Tailwind CSS v4**. shadcn/ui v2 (released late 2025) officially supports Tailwind v4's CSS-first configuration, but the existing theme must be mapped to shadcn/ui's expected CSS variable naming convention. The existing `index.css` already uses the correct shadcn/ui variable names (`--color-background`, `--color-foreground`, `--color-card`, etc.), which means initialization is straightforward -- the theme is already 95% compatible.

---

## 2. Requirements Analysis

### 2.1 Functional Requirements (Prioritized)

**Must-Have (Core Rebuild):**
- FR-1: All 15 existing pages must be rebuilt with equivalent functionality
- FR-2: shadcn/ui component library integrated for all UI primitives (Button, Input, Select, Dialog, Popover, DropdownMenu, Table, Tabs, Badge, Skeleton, Tooltip, Calendar, Command)
- FR-3: TanStack Table for all sortable/paginated data views (Projects, Sessions, Model Comparison, Tool Usage, Pricing Editor)
- FR-4: Consistent chart theming via shared ChartContainer component
- FR-5: Skeleton loading states for all data-driven sections
- FR-6: Global error boundary with retry capability
- FR-7: Responsive layout with collapsible sidebar at <1024px
- FR-8: Dark/light mode toggle persisted to localStorage

**Should-Have (Quality Improvements):**
- FR-9: DateRangePicker upgrade from native inputs to shadcn/ui Calendar + Popover
- FR-10: Command palette (existing cmdk) restyled with shadcn/ui Command component
- FR-11: Export functionality consolidated into a shared pattern
- FR-12: Breadcrumb navigation for drill-down pages (Project Detail, Session Detail)
- FR-13: Accessible keyboard navigation for all interactive elements
- FR-14: Toast notifications for async operations (rebuild, pricing save)

**Could-Have (Future Enhancements):**
- FR-15: Drag-and-drop dashboard layout customization
- FR-16: Saved views / bookmarked explorer queries
- FR-17: Print-optimized stylesheet for reports

### 2.2 Non-Functional Requirements

| NFR | Target | Rationale |
|-----|--------|-----------|
| Initial page load | <1.5s on localhost | Desktop app, no network latency |
| Bundle size (gzipped) | <600KB total | Current vendor chunks + lazy loading |
| Lighthouse accessibility | >90 | shadcn/ui provides Radix primitives which are WCAG 2.1 AA |
| TypeScript strict mode | Maintained | Already enabled in tsconfig.app.json |
| Test coverage | Maintain 703+ backend tests, add 50+ frontend component tests |
| Theme switch latency | <50ms | CSS variable swap, no re-render |

### 2.3 Constraints & Assumptions

**Constraints:**
- C-1: Tailwind CSS 4 with `@theme` directive (no tailwind.config.js). shadcn/ui v2 must be configured for v4.
- C-2: Vite 7 build toolchain. No webpack migration.
- C-3: React 19 with lazy() for route-level code splitting.
- C-4: Single shared aiosqlite connection -- no concurrent query concerns.
- C-5: Backend API prefix is `/api` on all routes. WebSocket at `/ws/live`.
- C-6: Build output goes to `ccwap/static/` for FastAPI to serve.
- C-7: Recharts 3.7 strict typing constraints remain (Formatter<number, NameType>).

**Assumptions:**
- A-1: shadcn/ui v2 (2025+) supports Tailwind v4's CSS-first configuration natively.
- A-2: The existing CSS variable naming convention (`--color-background`, `--color-primary`, etc.) is already aligned with shadcn/ui expectations.
- A-3: No backend API breaking changes -- all existing response shapes are preserved.
- A-4: react-day-picker v9 (already installed) is used by shadcn/ui Calendar component.
- A-5: The page structure (15 routes, sidebar nav, top bar) remains the same.

### 2.4 Gaps & Clarifications Needed

- **GAP-1**: The existing `@tailwindcss/vite` plugin (v4.1.18) -- does it support shadcn/ui's expected `@layer base` directives? **Assumption: Yes, verified by Tailwind v4 docs.**
- **GAP-2**: Should the sidebar be collapsible on desktop (not just mobile)? **Recommendation: Yes, add a toggle.**
- **GAP-3**: Is there a design system or mockup for the rebuilt UI, or should we match the existing visual style? **Assumption: Match existing style with shadcn/ui polish.**

---

## 3. Architecture Decisions

### ADR-001: shadcn/ui Integration Strategy

- **Context**: The frontend has 21 custom components, many of which are ad-hoc implementations of common UI patterns (buttons, inputs, selects, dropdowns, tables). These lack consistent styling, accessibility, and keyboard interaction. A component library would eliminate this inconsistency.
- **Decision**: Adopt shadcn/ui v2 with copy-paste installation into `src/components/ui/`. Use the existing Tailwind v4 `@theme` variables directly -- no theming bridge needed because the existing CSS variables already match shadcn/ui's expected names. Install components incrementally: start with primitives (Button, Input, Select, Badge), then composites (Table, Dialog, Popover, Calendar, Command, DropdownMenu, Tabs, Skeleton, Tooltip).
- **Status**: Accepted
- **Consequences**:
  - Positive: Radix-based accessibility out of the box. Consistent styling. Reduced custom code.
  - Positive: Components are local files (not npm dependency), so they can be customized freely.
  - Negative: ~25 new files in `src/components/ui/`. Initial setup effort.
  - Negative: Must verify each shadcn/ui component renders correctly with Tailwind v4's `@theme` approach before using in production pages.
- **Alternatives Considered**:
  - **Headless UI (Tailwind Labs)**: Fewer components, no table primitives, less ecosystem. Rejected.
  - **Mantine / Chakra**: Too opinionated, would fight Tailwind theming. Rejected.
  - **Keep hand-rolling**: Status quo leads to growing inconsistency. Rejected.

### ADR-002: Page Component Architecture Pattern

- **Context**: Current pages are 200-580 line monoliths that inline data fetching, transformation, chart config, and layout. ExplorerPage.tsx is 581 lines. ProductivityPage.tsx is 329 lines. This makes pages hard to test, hard to modify, and easy to introduce regressions.
- **Decision**: Adopt a **three-layer page architecture**:
  1. **Page Shell** (e.g., `DashboardPage.tsx`): Owns the `<PageLayout>`, orchestrates data hooks, passes data to sections. 50-100 lines.
  2. **Page Sections** (e.g., `DashboardVitals.tsx`, `DashboardCostTrend.tsx`): Self-contained visual blocks that receive typed props. Own their chart/table config. 30-80 lines each.
  3. **Shared Components** (e.g., `<ChartContainer>`, `<DataTable>`, `<MetricCardGrid>`): Reusable across pages.
- **Status**: Accepted
- **Consequences**:
  - Positive: Each section is independently testable. Pages become compositional.
  - Positive: New reports can be added by creating a section + hook, not modifying a monolith.
  - Negative: More files per page (3-6 vs 1). Need clear naming convention.
  - Negative: Props drilling for date range. Mitigated by keeping hooks at page level.
- **Alternatives Considered**:
  - **Feature slices (co-located everything)**: Too much structure for 15 pages. Over-engineered. Rejected.
  - **Keep monolithic pages**: Technical debt continues to accumulate. Rejected.

### ADR-003: Table Architecture -- TanStack Table for Complex Views

- **Context**: The codebase has 6 pages with sortable tables, all hand-rolled with different sort implementations. ProjectsPage has server-side sort+pagination. ModelComparisonPage has client-side sort. ProductivityPage has no sort. SessionsPage has pagination but inline sorting.
- **Decision**: Use **TanStack Table v8** with shadcn/ui's DataTable recipe for all tabular data. Server-side operations (sort, filter, paginate) for Projects and Sessions (large datasets). Client-side operations for Model Comparison, Tool Usage, and Pricing Editor (small datasets, <100 rows).
- **Status**: Accepted
- **Consequences**:
  - Positive: Consistent sort/filter/pagination UX across all tables.
  - Positive: Column definitions are declarative. Easy to add columns.
  - Positive: Built-in virtualization support via `@tanstack/react-virtual` (already installed).
  - Negative: Learning curve for TanStack Table column definition API.
- **Alternatives Considered**:
  - **AG Grid**: Enterprise feel, heavy bundle (~200KB). Overkill for this use case. Rejected.
  - **Custom table component**: What we have now. Inconsistent. Rejected.

### ADR-004: Chart Theming via Shared ChartContainer

- **Context**: Every page inlines Recharts `<ResponsiveContainer>`, tooltip styling, axis configuration, and gradient definitions. The same `TOOLTIP_STYLE` is imported everywhere. Gradient IDs conflict when multiple charts appear on the same page (known bug with `id="costGrad"` duplicates).
- **Decision**: Create a `<ChartContainer>` component that wraps `<ResponsiveContainer>` and provides:
  1. Consistent height/padding
  2. Loading skeleton state
  3. Empty state
  4. Unique gradient ID generation (prefix with chart name)
  5. A `<ChartTooltip>` component that standardizes tooltip appearance
  6. A `useChartConfig()` hook that returns axis styles, animation settings (disabled for >200 points), and theme-aware colors
- **Status**: Accepted
- **Consequences**:
  - Positive: Chart setup goes from ~30 lines of boilerplate to ~5 lines.
  - Positive: Gradient ID conflicts eliminated.
  - Negative: Slight learning curve for custom chart component API.
- **Alternatives Considered**:
  - **shadcn/ui Charts**: These are thin Recharts wrappers. They add configuration overhead without sufficient benefit over our custom approach. Could adopt their color convention (`--chart-1` etc.) but we already have an equivalent. Partially adopted for color naming.

### ADR-005: Data Fetching & Caching Strategy

- **Context**: The app has a global `staleTime: 30_000` with `refetchOnWindowFocus: false`. The `getStaleTime()` utility in chartConfig.ts implements smarter logic (Infinity for historical ranges, 2min for today-inclusive, 5min for all-time) but is not consistently used.
- **Decision**: Implement a **tiered staleTime strategy** applied consistently via the API hooks:
  - Historical date ranges (to < today): `staleTime: Infinity`
  - Ranges including today: `staleTime: 2 * 60 * 1000` (2 minutes)
  - All-time (no date filter): `staleTime: 5 * 60 * 1000` (5 minutes)
  - Session replay (immutable): `staleTime: Infinity`
  - Settings/config: `staleTime: Infinity` until mutation
  - Always `refetchOnWindowFocus: false` (desktop app)
  This logic lives in a `useSmartStaleTime(dateRange)` hook used by all date-filtered API hooks.
- **Status**: Accepted
- **Consequences**:
  - Positive: Reduced unnecessary refetches. Better perceived performance.
  - Positive: Historical data never refetches, saving SQLite reads.
  - Negative: Slightly more complex hook setup.

### ADR-006: Skeleton Loading Strategy

- **Context**: Current loading states are a single `<LoadingState>` spinner component. This causes layout shift when data arrives because the full page renders at once.
- **Decision**: Implement **skeleton loading** at the section level, not the page level. Each page section (MetricCardGrid, ChartContainer, DataTable) renders a skeleton placeholder matching its final dimensions. The page shell renders immediately with all section skeletons visible, then sections hydrate independently as their queries resolve.
- **Status**: Accepted
- **Consequences**:
  - Positive: Zero layout shift. Professional feel.
  - Positive: Independent section loading -- fast queries appear immediately.
  - Negative: Must design skeleton for each section type (4 patterns: card grid, chart, table, list).

### ADR-007: Responsive Sidebar with Collapsible State

- **Context**: The current sidebar is fixed at `w-56` with no collapse behavior. On smaller screens it wastes space. There is no mobile consideration.
- **Decision**: Implement a **collapsible sidebar** with three states:
  1. **Expanded** (>1280px default): Full width with labels, `w-56`
  2. **Collapsed** (user toggle or 1024-1280px): Icon-only, `w-14`
  3. **Mobile overlay** (<1024px): Hidden by default, slide-in overlay triggered by hamburger menu
  State persisted to localStorage via `useLocalStorage('ccwap:sidebar-collapsed')`.
- **Status**: Accepted
- **Consequences**:
  - Positive: More screen real estate for charts on smaller screens.
  - Positive: Works on tablets/smaller laptops.
  - Negative: More complex sidebar component. Need tooltip on collapsed icons.

### ADR-008: Dark/Light Mode Implementation

- **Context**: The app already has a `.dark` class in `index.css` with complete dark theme variables and a `useTheme` hook. The ThemeToggle component exists. This is working correctly.
- **Decision**: **Keep the existing implementation**. The `.dark` class approach with CSS variables is the same pattern shadcn/ui uses. No changes needed. Verify that all new shadcn/ui components respect the existing CSS variables.
- **Status**: Accepted (no change)
- **Consequences**:
  - Positive: Zero migration work.
  - Positive: shadcn/ui components will automatically theme correctly because they use the same CSS variable names.

### ADR-009: Backend API -- Minor Additions Only

- **Context**: The existing 27 endpoints cover all current page needs. Analysis of each page against its API reveals three gaps.
- **Decision**: Add three new endpoints:
  1. `GET /api/dashboard/summary-cards` -- Lightweight endpoint returning just the 4 vitals + deltas in a single call (currently requires 2 calls: `/dashboard` + `/dashboard/deltas`). Reduces initial page load latency.
  2. `GET /api/projects/{path}/sessions` -- Direct sessions-for-project endpoint (currently requires encoding project path into query param on `/sessions?project=...`). Cleaner URL for Project Detail drill-down.
  3. `GET /api/health/version` -- Returns `{ version, schema_version, python_version, uptime_seconds }` for the Settings page footer and about dialog.
  All other endpoints remain unchanged.
- **Status**: Proposed
- **Consequences**:
  - Positive: Fewer round-trips for Dashboard page.
  - Positive: Cleaner URL structure for project drill-down.
  - Negative: 3 new query functions and route handlers (~50 lines each).
- **Alternatives Considered**:
  - **GraphQL**: Massive overkill for a single-user desktop app with 27 endpoints. Rejected.
  - **API response aggregation middleware**: Over-engineering. Rejected.

---

## 4. Technical Architecture Overview

### 4.1 System Decomposition

```
ccwap/frontend/src/
|
|-- main.tsx                    # Entry: BrowserRouter + App
|-- App.tsx                     # QueryClient + AppShell + Routes
|
|-- components/
|   |-- layout/                 # App shell components
|   |   |-- AppShell.tsx        # Sidebar + TopBar + main wrapper
|   |   |-- Sidebar.tsx         # Collapsible nav (expanded/collapsed/mobile)
|   |   |-- TopBar.tsx          # Search, date picker, theme toggle, Cmd+K
|   |   |-- PageLayout.tsx      # Page wrapper (title, subtitle, actions, children)
|   |   |-- Breadcrumbs.tsx     # Dynamic breadcrumb trail
|   |
|   |-- ui/                     # shadcn/ui primitives (copy-paste installed)
|   |   |-- button.tsx
|   |   |-- input.tsx
|   |   |-- select.tsx
|   |   |-- badge.tsx
|   |   |-- skeleton.tsx
|   |   |-- dialog.tsx
|   |   |-- popover.tsx
|   |   |-- dropdown-menu.tsx
|   |   |-- table.tsx
|   |   |-- tabs.tsx
|   |   |-- tooltip.tsx
|   |   |-- calendar.tsx
|   |   |-- command.tsx
|   |   |-- separator.tsx
|   |   |-- scroll-area.tsx
|   |   |-- sheet.tsx           # Mobile sidebar overlay
|   |   |-- toast.tsx
|   |   |-- toaster.tsx
|   |
|   |-- composite/              # App-specific shared components
|   |   |-- MetricCard.tsx      # Stat card with delta badge + skeleton
|   |   |-- MetricCardGrid.tsx  # Grid of MetricCards with loading state
|   |   |-- ChartContainer.tsx  # ResponsiveContainer + skeleton + empty + gradient ID
|   |   |-- ChartTooltip.tsx    # Standardized Recharts tooltip
|   |   |-- DataTable.tsx       # TanStack Table + shadcn/ui Table wrapper
|   |   |-- DataTablePagination.tsx
|   |   |-- DataTableColumnHeader.tsx  # Sortable column header
|   |   |-- DateRangePicker.tsx # Calendar popover + preset buttons
|   |   |-- CommandPalette.tsx  # Cmd+K with shadcn/ui Command
|   |   |-- ExportDropdown.tsx  # CSV/JSON export via DropdownMenu
|   |   |-- DeltaBadge.tsx      # +/-% badge
|   |   |-- EmptyState.tsx      # Centered empty message
|   |   |-- ErrorState.tsx      # Error with retry button
|   |
|   |-- charts/                 # Specialized chart components
|   |   |-- HeatmapGrid.tsx     # CSS Grid heatmap (keep, already good)
|   |   |-- TokenWaterfall.tsx  # Stacked bar per turn (keep)
|   |   |-- CostOverlayLine.tsx # SVG polyline for session timeline (keep)
|   |   |-- TurnBlock.tsx       # Individual turn in timeline (extract from SessionDetailPage)
|   |   |-- AgentTreeView.tsx   # Tree visualization (keep)
|
|-- pages/                      # Route-level components (thin orchestrators)
|   |-- dashboard/
|   |   |-- DashboardPage.tsx   # Page shell: hooks + section composition
|   |   |-- DashboardVitals.tsx # 4 metric cards + deltas
|   |   |-- DashboardActivity.tsx   # Calendar heatmap
|   |   |-- DashboardSparkline.tsx  # 7-day cost sparkline
|   |   |-- DashboardCostTrend.tsx  # Cost trend area chart
|   |   |-- DashboardTopProjects.tsx # Top projects list
|   |   |-- DashboardRecentSessions.tsx # Recent sessions list
|   |
|   |-- projects/
|   |   |-- ProjectsPage.tsx    # Search + DataTable + pagination
|   |   |-- ProjectsTable.tsx   # Column defs + TanStack Table
|   |   |-- ProjectExpandedRow.tsx  # Inline detail panel
|   |
|   |-- project-detail/
|   |   |-- ProjectDetailPage.tsx
|   |   |-- ProjectDetailHeader.tsx
|   |   |-- ProjectDetailCharts.tsx
|   |   |-- ProjectDetailSessions.tsx
|   |
|   |-- sessions/
|   |   |-- SessionsPage.tsx
|   |   |-- SessionsTable.tsx
|   |
|   |-- session-detail/
|   |   |-- SessionDetailPage.tsx
|   |   |-- SessionTimeline.tsx     # TurnBlock strip + CostOverlayLine
|   |   |-- SessionCharts.tsx       # Cost breakdown + Token waterfall
|   |   |-- TurnDetailPanel.tsx     # Side panel for selected turn
|   |
|   |-- cost/
|   |   |-- CostPage.tsx
|   |   |-- CostSummary.tsx
|   |   |-- CostForecast.tsx
|   |   |-- CostTrend.tsx
|   |   |-- CostByTokenType.tsx
|   |   |-- CostByModel.tsx
|   |   |-- CostByProject.tsx
|   |   |-- CostCacheSavings.tsx
|   |   |-- CostBudgetTracker.tsx
|   |   |-- CostAnomalies.tsx
|   |   |-- CostCumulative.tsx
|   |   |-- CostCacheCalculator.tsx
|   |
|   |-- productivity/
|   |   |-- ProductivityPage.tsx
|   |   |-- ProductivitySummary.tsx
|   |   |-- ProductivityLocTrend.tsx
|   |   |-- ProductivityLanguages.tsx
|   |   |-- ProductivityToolUsage.tsx  # DataTable
|   |   |-- ProductivityErrors.tsx
|   |   |-- ProductivityFileHotspots.tsx
|   |   |-- ProductivityEfficiency.tsx
|   |   |-- ProductivityLangTrend.tsx
|   |   |-- ProductivityToolSuccess.tsx
|   |   |-- ProductivityFileChurn.tsx
|   |
|   |-- analytics/
|   |   |-- AnalyticsPage.tsx
|   |   |-- AnalyticsThinking.tsx
|   |   |-- AnalyticsTruncation.tsx
|   |   |-- AnalyticsSidechains.tsx
|   |   |-- AnalyticsCacheTiers.tsx
|   |   |-- AnalyticsSkillsAgents.tsx
|   |   |-- AnalyticsBranches.tsx
|   |   |-- AnalyticsVersions.tsx
|   |
|   |-- heatmap/
|   |   |-- HeatmapPage.tsx
|   |
|   |-- models/
|   |   |-- ModelComparisonPage.tsx
|   |   |-- ModelTable.tsx          # DataTable with sort
|   |   |-- ModelRadarChart.tsx
|   |   |-- ModelScatterChart.tsx
|   |   |-- ModelUsageTrend.tsx
|   |
|   |-- workflows/
|   |   |-- WorkflowPage.tsx
|   |
|   |-- explorer/
|   |   |-- ExplorerPage.tsx
|   |   |-- ExplorerControls.tsx    # Metric/GroupBy/SplitBy selects
|   |   |-- ExplorerFilters.tsx     # MultiSelect filters
|   |   |-- ExplorerCharts.tsx      # Dynamic chart rendering
|   |   |-- ExplorerDataTable.tsx   # Raw data table
|   |
|   |-- experiments/
|   |   |-- ExperimentsPage.tsx
|   |
|   |-- live/
|   |   |-- LiveMonitorPage.tsx
|   |   |-- LiveConnectionStatus.tsx
|   |   |-- LiveVitals.tsx
|   |   |-- LiveEventLog.tsx
|   |
|   |-- settings/
|   |   |-- SettingsPage.tsx
|   |   |-- SettingsPricing.tsx     # DataTable with inline edit
|   |   |-- SettingsEtl.tsx
|   |   |-- SettingsExport.tsx
|   |   |-- SettingsPresets.tsx
|   |   |-- SettingsNotifications.tsx
|
|-- api/                        # TanStack Query hooks (KEEP structure, enhance)
|   |-- client.ts               # apiFetch, buildQuery, ApiError (keep as-is)
|   |-- keys.ts                 # Query key factories (keep as-is)
|   |-- dashboard.ts            # (keep, add useDashboardSummaryCards)
|   |-- projects.ts             # (keep)
|   |-- sessions.ts             # (keep)
|   |-- cost.ts                 # (keep)
|   |-- productivity.ts         # (keep)
|   |-- analytics.ts            # (keep)
|   |-- heatmap.ts              # (keep)
|   |-- models.ts               # (keep)
|   |-- workflows.ts            # (keep)
|   |-- explorer.ts             # (keep)
|   |-- experiments.ts          # (keep)
|   |-- settings.ts             # (keep)
|   |-- search.ts               # (keep)
|
|-- hooks/                      # Custom hooks (KEEP all, enhance)
|   |-- useDateRange.ts         # (keep as-is, well-designed)
|   |-- useWebSocket.ts         # (keep as-is, well-designed)
|   |-- useLocalStorage.ts      # (keep)
|   |-- useExport.ts            # (keep)
|   |-- useKeyboardShortcuts.ts # (keep)
|   |-- useTheme.ts             # (keep)
|   |-- useSmartStaleTime.ts    # NEW: tiered staleTime based on dateRange
|   |-- useSidebar.ts           # NEW: sidebar collapse state
|   |-- useMediaQuery.ts        # NEW: responsive breakpoint detection
|
|-- lib/
|   |-- utils.ts                # cn(), formatters (keep, enhance)
|   |-- chartConfig.ts          # Shared chart constants (keep, enhance)
|   |-- table-utils.ts          # NEW: TanStack Table column helpers
|
|-- types/                      # NEW: shared TypeScript types
|   |-- api.ts                  # API response types (extract from api/ modules)
|   |-- common.ts               # DateRange, Pagination, SortConfig
|
|-- index.css                   # Tailwind + theme variables (keep, add @layer base for shadcn/ui)
```

### 4.2 Data Architecture

**Data Flow (unchanged):**
```
Claude Code JSONL files
    |
    v
ETL Pipeline (ccwap/etl/)
    |
    v
SQLite Database (7 tables, WAL mode)
    |
    v
FastAPI async queries (ccwap/server/queries/)
    |
    v
Pydantic response models (ccwap/server/models/)
    |
    v
REST API (27 endpoints, /api prefix)
    |
    v
TanStack Query hooks (ccwap/frontend/src/api/)
    |
    v
Page Components -> Section Components -> Chart/Table/Card Components
```

**WebSocket Flow (unchanged):**
```
File Watcher (ccwap/server/file_watcher.py)
    |
    v
ConnectionManager (ccwap/server/websocket.py)
    |
    v
WebSocket /ws/live
    |
    v
useWebSocket hook -> LiveMonitorPage sections
```

**Caching Strategy:**
```
Query Type              | staleTime        | gcTime   | refetchOnWindowFocus
------------------------|------------------|----------|--------------------
Historical date range   | Infinity         | 300_000  | false
Today-inclusive range    | 120_000 (2min)   | 300_000  | false
All-time (no dates)     | 300_000 (5min)   | 300_000  | false
Session replay          | Infinity         | 600_000  | false
Settings/config         | Infinity         | Infinity | false
Search results          | 60_000 (1min)    | 300_000  | false
WebSocket (not cached)  | N/A              | N/A      | N/A
```

### 4.3 Integration Architecture

**API Layer** (no changes to existing pattern):
- `apiFetch<T>()` generic fetcher with ApiError class
- `buildQuery()` parameter serializer
- Per-domain hook modules with typed return values
- Query key factories in `keys.ts` for cache management

**WebSocket Layer** (no changes):
- `useWebSocket()` hook with reconnection, ping/pong, visibility-based pause
- Message types: `etl_update`, `active_session`, `daily_cost_update`, `pong`

### 4.4 Security Architecture

**No changes needed.** This is a single-user desktop application:
- No authentication/authorization
- No CORS (same-origin serving from FastAPI)
- SQLite file permissions controlled by OS
- CSV export formula injection already handled (tab-prefix for `=`,`+`,`-`,`@`)

### 4.5 Infrastructure & Deployment

**No changes to deployment model:**
- `vite build` outputs to `ccwap/static/`
- FastAPI mounts static files with SPA fallback
- `python -m ccwap web` starts the server
- Dev: `vite` dev server with proxy to FastAPI at :8080

**Build enhancement:**
- Add `@vitejs/plugin-react-swc` for faster dev builds (SWC is 20x faster than Babel for JSX transform)
- Update manual chunks to include `@radix-ui` vendor chunk

Updated `vite.config.ts` chunk strategy:
```typescript
manualChunks: {
  'react-vendor': ['react', 'react-dom', 'react-router'],
  'chart-vendor': ['recharts'],
  'query-vendor': ['@tanstack/react-query'],
  'radix-vendor': [/* @radix-ui/* packages used by shadcn/ui */],
}
```

### 4.6 Observability

**Frontend:**
- Error boundary catches all React render errors, displays retry UI
- `ApiError` class preserves HTTP status + detail for error states
- Console errors for WebSocket failures (already present)
- No external monitoring (desktop app -- no Sentry/DataDog needed)

**Backend (no changes):**
- Global exception handler logs via Python logging
- FastAPI request logging via middleware

---

## 5. Technology Stack Recommendations

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| **UI Components** | shadcn/ui | v2 (latest) | Radix primitives + Tailwind. Already uses same deps (clsx, tailwind-merge, CVA, lucide-react). |
| **Tables** | TanStack Table | v8 | Already installed (`@tanstack/react-virtual`). Declarative column defs. Server + client sort/filter. |
| **Charts** | Recharts | 3.7 (keep) | Existing investment. shadcn/ui charts are just Recharts wrappers. |
| **Data Fetching** | TanStack Query | v5 (keep) | Excellent caching, typed hooks, devtools. |
| **Routing** | React Router | v7 (keep) | Working, supports lazy routes. |
| **Styling** | Tailwind CSS | v4 (keep) | CSS-first `@theme` config already in place. |
| **Icons** | Lucide React | latest (keep) | Tree-shakeable, consistent with shadcn/ui default. |
| **Command Palette** | cmdk | v1 (keep) | Already installed. shadcn/ui Command wraps this. |
| **Date Picker** | react-day-picker | v9 (keep) | Already installed. shadcn/ui Calendar wraps this. |
| **Build** | Vite | v7 (keep) | Fast dev/build. Add SWC plugin for faster HMR. |
| **Test** | Vitest + Testing Library | latest (keep) | Already configured. |

**New packages to install:**

```bash
# shadcn/ui peer deps (most already installed)
npm install @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-popover \
  @radix-ui/react-select @radix-ui/react-separator @radix-ui/react-slot \
  @radix-ui/react-tabs @radix-ui/react-tooltip @radix-ui/react-scroll-area \
  @radix-ui/react-sheet

# TanStack Table (peer of already-installed react-virtual)
npm install @tanstack/react-table

# Build optimization
npm install -D @vitejs/plugin-react-swc
```

Estimated additional bundle impact: ~35KB gzipped (Radix primitives are tree-shakeable).

---

## 6. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R-1 | shadcn/ui v2 incompatibility with Tailwind v4 `@theme` directive | Low | High | Spike: install 2 shadcn/ui components (Button, Table) and verify rendering before committing to full adoption. Fallback: manually adjust component CSS to use `@theme` variables. |
| R-2 | TanStack Table + server-side pagination increases API complexity | Low | Medium | The Projects and Sessions endpoints already support server-side sort/pagination. TanStack Table's `manualSorting` and `manualPagination` flags simply wire into existing params. |
| R-3 | Page section decomposition introduces prop-drilling complexity | Medium | Low | Keep data fetching at page level. Pass pre-formatted props to sections. If 3+ levels of drilling emerge, introduce a page-level context (unlikely with current structure). |
| R-4 | Recharts 3.7 strict typing conflicts with shadcn/ui chart wrappers | Low | Low | Use Recharts directly (not shadcn/ui chart components). Our existing pattern works. The `ChartContainer` is a layout wrapper, not a Recharts wrapper. |
| R-5 | Bundle size increase from Radix + shadcn/ui exceeds 600KB budget | Low | Medium | Monitor with `vite-bundle-visualizer`. Radix components are tree-shakeable. Current estimate: +35KB gzipped. Well within budget. |
| R-6 | Regression in existing functionality during page rebuild | Medium | High | Rebuild pages one at a time. Keep old page files until replacement is verified. Run existing backend test suite after each phase. Add visual smoke tests per page. |
| R-7 | Developer productivity impact from unfamiliar shadcn/ui patterns | Medium | Low | shadcn/ui components are plain React+Tailwind files. No magic. Copy-paste from docs. Short ramp-up. |
| R-8 | `@vitejs/plugin-react-swc` compatibility with existing config | Low | Low | Drop-in replacement for `@vitejs/plugin-react`. If issues, revert to Babel plugin (zero risk). |

---

## 7. Implementation Guidance for Orchestrator

### 7.1 Recommended Phase Breakdown

#### Phase 0: Foundation (1 session, ~2 hours)
**Goal**: Set up shadcn/ui infrastructure, verify Tailwind v4 compatibility, install TanStack Table.

Tasks:
1. Install Radix packages + `@tanstack/react-table` + `@vitejs/plugin-react-swc`
2. Update `vite.config.ts` to use SWC plugin + add `radix-vendor` chunk
3. Add `@layer base` reset in `index.css` (required by some shadcn/ui components)
4. Copy-paste install 6 foundation shadcn/ui components: `button.tsx`, `input.tsx`, `badge.tsx`, `skeleton.tsx`, `separator.tsx`, `scroll-area.tsx`
5. Create `ChartContainer.tsx` and `ChartTooltip.tsx` composite components
6. Create `MetricCardGrid.tsx` with skeleton support
7. Create `useSmartStaleTime.ts`, `useSidebar.ts`, `useMediaQuery.ts` hooks
8. **Verification**: Render a test page using Button, Input, Badge, Skeleton to confirm Tailwind v4 theming works

**Deliverable**: Foundation layer compiles and renders correctly in both light and dark modes.

#### Phase 1: Shared Components (1 session, ~3 hours)
**Goal**: Build all shared composite components needed by pages.

Tasks:
1. Install remaining shadcn/ui components: `dialog.tsx`, `popover.tsx`, `dropdown-menu.tsx`, `table.tsx`, `tabs.tsx`, `tooltip.tsx`, `calendar.tsx`, `command.tsx`, `sheet.tsx`, `select.tsx`, `toast.tsx`, `toaster.tsx`
2. Build `DataTable.tsx` + `DataTablePagination.tsx` + `DataTableColumnHeader.tsx` using TanStack Table + shadcn/ui Table
3. Build `DateRangePicker.tsx` using Calendar + Popover + preset buttons
4. Rebuild `Sidebar.tsx` with collapsible state (3 modes)
5. Rebuild `TopBar.tsx` with new DateRangePicker, theme toggle (shadcn/ui button), Cmd+K trigger
6. Rebuild `CommandPalette.tsx` using shadcn/ui Command
7. Rebuild `ExportDropdown.tsx` using shadcn/ui DropdownMenu
8. Build `Breadcrumbs.tsx` component
9. Build `AppShell.tsx` that composes Sidebar + TopBar + main area
10. Add `EmptyState.tsx` and `ErrorState.tsx` using shadcn/ui styling
11. **Verification**: Mount AppShell in App.tsx, verify sidebar collapse, date picker, command palette all work

**Deliverable**: All shared components working. App shell renders with old pages still functional.

#### Phase 2: Simple Pages (1-2 sessions, ~4 hours)
**Goal**: Rebuild the simpler pages using new components.

Order (simplest to most complex):
1. **HeatmapPage** -- Simple: metric toggle (Tabs), one chart (HeatmapGrid), summary cards. ~30 minutes.
2. **SettingsPage** -- Forms: PricingEditor (DataTable), ETL status cards, export (DropdownMenu), presets, notifications. ~45 minutes.
3. **LiveMonitorPage** -- WebSocket: connection status, vitals grid, sparkline, event log. ~30 minutes.
4. **ExperimentsPage** -- Tags CRUD, comparison table. ~30 minutes.
5. **WorkflowPage** -- Summary cards, charts, table. ~30 minutes.
6. **ModelComparisonPage** -- DataTable (client sort) + radar + scatter + area chart. ~45 minutes.

**Verification per page**: Visual comparison with old page, all data loads, interactions work.

#### Phase 3: Complex Pages (2 sessions, ~5 hours)
**Goal**: Rebuild data-heavy pages.

Order:
1. **DashboardPage** -- Decompose into 6 sections. Activity calendar, sparkline, cost trend, top projects, recent sessions. ~1 hour.
2. **CostPage** -- Decompose into 8 sections. Budget tracker, cache calculator, anomalies. ~1 hour.
3. **ProductivityPage** -- Decompose into 8 sections. Tool usage DataTable, language trend, file churn treemap. ~1 hour.
4. **AnalyticsPage** -- Decompose into 7 sections. Thinking, truncation, sidechains, cache tiers, skills, branches, versions. ~45 minutes.
5. **ProjectsPage** -- Server-side DataTable with search, sort, pagination, expanded rows. ~45 minutes.
6. **SessionsPage** -- Server-side DataTable with project filter, pagination. ~30 minutes.

#### Phase 4: Detail Pages + Explorer (1 session, ~3 hours)
**Goal**: Rebuild the most complex interactive pages.

1. **SessionDetailPage** -- Timeline scrubber (extract TurnBlock, CostOverlayLine), side panel, cost/token chart toggle. ~1.5 hours.
2. **ProjectDetailPage** -- Header, charts, sessions list. ~30 minutes.
3. **ExplorerPage** -- Controls (Select), filters (MultiSelect via Popover + Checkbox), dynamic charts, data table. ~1 hour.

#### Phase 5: Polish + Testing (1 session, ~2 hours)
**Goal**: Final verification, cleanup, tests.

1. Remove all old page files
2. Run full backend test suite (`python -m pytest ccwap/tests/ -q`)
3. Add frontend component tests for: DataTable, DateRangePicker, MetricCard, ChartContainer, Sidebar
4. Bundle size audit with `vite-bundle-visualizer`
5. Accessibility audit: keyboard navigation, screen reader on key flows
6. Visual regression check: every page in light + dark mode
7. Update manual chunks in vite.config.ts based on actual Radix imports
8. Final `vite build` to verify production output

### 7.2 Critical Path Dependencies

```
Phase 0 (Foundation)
  |
  v
Phase 1 (Shared Components)
  |
  +---> Phase 2 (Simple Pages)     [can start immediately after Phase 1]
  |
  +---> Phase 3 (Complex Pages)    [can start immediately after Phase 1]
  |
  +---> Phase 4 (Detail + Explorer) [can start after Phase 1, but ideally after Phase 3]
  |
  v
Phase 5 (Polish + Testing)        [after all pages complete]
```

Phases 2, 3, and 4 can be parallelized across agents if desired. Each page rebuild is independent -- no page depends on another page's components.

### 7.3 Spike/POC Requirements

**Spike 1 (CRITICAL, must complete before Phase 0):**
- Install shadcn/ui Button and Table components
- Verify they render correctly with Tailwind v4 `@theme` variables
- Verify dark mode toggle works
- Estimated time: 15 minutes
- **If this fails**: Fall back to manual Radix + Tailwind components without the shadcn/ui CLI

**Spike 2 (before Phase 1):**
- Build a minimal TanStack Table with server-side sort/pagination wired to the existing `/api/projects` endpoint
- Verify column header sort indicators, pagination controls, and loading states
- Estimated time: 30 minutes

### 7.4 Key Patterns & Conventions to Follow

**File naming:**
- shadcn/ui primitives: lowercase kebab-case (`button.tsx`, `dropdown-menu.tsx`)
- Composite components: PascalCase (`DataTable.tsx`, `ChartContainer.tsx`)
- Page sections: PascalCase with page prefix (`DashboardVitals.tsx`, `CostForecast.tsx`)
- Hooks: camelCase with `use` prefix (`useSmartStaleTime.ts`)

**Component patterns:**
```tsx
// Page shell pattern
export default function DashboardPage() {
  const { dateRange } = useDateRange()
  const { data, isLoading, error } = useDashboard(dateRange)
  const { data: deltas } = useDashboardDeltas(dateRange)

  return (
    <PageLayout title="Dashboard" subtitle="Overview" actions={<ExportDropdown />}>
      <DashboardVitals data={data?.vitals} deltas={deltas} isLoading={isLoading} />
      <DashboardActivity />
      <DashboardCostTrend data={data?.cost_trend} isLoading={isLoading} />
      <DashboardTopProjects data={data?.top_projects} isLoading={isLoading} />
      <DashboardRecentSessions data={data?.recent_sessions} isLoading={isLoading} />
    </PageLayout>
  )
}
```

```tsx
// Section pattern with skeleton
interface DashboardVitalsProps {
  data?: VitalsData
  deltas?: PeriodDelta[]
  isLoading: boolean
}

export function DashboardVitals({ data, deltas, isLoading }: DashboardVitalsProps) {
  if (isLoading) return <MetricCardGrid count={4} skeleton />

  return (
    <MetricCardGrid>
      <MetricCard title="Sessions" value={formatNumber(data.sessions)} ... />
      ...
    </MetricCardGrid>
  )
}
```

```tsx
// ChartContainer pattern
<ChartContainer title="Cost Trend" height={256} isLoading={isLoading} isEmpty={!data?.length}>
  <AreaChart data={data}>
    ...
  </AreaChart>
</ChartContainer>
```

```tsx
// DataTable pattern (server-side)
const columns: ColumnDef<ProjectData>[] = [
  { accessorKey: 'project_display', header: ({ column }) => <DataTableColumnHeader column={column} title="Project" /> },
  { accessorKey: 'cost', header: ({ column }) => <DataTableColumnHeader column={column} title="Cost" />,
    cell: ({ row }) => formatCurrency(row.getValue('cost')) },
  ...
]
```

**Card styling** (unchanged from existing convention):
```
rounded-lg border border-border bg-card p-4
```

**Chart colors** (use existing CSS variables):
```
var(--color-chart-1) through var(--color-chart-5)
var(--color-token-input), var(--color-token-output), etc.
```

**Gradient ID uniqueness** (new convention):
```tsx
// Always prefix gradient IDs with page + chart name
<linearGradient id="dashboard-costTrend-grad" ...>
```

### 7.5 Handoff Notes for Implementation Agents

1. **DO NOT change any backend Python files** unless implementing the 3 new endpoints in ADR-009. The query layer, models, and routes are stable.

2. **DO NOT change the API response shapes.** The frontend types in `api/*.ts` must match the existing Pydantic models exactly.

3. **Keep the existing `api/` directory structure.** Hooks are well-organized by domain. Add new hooks to existing files, do not restructure.

4. **Keep the existing `hooks/` directory.** All 6 hooks are well-designed and tested. Add new hooks alongside them.

5. **The `index.css` file is critical.** The `@theme` block defines all CSS variables. When installing shadcn/ui, do NOT replace this file. Only add the `@layer base` directives that shadcn/ui components need (if any).

6. **Tailwind v4 gotcha**: There is no `tailwind.config.js`. All configuration is in `index.css` via `@theme`. The `cn()` utility in `lib/utils.ts` is already the shadcn/ui standard.

7. **Recharts typing**: Use `any` for Pie label callbacks and Tooltip formatter params where TypeScript gets in the way. This is an established pattern in the codebase (see CostPage, ExplorerPage). Do not fight the types.

8. **Date string handling**: Always use `toDateStr()` and `parseDateStr()` from `lib/utils.ts`. Never use `toISOString().slice(0,10)` (UTC pitfall) or `new Date("YYYY-MM-DD")` (UTC midnight pitfall).

9. **Gradient IDs**: When multiple charts appear on the same page, gradient IDs MUST be unique. Use the pattern `{pageName}-{chartName}-grad`. This was a known bug in the MVP.

10. **Session detail timeline**: The `TurnBlock` and `CostOverlayLine` components in `SessionDetailPage.tsx` are complex and well-tested. Extract them into separate files in `components/charts/` but do not rewrite the logic.

11. **Explorer page MultiSelect**: The inline `MultiSelect` component in ExplorerPage is 65 lines and works correctly. Extract it to `components/composite/MultiSelect.tsx` (or use shadcn/ui Popover + Checkbox pattern).

12. **Build verification**: After each phase, run `cd ccwap/frontend && npm run build` to verify the production build succeeds. Check that `ccwap/static/` contains `index.html` and `assets/`.

13. **Testing**: The frontend test infrastructure is already set up (Vitest + Testing Library + jsdom). Tests live in `src/__tests__/`. Add component tests for new shared components. Do NOT remove existing tests.

14. **Package installation**: Use `cd ccwap/frontend && npm install <package>` (NOT `pip install`). Backend deps are in `requirements-web.txt`.

---

## Appendix A: Existing Endpoint Inventory

| # | Method | Path | Used By |
|---|--------|------|---------|
| 1 | GET | /api/health | Health check |
| 2 | GET | /api/dashboard | DashboardPage |
| 3 | GET | /api/dashboard/deltas | DashboardPage |
| 4 | GET | /api/dashboard/activity-calendar | DashboardPage |
| 5 | GET | /api/projects | ProjectsPage |
| 6 | GET | /api/projects/{path}/detail | ProjectDetailPage |
| 7 | GET | /api/sessions | SessionsPage |
| 8 | GET | /api/sessions/{id}/replay | SessionDetailPage |
| 9 | GET | /api/cost | CostPage |
| 10 | GET | /api/cost/anomalies | CostPage |
| 11 | GET | /api/cost/cumulative | CostPage |
| 12 | GET | /api/cost/cache-simulation | CostPage (CacheCalculator) |
| 13 | GET | /api/productivity | ProductivityPage |
| 14 | GET | /api/productivity/efficiency-trend | ProductivityPage |
| 15 | GET | /api/productivity/language-trend | ProductivityPage |
| 16 | GET | /api/productivity/tool-success-trend | ProductivityPage |
| 17 | GET | /api/productivity/file-churn | ProductivityPage |
| 18 | GET | /api/analytics | AnalyticsPage |
| 19 | GET | /api/analytics/thinking-trend | AnalyticsPage |
| 20 | GET | /api/analytics/cache-trend | AnalyticsPage |
| 21 | GET | /api/heatmap | HeatmapPage |
| 22 | GET | /api/models | ModelComparisonPage |
| 23 | GET | /api/workflows | WorkflowPage |
| 24 | GET | /api/explorer | ExplorerPage |
| 25 | GET | /api/explorer/filters | ExplorerPage |
| 26 | GET | /api/experiments/tags | ExperimentsPage |
| 27 | POST | /api/experiments/tags | ExperimentsPage |
| 28 | DELETE | /api/experiments/tags/{name} | ExperimentsPage |
| 29 | GET | /api/experiments/compare | ExperimentsPage |
| 30 | GET | /api/experiments/compare-multi | ExperimentsPage |
| 31 | GET | /api/experiments/tags/{name}/sessions | ExperimentsPage |
| 32 | GET | /api/search | CommandPalette |
| 33 | GET | /api/settings | SettingsPage |
| 34 | PUT | /api/settings/pricing | SettingsPage |
| 35 | POST | /api/settings/rebuild | SettingsPage |
| 36 | GET | /api/settings/export | SettingsPage |
| WS | - | /ws/live | LiveMonitorPage |

## Appendix B: shadcn/ui Component Installation Order

```
Phase 0: button, input, badge, skeleton, separator, scroll-area
Phase 1: dialog, popover, dropdown-menu, table, tabs, tooltip, calendar, command, sheet, select, toast, toaster
```

Total: 18 shadcn/ui components.

## Appendix C: Existing Components to KEEP vs REBUILD vs EXTRACT

| Component | Action | Notes |
|-----------|--------|-------|
| `Sidebar.tsx` | REBUILD | Add collapsible state, mobile overlay |
| `TopBar.tsx` | REBUILD | Integrate new DateRangePicker, shadcn/ui buttons |
| `PageLayout.tsx` | KEEP | Already clean. Add optional breadcrumbs prop. |
| `CommandPalette.tsx` | REBUILD | Use shadcn/ui Command component |
| `DateRangePicker.tsx` | REBUILD | Use shadcn/ui Calendar + Popover |
| `ExportDropdown.tsx` | REBUILD | Use shadcn/ui DropdownMenu |
| `ErrorBoundary.tsx` | KEEP | Works correctly |
| `ThemeToggle.tsx` | REBUILD | Use shadcn/ui Button + DropdownMenu |
| `BudgetTracker.tsx` | KEEP | Self-contained, works |
| `CacheCalculator.tsx` | KEEP | Self-contained, works |
| `MetricCard.tsx` | ENHANCE | Add skeleton prop |
| `ChartCard.tsx` | REPLACE | With new ChartContainer |
| `DeltaBadge.tsx` | KEEP | Works correctly |
| `LoadingState.tsx` | KEEP | Used for page-level fallback, keep alongside skeleton |
| `ErrorState.tsx` | ENHANCE | Add retry button |
| `EmptyState.tsx` | ENHANCE | Add icon support |
| `CostTicker.tsx` | KEEP | Animated counter, works |
| `ActiveSessionBadge.tsx` | KEEP | Works correctly |
| `HeatmapGrid.tsx` | KEEP | CSS Grid implementation, well-designed |
| `TokenWaterfall.tsx` | KEEP | Works correctly |
| `AgentTreeView.tsx` | KEEP | Works correctly |
| `TurnBlock` (inline in SessionDetailPage) | EXTRACT | Move to `components/charts/TurnBlock.tsx` |
| `CostOverlayLine` (inline in SessionDetailPage) | EXTRACT | Move to `components/charts/CostOverlayLine.tsx` |
| `TurnDetailPanel` (inline in SessionDetailPage) | EXTRACT | Move to `pages/session-detail/TurnDetailPanel.tsx` |
| `MultiSelect` (inline in ExplorerPage) | EXTRACT | Move to `components/composite/MultiSelect.tsx` or rebuild with Popover+Checkbox |
| `PricingEditor` (inline in SettingsPage) | EXTRACT | Move to `pages/settings/SettingsPricing.tsx`, use DataTable |
| `ExpandedRow` (inline in ProjectsPage) | EXTRACT | Move to `pages/projects/ProjectExpandedRow.tsx` |
