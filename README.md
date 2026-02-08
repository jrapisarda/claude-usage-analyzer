# CCWAP - Claude Code Workflow Analytics Platform

A zero-dependency Python CLI tool that ETLs Claude Code session data from JSONL files into SQLite and produces actionable analytics on usage, costs, and productivity metrics.

## Overview

CCWAP transforms raw Claude Code session logs into structured insights by:

- Parsing JSONL session files with a streaming parser (memory-efficient for >100MB files)
- Loading data into a 7-table SQLite database with WAL mode for concurrent access
- Calculating accurate per-model, per-token-type costs (Opus 4.6/4.5, Sonnet, Haiku)
- Generating 30+ project metrics including LOC, error rates, and cost efficiency
- Surfacing deep analytics: extended thinking, truncation, sidechains, cache tiers, and more
- Tracking experiments with tags for A/B testing workflows
- Comparing trends across time periods with delta analysis

**Key Features:**

- Python 3.10+ with zero external dependencies
- UUID-based deduplication prevents double-counting
- Incremental ETL processes only new/modified files
- Per-model pricing (Opus 4.6, Opus 4.5, Sonnet, Haiku) with cache token handling
- 25+ report views covering cost, productivity, model usage, and session complexity
- Real-time watch mode for continuous monitoring
- 50+ language detection for LOC counting
- Snapshot comparisons for tracking changes over time

## Installation

### Requirements

- Python 3.10 or higher
- Claude Code (must be installed and run at least once)

### Setup

1. Clone or download this repository:

```bash
git clone <repository-url>
cd claude-usage-analyzer
```

2. Add to your PATH or create an alias:

```bash
# Option 1: Add to PATH
export PATH="$PATH:/path/to/claude-usage-analyzer"

# Option 2: Create alias
alias ccwap="python /path/to/claude-usage-analyzer/ccwap/ccwap.py"
```

3. Run CCWAP for the first time:

```bash
python -m ccwap
```

This will:
- Create `~/.ccwap/analytics.db` (SQLite database)
- Create `~/.ccwap/config.json` (configuration file)
- Scan `~/.claude/projects/` for JSONL files
- Parse and load all session data

## Quick Start

### Basic Usage

```bash
# Show summary with all-time totals
python -m ccwap

# Show all reports
python -m ccwap --all

# Daily breakdown (rolling 30 days)
python -m ccwap --daily

# Project metrics with 30+ fields
python -m ccwap --projects

# Weekly totals with WoW deltas
python -m ccwap --weekly
```

### Filtering by Date

```bash
# Today's activity
python -m ccwap --today --daily

# Last week
python -m ccwap --last-week --projects

# Custom date range
python -m ccwap --from 2026-01-01 --to 2026-01-31 --daily

# This month
python -m ccwap --this-month --projects
```

### Analysis Reports

```bash
# Tool usage breakdown
python -m ccwap --tools

# Lines of code by language
python -m ccwap --languages

# Productivity metrics
python -m ccwap --efficiency

# Error analysis with categories, CC version, and model correlation
python -m ccwap --errors

# Activity by hour of day
python -m ccwap --hourly

# Cost forecast
python -m ccwap --forecast
```

### Deep Analytics

```bash
# Extended thinking analysis (thinking chars by model, project, daily trend)
python -m ccwap --thinking

# Model comparison (usage, tokens, efficiency, cache rates)
python -m ccwap --models

# Cost breakdown by token type (input, output, cache_read, cache_write)
python -m ccwap --cost-breakdown

# Truncation/stop reason analysis with cost impact
python -m ccwap --truncation

# File hotspot analysis (most modified, highest error rate)
python -m ccwap --files

# Branch-aware analytics (cost and efficiency by git branch)
python -m ccwap --branches

# CC version impact on efficiency and error rates
python -m ccwap --versions

# Human vs AI turn breakdown and autonomy metrics
python -m ccwap --user-types

# Sidechain/branching overhead analysis
python -m ccwap --sidechains

# Ephemeral cache tier analysis (5-min and 1-hour tiers)
python -m ccwap --cache-tiers

# Skill invocation and agent spawn analytics
python -m ccwap --skills
```

