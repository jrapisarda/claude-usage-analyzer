# Requirements Document: CCWAP Frontend — Web Dashboard for Claude Code Workflow Analytics Platform

**Version:** 1.0  
**Date:** 2026-02-05  
**Stakeholder:** Jonathan Rapier, CEO — BioInfo AI  
**Status:** Approved for Implementation

---

## Executive Summary

CCWAP Frontend is a React-based web dashboard that provides a visual interface for the existing Claude Code Workflow Analytics Platform (CCWAP). It replaces CLI-only interaction with an 8-page interactive dashboard served from a local FastAPI backend, enabling click-through drill-down analytics, real-time session monitoring via WebSocket, rich session replay with a timeline scrubber, and full export capabilities. The product is a paid tool ($99–$149 one-time license) targeting individual Claude Code power users who need to understand, optimize, and justify their AI-assisted development workflows.

### Business Value

CCWAP CLI currently has 25+ report views behind flags that users must memorize. Power users forget which reports exist, cannot interactively explore data relationships, and cannot drill from a high-level cost anomaly down to the specific session turn that caused it. The frontend solves discoverability (navigable pages replace memorized flags), interactivity (click-through drill-down replaces re-running commands with new parameters), and real-time visibility (live WebSocket monitor replaces CLI watch mode). As the first paid Claude Code analytics tool in a market where every alternative is free, CCWAP Frontend occupies a premium niche — delivering workflow intelligence, not just cost tracking.

### Scope Classification

- **Type:** Enhancement (adds web frontend to existing CLI tool, extends backend with FastAPI + WebSocket)
- **Target:** Production-Complete (ship-ready, paid product quality)
- **Timeline:** Near-term — needed for product launch and revenue generation

---

## 1. Stakeholders & Users

### Primary Users

| Role | Technical Level | Primary Actions |
|------|-----------------|-----------------|
| Individual Claude Code developers (Pro/Max/API) | High — daily Claude Code users, comfortable with terminals, understand tokens/costs/models | Open dashboard after sessions. Drill into projects and sessions. Monitor live sessions. Compare workflow experiments. Export data for sharing/reporting. |

### Secondary Users / Systems

| Entity | Interaction Type | Notes |
|--------|------------------|-------|
| CCWAP CLI | Data Producer | Existing ETL pipeline parses JSONL → SQLite. Frontend reads from this SQLite database. CLI continues to work independently. |
| Claude Code JSONL files | Data Producer | `~/.claude/projects/<encoded-path>/*.jsonl` — raw session data. Live Monitor watches these for real-time updates. |
| SQLite database (`~/.ccwap/analytics.db`) | Data Source | 7-table schema populated by CCWAP ETL. All frontend queries read from here. |
| FastAPI backend | Middleware | New component — serves REST API + WebSocket + static React SPA |

### Approval Authority

Jonathan Rapier — sole stakeholder and product owner.

---

## 2. Functional Requirements

### 2.1 Core User Journeys

#### Journey 1: Post-Session Dashboard Review

```
Trigger: Developer finishes a Claude Code session, opens browser to localhost:8080
Steps:
1. Dashboard loads with today's vitals strip (sessions, cost, LOC, errors, 7-day sparkline)
2. Top-10 project table shows projects sorted by recent activity
3. 30-day cost chart renders with daily granularity
4. Activity feed shows most recent sessions with key stats
5. Developer spots a cost spike on the chart, clicks the data point
6. Drills into that day's sessions, clicks into a specific session
7. Session replay shows turn-by-turn timeline with cost accumulator
8. Developer identifies an expensive turn with high cache write, understands the cost driver
Outcome: Developer answers "what happened today?" in <30 seconds and "why was this expensive?" in <60 seconds, without typing a single CLI command.
```

#### Journey 2: Live Session Monitoring

```
Trigger: Developer starts a Claude Code session and wants to monitor costs in real-time
Steps:
1. Opens Live Monitor page in a second browser tab
2. WebSocket connects to FastAPI backend
3. Backend detects new JSONL data being written by Claude Code
4. Live display updates within 2 seconds: running cost, token accumulator, burn rate, sparkline
5. Developer sees cost climbing faster than expected
6. Developer adjusts approach in Claude Code (switches model, compacts context, etc.)
Outcome: Developer has real-time cost visibility and can course-correct mid-session.
```

#### Journey 3: Workflow Experiment Comparison

```
Trigger: Developer wants to compare two different workflow approaches (e.g., with and without a custom skill)
Steps:
1. Opens Experiments page
2. Creates tag "baseline" and assigns it to sessions from last week
3. Creates tag "with-custom-skill" and assigns it to this week's sessions
4. Clicks "Compare Tags" and selects the two tags
5. Side-by-side comparison renders: error rate, cost/KLOC, tokens/LOC, cache efficiency, tool success rates
6. Developer sees error rate dropped 40% with the custom skill
Outcome: Developer has quantitative evidence that the workflow change improved outcomes.
```

#### Journey 4: Deep Project Analysis

```
Trigger: Developer wants to understand a specific project's efficiency profile
Steps:
1. Opens Projects page
2. Uses column selector to show cost, LOC, error rate, cache hit rate, and models used
3. Sorts by cost descending to find most expensive project
4. Clicks the project row to expand inline detail (all 30+ metrics)
5. Clicks "View Details" to open full project page
6. Sees session list for this project, cost trend over time, tool usage breakdown, error categories
7. Drills into a high-error session to identify problematic patterns
Outcome: Developer understands exactly where money is going and where quality is suffering, per project.
```

#### Journey 5: Data Export for Reporting

```
Trigger: Developer needs to share analytics with a team lead or include in a status update
Steps:
1. Navigates to any page (e.g., Cost Analysis)
2. Sets date range to "This Month" using the global date picker
3. Clicks Export button
4. Selects CSV for table data, PNG for the cost trend chart
5. Downloads both files
Outcome: Developer has shareable artifacts without screenshots or manual data extraction.
```

### 2.2 Feature Specifications

#### Feature: Executive Command Center (Dashboard)

- **Description:** Default landing page providing zero-click answers to "what happened today?" and "what's the overall health of my Claude Code usage?"
- **Components:**
  1. **Vitals Strip** (top of page): Today's sessions, today's cost, today's LOC, today's error rate, 7-day cost sparkline (inline mini-chart). Each vital is a clickable link to the relevant detail page.
  2. **Top Projects Table**: Top 10 projects by recent activity. Columns: Project Name, Last Session, Sessions (period), Cost (period), LOC (period), Error Rate. Click row → drills to Project Detail page. "View All Projects →" link below table.
  3. **30-Day Cost Chart**: Area chart (Recharts AreaChart) showing daily cost for the last 30 days. Tooltip on hover shows date, cost, sessions, LOC. Click data point → drills to filtered daily view.
  4. **Activity Feed**: Reverse-chronological list of recent sessions (last 10). Each entry shows: project name, start time, duration, turns, cost, model(s) used. Click entry → drills to Session Detail.
- **Input:** Global date range picker state (default: Last 30 Days for chart, Today for vitals)
- **Output:** Rendered dashboard with live data from `/api/dashboard` endpoint
- **Business Rules:**
  - Vitals strip always shows today's data regardless of global date range selection
  - Project table respects global date range for aggregation
  - Chart respects global date range (adjusts granularity: daily <90d, weekly 90-365d, monthly >365d)
  - Activity feed always shows most recent 10 sessions regardless of date range
  - All monetary values formatted as USD with 2 decimal places
  - All token counts formatted with K/M suffixes (e.g., 2.5M, 856K)
- **Acceptance Criteria:**
  - [ ] Dashboard renders in <1 second from warm SQLite
  - [ ] Vitals strip shows accurate today's metrics matching `ccwap --today` output
  - [ ] Project table shows correct top 10 by most recent session timestamp
  - [ ] Cost chart renders 30 days of data with correct daily totals
  - [ ] Clicking a project row navigates to Project Detail with correct project pre-filtered
  - [ ] Clicking a chart data point navigates to filtered daily view for that date
  - [ ] Clicking an activity feed entry navigates to Session Detail

#### Feature: Global Date Range Picker

- **Description:** Persistent date range selector in the top navigation bar that filters all page views globally. Supports presets and custom range selection.
- **Presets:**
  - Today
  - Yesterday
  - This Week (Monday–today)
  - Last Week
  - Last 30 Days (default)
  - This Month
  - Last Month
  - All Time
- **Custom Range:** Calendar-based start/end date picker
- **Behavior:**
  - Selected range persists across page navigation (stored in URL query params and React state)
  - All API calls include the active date range as query parameters (`?from=YYYY-MM-DD&to=YYYY-MM-DD`)
  - Chart granularity adjusts automatically: daily for <90 days, weekly for 90–365, monthly for >365
  - Active range displayed in the picker button text (e.g., "Jan 1 – Jan 31, 2026")
- **Input:** User clicks preset or selects custom dates
- **Output:** All page data re-fetches with new date range
- **Business Rules:**
  - Date range cannot extend into the future
  - "Today" preset uses local timezone for date boundary
  - Empty date range (no data in period) shows empty state with message, not an error
  - URL is shareable — date range encoded in query params so bookmarks work
- **Acceptance Criteria:**
  - [ ] All 8 presets produce correct date boundaries
  - [ ] Custom range picker allows arbitrary start/end selection
  - [ ] Changing date range triggers data refresh on current page within 300ms
  - [ ] Date range persists when navigating between pages
  - [ ] URL reflects current date range and can be bookmarked/shared
  - [ ] Chart granularity switches correctly at 90-day and 365-day thresholds

