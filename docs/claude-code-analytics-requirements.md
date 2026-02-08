# Requirements Document: Claude Code Workflow Analytics Platform (CCWAP)

**Version:** 1.0  
**Date:** 2026-02-03  
**Stakeholder:** Jonathan Rapier, CEO — BioInfo AI  
**Status:** Approved for Implementation

---

## Executive Summary

CCWAP is a Python CLI tool that ETLs Claude Code session JSONL files into a persistent SQLite database and produces actionable analytics for evaluating AI-assisted development workflow effectiveness. It replaces an existing 2,400-line monolith (`claude-token-analyzer.py`) that has 5 systemic cost calculation bugs, 2 data completeness gaps, and ignores half the available JSONL fields. The new system shifts the core question from "how much did I spend" to "did that workflow change improve outcomes."

### Business Value

Jonathan runs 37+ production agents and iterates on skills, memory configurations, and requirements document strategies for Claude Code. He currently cannot answer critical questions like "did adding that skill reduce errors" or "did that 1,247-line requirements doc create context overhead." This tool provides the instrumentation layer for his Vault Pattern methodology — enabling data-driven optimization of AI-assisted development workflows that produce pharmaceutical-grade validation outputs. Accurate cost tracking alone (fixing the current ~100x cost overcount on daily views) eliminates false signals that distort decision-making.

### Scope Classification

- **Type:** Enhancement (full rewrite of existing tool, preserving CLI interface patterns)
- **Target:** Production-Complete
- **Timeline:** Near-term — needed for ongoing workflow optimization across active projects

---

## 1. Stakeholders & Users

### Primary Users

| Role | Technical Level | Primary Actions |
|------|-----------------|-----------------|
| Jonathan (CEO/Developer) | High — enterprise architect, AI-assisted development pioneer | Runs analytics after each project session. Compares workflow experiments. Evaluates agent/skill effectiveness. Tracks error rates and token efficiency across projects. |

### Secondary Users / Systems

| Entity | Interaction Type | Notes |
|--------|------------------|-------|
| Claude Code JSONL files | Data Producer | `~/.claude/projects/<encoded-path>/*.jsonl` — primary data source |
| stats-cache.json | Data Producer | `~/.claude/stats-cache.json` — supplementary aggregate data (limited, not authoritative for daily costs) |
| SQLite database | Data Sink | Persistent local storage for all extracted metrics across all time |
| JSON export files | Data Sink | Timestamped comparison snapshots for historical trending |

### Approval Authority

Jonathan Rapier — sole user and stakeholder.

---

## 2. Functional Requirements

### 2.1 Core User Journeys

#### Journey 1: Post-Session Analysis

```
Trigger: Jonathan completes a Claude Code project session and runs `ccwap --all`
Steps:
1. Tool scans ~/.claude/projects/ for all JSONL files (including agent-*.jsonl and subagents/)
2. ETL pipeline parses new/modified JSONL files and upserts into SQLite
3. Tool generates comprehensive --all report with accurate per-model costs,
   project metrics, tool usage, errors, languages, efficiency, and hourly activity
4. Tool writes timestamped JSON snapshot to ~/.ccwap/snapshots/
Outcome: Jonathan sees accurate, complete analytics for the current session
   and all historical data. Can immediately identify anomalies, error spikes,
   or efficiency changes.
```

#### Journey 2: Workflow Experiment Comparison

```
Trigger: Jonathan tags a session with `--tag "vault-pattern-v2"` and later
   wants to compare against sessions tagged "vault-pattern-v1"
Steps:
1. Tool queries SQLite for all sessions matching each tag
2. Produces side-by-side comparison: error rate, tokens/LOC, cost/KLOC,
   cache efficiency, tool success rates, agent spawn counts
3. Highlights statistically significant differences
Outcome: Jonathan can determine whether the workflow change (new skill,
   different requirements doc size, added agents) improved outcomes.
```

#### Journey 3: Week-over-Week Full-Field Comparison

```
Trigger: Jonathan runs `ccwap --compare last-week` or `ccwap --compare last-week --by-project`
Steps:
1. Tool aggregates all metrics for current week and previous week
2. Produces full pivot table: every metric with absolute values and % deltas
3. If --by-project, breaks down by project with per-project deltas
Outcome: Jonathan sees directional trends across all dimensions,
   not just tokens and cost.
```

#### Journey 4: Historical Trend Review

```
Trigger: Jonathan runs `ccwap --trend error-rate --last 8w`
Steps:
1. Tool queries SQLite for weekly aggregates over requested period
2. Renders ASCII trend chart showing metric over time
3. Annotates with tag markers where experiments were tagged
Outcome: Jonathan sees whether error rates are trending up/down
   and can correlate with specific workflow changes.
```

### 2.2 Feature Specifications

#### Feature: JSONL ETL Pipeline

- **Description:** Parses all JSONL session files from `~/.claude/projects/` and extracts structured data into SQLite. Handles main session files, `agent-*.jsonl` files, and `subagents/*.jsonl` files. Performs incremental processing (only new/modified files since last run).
- **Input:** JSONL files at `~/.claude/projects/<encoded-project-path>/*.jsonl`
- **Output:** Populated SQLite database at `~/.ccwap/analytics.db`
- **Business Rules:**
  - Must parse ALL JSONL record types: `user`, `assistant`, `queue-operation`, `file-history-snapshot`
  - Must extract ALL available fields per the JSONL schema (see Data Architecture §3.1)
  - Agent files (`agent-*.jsonl`) count tokens/cost but NOT user messages (to avoid double-counting)
  - Subagent files count tokens/cost but NOT user messages
  - Incremental: track file modification time + byte offset to avoid re-parsing unchanged files
  - Handle malformed JSON lines gracefully (skip and log, never crash)
  - Handle timezone normalization (JSONL timestamps are UTC with `Z` suffix)
- **Acceptance Criteria:**
  - [ ] All JSONL files in `~/.claude/projects/` are discovered and parsed, including nested `subagents/` directories
  - [ ] Agent files are included in token/cost totals but excluded from message counts
  - [ ] Re-running the tool on unchanged files completes in <2 seconds (incremental skip)
  - [ ] Malformed JSON lines are skipped with a warning count, not a crash
  - [ ] UTC timestamps are correctly converted to local time for display

#### Feature: Accurate Per-Model Cost Calculation

- **Description:** Calculates costs using the correct pricing tier for each token type (input, output, cache_read, cache_write) per model, per turn. Never applies a flat rate across token types.
- **Input:** Per-turn token usage from JSONL `message.usage` fields + model identifier from `message.model`
- **Output:** Accurate cost at turn, session, daily, weekly, project, and all-time granularity
- **Business Rules:**
  - Pricing table (per 1M tokens):

    | Model | Input | Output | Cache Read | Cache Write |
    |-------|-------|--------|------------|-------------|
    | claude-opus-4-5-20251101 | $15.00 | $75.00 | $1.50 | $18.75 |
    | claude-sonnet-4-5-20250929 | $3.00 | $15.00 | $0.30 | $3.75 |
    | claude-sonnet-4-20250514 | $3.00 | $15.00 | $0.30 | $3.75 |
    | claude-3-5-sonnet-20241022 | $3.00 | $15.00 | $0.30 | $3.75 |
    | claude-haiku-3-5-20241022 | $0.80 | $4.00 | $0.08 | $1.00 |

  - Cost is calculated PER TURN using that turn's actual model, never assumed
  - Costs aggregate upward: turn → session → daily → weekly → project → total
  - Cache read vs cache write must be tracked separately at all granularities
  - The `cache_creation.ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens` fields should be captured for future cache tier analysis
  - Pricing table must be configurable via `~/.ccwap/config.json` for new models
  - The `stats-cache.json` file is NOT used for cost calculation (it lacks per-day cache breakdowns); JSONL is the sole source of truth