### Real-Time Monitoring

```bash
# Watch mode: continuously poll for new session data
python -m ccwap --watch

# Force re-scan of recently modified files
python -m ccwap --force-scan

# Custom poll interval and recency window
python -m ccwap --watch --poll-interval 10 --recent-hours 48
```

## CLI Reference

### Report Views

| Flag | Description |
|------|-------------|
| `--all`, `-a` | Show all reports (summary + daily + projects) |
| `--daily` | Daily breakdown for rolling 30 days |
| `--weekly` | Weekly totals with week-over-week deltas |
| `--projects` | Comprehensive project metrics (30+ fields) |
| `--tools` | Tool usage breakdown with success rates |
| `--languages` | Lines of code by programming language |
| `--efficiency` | Productivity metrics (LOC/session, cost/KLOC) |
| `--errors` | Error analysis with categorization |
| `--hourly` | Activity distribution by hour of day |
| `--sessions` | List recent sessions with model count and sidechains |
| `--forecast` | Monthly spend projection based on trends |
| `--thinking` | Extended thinking analytics by model and project |
| `--models` | Model comparison (usage, tokens, efficiency) |
| `--cost-breakdown` | Cost breakdown by token type |
| `--truncation` | Truncation/stop reason analysis with cost impact |
| `--files` | File hotspot analysis (modifications, errors, languages) |
| `--branches` | Branch-aware analytics (cost, efficiency per branch) |
| `--versions` | CC version impact on efficiency and errors |
| `--user-types` | Human vs AI turn breakdown |
| `--sidechains` | Sidechain/branching overhead analysis |
| `--cache-tiers` | Ephemeral cache tier analysis (5m/1h) |
| `--skills` | Skill invocation and agent spawn analytics |
| `--db-stats` | Database statistics (row counts per table) |

### Session-Specific Views

| Flag | Description |
|------|-------------|
| `--session <ID>` | Show detailed session information |
| `--replay <ID>` | Replay session turn-by-turn with costs |

### Comparison & Trends

| Flag | Description |
|------|-------------|
| `--compare <PERIOD>` | Compare two time periods (last-week, last-month, DATE..DATE) |
| `--by-project` | Break down comparison by project |
| `--diff <FILE>` | Compare current data against a snapshot file |
| `--trend <METRIC>` | Show trend for a specific metric |
| `--last <PERIOD>` | Period for trend analysis (e.g., 8w for 8 weeks) |

### Experiment Tags

| Flag | Description |
|------|-------------|
| `--tag <NAME>` | Tag current sessions (use with date filters) |
| `--tag-range <NAME>` | Tag a date range of sessions |
| `--compare-tags <TAG_A> <TAG_B>` | Compare two experiment tags |

### Date Filters

| Flag | Description |
|------|-------------|
| `--today` | Filter to today only |
| `--yesterday` | Filter to yesterday |
| `--this-week` | Filter to current week (Monday-today) |
| `--last-week` | Filter to previous week |
| `--this-month` | Filter to current month |
| `--last-month` | Filter to previous month |
| `--from <DATE>` | Start date (YYYY-MM-DD) |
| `--to <DATE>` | End date (YYYY-MM-DD) |

### Filtering & Sorting

| Flag | Description |
|------|-------------|
| `--project <PATTERN>` | Filter by project name (partial match) |
| `--sort <FIELD>` | Sort by field (cost, loc_written, sessions, etc.) |

### Output Options

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON (for programmatic use) |
| `--export <FILE>` | Export data to CSV file |
| `--no-color` | Disable color output |

### Real-Time Monitoring

| Flag | Description |
|------|-------------|
| `--watch` | Watch mode: continuously monitor for changes |
| `--force-scan` | Force re-scan of recently modified files |
| `--poll-interval <SEC>` | Poll interval in seconds for watch mode (default: 5) |
| `--recent-hours <N>` | Process files modified within N hours (default: 24) |

### ETL Control

| Flag | Description |
|------|-------------|
| `--rebuild` | Force full re-ETL of all files |
| `--verbose`, `-v` | Verbose output with progress |