#### Feature: Projects Page

- **Description:** Full-featured project analytics table with all 30+ metrics, sortable columns, expandable detail rows, column selector, search/filter, and server-side pagination.
- **Default Columns (visible on load):**

  | Column | Description |
  |--------|-------------|
  | Project Name | Decoded display name |
  | Sessions | Count in date range |
  | Turns | Total turns in date range |
  | LOC Written | Lines of code written |
  | Cost | Per-model, per-token-type accurate cost |
  | Error Rate | Errors / total tool calls |
  | Cache Hit Rate | cache_read / (input + cache_read) |
  | Last Session | Timestamp of most recent session |

- **Additional Columns (via column selector, all from CCWAP's 30+ project metrics):**

  | Column | Description |
  |--------|-------------|
  | LOC Delivered | Net LOC after edits |
  | Lines Added | Net positive from Edit tool |
  | Lines Deleted | Net negative from Edit tool |
  | Files Created | Unique Write file paths |
  | Files Edited | Unique Edit file paths |
  | Input Tokens | Sum of input_tokens |
  | Output Tokens | Sum of output_tokens |
  | Cache Read Tokens | Sum of cache_read_input_tokens |
  | Cache Write Tokens | Sum of cache_creation_input_tokens |
  | Thinking Chars | Characters in thinking blocks |
  | Cost/KLOC | Cost per thousand LOC |
  | Tokens/LOC | Output tokens per LOC |
  | Error Count | Absolute error count |
  | Tool Calls | Total tool invocations |
  | Tool Success Rate | (total - errors) / total |
  | Agent Spawns | Count of agent sessions |
  | Skill Invocations | Count of isMeta skill entries |
  | Duration | Time span of sessions |
  | CC Version | Claude Code version(s) used |
  | Git Branch | Branch(es) active |
  | Models Used | Set of models |
  | Avg Turn Cost | Cost / turns |
  | LOC/Session | LOC / sessions |
  | Errors/KLOC | Errors per thousand LOC |

- **Interactions:**
  - Click column header → sort ascending/descending
  - Click row → expand inline detail panel showing all 30+ metrics in a formatted grid
  - Click "View Details →" in expanded row → navigate to Project Detail page
  - Column selector dropdown → toggle columns on/off, preference saved to localStorage
  - Search bar → filter projects by name (substring match)
  - Pagination → 50 rows per page, server-side
- **Input:** `/api/projects?sort=cost&order=desc&page=1&limit=50&from=DATE&to=DATE&search=TERM`
- **Output:** Paginated project list with requested metrics
- **Business Rules:**
  - Column preferences persist in localStorage across sessions
  - Totals row at bottom of table sums/averages as appropriate (sum for counts, weighted average for rates)
  - Empty projects (0 sessions in date range) are hidden by default with a toggle to show them
  - Sort is server-side (SQL ORDER BY) for performance
- **Acceptance Criteria:**
  - [ ] All 30+ metrics are available via column selector
  - [ ] Default 8 columns render on first load
  - [ ] Sorting by any column produces correct order
  - [ ] Expandable row shows all metrics in formatted grid
  - [ ] Column preferences persist across browser sessions
  - [ ] Search filters projects by partial name match
  - [ ] Pagination works correctly with 50+ projects
  - [ ] Totals row accurately aggregates visible data

#### Feature: Session Detail & Timeline Replay

- **Description:** Flagship feature. Rich visual session replay showing each turn as a color-coded block on a horizontal timeline, with running cost accumulator line, expandable turn details, and per-turn cost breakdown.
- **Components:**
  1. **Session Header**: Project name, session ID, start/end time, duration, total cost, total tokens, model(s), CC version, git branch, error count
  2. **Timeline Scrubber**: Horizontal scrollable strip where each turn is a block. Block width proportional to token count. Block color intensity mapped to cost (darker = more expensive). Running cost line overlaid as a cumulative area. Hover shows turn summary tooltip. Click expands turn detail below.
  3. **Turn Detail Panel**: Expanded view of clicked turn showing:
     - Turn number, timestamp, model used
     - User prompt (truncated to 500 chars with expand)
     - Tool calls: tool name, file path, success/error, LOC written
     - Token breakdown: input, output, cache read, cache write
     - Thinking chars (count only, not content)
     - Per-turn cost
     - Stop reason
  4. **Session Stats Sidebar**: Aggregate stats for this session — total cost, tokens by type, LOC, errors, tool call distribution (pie/donut chart), cost by model (if multi-model)
- **Input:** `/api/sessions/:id/replay` returns ordered turns with full detail
- **Output:** Rendered timeline with interactive turn blocks
- **Business Rules:**
  - Timeline blocks for agent-spawned turns are visually distinct (different border/indicator)
  - Error turns are marked with red indicator on the timeline
  - Truncation events (`stop_reason: max_tokens`) are marked with yellow indicator
  - Sidechain turns are visually grouped/indented
  - Long sessions (>200 turns) use virtual scrolling on the timeline for performance
  - Turn detail panel shows actual tool call content, not just metadata
  - High-cost turns (>$1.00) are highlighted with a cost badge on the timeline block
- **Acceptance Criteria:**
  - [ ] Timeline renders all turns in chronological order
  - [ ] Block width is proportional to token count
  - [ ] Block color intensity maps to cost
  - [ ] Running cost accumulator line is accurate (sum matches session total within $0.01)
  - [ ] Click on turn block expands detail panel with full turn data
  - [ ] Error turns show red indicator
  - [ ] Truncation turns show yellow indicator
  - [ ] Sessions with 200+ turns render without performance degradation
  - [ ] Per-turn costs sum to session total within $0.01

#### Feature: Cost Analysis Page

- **Description:** Comprehensive cost analytics with breakdowns by token type, model, project, and time trends, plus spend forecasting.
- **Components:**
  1. **Cost Summary Cards**: Total cost, average daily cost, cost per KLOC, cost per turn (for date range)
  2. **Cost by Token Type**: Stacked bar or donut chart — Input, Output, Cache Read, Cache Write with dollar amounts and percentages
  3. **Cost by Model**: Bar chart showing cost per model (Opus 4.6, Opus 4.5, Sonnet, Haiku)
  4. **Cost Trend Chart**: Time series area chart (granularity adjusts with date range). Optionally stacked by token type.
  5. **Cost by Project**: Horizontal bar chart, top 10 projects by cost
  6. **Cache Savings Analysis**: Card showing cache read cost vs. full input cost equivalent, savings percentage, savings dollar amount
  7. **Spend Forecast**: Projected monthly cost based on last 14 days with ±1σ confidence range. Shows: spent so far, projected remaining, projected total.
- **Input:** `/api/cost/summary`, `/api/cost/by-token-type`, `/api/cost/by-model`, `/api/cost/trend`, `/api/cost/by-project`, `/api/cost/forecast`
- **Output:** Rendered charts and summary cards
- **Business Rules:**
  - All costs use per-model, per-token-type pricing (never flat rate)
  - Token type colors are consistent across all charts: Input (blue), Output (green), Cache Read (purple), Cache Write (orange)
  - Forecast uses last 14 days of actual data, projects forward with mean ± 1σ
  - Forecast confidence range narrows as more of the current month has elapsed
  - Cache savings percentage calculated as: (full_input_cost - cache_read_cost) / full_input_cost
- **Acceptance Criteria:**
  - [ ] Token type breakdown matches `ccwap --cost-breakdown` output
  - [ ] Model breakdown matches `ccwap --models` cost column
  - [ ] Trend chart daily totals sum to match total cost for the period
  - [ ] Cache savings calculation is accurate
  - [ ] Forecast projects forward from current data with visible confidence range
  - [ ] All charts respect global date range picker

#### Feature: Productivity Page

- **Description:** Development productivity analytics covering LOC output, efficiency ratios, language distribution, tool usage, error analysis, and file hotspots.
- **Components:**
  1. **Efficiency Summary Cards**: LOC Written, LOC Delivered, Cost/KLOC, Tokens/LOC, LOC/Session
  2. **LOC Trend Chart**: Time series showing LOC written per day/week
  3. **Language Distribution**: Horizontal bar chart or treemap showing LOC by programming language (50+ languages detected)
  4. **Tool Usage Table**: Tool name, call count, success rate, avg LOC per call. Sortable. Top tools: Write, Edit, Bash, Read, Grep, Glob, etc.
  5. **Error Analysis Panel**:
     - Error rate trend over time
     - Error categorization donut chart (File not found, Syntax error, Timeout, Permission denied, etc.)
     - Top errors table: error message (truncated), count, project, most recent occurrence
     - Error rate by CC version (if multiple versions in date range)
  6. **File Hotspots**: Table of most-modified files. Columns: file path, modification count, error count, languages. Sortable.
- **Input:** `/api/productivity/summary`, `/api/productivity/loc-trend`, `/api/productivity/languages`, `/api/productivity/tools`, `/api/productivity/errors`, `/api/productivity/files`
- **Output:** Rendered analytics panels
- **Business Rules:**
  - LOC counts exclude blank lines and comments (matching CLI behavior)
  - Error rate = errors / total tool calls (consistent with CLI)
  - Language detection uses file extension mapping (50+ languages)
  - File paths in hotspot table are relative to project root when possible
- **Acceptance Criteria:**
  - [ ] Efficiency metrics match `ccwap --efficiency` output
  - [ ] Language breakdown matches `ccwap --languages` output
  - [ ] Tool usage matches `ccwap --tools` output
  - [ ] Error categorization matches `ccwap --errors` output
  - [ ] File hotspots match `ccwap --files` output
  - [ ] All components respect global date range picker

#### Feature: Deep Analytics Page

- **Description:** Advanced analytics for power users covering extended thinking, truncation analysis, sidechain behavior, cache tier efficiency, branch-aware metrics, CC version impact, and skill/agent usage.
- **Components:**
  1. **Extended Thinking Panel**: Thinking chars by model (bar chart), thinking chars by project (table), daily thinking trend. Shows percentage of output that is thinking vs. visible content.
  2. **Truncation Analysis**: Stop reason distribution (donut chart), truncation count trend, cost impact of truncated responses (estimated wasted tokens).
  3. **Sidechain Analysis**: Sidechain count by project, sidechain overhead (extra tokens/cost from branching), sidechain-to-main ratio.
  4. **Cache Tier Analysis**: Breakdown of ephemeral 5-minute vs 1-hour cache tokens. Tier efficiency comparison. Cache tier usage trend.
  5. **Branch Analytics**: Cost and LOC by git branch. Branch comparison table (cost, LOC, errors, sessions per branch).
  6. **CC Version Impact**: Version-over-version comparison of error rates, efficiency, and cost. Helps identify regression or improvement from CC updates.
  7. **Skills & Agents Panel**: Skill invocation frequency (bar chart), agent spawn count by project, agent cost as percentage of total.
- **Input:** `/api/analytics/thinking`, `/api/analytics/truncation`, `/api/analytics/sidechains`, `/api/analytics/cache-tiers`, `/api/analytics/branches`, `/api/analytics/versions`, `/api/analytics/skills`
- **Output:** Rendered analytics panels
- **Business Rules:**
  - Thinking char estimation uses ~4 chars per token approximation
  - Truncation cost impact estimated as: truncated_response_cost × 0.3 (assuming 30% of truncated work is wasted)
  - CC version comparison requires at least 2 versions with 5+ sessions each to display
  - Branch analytics excludes branches with fewer than 2 sessions
- **Acceptance Criteria:**
  - [ ] Thinking analysis matches `ccwap --thinking` output
  - [ ] Truncation analysis matches `ccwap --truncation` output
  - [ ] Sidechain metrics match `ccwap --sidechains` output
  - [ ] Cache tier breakdown matches `ccwap --cache-tiers` output
  - [ ] Branch metrics match `ccwap --branches` output
  - [ ] Version comparison matches `ccwap --versions` output
  - [ ] Skills/agents match `ccwap --skills` output

#### Feature: Experiments Page

- **Description:** Workflow experiment management — create tags, assign them to sessions, and produce quantitative comparisons between tagged groups.
- **Components:**
  1. **Tag Manager**: List of existing tags with session counts. Create new tag button. Delete tag button with confirmation.
  2. **Tag Assignment**: Select sessions (by date range, by project, or by individual selection) and assign a tag. Bulk assignment supported.
  3. **Comparison Builder**: Select two tags from dropdowns. Click "Compare" to generate side-by-side metrics.
  4. **Comparison Results Table**: All core metrics with columns: Metric, Tag A Value, Tag B Value, Delta (absolute), Delta (%). Color-coded: green for improvements, red for regressions. Metrics include: sessions, turns, LOC, cost, cost/KLOC, error rate, cache hit rate, tokens/LOC, tool success rate, agent spawn count, avg turn cost.
  5. **Trend with Tag Annotations**: Time series chart with vertical markers where tags were applied, showing how metrics changed before/after an experiment.
- **Input:** `/api/experiments/tags`, `/api/experiments/assign`, `/api/experiments/compare`
- **Output:** Tag management UI and comparison results
- **Business Rules:**
  - A session can have multiple tags
  - Tags are free-form strings, alphanumeric + hyphens + underscores
  - Comparison requires both tags to have at least 1 session
  - Delta color coding: lower cost = green, lower errors = green, higher LOC = green, higher cache hit rate = green
  - Tag annotations on trend charts show as vertical dashed lines with tag name labels
- **Acceptance Criteria:**
  - [ ] Tags persist in SQLite across server restarts
  - [ ] Bulk tag assignment works for date range and project filters
  - [ ] Comparison table shows all core metrics with correct deltas
  - [ ] Color coding correctly identifies improvements vs regressions
  - [ ] Trend chart renders tag annotation markers at correct dates
  - [ ] Matches `ccwap --compare-tags` output for identical tag selections

#### Feature: Live Session Monitor

- **Description:** Real-time session monitoring via WebSocket connection. Displays running cost, token accumulation, burn rate, and live sparkline for the currently active Claude Code session.
- **Components:**
  1. **Connection Status Indicator**: Green dot = connected, yellow = reconnecting, red = disconnected
  2. **Active Session Card**: Session ID, project name, start time, elapsed time (live counter)
  3. **Cost Ticker**: Large-format running cost display, updating in real-time. Formatted to 4 decimal places during session (precision matters at sub-dollar amounts).
  4. **Token Accumulator**: Four gauges/counters for input, output, cache read, cache write tokens. Each updates independently.
  5. **Burn Rate**: Cost per minute calculated from last 5 minutes of activity. Displayed with trend arrow (↑ increasing, ↓ decreasing, → stable).
  6. **Live Sparkline**: Rolling 30-minute cost sparkline (Recharts LineChart, compact). One data point per minute.
  7. **Turn Counter**: Total turns in session, incrementing live.
- **WebSocket Protocol:**
  - Client connects to `ws://localhost:8080/ws/live`
  - Server watches `~/.claude/projects/` for file changes (inotify on Linux, polling fallback on Windows/macOS)
  - On new JSONL data detected: parse new entries, compute incremental cost, push update message to client
  - Message format:
    ```json
    {
      "type": "session_update",
      "session_id": "uuid",
      "project": "project-name",
      "timestamp": "ISO-8601",
      "cumulative": {
        "cost": 1.2345,
        "input_tokens": 1234,
        "output_tokens": 567,
        "cache_read_tokens": 8901,
        "cache_write_tokens": 2345,
        "turns": 15,
        "errors": 1
      },
      "turn": {
        "model": "claude-opus-4-5-20251101",
        "cost": 0.0567,
        "tokens": 1234,
        "tool_calls": ["Write", "Bash"]
      }
    }
    ```
  - Heartbeat every 30 seconds to maintain connection
  - Auto-reconnect on disconnect with exponential backoff (1s, 2s, 4s, max 30s)
- **Input:** WebSocket connection to FastAPI backend
- **Output:** Real-time dashboard with live-updating metrics
- **Business Rules:**
  - Updates must appear within 2 seconds of new JSONL data being written
  - If no active session detected, show "No active session" state with last session summary
  - Multiple simultaneous sessions: show the most recently active one with a session switcher (stretch goal — defer if complex)
  - Cost calculation uses same per-model, per-token-type pricing as all other views
  - Sparkline maintains 30 minutes of history in browser memory (not persisted)
  - If browser tab is backgrounded, accumulate updates and render on tab focus
- **Acceptance Criteria:**
  - [ ] WebSocket connects successfully on page load
  - [ ] New JSONL data triggers UI update within 2 seconds
  - [ ] Running cost matches what `ccwap --today` would report for the session
  - [ ] Burn rate calculation is accurate (cost delta / time delta for last 5 minutes)
  - [ ] Live sparkline updates once per minute with new data point
  - [ ] Connection status indicator accurately reflects WebSocket state
  - [ ] Auto-reconnect works after network disruption
  - [ ] "No active session" state displays correctly when idle

#### Feature: Settings Page

- **Description:** Configuration management for pricing, display preferences, data management, and license information.
- **Components:**
  1. **Pricing Table Editor**: Editable table of model pricing (per 1M tokens for input, output, cache read, cache write). Pre-populated with current Anthropic pricing. Save button writes to `~/.ccwap/config.json`.
  2. **Display Preferences**: Default date range, default sort column for Projects, timezone selection, number format (decimal places for costs).
  3. **Data Management**: ETL status (last run time, files processed, entries parsed). "Rebuild Database" button (triggers `--rebuild` equivalent). Database file size. Row counts per table.
  4. **License Information**: Product name, version, license type (perpetual), purchase date placeholder, support email.
  5. **About**: CCWAP version, Python version, FastAPI version, React version. Links to documentation.
- **Input:** User edits configuration values
- **Output:** Updated `~/.ccwap/config.json`, updated display preferences in localStorage
- **Business Rules:**
  - Pricing changes take effect on next page refresh (no live recalculation of historical data)
  - To recalculate historical costs with new pricing: user must click "Rebuild Database"
  - Display preferences persist in localStorage (client-side, no backend call)
  - "Rebuild Database" shows progress indicator and prevents navigation until complete
  - Invalid pricing values (negative, non-numeric) are rejected with inline validation error
- **Acceptance Criteria:**
  - [ ] Pricing table loads current values from config.json
  - [ ] Saving new pricing writes to config.json successfully
  - [ ] Display preferences persist across browser sessions
  - [ ] ETL status shows accurate last run information
  - [ ] "Rebuild Database" triggers full re-ETL and shows progress
  - [ ] Database stats match `ccwap --db-stats` output

#### Feature: Export System

- **Description:** Universal export capability available on every page. Supports CSV for table data, JSON for structured data, and PNG for chart images.
- **Components:**
  1. **Export Button**: Present in page header area on every page. Dropdown with format options.
  2. **CSV Export**: Exports the current table view (respecting filters, sort, and column selection) as a CSV file.
  3. **JSON Export**: Exports the current view's full data payload as formatted JSON.
  4. **Chart PNG Export**: Each chart component has a small camera/download icon. Clicking exports that specific chart as a PNG image via `html2canvas` or Recharts' built-in SVG export.
- **Input:** User clicks export and selects format
- **Output:** Downloaded file with appropriate name and timestamp (e.g., `ccwap-projects-2026-02-05.csv`)
- **Business Rules:**
  - CSV export includes all visible columns plus the current date range in a header comment
  - JSON export includes metadata (date range, generated timestamp, CCWAP version)
  - PNG export captures the chart at 2x resolution for print quality
  - File names follow pattern: `ccwap-{page}-{date}.{ext}`
  - Export downloads immediately (client-side generation, no server round-trip for CSV/JSON)
- **Acceptance Criteria:**
  - [ ] Export button appears on all 8 pages
  - [ ] CSV export produces valid CSV with correct column headers
  - [ ] JSON export produces valid JSON with metadata
  - [ ] PNG export captures chart at 2x resolution
  - [ ] File names include page name and current date
  - [ ] Exported CSV respects current column selection and sort order

#### Feature: Dark Mode

- **Description:** Dark mode as default theme with light mode toggle. Developer-tool aesthetic with high contrast for readability.
- **Implementation:**
  - Tailwind CSS `dark:` variant for all color values
  - Theme toggle button in top navigation bar (sun/moon icon)
  - Preference persisted in localStorage
  - On first visit: dark mode (no OS detection — dark is the default for this audience)
- **Color Palette (Dark Mode):**
  - Background: slate-900 (#0f172a)
  - Card/Panel: slate-800 (#1e293b)
  - Border: slate-700 (#334155)
  - Text primary: slate-100 (#f1f5f9)
  - Text secondary: slate-400 (#94a3b8)
  - Accent/primary: blue-500 (#3b82f6)
  - Success: green-500 (#22c55e)
  - Warning: amber-500 (#f59e0b)
  - Error: red-500 (#ef4444)
  - Chart colors: blue-500, green-500, purple-500, orange-500 (token type mapping)
- **Color Palette (Light Mode):**
  - Background: white (#ffffff)
  - Card/Panel: gray-50 (#f9fafb)
  - Border: gray-200 (#e5e7eb)
  - Text primary: gray-900 (#111827)
  - Text secondary: gray-500 (#6b7280)
  - Accent/primary: blue-600 (#2563eb)
  - Same semantic colors for success/warning/error/charts
- **Business Rules:**
  - Theme toggle is instant (no page reload)
  - All charts must be readable in both themes (Recharts adapts to CSS variables)
  - All text meets WCAG AA contrast ratio (4.5:1 minimum) in both themes
- **Acceptance Criteria:**
  - [ ] Dark mode is the default on first visit
  - [ ] Theme toggle switches instantly without page reload
  - [ ] Preference persists across browser sessions (localStorage)
  - [ ] All text meets WCAG AA contrast in both modes
  - [ ] All charts are readable in both modes
  - [ ] No visual artifacts (unstyled elements) in either mode

### 2.3 Edge Cases & Error Handling

| Scenario | Expected Behavior | User Feedback |
|----------|-------------------|---------------|
| Backend server not running | SPA shows connection error overlay with "Start CCWAP server: `ccwap serve`" instructions | Full-screen error with command to run |
| WebSocket disconnects during live monitoring | Auto-reconnect with exponential backoff. Show yellow status indicator. | "Reconnecting..." with spinner |
| No data in selected date range | Show empty state with illustration, not a broken page | "No data for this period. Try expanding the date range." |
| SQLite database doesn't exist | Backend returns 503 with helpful message | "Database not found. Run `ccwap` to initialize." |
| Database locked during ETL | Backend retries with WAL mode. Frontend shows brief loading state. | Transparent to user (WAL handles concurrent reads) |
| Session with 0 turns | Show session header with "No turns recorded" body | "This session has no recorded turns." |
| Very long session (500+ turns) | Virtual scrolling on timeline. Paginated turn list. | Performance stays smooth via virtualization |
| Unknown model in session data | Display model string as-is. Cost shows "Default pricing" indicator. | Small badge: "⚠ Unknown model — default pricing used" |
| Chart with single data point | Render as a dot, not a line/area | Appropriate for single-day range |
| Export with 0 rows | Export empty CSV with headers only. Show toast: "No data to export." | Toast notification |
| Browser tab backgrounded during live monitor | Accumulate WebSocket messages, render batch update on tab focus | Seamless — user sees current state on return |
| Config.json missing or corrupt | Backend uses hardcoded defaults. Settings page shows warning. | "Configuration file missing or invalid. Using defaults." |
| JSONL files deleted (cleanupPeriodDays) | Data remains in SQLite. No frontend impact. ETL warns on next run. | No user-facing issue from frontend |

---

## 3. Data Architecture

### 3.1 Data Entities

The frontend does not introduce new persistent data entities. All data is read from CCWAP's existing 7-table SQLite schema via the FastAPI REST API. The frontend stores only UI preferences in browser localStorage.

#### Existing Entities (Backend — Read Only from Frontend)

| Entity | Frontend Usage | Key Fields Consumed |
|--------|----------------|---------------------|
| `sessions` | Session list, project aggregation, drill-down | session_id, project_path, project_display, first_timestamp, last_timestamp, cc_version, git_branch, is_agent |
| `turns` | Session replay, turn-level analytics | uuid, session_id, timestamp, entry_type, model, all token fields, cost, stop_reason, thinking_chars, is_sidechain |
| `tool_calls` | Tool usage reports, error analysis, LOC counting, file hotspots | tool_name, file_path, success, error_message, error_category, loc_written, lines_added, lines_deleted, language |
| `experiment_tags` | Experiment page, tag management, comparison | tag_name, session_id, created_at |
| `daily_summaries` | Dashboard charts, trend views, cost analysis (**MUST BE POPULATED — PREREQUISITE**) | date, sessions, turns, tool_calls, errors, loc_written, all token fields, cost, agent_spawns, skill_invocations |
| `etl_state` | Settings page ETL status | file_path, last_mtime, last_processed, entries_parsed |
| `snapshots` | Settings page data management | timestamp, file_path, summary_json |

#### Client-Side Storage (localStorage)

| Key | Type | Purpose |
|-----|------|---------|
| `ccwap-theme` | `"dark" \| "light"` | Theme preference |
| `ccwap-project-columns` | `string[]` | Selected columns for Projects table |
| `ccwap-date-range` | `{preset: string} \| {from: string, to: string}` | Last active date range |
| `ccwap-page-size` | `number` | Table pagination preference |

### 3.2 Data Flow Diagram

```
┌───────────────────────┐
│  Claude Code           │
│  (writes JSONL files)  │
└──────────┬────────────┘
           │ filesystem
           ▼
┌───────────────────────┐     ┌──────────────────────────┐
│  JSONL Files           │     │  CCWAP ETL Pipeline       │
│  ~/.claude/projects/   │────▶│  (existing, runs on       │
│                        │     │   `ccwap` or `ccwap serve`)│
└───────────┬───────────┘     └──────────┬───────────────┘
            │                             │
            │ (Live Monitor watches       │ writes
            │  for new data)              ▼
            │              ┌──────────────────────────┐
            │              │  SQLite Database           │
            │              │  ~/.ccwap/analytics.db     │
            │              │  (7 tables + daily_summaries│
            │              │   materialized)             │
            │              └──────────┬───────────────┘
            │                         │ reads
            ▼                         ▼
┌───────────────────────────────────────────────────┐
│  FastAPI Backend (localhost:8080)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐│
│  │ REST API     │  │ WebSocket    │  │ Static    ││
│  │ /api/*       │  │ /ws/live     │  │ SPA Files ││
│  │ (fat, pre-   │  │ (push updates│  │ (React    ││
│  │  aggregated) │  │  on new JSONL│  │  build)   ││
│  └──────┬──────┘  └──────┬───────┘  └─────┬─────┘│
└─────────┼────────────────┼─────────────────┼──────┘
          │                │                 │
          ▼                ▼                 ▼
┌───────────────────────────────────────────────────┐
│  React SPA (browser)                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ TanStack │ │ WebSocket│ │ Recharts │          │
│  │ Query    │ │ Client   │ │ Charts   │          │
│  │ (REST    │ │ (Live    │ │ (render  │          │
│  │  cache)  │ │  Monitor)│ │  data)   │          │
│  └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────────────────────────────────┐         │
│  │ localStorage (theme, columns, prefs) │         │
│  └──────────────────────────────────────┘         │
└───────────────────────────────────────────────────┘
```

### 3.3 Data Sources & Sinks

| Source/Sink | Type | Format | Volume | Frequency |
|-------------|------|--------|--------|-----------|
| SQLite analytics.db | Database | SQLite | 50–200MB | Read on every API request |
| JSONL session files | File | JSONL | 1–500MB total | Watched in real-time by Live Monitor |
| config.json | File | JSON | <5KB | Read on server start, written from Settings |
| localStorage | Browser | Key-value | <10KB | Read/written on UI interactions |
| Export files (CSV/JSON/PNG) | File | Various | <5MB per export | Generated on-demand by user |

### 3.4 Validation Rules

| Field/Entity | Rule | Error Response |
|--------------|------|----------------|
| Date range `from` | Must be ISO date, ≤ today | 400: "Invalid start date" |
| Date range `to` | Must be ISO date, ≥ `from`, ≤ today | 400: "Invalid end date" |
| Page/limit params | Must be positive integers, limit ≤ 200 | 400: "Invalid pagination params" |
| Sort field | Must be in allowed column list | 400: "Invalid sort field: {field}" |
| Session ID | Must exist in sessions table | 404: "Session not found" |
| Tag name | Alphanumeric + hyphens + underscores, 1–100 chars | 400: "Invalid tag name" |
| Pricing values | Must be non-negative numbers | 400: "Invalid pricing value" |

---

## 4. Integration Points

### 4.1 External Systems

#### Integration: CCWAP SQLite Database

- **Type:** Database (file-based)
- **Direction:** Inbound (read-only from frontend perspective, except Settings writes to config)
- **Authentication:** File system permissions (localhost)
- **Connection:** `sqlite3` connection in FastAPI via `aiosqlite` for async access
- **Data Contract:** Existing 7-table CCWAP schema (sessions, turns, tool_calls, experiment_tags, daily_summaries, etl_state, snapshots)
- **Error Handling:** Database not found → 503 with setup instructions. Database locked → retry with WAL mode. Corrupt database → suggest `ccwap --rebuild`.

#### Integration: JSONL Files (Live Monitor)

- **Type:** File system watch
- **Direction:** Inbound (read-only)
- **Authentication:** File system permissions
- **Endpoint/Connection:** `~/.claude/projects/` directory tree
- **Data Contract:** Claude Code JSONL format (see CCWAP requirements doc §4.1 for full schema)
- **Error Handling:** File not readable → skip with warning. Directory missing → disable Live Monitor with message.

#### Integration: Config File

- **Type:** File system read/write
- **Direction:** Bidirectional
- **Authentication:** File system permissions
- **Endpoint/Connection:** `~/.ccwap/config.json`
- **Data Contract:**
  ```json
  {
    "pricing": {
      "claude-opus-4-5-20251101": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75
      }
    },
    "server": {
      "port": 8080,
      "host": "127.0.0.1"
    },
    "display": {
      "default_date_range": "last-30-days",
      "default_sort": "cost",
      "page_size": 50
    }
  }
  ```
- **Error Handling:** Missing file → create with defaults. Invalid JSON → use defaults, warn in Settings page.

### 4.2 Internal Dependencies

| Dependency | Purpose | Criticality |
|------------|---------|-------------|
| FastAPI | REST API + WebSocket server | Critical |
| uvicorn | ASGI server for FastAPI | Critical |
| pydantic | Request/response validation, API models | Critical |
| aiosqlite | Async SQLite access for FastAPI | Critical |
| React 18 | SPA framework | Critical |
| Vite | Build toolchain | Critical (build time only) |
| React Router | Client-side routing | Critical |
| TanStack Query | Server state management, caching | Critical |
| Recharts | Chart rendering | Critical |
| shadcn/ui | UI component library (Radix + Tailwind) | High |
| Tailwind CSS | Styling | High |
| html2canvas or similar | Chart PNG export | Medium |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Metric | Requirement | Measurement |
|--------|-------------|-------------|
| Dashboard initial load | < 1 second (warm SQLite) | Time from navigation to full render |
| SPA page navigation | < 300ms | Time from click to full render (client-side route) |
| API response time | < 200ms for aggregated endpoints | Server-side measured, logged |
| API response time (session replay) | < 500ms for sessions with <200 turns | Server-side measured |
| WebSocket update latency | < 2 seconds from JSONL write to UI update | End-to-end measured |
| Table render (50 rows) | < 100ms | Browser paint timing |
| Chart render (180 data points) | < 200ms | Browser paint timing |
| Initial SPA bundle load | < 500KB gzipped | Vite build output |
| Memory usage (browser) | < 100MB for typical usage | Chrome DevTools heap snapshot |

### 5.2 Security

- **Authentication:** None (localhost, single-player)
- **Authorization:** None
- **Data Protection:** All data stays on local machine. No network calls except to localhost. No telemetry, no analytics, no phone-home.
- **CORS:** Restricted to localhost only
- **Audit Requirements:** None

### 5.3 Compliance

| Framework | Requirements | Implementation Notes |
|-----------|--------------|---------------------|
| N/A | Local developer tool — no compliance requirements | No PII transmitted. All data local. |

### 5.4 Reliability

- **Availability Target:** N/A (local tool, user starts/stops server)
- **Recovery Time Objective:** If server crashes, user restarts `ccwap serve`. Frontend reconnects automatically.
- **Recovery Point Objective:** Zero data loss — SQLite and JSONL are source of truth. Frontend stores only UI preferences.
- **Backup Strategy:** None needed for frontend. Data persists in SQLite/JSONL.

### 5.5 Scalability

- **Current Scale:** ~150 sessions, ~5,000 turns, ~1 billion tokens tracked
- **Design Target:** 10x current: 1,500 sessions, 50,000 turns, 10 billion tokens
- **Scaling Strategy:** Server-side pagination and pre-aggregated endpoints handle growth. Virtual scrolling for long lists. Chart auto-granularity (daily/weekly/monthly) prevents excessive data points.

---

## 6. Technical Specifications

### 6.1 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Frontend Framework | React 18+ | Industry standard SPA framework. Large ecosystem. Developer audience expects it. |
| Build Tool | Vite | Fast HMR, excellent production builds, modern ESM-native. |
| Routing | React Router v6+ | Standard React routing. Supports URL-based state (date range, filters). |
| Server State | TanStack Query (React Query) | Caching, refetch, loading/error states out of the box. Eliminates boilerplate. |
| Charting | Recharts | React-native composable charts. Good tooltip/interaction support. Recharts handles responsive containers. |
| UI Components | shadcn/ui (Radix + Tailwind) | Accessible, customizable, no heavy dependency. Copy-paste pattern. |
| Styling | Tailwind CSS 3.x | Utility-first, dark mode via `dark:` variant, consistent design system. |
| Backend Framework | FastAPI | Async REST + native WebSocket support. Auto-generated OpenAPI docs. Pydantic validation. |
| ASGI Server | uvicorn | Production-grade ASGI server for FastAPI. |
| Database Access | aiosqlite | Async SQLite for non-blocking database queries in FastAPI. |
| API Validation | Pydantic v2 | Request/response models with automatic serialization. |
| Language | TypeScript (frontend), Python 3.10+ (backend) | TypeScript for type safety in SPA. Python for consistency with CCWAP codebase. |

### 6.2 Architecture Pattern

- **Pattern:** Local SPA + REST API (monolith backend serving both API and static files)
- **Rationale:** Simplest deployment model — one `ccwap serve` command. Backend is a monolith serving pre-aggregated API endpoints and static React build files. Frontend is a standard SPA with client-side routing. WebSocket for live monitoring. This pattern is proven by Jupyter, MLflow, Grafana, and similar local-first developer tools.

### 6.3 Project Structure

```
ccwap/
├── ccwap.py                        # CLI entry point (existing, add `serve` command)
├── __main__.py                     # Module entry point
├── config/                         # Configuration loading (existing)
├── cost/                           # Pricing and cost calculation (existing)
├── etl/                            # JSONL parsing and loading (existing)
├── models/                         # SQLite schema and entities (existing)
├── output/                         # CLI formatting and snapshots (existing)
├── reports/                        # CLI report generators (existing)
├── utils/                          # Utilities (existing)
├── tests/                          # Existing test suite (231 tests)
│
├── server/                         # NEW — FastAPI backend
│   ├── __init__.py
│   ├── app.py                      # FastAPI app factory, CORS, static file mount
│   ├── dependencies.py             # Database connection, config injection
│   ├── websocket.py                # WebSocket manager for Live Monitor
│   ├── file_watcher.py             # JSONL file system watcher for Live Monitor
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── dashboard.py            # GET /api/dashboard
│   │   ├── projects.py             # GET /api/projects, GET /api/projects/:id
│   │   ├── sessions.py             # GET /api/sessions, GET /api/sessions/:id,
│   │   │                           #     GET /api/sessions/:id/replay
│   │   ├── cost.py                 # GET /api/cost/summary, /by-token-type,
│   │   │                           #     /by-model, /trend, /by-project, /forecast
│   │   ├── productivity.py         # GET /api/productivity/summary, /loc-trend,
│   │   │                           #     /languages, /tools, /errors, /files
│   │   ├── analytics.py            # GET /api/analytics/thinking, /truncation,
│   │   │                           #     /sidechains, /cache-tiers, /branches,
│   │   │                           #     /versions, /skills
│   │   ├── experiments.py          # GET/POST/DELETE /api/experiments/tags,
│   │   │                           #     POST /api/experiments/assign,
│   │   │                           #     GET /api/experiments/compare
│   │   ├── settings.py             # GET/PUT /api/settings/pricing,
│   │   │                           #     GET /api/settings/etl-status,
│   │   │                           #     POST /api/settings/rebuild
│   │   └── export.py               # GET /api/export/:page?format=csv|json
│   ├── models/                     # Pydantic response models
│   │   ├── __init__.py
│   │   ├── dashboard.py
│   │   ├── projects.py
│   │   ├── sessions.py
│   │   ├── cost.py
│   │   ├── productivity.py
│   │   ├── analytics.py
│   │   ├── experiments.py
│   │   └── common.py               # Shared models (pagination, date range, etc.)
│   └── queries/                    # SQL query modules (centralized)
│       ├── __init__.py
│       ├── dashboard_queries.py
│       ├── project_queries.py
│       ├── session_queries.py
│       ├── cost_queries.py
│       ├── productivity_queries.py
│       ├── analytics_queries.py
│       └── experiment_queries.py
│
├── frontend/                       # NEW — React SPA source
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx                # React entry point
│   │   ├── App.tsx                 # Router setup, theme provider, query client
│   │   ├── api/                    # API client layer
│   │   │   ├── client.ts           # Axios/fetch wrapper, base URL config
│   │   │   ├── dashboard.ts        # Dashboard API hooks (useQuery)
│   │   │   ├── projects.ts         # Project API hooks
│   │   │   ├── sessions.ts         # Session API hooks
│   │   │   ├── cost.ts             # Cost API hooks
│   │   │   ├── productivity.ts     # Productivity API hooks
│   │   │   ├── analytics.ts        # Analytics API hooks
│   │   │   ├── experiments.ts      # Experiment API hooks
│   │   │   └── settings.ts         # Settings API hooks
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx     # Navigation sidebar
│   │   │   │   ├── TopBar.tsx      # Date picker, theme toggle, export button
│   │   │   │   └── PageLayout.tsx  # Standard page wrapper
│   │   │   ├── charts/
│   │   │   │   ├── CostAreaChart.tsx
│   │   │   │   ├── TokenBreakdownChart.tsx
│   │   │   │   ├── ModelCostChart.tsx
│   │   │   │   ├── LanguageChart.tsx
│   │   │   │   ├── ErrorCategoryChart.tsx
│   │   │   │   ├── LiveSparkline.tsx
│   │   │   │   └── ChartExportWrapper.tsx  # HOC adding PNG export to any chart
│   │   │   ├── tables/
│   │   │   │   ├── DataTable.tsx    # Generic sortable, paginated table
│   │   │   │   ├── ColumnSelector.tsx
│   │   │   │   ├── ExpandableRow.tsx
│   │   │   │   └── ProjectTable.tsx # Projects-specific table configuration
│   │   │   ├── dashboard/
│   │   │   │   ├── VitalsStrip.tsx
│   │   │   │   ├── ProjectGrid.tsx
│   │   │   │   ├── ActivityFeed.tsx
│   │   │   │   └── CostOverview.tsx
│   │   │   ├── session/
│   │   │   │   ├── TimelineScrubber.tsx   # Flagship timeline replay component
│   │   │   │   ├── TurnBlock.tsx
│   │   │   │   ├── TurnDetail.tsx
│   │   │   │   ├── SessionHeader.tsx
│   │   │   │   └── SessionStats.tsx
│   │   │   ├── live/
│   │   │   │   ├── LiveMonitor.tsx
│   │   │   │   ├── CostTicker.tsx
│   │   │   │   ├── TokenAccumulator.tsx
│   │   │   │   ├── BurnRate.tsx
│   │   │   │   └── ConnectionStatus.tsx
│   │   │   ├── experiments/
│   │   │   │   ├── TagManager.tsx
│   │   │   │   ├── TagAssignment.tsx
│   │   │   │   ├── ComparisonBuilder.tsx
│   │   │   │   └── ComparisonResults.tsx
│   │   │   └── common/
│   │   │       ├── DateRangePicker.tsx
│   │   │       ├── ThemeToggle.tsx
│   │   │       ├── ExportDropdown.tsx
│   │   │       ├── EmptyState.tsx
│   │   │       ├── LoadingState.tsx
│   │   │       ├── ErrorState.tsx
│   │   │       └── MetricCard.tsx
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── ProjectsPage.tsx
│   │   │   ├── ProjectDetailPage.tsx
│   │   │   ├── SessionsPage.tsx
│   │   │   ├── SessionDetailPage.tsx
│   │   │   ├── CostAnalysisPage.tsx
│   │   │   ├── ProductivityPage.tsx
│   │   │   ├── DeepAnalyticsPage.tsx
│   │   │   ├── ExperimentsPage.tsx
│   │   │   ├── LiveMonitorPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts     # WebSocket connection manager
│   │   │   ├── useDateRange.ts     # Global date range state
│   │   │   ├── useTheme.ts         # Theme toggle
│   │   │   ├── useExport.ts        # Export functionality
│   │   │   └── useLocalStorage.ts  # Type-safe localStorage
│   │   ├── lib/
│   │   │   ├── utils.ts            # Formatting helpers (currency, tokens, dates)
│   │   │   ├── constants.ts        # Color palette, chart config, token type colors
│   │   │   └── types.ts            # Shared TypeScript interfaces
│   │   └── styles/
│   │       └── globals.css         # Tailwind imports, custom CSS variables
│   └── dist/                       # Production build output (gitignored, built at publish)
│
├── static/                         # Built frontend files (copied from frontend/dist at build time)
│                                   # Served by FastAPI at / route
└── tests/
    ├── test_server/                # NEW — Backend API tests
    │   ├── test_dashboard_api.py
    │   ├── test_projects_api.py
    │   ├── test_sessions_api.py
    │   ├── test_cost_api.py
    │   ├── test_productivity_api.py
    │   ├── test_analytics_api.py
    │   ├── test_experiments_api.py
    │   ├── test_websocket.py
    │   └── conftest.py             # Test fixtures, mock SQLite database
    └── (existing CLI tests)
```

### 6.4 API Contracts

#### Endpoint: GET /api/dashboard

- **Description:** Returns all data needed for the Dashboard page in a single request.
- **Query Parameters:** `from` (date), `to` (date)
- **Response (Success):**
  ```json
  {
    "vitals": {
      "today": {
        "sessions": 3,
        "cost": 45.67,
        "loc_written": 2340,
        "error_rate": 0.023,
        "turns": 87
      },
      "sparkline_7d": [12.30, 45.60, 23.40, 0.00, 67.80, 34.50, 45.67]
    },
    "top_projects": [
      {
        "project_display": "my-web-app",
        "project_path": "c--projects-my-web-app",
        "last_session": "2026-02-05T14:30:00Z",
        "sessions": 12,
        "cost": 18.45,
        "loc_written": 12340,
        "error_rate": 0.023
      }
    ],
    "cost_trend": [
      {
        "date": "2026-01-06",
        "cost": 12.30,
        "sessions": 2,
        "loc_written": 1200
      }
    ],
    "recent_sessions": [
      {
        "session_id": "abc-123",
        "project_display": "my-web-app",
        "first_timestamp": "2026-02-05T10:00:00Z",
        "duration_seconds": 3600,
        "turns": 45,
        "cost": 12.34,
        "models": ["claude-opus-4-5-20251101"]
      }
    ]
  }
  ```
- **Status Codes:** 200, 503 (database not found)

#### Endpoint: GET /api/projects

- **Description:** Returns paginated project list with requested metrics.
- **Query Parameters:** `from`, `to`, `sort` (field), `order` (asc/desc), `page`, `limit`, `search` (name filter)
- **Response (Success):**
  ```json
  {
    "projects": [
      {
        "project_path": "c--projects-my-web-app",
        "project_display": "my-web-app",
        "sessions": 12,
        "turns": 456,
        "loc_written": 12340,
        "loc_delivered": 10200,
        "cost": 18.45,
        "error_rate": 0.023,
        "cache_hit_rate": 0.94,
        "last_session": "2026-02-05T14:30:00Z",
        "input_tokens": 45000,
        "output_tokens": 120000,
        "cache_read_tokens": 890000,
        "cache_write_tokens": 56000,
        "thinking_chars": 234000,
        "cost_per_kloc": 1.49,
        "tokens_per_loc": 9.7,
        "error_count": 12,
        "tool_calls": 520,
        "tool_success_rate": 0.977,
        "agent_spawns": 3,
        "skill_invocations": 5,
        "duration_seconds": 43200,
        "cc_versions": ["2.0.74"],
        "git_branches": ["main", "feature/auth"],
        "models_used": ["claude-opus-4-5-20251101"],
        "avg_turn_cost": 0.04,
        "loc_per_session": 1028,
        "errors_per_kloc": 0.97,
        "lines_added": 11000,
        "lines_deleted": 800,
        "files_created": 45,
        "files_edited": 120
      }
    ],
    "totals": {
      "sessions": 145,
      "turns": 5278,
      "loc_written": 110191,
      "cost": 2491.72
    },
    "pagination": {
      "page": 1,
      "limit": 50,
      "total_count": 20,
      "total_pages": 1
    }
  }
  ```
- **Status Codes:** 200, 400 (invalid params), 503

#### Endpoint: GET /api/sessions/:id/replay

- **Description:** Returns all turns for a session in chronological order with full detail for timeline replay.
- **Response (Success):**
  ```json
  {
    "session": {
      "session_id": "abc-123",
      "project_display": "my-web-app",
      "first_timestamp": "2026-02-05T10:00:00Z",
      "last_timestamp": "2026-02-05T11:00:00Z",
      "duration_seconds": 3600,
      "total_cost": 12.34,
      "total_turns": 45,
      "cc_version": "2.0.74",
      "git_branch": "main",
      "models_used": ["claude-opus-4-5-20251101"],
      "error_count": 2
    },
    "turns": [
      {
        "uuid": "turn-uuid-1",
        "turn_number": 1,
        "timestamp": "2026-02-05T10:00:05Z",
        "entry_type": "assistant",
        "model": "claude-opus-4-5-20251101",
        "input_tokens": 1234,
        "output_tokens": 567,
        "cache_read_tokens": 8901,
        "cache_write_tokens": 2345,
        "cost": 0.62,
        "cumulative_cost": 0.62,
        "stop_reason": "end_turn",
        "thinking_chars": 1200,
        "is_sidechain": false,
        "is_meta": false,
        "tool_calls": [
          {
            "tool_name": "Write",
            "file_path": "src/app.py",
            "success": true,
            "loc_written": 45,
            "language": "python"
          }
        ],
        "user_prompt_preview": "Create a FastAPI server that..."
      }
    ],
    "stats": {
      "cost_by_model": {"claude-opus-4-5-20251101": 12.34},
      "tool_distribution": {"Write": 15, "Edit": 10, "Bash": 20},
      "tokens_by_type": {
        "input": 5000,
        "output": 25000,
        "cache_read": 400000,
        "cache_write": 15000
      }
    }
  }
  ```
- **Status Codes:** 200, 404 (session not found), 503

#### Endpoint: WebSocket /ws/live

- **Description:** Real-time session monitoring. Server pushes updates when new JSONL data is detected.
- **Client → Server Messages:**
  ```json
  {"type": "subscribe"}
  {"type": "ping"}
  ```
- **Server → Client Messages:**
  ```json
  {
    "type": "session_update",
    "session_id": "uuid",
    "project": "project-name",
    "timestamp": "ISO-8601",
    "cumulative": {
      "cost": 1.2345,
      "input_tokens": 1234,
      "output_tokens": 567,
      "cache_read_tokens": 8901,
      "cache_write_tokens": 2345,
      "turns": 15,
      "errors": 1,
      "elapsed_seconds": 300
    },
    "turn": {
      "model": "claude-opus-4-5-20251101",
      "cost": 0.0567,
      "tokens": 1234,
      "tool_calls": ["Write", "Bash"]
    }
  }
  ```
  ```json
  {"type": "heartbeat", "timestamp": "ISO-8601"}
  ```
  ```json
  {"type": "no_active_session", "last_session_summary": {...}}
  ```
- **Status Codes:** 101 (WebSocket upgrade), 503

---

## 7. Testing Requirements

### 7.1 Test Scenarios

#### Scenario: Dashboard Loads with Correct Vitals

- **Type:** Integration
- **Preconditions:** SQLite database with known session data for today
- **Steps:**
  1. Start FastAPI server
  2. Request GET /api/dashboard
  3. Verify vitals.today matches expected values from known data
- **Expected Result:** Sessions, cost, LOC, error rate match manual calculation
- **Priority:** Critical

#### Scenario: Date Range Filtering Across All Endpoints

- **Type:** Integration
- **Preconditions:** Database with sessions spanning multiple weeks
- **Steps:**
  1. Request GET /api/projects?from=2026-01-01&to=2026-01-07
  2. Verify only sessions within that range are included in aggregation
  3. Repeat for /api/cost/summary, /api/productivity/summary
- **Expected Result:** All endpoints respect date range consistently
- **Priority:** Critical

#### Scenario: Session Replay Turn Costs Sum to Total

- **Type:** Integration
- **Preconditions:** Session with known turns and costs
- **Steps:**
  1. Request GET /api/sessions/:id/replay
  2. Sum all turn costs
  3. Compare to session.total_cost
- **Expected Result:** Sum matches within $0.01
- **Priority:** Critical

#### Scenario: WebSocket Live Monitor Updates

- **Type:** Integration
- **Preconditions:** FastAPI server running with WebSocket support
- **Steps:**
  1. Connect WebSocket to /ws/live
  2. Append new JSONL entry to a session file
  3. Verify WebSocket pushes update within 2 seconds
  4. Verify cumulative cost is accurate
- **Expected Result:** Update received within 2 seconds, cost is correct
- **Priority:** Critical

#### Scenario: Project Table Pagination

- **Type:** Integration
- **Preconditions:** Database with 60+ projects
- **Steps:**
  1. Request GET /api/projects?page=1&limit=50
  2. Verify 50 results returned
  3. Request GET /api/projects?page=2&limit=50
  4. Verify remaining results returned
  5. Verify no duplicates across pages
- **Expected Result:** All projects returned across pages, no duplicates
- **Priority:** High

#### Scenario: Experiment Tag Comparison

- **Type:** E2E
- **Preconditions:** Sessions tagged with two different tags
- **Steps:**
  1. POST /api/experiments/assign — assign tag "baseline" to sessions A, B
  2. POST /api/experiments/assign — assign tag "experiment" to sessions C, D
  3. GET /api/experiments/compare?tag_a=baseline&tag_b=experiment
  4. Verify all metrics computed and deltas are correct
- **Expected Result:** Comparison table with accurate metrics and deltas
- **Priority:** High

#### Scenario: Export Produces Valid CSV

- **Type:** Integration
- **Preconditions:** Database with project data
- **Steps:**
  1. Request GET /api/export/projects?format=csv&from=2026-01-01&to=2026-02-01
  2. Verify output is valid CSV with correct headers
  3. Verify row count matches project count for the date range
- **Expected Result:** Valid CSV file with accurate data
- **Priority:** High

#### Scenario: Dark/Light Mode Persistence

- **Type:** E2E (frontend)
- **Preconditions:** Browser with no localStorage data
- **Steps:**
  1. Load app — verify dark mode is active
  2. Toggle to light mode — verify visual switch
  3. Refresh page — verify light mode persists
  4. Toggle back to dark — refresh — verify dark persists
- **Expected Result:** Theme preference survives page reload
- **Priority:** Medium

### 7.2 Test Coverage Requirements

| Category | Coverage Target | Notes |
|----------|-----------------|-------|
| Backend API Unit Tests | 90%+ | All route handlers, query modules, Pydantic models |
| Backend Integration Tests | Core paths | All API endpoints with test SQLite database |
| WebSocket Tests | Connection lifecycle | Connect, subscribe, receive updates, reconnect |
| Frontend Component Tests | 70%+ | Key components: DataTable, TimelineScrubber, DateRangePicker, LiveMonitor |
| Frontend E2E Tests | Critical paths | Dashboard load, drill-down navigation, date range filtering, export |

### 7.3 Test Data Requirements

- **Test SQLite database** with deterministic data: 10 projects, 50 sessions, 500 turns, known costs
- **Test JSONL files** for Live Monitor WebSocket testing
- **Frontend test fixtures**: Mock API responses matching Pydantic model schemas
- All test data must produce known, hand-calculated expected values for cost verification

---

## 8. Deployment & Operations

### 8.1 Deployment Target

- **Environment:** Local (user's development machine)
- **Infrastructure:** Bare metal — Python process serving FastAPI
- **Orchestration:** None — single `ccwap serve` command

### 8.2 Environment Configuration

| Environment | Purpose | Config Notes |
|-------------|---------|--------------|
| Development (frontend) | React dev server with hot reload | `npm run dev` in `frontend/`, proxies API calls to FastAPI at localhost:8080 |
| Development (backend) | FastAPI with auto-reload | `uvicorn ccwap.server.app:app --reload` |
| Production (local) | Single process serving API + static SPA | `ccwap serve` → uvicorn serves FastAPI which mounts React build at `/` |

### 8.3 Build & Distribution

- **Frontend build:** `cd frontend && npm run build` produces optimized React SPA in `frontend/dist/`
- **Package bundling:** `frontend/dist/` contents are copied to `ccwap/static/` and included in the Python package
- **Distribution:** `pip install ccwap` installs everything (CLI + backend + bundled frontend)
- **No Node.js required** on user's machine — only at build/publish time

### 8.4 CLI Integration

```bash
# New command added to existing CCWAP CLI
ccwap serve                    # Start web dashboard (default: localhost:8080)
ccwap serve --port 9090        # Custom port
ccwap serve --host 0.0.0.0     # Listen on all interfaces (advanced)
ccwap serve --no-browser        # Don't auto-open browser
```

- On `ccwap serve`, the tool:
  1. Runs ETL (incremental, processes new JSONL files)
  2. Starts FastAPI/uvicorn on configured port
  3. Opens default browser to `http://localhost:8080`
  4. Prints "Dashboard running at http://localhost:8080 — press Ctrl+C to stop"

### 8.5 Monitoring & Observability

| Aspect | Tool/Approach | Alerts |
|--------|---------------|--------|
| Server health | `/api/health` endpoint returning status + uptime | None (local tool) |
| API errors | FastAPI exception handlers return structured JSON, log to stderr | Console output |
| WebSocket status | Connection status indicator in UI | Visual indicator only |

---

## 9. Documentation Requirements

### 9.1 Required Documentation

| Document | Audience | Contents |
|----------|----------|----------|
| README.md | Users (developers) | Overview, installation, quick start, `ccwap serve` usage, screenshots, feature list, configuration, FAQ |
| API Reference | Extension developers | Auto-generated from FastAPI OpenAPI docs at `/docs` |
| ARCHITECTURE.md | Contributors | Data flow, component hierarchy, API contract summary |

### 9.2 README Structure

```markdown
# CCWAP — Claude Code Workflow Analytics Platform

## Overview
## Screenshots
## Installation
### Requirements
### Setup
## Quick Start
### CLI Usage (existing)
### Web Dashboard
## Features
### Dashboard
### Projects
### Session Replay
### Cost Analysis
### Productivity
### Deep Analytics
### Experiments
### Live Monitor
### Export
## Configuration
### Pricing Table
### Display Preferences
### Server Settings
## API Reference
## FAQ
## License
## Support
```

---

## 10. Constraints & Risks

### 10.1 Known Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| FastAPI + uvicorn + pydantic + aiosqlite are new dependencies | CCWAP is no longer zero-dependency | Accepted trade-off for productization. Document in requirements. |
| Frontend requires Node.js at build time (not runtime) | Build pipeline needs Node 18+ | Only needed by developer, not end user. Pre-built SPA bundled in package. |
| SQLite concurrent access limitations | ETL writes while server reads could conflict | WAL mode handles this natively. FastAPI uses aiosqlite for non-blocking reads. |
| Chromium-only browser support | Firefox/Safari users may see issues | Document requirement. Developer audience overwhelmingly uses Chromium. |
| `daily_summaries` table is currently unpopulated | Dashboard and charts have no pre-aggregated data source | PREREQUISITE: Update ETL to materialize daily_summaries on every run. |
| Session replay for very long sessions (500+ turns) | Browser memory and render performance | Virtual scrolling on timeline. Paginate turn detail list. |

### 10.2 Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| daily_summaries not populated before frontend ships | High (known gap) | Critical (dashboard broken) | Explicit prerequisite. ETL update must complete before frontend development begins. |
| FastAPI/React bundle exceeds 500KB gzipped | Low | Medium (slow first load) | Vite tree-shaking. Code-split by route. Monitor bundle size in CI. |
| Recharts performance with 1000+ data points | Low | Medium (chart lag) | Auto-granularity (daily/weekly/monthly). Limit max data points per chart to 365. |
| WebSocket reliability on Windows | Medium | Medium (Live Monitor unreliable) | File polling fallback for JSONL watching on Windows (inotify not available). |
| Anthropic changes JSONL format | Medium | Low (existing ETL handles defensively) | Same defensive parsing strategy. Frontend degrades gracefully on missing fields. |
| User expects cloud sync / multi-device | Low | Low (feature expectation mismatch) | Clear documentation: local-only for v1. Cloud is future roadmap. |

### 10.3 Assumptions

| Assumption | If False |
|------------|----------|
| Python 3.10+ is available on target machines | Need to support older Python or document requirement clearly |
| Users have Chromium-based browser installed | Need to test and support Firefox/Safari |
| Users run `ccwap serve` manually (not as a system service) | Need to provide systemd/launchd service files |
| SQLite WAL mode handles concurrent ETL + server reads | Need to implement read-retry logic or separate databases |
| 50-row pagination is appropriate for 20–50 project datasets | Need to support configurable page sizes |
| One-time license model doesn't require license validation infrastructure | Need to implement key validation if piracy becomes an issue |
| Pre-built React SPA can be bundled into Python package <5MB | Need to optimize bundle or use CDN for assets |

---

## 11. Success Criteria

### 11.1 MVP Acceptance Criteria

- [ ] `ccwap serve` starts FastAPI + serves React SPA on `localhost:8080` (port configurable)
- [ ] Dashboard loads in <1s and displays: today's vitals, top-10 project table, 30-day cost chart, recent activity feed
- [ ] Global date range picker (presets + custom) filters all views consistently
- [ ] Projects page renders 50+ projects with sortable columns, expandable rows, column selector, and server-side pagination
- [ ] Click-through drill-down works end-to-end: Dashboard → Project → Session → Turn-level replay
- [ ] Session replay renders rich timeline scrubber with color-coded turn blocks, running cost accumulator, and expandable turn detail
- [ ] Cost Analysis page shows token type breakdown, model breakdown, forecast, and trend charts
- [ ] Productivity page shows LOC, efficiency, languages, tools, errors, and file hotspots
- [ ] Deep Analytics page shows thinking, truncation, sidechains, cache tiers, branches, versions, skills
- [ ] Experiments page supports tag creation, tag-to-session assignment, and side-by-side tag comparison
- [ ] Live Monitor connects via WebSocket, displays running cost/tokens/burn rate with live sparkline, updates within 2 seconds of new JSONL data
- [ ] Export button on every view produces CSV and JSON; chart PNG export works on all chart components
- [ ] Dark mode is default, light mode toggle works, preference persists in localStorage
- [ ] Settings page allows pricing table editing, display preferences, and shows license info
- [ ] All API endpoints return proper error responses (not stack traces) on failure
- [ ] `daily_summaries` table is populated by ETL and used by all dashboard/chart queries

### 11.2 Definition of Done

- [ ] All 16 MVP acceptance criteria pass
- [ ] Backend API tests pass (90%+ coverage on route handlers and query modules)
- [ ] Frontend component tests pass (70%+ coverage on key components)
- [ ] E2E tests pass for critical paths (dashboard load, drill-down, date range, export)
- [ ] WebSocket live monitor tests pass (connect, update, reconnect)
- [ ] All API responses match documented Pydantic models
- [ ] Lighthouse scores: Performance 90+, Accessibility 95+, Best Practices 100
- [ ] React production bundle < 500KB gzipped
- [ ] README.md complete with installation, usage, screenshots, and FAQ
- [ ] ARCHITECTURE.md complete with data flow and component hierarchy
- [ ] FastAPI auto-generated OpenAPI docs accessible at /docs
- [ ] `ccwap serve` works on Windows, macOS, and Linux
- [ ] Stakeholder runs dashboard against actual production CCWAP database and confirms accuracy
- [ ] Stakeholder sign-off received

### 11.3 Out of Scope (Explicit)

- Multi-user support, authentication, or team features
- Cloud hosting or SaaS deployment
- Mobile-responsive design (desktop-only, developer tool)
- License key validation or copy protection
- Custom SQL query interface
- Integration with external services (Slack, GitHub, Jira)
- Notifications, alerts, or email reports
- Multi-session simultaneous monitoring in Live Monitor
- Historical comparison in Live Monitor view
- Firefox or Safari browser optimization
- Automated CI/CD pipeline for the frontend (manual build for now)
- Data import from other tools (ccusage, Claude Code Usage Monitor)
- Internationalization or localization (English only)
- Print-optimized layouts

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| CCWAP | Claude Code Workflow Analytics Platform — the existing CLI tool being extended |
| SPA | Single Page Application — React app with client-side routing |
| Fat API | Backend API that returns pre-aggregated, ready-to-render data |
| TanStack Query | React library for server state management (caching, refetch, loading states) |
| shadcn/ui | Component library built on Radix UI primitives with Tailwind CSS styling |
| Recharts | React-based composable charting library |
| Timeline Scrubber | Rich visual session replay showing turns as blocks on a horizontal timeline |
| Vitals Strip | Dashboard top bar showing key daily metrics at a glance |
| Burn Rate | Cost per minute calculated from recent session activity |
| Virtual Scrolling | Rendering only visible items in long lists for performance |
| WAL Mode | SQLite Write-Ahead Logging — enables concurrent reads during writes |
| daily_summaries | Materialized table of pre-aggregated daily metrics (MUST BE POPULATED) |
| JSONL | JSON Lines format — one JSON object per line, used by Claude Code for session logs |
| ETL | Extract, Transform, Load — pipeline that parses JSONL into SQLite |
| Vault Pattern | Jonathan's proprietary AI-assisted development methodology |

## Appendix B: Reference Materials

| Resource | Link/Location | Purpose |
|----------|---------------|---------|
| CCWAP CLI README | (uploaded, in conversation context) | Full CLI feature reference, database schema, configuration |
| CCWAP Requirements Doc | (uploaded, `claude-code-analytics-requirements.md`) | Original CCWAP requirements with full data architecture |
| FastAPI Documentation | https://fastapi.tiangolo.com/ | Backend framework reference |
| Recharts Documentation | https://recharts.org/ | Charting library reference |
| shadcn/ui Documentation | https://ui.shadcn.com/ | Component library reference |
| TanStack Query Documentation | https://tanstack.com/query/ | Server state management reference |
| Tailwind CSS Documentation | https://tailwindcss.com/docs | Styling framework reference |
| Vite Documentation | https://vitejs.dev/ | Build tool reference |
| React Router Documentation | https://reactrouter.com/ | Routing reference |
| ccusage (competitor) | https://github.com/ryoppippi/ccusage | Free CLI tool — competitive reference |
| Claude Code Usage Monitor (competitor) | https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor | Free monitoring tool — competitive reference |
| claude-code-otel (competitor) | https://github.com/ColeMurray/claude-code-otel | OTel observability stack — competitive reference |
| Anthropic API Pricing | https://code.claude.com/docs/en/costs | Pricing reference for cost calculation |

## Appendix C: Prerequisite — daily_summaries Population

**This must be completed before frontend development begins.**

The CCWAP ETL pipeline must be updated to materialize the `daily_summaries` table on every ETL run. The table schema already exists but is never populated. The following fields must be computed and stored per date:

| Field | Aggregation |
|-------|-------------|
| date | Group key (YYYY-MM-DD) |
| sessions | COUNT DISTINCT session_id |
| messages | COUNT turns in date (named 'messages' in original schema) |
| user_turns | COUNT turns WHERE entry_type = 'user' |
| tool_calls | COUNT tool_calls in date |
| errors | COUNT tool_calls WHERE success = FALSE |
| error_rate | errors / tool_calls |
| loc_written | SUM tool_calls.loc_written |
| loc_delivered | SUM tool_calls.lines_added - SUM tool_calls.lines_deleted |
| lines_added | SUM tool_calls.lines_added |
| lines_deleted | SUM tool_calls.lines_deleted |
| files_created | COUNT DISTINCT file_path WHERE tool_name = 'Write' |
| files_edited | COUNT DISTINCT file_path WHERE tool_name = 'Edit' |
| input_tokens | SUM turns.input_tokens |
| output_tokens | SUM turns.output_tokens |
| cache_read_tokens | SUM turns.cache_read_tokens |
| cache_write_tokens | SUM turns.cache_write_tokens |
| thinking_chars | SUM turns.thinking_chars |
| cost | SUM turns.cost (per-model, per-token-type) |
| agent_spawns | COUNT sessions WHERE is_agent = TRUE |
| skill_invocations | COUNT turns WHERE is_meta = TRUE |

**Materialization strategy:** On each ETL run, recompute daily_summaries for all dates that had new/modified session data. Full rebuild on `--rebuild`. Incremental update otherwise (only recompute affected dates).

---

**Document Approval**

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Stakeholder | Jonathan Rapier | 2026-02-05 | ☑ Approved |
| BSA | Claude (Opus 4.6) | 2026-02-05 | ☑ Generated |