- **Acceptance Criteria:**
  - [ ] Running against the provided sample data produces costs matching manual calculation within $0.01
  - [ ] Daily cost totals sum to match the all-time total (no divergence between calculation paths)
  - [ ] Each model's cost is reported independently in model breakdown views
  - [ ] Adding a new model to config.json is picked up on next run without code changes

#### Feature: Experiment Tagging

- **Description:** Allows user to tag sessions or date ranges with experiment labels for later comparison.
- **Input:** CLI flag `--tag "experiment-name"` applied to current run or `--tag-range "experiment-name" --from DATE --to DATE` for retroactive tagging
- **Output:** Tag stored in SQLite `experiment_tags` table, associated with session IDs
- **Business Rules:**
  - A session can have multiple tags
  - Tags are free-form strings (user-defined)
  - Auto-detected metadata is stored alongside tags: Claude Code version, whether agents were spawned, whether skills were invoked, count of skill invocations, count of agent spawns
  - `--compare-tags "tag-a" "tag-b"` produces side-by-side metrics comparison
- **Acceptance Criteria:**
  - [ ] Tags persist in SQLite across runs
  - [ ] `--compare-tags` produces comparison table with deltas for all core metrics
  - [ ] Auto-detected metadata (CC version, agent count, skill count) is accurate against manual JSONL inspection

#### Feature: Comprehensive Project-Level Metrics

- **Description:** Per-project reporting with full metric set, far beyond the current LOC + cost view.
- **Input:** Aggregated session data from SQLite
- **Output:** Project report table and per-project detail view
- **Metrics per project (all required):**

  | Metric | Description | Source |
  |--------|-------------|--------|
  | Sessions | Count of unique sessions | session_id count |
  | Messages | User + assistant message count (excludes agent files) | type=user/assistant |
  | User Turns | User message count only | type=user |
  | LOC Written | Lines in Write tool content (non-blank, non-comment) | tool_use name=Write, content |
  | LOC Delivered (Net) | Lines added minus lines deleted via Edit tool | Edit old_string/new_string diff |
  | Lines Added | Net positive line changes from Edit | Edit diff where new > old |
  | Lines Deleted | Net negative line changes from Edit | Edit diff where old > new |
  | Files Created | Unique file paths from Write tool | Write file_path, deduplicated |
  | Files Edited | Unique file paths from Edit tool | Edit file_path, deduplicated |
  | Input Tokens | Sum of input_tokens per model | usage.input_tokens |
  | Output Tokens | Sum of output_tokens per model | usage.output_tokens |
  | Cache Read Tokens | Sum of cache_read_input_tokens per model | usage.cache_read_input_tokens |
  | Cache Write Tokens | Sum of cache_creation_input_tokens per model | usage.cache_creation_input_tokens |
  | Thinking Tokens | Estimated from thinking content blocks (~4 chars/token) | content type=thinking |
  | Cost | Accurate per-model, per-token-type cost | Calculated from above |
  | Cost/KLOC | Cost per thousand LOC written | cost / (loc_written / 1000) |
  | Tokens/LOC | Output tokens per LOC written | output_tokens / loc_written |
  | Error Count | Tool calls with is_error=true or error content | tool_result is_error + content matching |
  | Error Rate | Errors / total tool calls | error_count / tool_call_count |
  | Tool Calls | Total tool invocations | content type=tool_use |
  | Tool Success Rate | Successful tool calls / total | (total - errors) / total |
  | Agent Spawns | Count of agent-*.jsonl files with activity | agent file count |
  | Skill Invocations | Count of isMeta=true entries with skill tool calls | isMeta + Skill tool_use |
  | Duration | Time from first to last timestamp | timestamp range |
  | CC Version | Claude Code version used | version field |
  | Git Branch | Active branch during session | gitBranch field |
  | Models Used | Set of models used in session | message.model |
  | Cache Hit Rate | cache_read / (input + cache_read) | calculated |
  | Avg Turn Cost | Total cost / user turns | calculated |
  | LOC/Session | LOC written per session | loc_written / sessions |
  | Errors/KLOC | Errors per thousand LOC | errors / (loc / 1000) |

- **Acceptance Criteria:**
  - [ ] All 30+ metrics above are computed and displayed for each project
  - [ ] Project table is sortable by any metric via `--sort` flag
  - [ ] `--project "pattern"` wildcard filter works correctly
  - [ ] Totals row at bottom accurately sums/averages as appropriate per metric

#### Feature: Week-over-Week Comparison (All Fields)

- **Description:** Full-field comparison between time periods, optionally broken down by project.
- **Input:** `--compare last-week`, `--compare last-month`, `--compare YYYY-MM-DD..YYYY-MM-DD`
- **Output:** Table with all metrics showing previous period, current period, absolute delta, and percentage delta
- **Business Rules:**
  - Default comparison: current week vs previous week
  - All project-level metrics from §2.2 Feature "Comprehensive Project-Level Metrics" are included
  - `--compare last-week --by-project` produces per-project pivot with deltas
  - Cost comparison uses accurate per-model calculation (not flat rate)
  - Color coding: green for improvements (lower cost, lower errors), red for regressions
- **Acceptance Criteria:**
  - [ ] All metrics show both absolute and percentage deltas
  - [ ] `--by-project` breaks down comparison to per-project level
  - [ ] Zero-division is handled gracefully (show "N/A" not crash)

#### Feature: LOC Tracking (Both Generated and Delivered)