## Example Workflows

### Daily Cost Monitoring

```bash
# Check today's spend
python -m ccwap --today

# Compare this week vs last week
python -m ccwap --compare last-week
```

### Project Analysis

```bash
# Find most expensive projects
python -m ccwap --projects --sort cost

# Analyze specific project
python -m ccwap --projects --project my-app

# Check project error rates
python -m ccwap --projects --this-month
```

### Experiment Tracking

```bash
# Tag sessions for experiment A
python -m ccwap --tag experiment-A --from 2026-01-15 --to 2026-01-20

# Tag sessions for experiment B
python -m ccwap --tag experiment-B --from 2026-01-21 --to 2026-01-27

# Compare the two experiments
python -m ccwap --compare-tags experiment-A experiment-B
```

### Language-Specific Analysis

```bash
# See which languages you're writing most
python -m ccwap --languages

# Check Python-specific productivity
python -m ccwap --projects --this-month | grep -i python
```

### Error Investigation

```bash
# View all errors this week (includes CC version and model correlation)
python -m ccwap --errors --this-week

# Check error rate trends
python -m ccwap --trend error_rate --last 4w
```

### Model and Cost Analysis

```bash
# Compare model efficiency (tokens, cost, cache rates)
python -m ccwap --models

# See where your money goes by token type
python -m ccwap --cost-breakdown

# Check if truncations are wasting tokens
python -m ccwap --truncation

# Analyze extended thinking overhead
python -m ccwap --thinking
```

### Branch and Version Analysis

```bash
# Compare cost across git branches
python -m ccwap --branches

# Check if a CC version upgrade improved efficiency
python -m ccwap --versions

# See how much overhead sidechains add
python -m ccwap --sidechains
```

### Session Complexity

```bash
# List sessions with model count and sidechain indicators
python -m ccwap --sessions

# Deep-dive into a specific session (includes complexity metrics)
python -m ccwap --session abc123

# Replay a session turn-by-turn
python -m ccwap --replay abc123
```

## Configuration

CCWAP uses `~/.ccwap/config.json` for configuration. All fields are optional with sensible defaults.

### Example Configuration

```json
{
  "database_path": "~/.ccwap/analytics.db",
  "snapshots_path": "~/.ccwap/snapshots",
  "claude_projects_path": "~/.claude/projects",

  "pricing": {
    "claude-opus-4-6": {
      "input": 5.00,
      "output": 25.00,
      "cache_read": 0.50,
      "cache_write": 6.25
    },
    "claude-opus-4-5-20251101": {
      "input": 15.00,
      "output": 75.00,
      "cache_read": 1.50,
      "cache_write": 18.75
    },
    "claude-sonnet-4-5-20250929": {
      "input": 3.00,
      "output": 15.00,
      "cache_read": 0.30,
      "cache_write": 3.75
    },
    "claude-haiku-4-5-20251001": {
      "input": 1.00,
      "output": 5.00,
      "cache_read": 0.10,
      "cache_write": 1.25
    },
    "claude-haiku-3-5-20241022": {
      "input": 0.80,
      "output": 4.00,
      "cache_read": 0.08,
      "cache_write": 1.00
    },
    "default": {
      "input": 3.00,
      "output": 15.00,
      "cache_read": 0.30,
      "cache_write": 3.75
    }
  },

  "budget_alerts": {
    "daily_warning": 10.00,
    "weekly_warning": 50.00,
    "monthly_warning": 200.00
  },

  "display": {
    "color_enabled": true,
    "progress_threshold_mb": 10,
    "table_max_width": 120
  },

  "pricing_version": "2026-02-01"
}
```

### Configuration Fields

**Paths:**
- `database_path`: SQLite database location (default: `~/.ccwap/analytics.db`)
- `snapshots_path`: Snapshot storage directory (default: `~/.ccwap/snapshots`)
- `claude_projects_path`: Claude Code projects directory (default: `~/.claude/projects`)

**Pricing:**
- Per-model pricing in USD per 1M tokens
- Separate rates for: `input`, `output`, `cache_read`, `cache_write`
- `default` pricing used for unknown models
- Pricing automatically applied during ETL

**Budget Alerts:**
- `daily_warning`: Alert threshold for daily spend (null to disable)
- `weekly_warning`: Alert threshold for weekly spend
- `monthly_warning`: Alert threshold for monthly spend

**Display:**
- `color_enabled`: Enable/disable colored output
- `progress_threshold_mb`: Show progress bar for files larger than this (MB)
- `table_max_width`: Maximum table width for reports

## Database Schema

CCWAP uses a 7-table SQLite schema with proper indexes:

### Tables

1. **sessions** - Session metadata (project, timestamps, version)
2. **turns** - Individual JSONL entries with token usage and costs
3. **tool_calls** - Tool invocations with success/error tracking
4. **experiment_tags** - User-defined labels for A/B testing
5. **daily_summaries** - Materialized daily aggregates
6. **etl_state** - File processing state for incremental ETL
7. **snapshots** - Snapshot metadata for diff comparisons

### Key Features

- **WAL mode** for concurrent reads during ETL
- **UUID-based deduplication** prevents duplicate turns
- **Foreign key constraints** maintain referential integrity
- **Comprehensive indexes** optimize query performance
- **Versioned migrations** support schema evolution

For detailed schema documentation, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Output Examples

### Summary View

```
CLAUDE CODE WORKFLOW ANALYTICS

ALL-TIME TOTALS
----------------------------------------
Sessions:        42
Turns:           1,234
Input Tokens:    2.5M
Output Tokens:   856K
Cache Read:      1.2M
Cache Write:     180K
Total Cost:      $45.67

Cache Hit Rate:  32.4%

TODAY ●
----------------------------------------
Sessions:        3
Turns:           87
Cost:            $2.34

COST BY MODEL
----------------------------------------
  opus-4-6                    $18.50
  opus-4-5                    $10.00
  sonnet-4-5                  $15.20
  haiku-3-5                   $1.97

TOP PROJECTS BY COST
----------------------------------------
  my-web-app                  $18.45 (12 sessions)
  data-pipeline               $12.30 (8 sessions)
  api-server                  $8.92 (6 sessions)
```

### Project Metrics

```
PROJECT METRICS

Project                Sessions  Turns    LOC   Tokens    Cost    Err%
-----------------------------------------------------------------------------
my-web-app                   12    456  12,340  1.2M   $18.45   2.3%
data-pipeline                 8    234   8,920  890K   $12.30   1.1%
api-server                    6    189   5,670  645K    $8.92   0.5%
```

### Weekly Comparison

```
WEEKLY BREAKDOWN

Week          Sessions  Turns  Tokens    Cost   Think  Trunc  WoW Δ
------------------------------------------------------------------------
2026-W05            15    567    1.2M  $23.45   245K      2  +12.3%
2026-W04            13    432    980K  $20.89   198K      0   -5.2%
2026-W03            14    456    1.1M  $22.01   210K      1  +18.7%
```

## Advanced Features

### Incremental ETL

CCWAP tracks file modification times and byte offsets to only process new data:

- Files unchanged since last run are skipped
- Modified files are re-processed entirely
- Duplicate UUIDs are ignored (INSERT OR IGNORE)
- Commit after each file for crash recovery

### Agent Session Tracking

CCWAP automatically detects and tracks agent sessions:

- Main sessions: `<session-id>.jsonl`
- Agent sessions: `agent-<agent-id>.jsonl`
- Subagent sessions: `subagents/<subagent-id>.jsonl`

Agent costs are included in project totals but message counts are excluded to avoid confusion.

### Cost Calculation Accuracy

CCWAP fixes common cost calculation bugs:

- **Per-model pricing**: Each turn uses its own model for cost calculation (Opus 4.6, Opus 4.5, Sonnet 4.5/4, Haiku 4.5/3.5)
- **Per-token-type pricing**: Separate rates for input, output, cache_read, cache_write
- **No flat rates**: Never uses simplified cost formulas
- **Cache tokens**: Properly accounts for savings on cached input
- **Ephemeral cache tiers**: Tracks 5-minute and 1-hour ephemeral cache tokens separately