- **Description:** Tracks both "LOC Generated" (total content in Write tool calls — measures Claude's output volume) and "LOC Delivered" (net lines after accounting for edits/rewrites — measures actual deliverable).
- **Input:** Write tool `content` field and Edit tool `old_string`/`new_string` fields
- **Output:** Both metrics at session and project level
- **Business Rules:**
  - LOC Generated: count non-blank, non-comment lines in ALL Write tool content fields (even if same file is written multiple times — this is measuring generation volume)
  - LOC Delivered: for each unique file path, count the FINAL Write content + net Edit changes. This represents what actually shipped.
  - Both metrics displayed side-by-side in project view
  - Language detection from file extension applied to both metrics
  - LOC counting excludes blank lines and single-line comments (`#`, `//`, `--`, `/* */`)
  - Multi-line comment/docstring handling for Python (`"""`, `'''`) and C-style (`/* ... */`)
- **Acceptance Criteria:**
  - [ ] LOC Generated ≥ LOC Delivered for every project (by definition)
  - [ ] A file written 5 times counts 5x in Generated but only the final version in Delivered
  - [ ] Edit-only sessions (no Write calls) still show LOC Delivered from net Edit changes
  - [ ] Language breakdown is accurate for both metrics

#### Feature: Error Analysis with Workflow Context

- **Description:** Error tracking enriched with workflow context to answer "did this workflow change cause more errors."
- **Input:** Tool result entries with `is_error=true` or error content, plus session metadata
- **Output:** Error reports with categorization, project breakdown, sample errors, and trend data
- **Business Rules:**
  - Error detection sources (in priority order):
    1. `toolUseResult.success === false` (structured, most reliable)
    2. `tool_result` content with `is_error: true`
    3. `tool_result` content containing error patterns in first 200 chars (fallback)
  - Error categorization: File not found, Permission denied, Syntax error, Timeout, Connection error, Exit code non-zero, Other
  - For each error, capture: project, session_id, timestamp, tool name, file path (if applicable), error text (truncated to 200 chars), CC version, whether agents/skills were active
  - Error rate calculated as: errors / total tool calls (not total messages)
  - Errors/KLOC: errors per 1,000 LOC written (measures code quality signal)
- **Acceptance Criteria:**
  - [ ] Structured `toolUseResult.success` is used when available, not regex matching
  - [ ] Error rate is calculated consistently across all views (project, daily, weekly)
  - [ ] `--errors` view shows categorization, project breakdown, and sample errors
  - [ ] Errors correlate to CC version and agent/skill presence for experiment analysis

#### Feature: Daily/Weekly/Monthly Reports with Rolling Windows

- **Description:** Time-based reports that always include the current day, use accurate cost calculation, and support configurable windows.
- **Input:** SQLite aggregated data by date
- **Output:** Tabular CLI reports
- **Business Rules:**
  - `--daily`: Rolling 30 days ending today (inclusive). Always includes today's data from live JSONL parsing.
  - `--weekly`: Aggregated by ISO week (Monday start). Current partial week included.
  - `--monthly`: Aggregated by calendar month. Current partial month included.
  - ALL time-based reports use per-model, per-token-type cost calculation from JSONL data
  - Anomaly detection: flag days where cost exceeds 2x the rolling 7-day average
  - Week-over-week delta shown in weekly view for all columns
  - Live indicator (●) for today's data when computed from real-time JSONL scan
- **Acceptance Criteria:**
  - [ ] `--daily` always shows today, even if stats-cache.json hasn't updated
  - [ ] Daily cost totals match what `--all` reports as the total (no divergent paths)
  - [ ] Anomaly detection correctly identifies cost spikes

#### Feature: Session Replay with Per-Turn Costs

- **Description:** Replay a session showing each turn's user prompt, assistant actions, tool calls, token usage, and cumulative running cost. Existing feature, retained and fixed.
- **Input:** `--replay <session-id>` (supports partial ID match)
- **Output:** Chronological turn-by-turn display
- **Business Rules:**
  - Per-turn cost uses that turn's actual model, not session-level assumption
  - High-output turns (>10K tokens) are flagged
  - Tool calls listed with file paths
  - Cumulative cost shown as running total
  - Thinking content noted but not displayed in full
- **Acceptance Criteria:**
  - [ ] Per-turn cost sums to session total within $0.01
  - [ ] Partial session ID matching works (first N characters)

#### Feature: Spend Forecasting

- **Description:** Projects weekly and monthly spend based on historical patterns. Existing feature, retained with accurate cost basis.
- **Input:** Historical daily cost data from SQLite
- **Output:** Projected spend with confidence range
- **Business Rules:**
  - Uses last 14 days of actual cost data (from SQLite, not stats-cache)
  - Calculates mean, standard deviation
  - Projects: spent-so-far + (avg_daily × days_remaining) with ±1σ range
  - Trend analysis: compares last 7 days average to previous 7 days average
  - Budget alerts if configured in `~/.ccwap/config.json`
- **Acceptance Criteria:**
  - [ ] Forecast uses accurate historical costs, not the flat-rate calculation
  - [ ] Confidence range narrows as more of the period has elapsed

#### Feature: JSON Export for Comparison History

- **Description:** Every `--all` run automatically writes a timestamped JSON snapshot to enable historical comparison.
- **Input:** Current run's complete metrics
- **Output:** `~/.ccwap/snapshots/YYYY-MM-DD_HH-MM-SS.json`
- **Business Rules:**
  - Contains all metrics at summary, project, and daily granularity
  - Includes any active tags
  - `--diff <snapshot-file>` loads a previous snapshot and produces delta report
  - Snapshots are never auto-deleted
- **Acceptance Criteria:**
  - [ ] Snapshot JSON schema is stable and documented
  - [ ] `--diff` correctly loads and compares any valid snapshot file

#### Feature: Auto-Detection of Workflow Metadata

- **Description:** Automatically extracts workflow configuration signals from JSONL without requiring manual annotation.
- **Input:** JSONL fields: `version`, `isMeta`, `sourceToolUseID`, `isSidechain`, `toolUseResult.commandName`, agent file presence
- **Output:** Per-session metadata stored in SQLite
- **Detected signals:**

  | Signal | Source | Purpose |
  |--------|--------|---------|
  | CC Version | `version` field on every entry | Track behavior changes across CC updates |
  | Agent Spawns | `agent-*.jsonl` file count per project/session | Measure multi-agent usage |
  | Skill Invocations | `isMeta=true` + `sourceToolUseID` entries | Track skill usage frequency |
  | Skill Names | `toolUseResult.commandName` | Identify which skills were used |
  | Sidechain Usage | `isSidechain=true` entries | Track branching conversations |
  | Git Branch | `gitBranch` field | Correlate work to branches |
  | Stop Reason | `message.stop_reason` | Identify truncated vs completed responses |
  | Service Tier | `message.usage.service_tier` | Track API tier |
  | Working Directory | `cwd` field | Map sessions to actual project paths |

- **Acceptance Criteria:**
  - [ ] All 9 signals above are extracted and stored
  - [ ] `--session <id>` detail view displays all detected metadata
  - [ ] Metadata is queryable in comparison views

### 2.3 Edge Cases & Error Handling

| Scenario | Expected Behavior | User Feedback |
|----------|-------------------|---------------|
| JSONL file with malformed JSON lines | Skip bad lines, continue parsing | Warning: "Skipped N malformed lines in {file}" |
| JSONL file with no timestamp fields | Skip file (cannot determine date) | Warning: "No timestamps found in {file}, skipping" |
| Session with 0 messages after date filter | Exclude from results | No output (silent exclusion) |
| stats-cache.json missing or corrupt | Proceed with JSONL-only data (this is the primary source anyway) | Info: "stats-cache.json not found, using JSONL data only" |
| SQLite database missing | Create fresh database with schema | Info: "Creating new analytics database" |
| SQLite database schema outdated | Run migration to add new columns/tables | Info: "Migrating database schema from v{old} to v{new}" |
| ~/.claude/projects/ doesn't exist | Exit with helpful message | Error: "Claude Code projects directory not found. Has Claude Code been run?" |
| Duplicate JSONL entries (known CC bug with stream-json mode) | Deduplicate by UUID before insert | Silent dedup (log count in verbose mode) |
| Session spans midnight (timestamps cross date boundary) | Attribute each entry to its own date | Correct per-entry date assignment |
| Unknown model in JSONL | Use 'default' pricing (Sonnet tier) | Warning: "Unknown model '{name}', using default pricing" |
| Agent file with no corresponding main session | Include in token/cost totals for project | Normal processing (orphan agents still count) |
| Very large JSONL file (>100MB) | Stream processing, never load entire file to memory | Progress indicator for files >10MB |
| Concurrent runs of the tool | SQLite WAL mode handles concurrent reads | No special handling needed |

---

## 3. Data Architecture

### 3.1 Data Entities

#### Entity: sessions

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| session_id | TEXT | PRIMARY KEY | UUID from JSONL filename |
| project_path | TEXT | NOT NULL | Encoded project directory name |
| project_display | TEXT | | Human-readable project name (decoded from path) |
| first_timestamp | DATETIME | NOT NULL | First entry timestamp (UTC) |
| last_timestamp | DATETIME | | Last entry timestamp (UTC) |
| duration_seconds | INTEGER | | last - first timestamp |
| cc_version | TEXT | | Claude Code version string |
| git_branch | TEXT | | Git branch active during session |
| cwd | TEXT | | Working directory |
| is_agent | BOOLEAN | DEFAULT FALSE | Whether this is an agent-spawned session |
| parent_session_id | TEXT | | For agent sessions, the parent session |
| file_path | TEXT | NOT NULL | Absolute path to the JSONL file |
| file_mtime | REAL | | File modification time (for incremental processing) |
| file_size | INTEGER | | File size in bytes (for change detection) |

#### Entity: turns

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| session_id | TEXT | FK → sessions | |
| uuid | TEXT | UNIQUE | Entry UUID for deduplication |
| parent_uuid | TEXT | | Parent entry UUID (conversation threading) |
| timestamp | DATETIME | NOT NULL | Entry timestamp (UTC) |
| entry_type | TEXT | NOT NULL | 'user', 'assistant', 'queue-operation', etc. |
| model | TEXT | | Model used for this turn (assistant turns) |
| input_tokens | INTEGER | DEFAULT 0 | |
| output_tokens | INTEGER | DEFAULT 0 | |
| cache_read_tokens | INTEGER | DEFAULT 0 | |
| cache_write_tokens | INTEGER | DEFAULT 0 | |
| ephemeral_5m_tokens | INTEGER | DEFAULT 0 | 5-minute ephemeral cache tokens |
| ephemeral_1h_tokens | INTEGER | DEFAULT 0 | 1-hour ephemeral cache tokens |
| cost | REAL | DEFAULT 0 | Calculated cost for this turn |
| stop_reason | TEXT | | 'end_turn', 'max_tokens', 'tool_use', etc. |
| service_tier | TEXT | | 'standard', etc. |
| is_sidechain | BOOLEAN | DEFAULT FALSE | |
| is_meta | BOOLEAN | DEFAULT FALSE | Skill invocation entry |
| source_tool_use_id | TEXT | | Links meta entries to tool calls |
| thinking_chars | INTEGER | DEFAULT 0 | Character count of thinking blocks |
| user_type | TEXT | | 'external', 'internal' |

#### Entity: tool_calls

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| turn_id | INTEGER | FK → turns | |
| session_id | TEXT | FK → sessions | |
| tool_use_id | TEXT | | The tool_use ID for matching results |
| tool_name | TEXT | NOT NULL | 'Write', 'Edit', 'Bash', 'Read', etc. |
| file_path | TEXT | | Target file path if applicable |
| input_size | INTEGER | DEFAULT 0 | Size of tool input in chars |
| output_size | INTEGER | DEFAULT 0 | Size of tool output (Write content) in chars |
| success | BOOLEAN | DEFAULT TRUE | |
| error_message | TEXT | | Truncated error text (max 500 chars) |
| error_category | TEXT | | Categorized error type |
| command_name | TEXT | | For skill invocations (toolUseResult.commandName) |
| loc_written | INTEGER | DEFAULT 0 | LOC count for Write tool calls |
| lines_added | INTEGER | DEFAULT 0 | Net lines added for Edit tool calls |
| lines_deleted | INTEGER | DEFAULT 0 | Net lines deleted for Edit tool calls |
| language | TEXT | | Detected programming language from file extension |
| timestamp | DATETIME | | Timestamp of the tool call |

#### Entity: experiment_tags

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| tag_name | TEXT | NOT NULL | User-defined experiment label |
| session_id | TEXT | FK → sessions | |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | |

#### Entity: daily_summaries (materialized/cached)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| date | TEXT | PRIMARY KEY | YYYY-MM-DD |
| sessions | INTEGER | | |
| messages | INTEGER | | |
| user_turns | INTEGER | | |
| tool_calls | INTEGER | | |
| errors | INTEGER | | |
| error_rate | REAL | | |
| loc_written | INTEGER | | |
| loc_delivered | INTEGER | | |
| lines_added | INTEGER | | |
| lines_deleted | INTEGER | | |
| files_created | INTEGER | | |
| files_edited | INTEGER | | |
| input_tokens | INTEGER | | |
| output_tokens | INTEGER | | |
| cache_read_tokens | INTEGER | | |
| cache_write_tokens | INTEGER | | |
| thinking_chars | INTEGER | | |
| cost | REAL | | Accurate per-model cost |
| agent_spawns | INTEGER | | |
| skill_invocations | INTEGER | | |

#### Entity: etl_state

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| file_path | TEXT | PRIMARY KEY | Absolute path to JSONL file |
| last_mtime | REAL | | File modification time at last parse |
| last_size | INTEGER | | File size at last parse |
| last_processed | DATETIME | | When we last processed this file |
| entries_parsed | INTEGER | | Total entries parsed from this file |

#### Entity: snapshots

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| timestamp | DATETIME | NOT NULL | When snapshot was taken |
| file_path | TEXT | NOT NULL | Path to JSON snapshot file |
| tags | TEXT | | Comma-separated active tags |
| summary_json | TEXT | | Full metrics JSON blob |

#### Relationships

```
sessions --[1:many]--> turns
sessions --[1:many]--> tool_calls (denormalized for query speed)
turns --[1:many]--> tool_calls
sessions --[many:many]--> experiment_tags
sessions --[aggregates to]--> daily_summaries
etl_state --[tracks]--> JSONL files (1:1)
```

### 3.2 Data Flow Diagram

```
┌──────────────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  ~/.claude/projects/  │     │    ETL Pipeline      │     │  SQLite Database  │
│  *.jsonl files        │────▶│  (incremental parse) │────▶│  ~/.ccwap/        │
│  agent-*.jsonl        │     │  deduplicate by UUID  │     │  analytics.db     │
│  subagents/*.jsonl    │     │  per-model cost calc  │     │                  │
└──────────────────────┘     └─────────────────────┘     └──────────────────┘
                                       │                          │
                                       │                          │
                                       ▼                          ▼
                              ┌─────────────────┐     ┌──────────────────┐
                              │  Auto-Detection  │     │  Report Engine   │
                              │  CC version      │     │  CLI output      │
                              │  Agents/Skills   │     │  JSON snapshots  │
                              │  Git branch      │     │  Comparison      │
                              └─────────────────┘     └──────────────────┘
```

### 3.3 Data Sources & Sinks

| Source/Sink | Type | Format | Volume | Frequency |
|-------------|------|--------|--------|-----------|
| JSONL session files | File | JSONL (one JSON object per line) | ~50-100 files, 1-500MB total | Continuous (Claude Code appends during sessions) |
| stats-cache.json | File | JSON | Single file, <100KB | Updated by Claude Code periodically |
| SQLite analytics.db | Database | SQLite | Growing, ~50-200MB over months | Updated on each tool run |
| JSON snapshots | File | JSON | One per --all run, ~50-200KB each | On each tool run |
| config.json | File | JSON | Single file, <5KB | Manual edits (pricing, budgets) |

### 3.4 Validation Rules

| Field/Entity | Rule | Error Response |
|--------------|------|----------------|
| JSONL line | Must be valid JSON | Skip line, increment malformed counter |
| timestamp | Must be ISO-8601 parseable | Skip entry if no valid timestamp available |
| uuid | Must be non-empty string | Skip entry (cannot deduplicate) |
| session_id | Must be non-empty string | Derive from filename if missing |
| model | Must be non-empty for assistant turns with usage | Use 'default' pricing, log warning |
| token counts | Must be non-negative integers | Treat negative values as 0 |
| cost | Must be non-negative | Assert; negative cost indicates calculation bug |
| file_path (tool calls) | No validation (can be any string) | Store as-is |
| LOC count | Must be non-negative | Assert; negative LOC indicates counting bug |

---

## 4. Integration Points

### 4.1 External Systems

#### Integration: Claude Code JSONL Files

- **Type:** File system read
- **Direction:** Inbound (read-only)
- **Authentication:** File system permissions (user home directory)
- **Endpoint/Connection:** `~/.claude/projects/<encoded-path>/*.jsonl`
- **Data Contract:**
  ```json
  {
    "parentUuid": "string|null",
    "isSidechain": false,
    "userType": "external",
    "cwd": "string",
    "sessionId": "uuid-string",
    "version": "2.0.74",
    "gitBranch": "string",
    "type": "user|assistant|queue-operation|file-history-snapshot",
    "message": {
      "role": "user|assistant",
      "model": "claude-opus-4-5-20251101",
      "content": [
        {"type": "text", "text": "string"},
        {"type": "tool_use", "id": "string", "name": "string", "input": {}},
        {"type": "tool_result", "tool_use_id": "string", "content": "string", "is_error": false},
        {"type": "thinking", "thinking": "string", "signature": "string"}
      ],
      "usage": {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_creation": {
          "ephemeral_5m_input_tokens": 0,
          "ephemeral_1h_input_tokens": 0
        },
        "service_tier": "standard"
      },
      "stop_reason": "end_turn|max_tokens|tool_use|null"
    },
    "uuid": "uuid-string",
    "timestamp": "ISO-8601-with-Z",
    "isMeta": false,
    "sourceToolUseID": "string|undefined",
    "toolUseResult": {
      "success": true,
      "commandName": "string"
    }
  }
  ```
- **Error Handling:** File not found → skip with warning. Permission denied → skip with warning. Corrupt file → stream-parse, skip bad lines.

#### Integration: stats-cache.json (Supplementary)

- **Type:** File system read
- **Direction:** Inbound (read-only)
- **Authentication:** File system permissions
- **Endpoint/Connection:** `~/.claude/stats-cache.json`
- **Data Contract:** JSON with keys: `version`, `lastComputedDate`, `dailyActivity[]`, `dailyModelTokens[]`, `modelUsage{}`, `totalSessions`, `totalMessages`, `hourCounts{}`, `firstSessionDate`, `longestSession{}`
- **Error Handling:** Missing or corrupt → proceed without it. This file is supplementary only (used for hourCounts and session metadata, not for cost calculation).

### 4.2 Internal Dependencies

| Dependency | Purpose | Criticality |
|------------|---------|-------------|
| Python stdlib `sqlite3` | Database layer | Critical — core persistence |
| Python stdlib `json` | JSONL parsing | Critical — data ingestion |
| Python stdlib `pathlib` | File system traversal | Critical — file discovery |
| Python stdlib `argparse` | CLI interface | Critical — user interaction |
| Python stdlib `datetime` | Timestamp handling | Critical — date math |
| Python stdlib `collections` | Counters, defaultdicts | High — aggregation |
| Python stdlib `dataclasses` | Data structures | High — code organization |
| No external dependencies | Zero pip install | By design — matches existing tool pattern |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Metric | Requirement | Measurement |
|--------|-------------|-------------|
| Initial full ETL | < 60 seconds for 500MB of JSONL | Time from start to "ETL complete" message |
| Incremental ETL (no changes) | < 2 seconds | Time to detect no files changed |
| Incremental ETL (1 new session) | < 5 seconds | Time to parse 1 new file + update DB |
| Report generation (from SQLite) | < 1 second for any single view | Time from DB query to CLI output |
| `--all` report | < 3 seconds (post-ETL) | Time from ETL complete to all reports rendered |
| Memory usage | < 200MB peak for 500MB of JSONL | Process RSS during full ETL |

### 5.2 Security

- **Authentication:** None — local tool, file system permissions only
- **Authorization:** Reads only from user's home directory
- **Data Protection:** SQLite file inherits OS file permissions. No encryption at rest needed (local dev tool). No network calls.
- **Audit Requirements:** None beyond the snapshot JSON files (which serve as an audit trail)

### 5.3 Compliance

| Framework | Requirements | Implementation Notes |
|-----------|--------------|---------------------|
| N/A | Personal development tool — no compliance requirements | No PII beyond local file paths. No data leaves the machine. |

### 5.4 Reliability

- **Availability Target:** N/A (CLI tool, not a service)
- **Recovery Time Objective:** If SQLite DB corrupts, full re-ETL from JSONL (< 60 seconds)
- **Recovery Point Objective:** Zero data loss — JSONL files are the source of truth, DB is a cache
- **Backup Strategy:** SQLite DB is rebuildable from JSONL. Snapshots stored as flat JSON files. User should configure `cleanupPeriodDays: 99999` in Claude Code settings to prevent JSONL deletion.

### 5.5 Scalability

- **Current Scale:** ~50 sessions, ~33K messages, ~750 files, ~500MB JSONL
- **Growth Projection:** ~200 sessions/month at current pace. ~2GB JSONL after 6 months.
- **Scaling Strategy:** SQLite handles this volume trivially. Incremental ETL ensures each run only processes new data. If >10GB ever becomes an issue, archive older JSONL and keep SQLite as the queryable store.

---

## 6. Technical Specifications

### 6.1 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Language | Python 3.10+ | Matches existing tool. Stakeholder expertise. |
| Database | SQLite (stdlib `sqlite3`) | Zero dependencies. Portable. Sufficient for local analytics. Supports WAL mode for concurrent reads. |
| CLI Framework | `argparse` (stdlib) | Matches existing tool. No pip install needed. |
| Configuration | JSON files | Simple, human-editable, stdlib parseable |
| Infrastructure | Local machine (Windows — D: drive) | Claude Code runs locally |

### 6.2 Architecture Pattern

- **Pattern:** Modular monolith with clear layer separation (not a single-file monolith like current tool)
- **Rationale:** The current 2,400-line single file is unmaintainable. Separating into modules (ETL, models, reports, cost calculation, config) enables independent testing and future extension, while keeping deployment simple (copy directory, run script).

### 6.3 Project Structure

```
ccwap/
├── ccwap.py                    # CLI entry point (argparse, dispatch)
├── etl/
│   ├── __init__.py
│   ├── parser.py               # JSONL line-by-line parser
│   ├── extractor.py            # Field extraction from parsed entries
│   ├── loader.py               # SQLite upsert logic
│   └── incremental.py          # File change detection, dedup
├── models/
│   ├── __init__.py
│   ├── schema.py               # SQLite schema creation + migrations
│   ├── dataclasses.py          # SessionStats, ProjectStats, ToolCall, etc.
│   └── queries.py              # Named SQL queries (all DB access centralized)
├── cost/
│   ├── __init__.py
│   └── calculator.py           # Per-model, per-token-type cost calculation
├── reports/
│   ├── __init__.py
│   ├── summary.py              # --all / default summary view
│   ├── daily.py                # --daily
│   ├── weekly.py               # --weekly
│   ├── projects.py             # --projects (full metrics)
│   ├── tools.py                # --tools
│   ├── languages.py            # --languages
│   ├── efficiency.py           # --efficiency
│   ├── errors.py               # --errors (with workflow context)
│   ├── sessions.py             # --sessions, --session, --replay
│   ├── compare.py              # --compare (all-field, by-project)
│   ├── forecast.py             # --forecast
│   ├── tags.py                 # --tag, --compare-tags
│   ├── trend.py                # --trend (ASCII charts)
│   └── hourly.py               # --hourly
├── output/
│   ├── __init__.py
│   ├── formatter.py            # Colors, bars, table rendering
│   ├── json_export.py          # --json output
│   ├── csv_export.py           # --export CSV
│   └── snapshot.py             # Timestamped JSON snapshot writer
├── config/
│   ├── __init__.py
│   └── loader.py               # Config file loading (~/.ccwap/config.json)
├── tests/
│   ├── test_cost_calculator.py # Verify cost math against known values
│   ├── test_parser.py          # Verify JSONL parsing edge cases
│   ├── test_etl.py             # Verify incremental ETL behavior
│   └── test_fixtures/          # Sample JSONL files for testing
│       ├── sample_session.jsonl
│       └── sample_agent.jsonl
└── README.md
```

### 6.4 CLI Interface

The CLI preserves all existing flags from the current tool for backward compatibility and adds new capabilities:

```
# Existing flags (preserved)
ccwap                           # Summary view (runs ETL first)
ccwap --all                     # All reports
ccwap --daily                   # Daily breakdown (rolling 30 days, always includes today)
ccwap --weekly                  # Weekly totals with WoW deltas
ccwap --projects                # Projects with FULL metric set
ccwap --tools                   # Tool usage breakdown
ccwap --languages               # LOC by language
ccwap --efficiency              # Productivity metrics
ccwap --errors                  # Error analysis with workflow context
ccwap --hourly                  # Activity by hour
ccwap --sessions                # List recent sessions
ccwap --session <id>            # Session detail (with auto-detected metadata)
ccwap --replay <id>             # Per-turn replay with accurate costs
ccwap --compare last-week       # Full-field period comparison
ccwap --forecast                # Spend forecast

# Date filters (preserved)
ccwap --today / --yesterday / --this-week / --last-week / --this-month / --last-month
ccwap --from YYYY-MM-DD --to YYYY-MM-DD

# Sort and filter (preserved)
ccwap --project "pattern"       # Wildcard project filter
ccwap --sort cost               # Sort projects by any metric

# Output (preserved)
ccwap --json                    # JSON output
ccwap --export file.csv         # CSV export
ccwap --no-color                # Disable ANSI colors

# NEW flags
ccwap --tag "experiment-name"                     # Tag current sessions
ccwap --tag-range "name" --from DATE --to DATE    # Retroactive tag
ccwap --compare-tags "tag-a" "tag-b"              # Compare experiments
ccwap --compare last-week --by-project            # Per-project period comparison
ccwap --trend <metric> --last <N>w                # Trend chart over N weeks
ccwap --diff <snapshot-file>                      # Compare against saved snapshot
ccwap --rebuild                                   # Force full re-ETL from JSONL
ccwap --verbose                                   # Show ETL progress and debug info
ccwap --db-stats                                  # Show database stats (row counts, size)
```

---

## 7. Testing Requirements

### 7.1 Test Scenarios

#### Scenario: Cost Calculation Accuracy

- **Type:** Unit
- **Preconditions:** Sample JSONL with known token counts for opus-4-5 model
- **Steps:**
  1. Parse sample JSONL with 10 input, 31971 cache_write, 12832 cache_read, 3 output tokens
  2. Calculate cost using opus-4-5 pricing
- **Expected Result:** Cost = (10/1M × $15) + (3/1M × $75) + (12832/1M × $1.50) + (31971/1M × $18.75) = $0.000150 + $0.000225 + $0.019248 + $0.599456 = $0.619079
- **Priority:** Critical

#### Scenario: Incremental ETL Skips Unchanged Files

- **Type:** Integration
- **Preconditions:** SQLite DB with previously parsed session
- **Steps:**
  1. Run ETL (should process file)
  2. Run ETL again without file changes
  3. Verify file was skipped via etl_state check
- **Expected Result:** Second run completes in <2 seconds, no new rows inserted
- **Priority:** Critical

#### Scenario: Agent Files Counted for Tokens Not Messages

- **Type:** Integration
- **Preconditions:** Project directory with main session file + agent-*.jsonl file
- **Steps:**
  1. Run ETL and generate project report
  2. Verify message count excludes agent file entries
  3. Verify token/cost totals include agent file entries
- **Expected Result:** Messages from main file only; costs from both files
- **Priority:** Critical

#### Scenario: Duplicate UUID Deduplication

- **Type:** Unit
- **Preconditions:** JSONL file with duplicate entries (same UUID appears twice)
- **Steps:**
  1. Parse file
  2. Verify only one row per UUID in turns table
- **Expected Result:** No duplicate turn rows
- **Priority:** High

#### Scenario: LOC Generated vs LOC Delivered

- **Type:** Unit
- **Preconditions:** Session where same file is written 3 times with increasing content
- **Steps:**
  1. Parse session
  2. Compare LOC Generated (sum of all 3 Write contents) vs LOC Delivered (only final Write)
- **Expected Result:** Generated > Delivered; Delivered matches final file content LOC
- **Priority:** High

#### Scenario: Experiment Tag Comparison

- **Type:** E2E
- **Preconditions:** Two sets of sessions tagged with different experiment names
- **Steps:**
  1. Tag sessions A, B, C with "baseline"
  2. Tag sessions D, E, F with "with-skills"
  3. Run `--compare-tags baseline with-skills`
- **Expected Result:** Side-by-side comparison with all metrics and deltas
- **Priority:** High

#### Scenario: Missing stats-cache.json

- **Type:** Integration
- **Preconditions:** No stats-cache.json exists
- **Steps:**
  1. Run `ccwap --all`
- **Expected Result:** Tool proceeds using JSONL data only. Info message displayed. All reports generate correctly.
- **Priority:** Medium

### 7.2 Test Coverage Requirements

| Category | Coverage Target | Notes |
|----------|-----------------|-------|
| Unit Tests | 90%+ | Focus on cost calculation, LOC counting, JSONL parsing, date math |
| Integration Tests | Core paths | ETL pipeline, incremental detection, SQLite queries |
| E2E Tests | All CLI flags | Each flag produces output without errors |

### 7.3 Test Data Requirements

Create test fixtures from anonymized versions of the stakeholder's actual JSONL files:
- `sample_session.jsonl` — complete session with user/assistant turns, tool calls, thinking blocks, errors
- `sample_agent.jsonl` — agent session file with tool calls
- `sample_with_skills.jsonl` — session with isMeta entries and skill invocations
- `sample_malformed.jsonl` — file with some corrupted JSON lines
- `sample_multi_model.jsonl` — session using multiple models (if applicable in future)

---

## 8. Deployment & Operations

### 8.1 Deployment Target

- **Environment:** Local (Windows, D: drive — Jonathan's development machine)
- **Infrastructure:** Bare metal (no containers)
- **Orchestration:** None — single CLI invocation

### 8.2 Environment Configuration

| Environment | Purpose | Config Notes |
|-------------|---------|--------------|
| Production (local) | Jonathan's Windows machine | Python 3.10+ required. No pip install. Copy directory, run `python ccwap.py`. |

### 8.3 CI/CD Requirements

- **Source Control:** Not specified — personal tool
- **Branch Strategy:** N/A
- **Pipeline Stages:** None — local execution
- **Deployment Strategy:** Copy and run

### 8.4 Monitoring & Observability

| Aspect | Tool/Approach | Alerts |
|--------|---------------|--------|
| ETL health | `--verbose` flag shows parse progress | Warnings for malformed files, unknown models |
| Database health | `--db-stats` shows row counts, DB file size | Warning if DB > 500MB |
| Data freshness | Compare last ETL timestamp to JSONL file mtimes | Warning if JSONL files are newer than last ETL |

---

## 9. Documentation Requirements

### 9.1 Required Documentation

| Document | Audience | Contents |
|----------|----------|----------|
| README.md | Jonathan (+ future users) | Overview, quick start, all CLI flags, config file format, pricing table, migration from old tool |
| Config reference | Jonathan | `~/.ccwap/config.json` schema with all options, defaults, and examples |
| Schema reference | Future development | SQLite table definitions with descriptions |

### 9.2 README Structure

```markdown
# Claude Code Workflow Analytics Platform (CCWAP)

## Overview
## Quick Start
## Migrating from claude-token-analyzer.py
## CLI Reference
### Report Commands
### Date Filters
### Experiment Tags
### Output Options
## Configuration
### Pricing Table
### Budget Alerts
### Custom Settings
## Database
### Schema Overview
### Rebuilding from JSONL
## How Cost Calculation Works
## IMPORTANT: Prevent JSONL Deletion
```

---

## 10. Constraints & Risks

### 10.1 Known Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| Zero external dependencies | Cannot use pandas, DuckDB, rich, or other analysis/display libraries | SQLite + stdlib is sufficient. Table formatting via custom formatter module. |
| Windows primary environment | Path handling must use pathlib (not hardcoded `/`) | pathlib handles cross-platform paths natively |
| JSONL schema is undocumented by Anthropic | Fields may change across CC versions | Defensive parsing — unknown fields are ignored, not errors. Schema versioning in ETL. |
| stats-cache.json lacks per-day cache token breakdowns | Cannot use it for accurate daily cost | Already mitigated: JSONL is the sole cost data source |
| LOC counting is heuristic | Multi-language comment detection isn't perfect | Acceptable trade-off — 95%+ accuracy is sufficient for comparative analytics |
| `cleanupPeriodDays` default is 30 | JSONL files auto-delete after 30 days | CRITICAL: User must set `cleanupPeriodDays: 99999` in `~/.claude/settings.json`. Tool should check this on startup and warn if not set. |

### 10.2 Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Claude Code changes JSONL schema | Medium | Medium | Defensive parsing. Version-specific extraction logic. CC version tracked per session. |
| JSONL files deleted before ETL | Low (if cleanupPeriodDays is set) | High (permanent data loss) | Check setting on startup. Warn loudly. Recommend cron/scheduled ETL. |
| SQLite DB corruption | Low | Low | DB is rebuildable from JSONL in <60 seconds via `--rebuild` |
| Duplicate JSONL entries (known CC bug) | Low | Low | UUID-based deduplication in ETL |
| Very long sessions (>10K turns) | Low | Medium (slow parse) | Stream processing, never load full file. Progress indicator for large files. |
| Pricing changes by Anthropic | Medium | Low (costs drift) | Configurable pricing in config.json. Warn if model not in pricing table. |

### 10.3 Assumptions

| Assumption | If False |
|------------|----------|
| All JSONL files are in `~/.claude/projects/` with encoded path directory names | Need to support additional JSONL locations |
| One JSONL file = one session (filename = session UUID) | Need to handle multi-session files |
| Agent files follow `agent-*.jsonl` naming convention | Need additional agent file detection |
| Python 3.10+ is available on the target machine | Need to support older Python or provide guidance |
| JSONL files are append-only (never modified in place) | Need full re-parse logic (not just new-line tracking) |
| UTC timestamps in JSONL with `Z` suffix | Need to handle other timezone formats |
| User runs tool manually after sessions (not automated) | Could add optional cron/hook integration later |

---

## 11. Success Criteria

### 11.1 MVP Acceptance Criteria

- [ ] ETL pipeline ingests ALL JSONL files (main sessions, agents, subagents) into SQLite
- [ ] Incremental ETL processes only new/changed files (<2 seconds for no-change runs)
- [ ] Cost calculation is accurate per-model, per-token-type (verified against manual calculation)
- [ ] Daily cost totals sum to match all-time total (no divergent calculation paths)
- [ ] `--all` produces complete report with all views: summary, daily, weekly, projects, tools, languages, efficiency, errors, hourly
- [ ] `--daily` shows rolling 30 days always including today
- [ ] `--projects` displays all 30+ metrics from §2.2
- [ ] `--compare last-week` produces full-field comparison with deltas
- [ ] `--compare last-week --by-project` produces per-project pivot with deltas
- [ ] `--tag` and `--compare-tags` work correctly for experiment comparison
- [ ] Both LOC Generated and LOC Delivered are tracked and displayed
- [ ] Error analysis includes structured `toolUseResult.success` detection
- [ ] Auto-detection captures CC version, agent spawns, skill invocations, git branch per session
- [ ] JSON snapshots written on every `--all` run
- [ ] Tool warns on startup if `cleanupPeriodDays` is not configured
- [ ] All existing CLI flags from current tool continue to work (backward compatibility)

### 11.2 Definition of Done

- [ ] All MVP acceptance criteria pass
- [ ] Unit tests pass for cost calculation, LOC counting, JSONL parsing
- [ ] Integration tests pass for ETL pipeline
- [ ] All CLI flags produce output without errors
- [ ] README.md complete with migration guide from old tool
- [ ] Stakeholder runs tool against actual production JSONL data and confirms numbers match expectations
- [ ] Stakeholder sign-off received

### 11.3 Out of Scope (Explicit)

- Web dashboard or HTML report generation — CLI only for this phase
- Snowflake / cloud database integration
- Real-time / watch mode (can be added later; current tool had this but it's low priority)
- Multi-user support or authentication
- Automated scheduling (cron integration) — user runs manually
- Git commit correlation (mapping tool calls to specific commits)
- Natural language querying of the SQLite database
- Cost alerts / notifications (beyond CLI warnings)
- Token-level billing window tracking (5-hour block analysis per ccusage)
- API cost vs subscription cost comparison

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| JSONL | JSON Lines — one JSON object per line, newline-delimited |
| ETL | Extract, Transform, Load — the pipeline that reads JSONL and writes to SQLite |
| LOC | Lines of Code — non-blank, non-comment lines |
| LOC Generated | Total LOC across all Write tool calls (measures Claude's output volume, includes rewrites) |
| LOC Delivered | Net LOC in final file state after all writes/edits (measures actual deliverable) |
| Turn | A single user message + assistant response pair |
| Session | A continuous Claude Code interaction identified by a UUID |
| Agent Session | A sub-session spawned by the main session (agent-*.jsonl files) |
| Experiment Tag | A user-defined label applied to one or more sessions for comparison |
| Cache Read | Tokens served from Anthropic's prompt cache (cheaper than fresh input) |
| Cache Write | Tokens written to Anthropic's prompt cache (more expensive than fresh input) |
| Ephemeral Cache | Short-lived cache tiers (5-minute and 1-hour) with distinct token counts |
| Vault Pattern | Jonathan's proprietary methodology for AI-assisted development with pharmaceutical-grade validation |
| CC | Claude Code — Anthropic's CLI-based AI coding assistant |
| Sidechain | A branching conversation path within a Claude Code session |
| isMeta | JSONL entries injected by Claude Code for skill/command invocations (not direct user messages) |

## Appendix B: Reference Materials

| Resource | Link/Location | Purpose |
|----------|---------------|---------|
| Current tool (broken) | `claude-token-analyzer.py` (uploaded) | Reference for existing CLI flags and feature set |
| Sample JSONL | Provided during interview | JSONL schema reference with all field types |
| stats-cache.json | Provided during interview | Understanding of supplementary data structure |
| ccusage | https://github.com/ryoppippi/ccusage | Best existing cost analysis tool — reference for correct cost calculation patterns |
| claude-code-usage-analyzer | https://github.com/aarora79/claude-code-usage-analyzer | Reference for statistical analysis approach (mean, median, P95) |
| Claude Code JSONL viewer (clog) | https://github.com/HillviewCap/clog | JSONL schema documentation |
| DuckDB analysis pattern | https://liambx.com/blog/claude-code-log-analysis-with-duckdb | Queryable log analysis approach |
| Claude Code settings | https://code.claude.com/docs/en/settings | `cleanupPeriodDays` configuration |
| Simon Willison — prevent log deletion | https://simonwillison.net/2025/Oct/22/claude-code-logs/ | Critical: JSONL auto-deletion after 30 days |
| Anthropic cost docs | https://code.claude.com/docs/en/costs | Official cost management guidance, pricing reference |
| Claude Code bug: duplicate JSONL entries | https://github.com/anthropics/claude-code/issues/5034 | Known bug requiring UUID deduplication |

## Appendix C: Bugs in Current Tool (claude-token-analyzer.py)

Documented here for the coding agent's reference when building the replacement.

### Bug 1: Flat-Rate Cost in Daily View (Line 1016)
```python
by_date[date]['cost'] = (total_tokens / 1_000_000) * 15.0  # WRONG
```
Applies Opus output rate ($75/MTok? Actually using $15 — unclear what this even represents) to ALL tokens regardless of type. Cache reads at $1.50/MTok are being charged at $15.00/MTok — a 10x overcount.

### Bug 2: Flat-Rate Cost in Weekly View (Line 1159)
```python
cost = (w['tokens'] / 1_000_000) * 15.0  # WRONG — same bug
```

### Bug 3: Flat-Rate Cost in Comparison View (Lines 1801-1802)
```python
prev_cost = (previous['tokens'] / 1_000_000) * 15.0  # WRONG
curr_cost = (current['tokens'] / 1_000_000) * 15.0    # WRONG
```

### Bug 4: Flat-Rate Cost in Forecast View (Line 1943)
```python
cost = (tokens / 1_000_000) * 15.0  # WRONG
```

### Bug 5: Default Model Pricing in Project View (Line 1826)
```python
return calculate_cost(p.input_tokens, p.output_tokens, p.cache_read, p.cache_write, 'default', config)
```
Uses 'default' pricing instead of actual models used. Projects using Opus get Sonnet pricing.

### Bug 6: Arbitrary Model Selection for Session Cost (Line 759)
```python
model = list(session.models_used)[0] if session.models_used else 'default'
```
Picks an arbitrary model from the set (set ordering is non-deterministic) instead of tracking per-turn model allocation.

### Bug 7: Missing Project Data on Recent Dates (Line 618)
```python
mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
if mtime.date() < target_date - timedelta(days=1):
    continue
```
The mtime optimization skips files not modified within 2 days. Sessions that span multiple days or were active recently but whose files weren't re-saved get dropped. The 02/02 report missing the sepsis-geo-ml project is likely caused by this.

### Bug 8: Agent Files Invisible in Project/Tool/Error Views (Line 691)
```python
for jsonl_file in project_path.glob('*.jsonl'):
    session = parse_session_file(jsonl_file, date_from, date_to)
```
`parse_session_file` skips `agent-*.jsonl` at line 367, so agent token usage is invisible in all session-based views (projects, tools, errors, efficiency).

### Bug 9: LOC-by-Language Evenly Distributed (Line 1244)
```python
lang_stats[lang] += session.loc_written // total_files
```
Divides LOC evenly across all files in a session rather than attributing LOC to the actual Write content for each file.

---

**Document Approval**

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Stakeholder | Jonathan Rapier | 2026-02-03 | ☑ Approved |
| BSA | Claude | 2026-02-03 | ☑ Generated |