### LOC Counting

CCWAP counts lines of code excluding blanks and comments:

- **50+ languages** supported with extension detection
- **Multi-line comments** handled with state machine parser
- **Docstrings** excluded (Python, etc.)
- **LOC Generated** vs **Net LOC** tracked separately

### Snapshot Comparisons

Create snapshots to track changes over time:

```bash
# Create snapshot
python -m ccwap --snapshot baseline

# Work for a week...

# Compare against baseline
python -m ccwap --diff baseline
```

## Data Retention

### Claude Code Settings

IMPORTANT: By default, Claude Code deletes JSONL files after 30 days. To preserve your data:

1. Edit `~/.claude/settings.json`
2. Set `"cleanupPeriodDays": 99999`

CCWAP will warn you if this setting is not configured properly.

### Database Maintenance

The SQLite database grows over time. To optimize:

```bash
# Vacuum database (reclaim space)
sqlite3 ~/.ccwap/analytics.db "VACUUM;"

# Check database size
du -h ~/.ccwap/analytics.db
```

## Troubleshooting

### "Database not found" Error

Run `python -m ccwap` without flags first to initialize the database.

### "File in use" Warning (Windows)

CCWAP skips files that are currently open by Claude Code. Run CCWAP when Claude is closed, or the file will be processed on the next run.

### Missing Sessions

Check that:
1. Claude Code has been run at least once
2. `~/.claude/projects/` contains JSONL files
3. cleanupPeriodDays is set high enough

### Incorrect Costs

If costs seem wrong:
1. Check `~/.ccwap/config.json` pricing table
2. Run with `--rebuild` to recalculate all costs
3. Verify model names match pricing table keys

### Performance Issues

For very large databases (>1GB):
- Run `VACUUM` to optimize
- Use date filters to limit query scope
- Consider archiving old sessions

## Development

### Running Tests

CCWAP includes 231 tests covering all major functionality:

```bash
# Run all tests
python -m pytest ccwap/tests/

# Run specific test file
python -m pytest ccwap/tests/test_etl.py

# Run with coverage
python -m pytest --cov=ccwap ccwap/tests/
```

### Project Structure

```
ccwap/
├── ccwap.py              # CLI entry point
├── __main__.py           # Module entry point
├── config/               # Configuration loading
├── cost/                 # Pricing and cost calculation
├── etl/                  # JSONL parsing and loading
├── models/               # SQLite schema and entities
├── output/               # Formatting and snapshots
├── reports/              # 25+ report generators
├── utils/                # Utilities (LOC, timestamps, paths)
└── tests/                # Test suite (231 tests)
```

### Architecture

For detailed architecture documentation including data flow diagrams and schema details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## FAQ

**Q: Does CCWAP send any data externally?**
A: No. All data stays on your local machine in SQLite.

**Q: Can I use CCWAP with multiple machines?**
A: Yes, but each machine will have its own database. You could sync the database file or merge databases using SQL.

**Q: How accurate are the cost calculations?**
A: Very accurate. CCWAP uses per-model, per-token-type pricing and accounts for cache tokens. Costs match Claude API pricing exactly.

**Q: Can I export data for external analysis?**
A: Yes, use `--json` for JSON output or `--export file.csv` for CSV format.

**Q: Does CCWAP work with Claude.ai web conversations?**
A: No, only Claude Code desktop app sessions (JSONL format).

**Q: What data does CCWAP surface from the JSONL files?**
A: Everything available: token usage, costs, models, extended thinking, stop reasons, sidechains, cache tiers, tool calls, file edits, errors, git branches, CC versions, skill invocations, and agent spawns.

**Q: How much disk space does CCWAP use?**
A: The database is typically 10-20% of the combined JSONL file size. A few MB for typical usage.

## License

[Include your license here]

## Contributing

[Include contribution guidelines here]

## Support

For issues, questions, or feature requests, please [open an issue](link-to-issues).

---

Built with Python 3.10+ | Zero external dependencies | SQLite backend
