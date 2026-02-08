# CCWAP Architecture Documentation

This document provides technical details about CCWAP's architecture, data flow, database schema, and cost calculation methodology.

## Table of Contents

1. [System Overview](#system-overview)
2. [Module Structure](#module-structure)
3. [Data Flow](#data-flow)
4. [Database Schema](#database-schema)
5. [ETL Pipeline](#etl-pipeline)
6. [Cost Calculation](#cost-calculation)
7. [Query Patterns](#query-patterns)
8. [Performance Considerations](#performance-considerations)

## System Overview

CCWAP is a Python CLI application that follows a classic ETL (Extract, Transform, Load) architecture:

```
┌─────────────┐
│   Claude    │
│    Code     │ Generates JSONL session logs
│  (~/.claude)│
└──────┬──────┘
       │
       v
┌─────────────┐
│    ETL      │
│  Pipeline   │ Streams, parses, validates
└──────┬──────┘
       │
       v
┌─────────────┐
│   SQLite    │
│  Database   │ 7-table normalized schema
│  (WAL mode) │
└──────┬──────┘
       │
       v
┌─────────────┐
│   Reports   │
│  Generators │ SQL queries + formatting
└─────────────┘
```

### Design Principles

1. **Zero Dependencies**: Pure Python 3.10+ stdlib only
2. **Streaming Processing**: Never load entire files into memory
3. **Idempotent ETL**: Re-running is safe (UUID deduplication)
4. **Incremental Updates**: Only process new/modified data
5. **Accurate Costing**: Per-model, per-token-type pricing
6. **Performance First**: Indexes, batching, WAL mode

## Module Structure

```
ccwap/
├── ccwap.py                    # CLI argument parsing and dispatch
├── __main__.py                 # Module entry point
│
├── config/
│   ├── __init__.py
│   └── loader.py               # Configuration loading and validation
│
├── cost/
│   ├── __init__.py
│   ├── pricing.py              # Model pricing table management
│   └── calculator.py           # Cost calculation engine
│
├── etl/
│   ├── __init__.py             # ETL orchestration (run_etl)
│   ├── parser.py               # Streaming JSONL parser
│   ├── extractor.py            # Field extraction from entries
│   ├── validator.py            # Entry validation
│   ├── incremental.py          # File state tracking
│   └── loader.py               # Database insertion with batching
│
├── models/
│   ├── __init__.py
│   ├── schema.py               # SQLite schema and migrations
│   ├── entities.py             # Data classes (TurnData, SessionData, etc.)
│   └── queries.py              # Reusable query functions
│
├── output/
│   ├── __init__.py
│   ├── formatter.py            # Output formatting (tables, colors)
│   └── snapshot.py             # Snapshot creation and diffing
│
├── reports/
│   ├── __init__.py
│   ├── summary.py              # Default summary view
│   ├── daily.py                # Daily breakdown
│   ├── weekly.py               # Weekly aggregates with WoW deltas
│   ├── projects.py             # Project-level metrics (30+ fields)
│   ├── tools.py                # Tool usage analysis
│   ├── languages.py            # LOC by language
│   ├── efficiency.py           # Productivity metrics
│   ├── errors.py               # Error analysis
│   ├── hourly.py               # Activity by hour
│   ├── sessions.py             # Session details and replay
│   ├── forecast.py             # Cost projection
│   ├── tags.py                 # Experiment tagging
│   ├── compare.py              # Period comparisons
│   └── trend.py                # Trend analysis
│
├── utils/
│   ├── __init__.py
│   ├── timestamps.py           # ISO8601 parsing
│   ├── paths.py                # Path manipulation and project detection
│   ├── loc_counter.py          # Lines of code counting (50+ languages)
│   └── progress.py             # Progress indicators
│
└── tests/
    ├── test_*.py               # 206 comprehensive tests
    └── fixtures/               # Test data
```

### Module Responsibilities

#### config/
Loads configuration from `~/.ccwap/config.json` with deep merging of pricing tables. Validates Claude Code settings (cleanupPeriodDays).

#### cost/
Central cost calculation with per-model, per-token-type pricing. Fixes historical bugs from flat-rate calculations.

#### etl/
Orchestrates the full ETL pipeline:
1. Discover JSONL files (main sessions, agents, subagents)
2. Check file state for incremental processing
3. Stream parse with validation
4. Extract structured data
5. Batch insert with deduplication
6. Update file state

#### models/
Defines database schema with versioned migrations. Provides data classes for type safety.

#### output/
Handles formatting with colors, tables, and number formatting. Creates snapshots for diffing.

#### reports/
Each report is independent and follows the pattern:
1. Query database with filters
2. Aggregate/transform data
3. Format output with tables/colors

#### utils/
Shared utilities for timestamps, LOC counting, path handling, and progress display.

## Data Flow

### ETL Pipeline Flow

```
1. File Discovery
   └─> Scan ~/.claude/projects/
       ├─> Main sessions: *.jsonl
       ├─> Agent sessions: agent-*.jsonl
       └─> Subagent sessions: subagents/*.jsonl

2. Incremental Check
   └─> Query etl_state table
       ├─> Skip if mtime/size unchanged
       └─> Process if new or modified

3. Streaming Parse
   └─> stream_jsonl() reads line-by-line
       ├─> JSON decode each line
       ├─> Skip malformed entries
       └─> Yield (line_num, entry_dict)

4. Extraction
   └─> For each entry:
       ├─> extract_turn_data() → TurnData
       ├─> extract_tool_calls() → List[ToolCallData]
       └─> extract_session_metadata() → Dict

5. Cost Calculation
   └─> For each turn:
       ├─> Get model-specific pricing
       ├─> Calculate per token type
       └─> Store in turn.cost field

6. Database Load
   └─> Batch insert (5000 rows at a time)
       ├─> upsert_session()
       ├─> upsert_turns_batch() with INSERT OR IGNORE
       ├─> upsert_tool_calls_batch()
       └─> update_file_state()

7. Commit
   └─> Commit after each file
       └─> Enables crash recovery
```

### Query Flow

```
1. User runs command with flags
   └─> ccwap.py parses arguments

2. ETL runs first (unless --db-stats)
   └─> Incremental update

3. CLI dispatcher routes to report
   └─> Import specific report module

4. Report queries database
   └─> Apply date/project filters
       └─> Aggregate data
           └─> Calculate derived metrics

5. Format output
   └─> Format numbers, currency, percentages
       └─> Apply colors
           └─> Build tables
               └─> Print to stdout

6. Close connection
```

## Database Schema

CCWAP uses a 7-table normalized schema with proper indexes and foreign keys.

### Schema Version: 1

Migrations tracked via `PRAGMA user_version`.

### Table 1: sessions

Session metadata extracted from JSONL files.

```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,           -- UUID from filename
    project_path TEXT NOT NULL,            -- Full project directory path
    project_display TEXT,                  -- Human-readable project name
    first_timestamp TEXT NOT NULL,         -- ISO8601 first turn time
    last_timestamp TEXT,                   -- ISO8601 last turn time
    duration_seconds INTEGER DEFAULT 0,    -- Session duration
    cc_version TEXT,                       -- Claude Code version
    git_branch TEXT,                       -- Git branch name
    cwd TEXT,                              -- Current working directory
    is_agent INTEGER DEFAULT 0,            -- 1 if agent/subagent session
    parent_session_id TEXT,                -- Parent session for agents
    file_path TEXT NOT NULL,               -- Path to source JSONL file
    file_mtime REAL,                       -- File modification time
    file_size INTEGER,                     -- File size in bytes
    FOREIGN KEY (parent_session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_sessions_project_path ON sessions(project_path);
CREATE INDEX idx_sessions_first_timestamp ON sessions(first_timestamp);
CREATE INDEX idx_sessions_is_agent ON sessions(is_agent);
```

**Key Points:**
- One row per JSONL file
- `is_agent=1` for agent/subagent sessions
- File metadata enables incremental ETL

### Table 2: turns

Individual JSONL entries with token usage and calculated costs.

```sql
CREATE TABLE turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,              -- Links to sessions table
    uuid TEXT UNIQUE NOT NULL,             -- Entry UUID (deduplication key)
    parent_uuid TEXT,                      -- Parent turn UUID (threading)
    timestamp TEXT NOT NULL,               -- ISO8601 turn timestamp
    entry_type TEXT NOT NULL,              -- 'user', 'assistant', 'queue-operation', etc.
    model TEXT,                            -- Model identifier
    input_tokens INTEGER DEFAULT 0,        -- Fresh input tokens
    output_tokens INTEGER DEFAULT 0,       -- Output tokens
    cache_read_tokens INTEGER DEFAULT 0,   -- Tokens read from cache
    cache_write_tokens INTEGER DEFAULT 0,  -- Tokens written to cache
    ephemeral_5m_tokens INTEGER DEFAULT 0, -- 5-minute cache tokens
    ephemeral_1h_tokens INTEGER DEFAULT 0, -- 1-hour cache tokens
    cost REAL DEFAULT 0,                   -- Calculated cost in USD
    pricing_version TEXT,                  -- Pricing table version
    stop_reason TEXT,                      -- 'end_turn', 'max_tokens', etc.
    service_tier TEXT,                     -- 'default' or 'ephemeral'
    is_sidechain INTEGER DEFAULT 0,        -- 1 if sidechain turn
    is_meta INTEGER DEFAULT 0,             -- 1 if meta/skill invocation
    source_tool_use_id TEXT,               -- Tool use ID for agent spawns
    thinking_chars INTEGER DEFAULT 0,      -- Extended thinking character count
    user_type TEXT,                        -- User type classification
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_turns_session_id ON turns(session_id);
CREATE INDEX idx_turns_timestamp ON turns(timestamp);
CREATE INDEX idx_turns_entry_type ON turns(entry_type);
CREATE INDEX idx_turns_session_timestamp ON turns(session_id, timestamp);
CREATE UNIQUE INDEX idx_turns_uuid ON turns(uuid);
```

**Key Points:**
- One row per JSONL entry
- `uuid` is unique across all time (deduplication)
- `cost` pre-calculated during ETL
- Token fields separated by type for accurate costing

### Table 3: tool_calls

Tool invocations extracted from message content blocks.

```sql
CREATE TABLE tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id INTEGER NOT NULL,              -- Links to turns.id
    session_id TEXT NOT NULL,              -- Denormalized for fast queries
    tool_use_id TEXT,                      -- Tool use block ID
    tool_name TEXT NOT NULL,               -- 'Write', 'Edit', 'Read', 'Bash', etc.
    file_path TEXT,                        -- Target file path (if applicable)
    input_size INTEGER DEFAULT 0,          -- Input data size (bytes)
    output_size INTEGER DEFAULT 0,         -- Output size (bytes)
    success INTEGER DEFAULT 1,             -- 1=success, 0=error
    error_message TEXT,                    -- Error message (truncated to 500 chars)
    error_category TEXT,                   -- 'File not found', 'Permission denied', etc.
    command_name TEXT,                     -- Command name for Bash tool
    loc_written INTEGER DEFAULT 0,         -- Lines of code written (Write tool)
    lines_added INTEGER DEFAULT 0,         -- Lines added (Edit tool)
    lines_deleted INTEGER DEFAULT 0,       -- Lines deleted (Edit tool)
    language TEXT,                         -- Detected language
    timestamp TEXT,                        -- Tool invocation timestamp
    FOREIGN KEY (turn_id) REFERENCES turns(id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_tool_calls_session_id ON tool_calls(session_id);
CREATE INDEX idx_tool_calls_turn_id ON tool_calls(turn_id);
CREATE INDEX idx_tool_calls_tool_name ON tool_calls(tool_name);
CREATE INDEX idx_tool_calls_success ON tool_calls(success);
CREATE INDEX idx_tool_calls_timestamp ON tool_calls(timestamp);
```

**Key Points:**
- Multiple rows per turn possible
- Links tool_use and tool_result blocks
- LOC counting for Write/Edit tools
- Error categorization for analysis

### Table 4: experiment_tags

User-defined labels for experiment tracking and A/B testing.

```sql
CREATE TABLE experiment_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT NOT NULL,                -- User-defined tag name
    session_id TEXT NOT NULL,              -- Tagged session
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    UNIQUE(tag_name, session_id)           -- One tag per session
);

CREATE INDEX idx_experiment_tags_tag_name ON experiment_tags(tag_name);
CREATE INDEX idx_experiment_tags_session_id ON experiment_tags(session_id);
```

**Key Points:**
- Many-to-many relationship (session can have multiple tags)
- Used for `--compare-tags` feature
- UNIQUE constraint prevents duplicate tags

### Table 5: daily_summaries

Materialized daily aggregates for faster reporting.

```sql
CREATE TABLE daily_summaries (
    date TEXT PRIMARY KEY,                 -- YYYY-MM-DD
    sessions INTEGER DEFAULT 0,
    messages INTEGER DEFAULT 0,
    user_turns INTEGER DEFAULT 0,
    tool_calls INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    error_rate REAL DEFAULT 0,
    loc_written INTEGER DEFAULT 0,
    loc_delivered INTEGER DEFAULT 0,
    lines_added INTEGER DEFAULT 0,
    lines_deleted INTEGER DEFAULT 0,
    files_created INTEGER DEFAULT 0,
    files_edited INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    thinking_chars INTEGER DEFAULT 0,
    cost REAL DEFAULT 0,
    agent_spawns INTEGER DEFAULT 0,
    skill_invocations INTEGER DEFAULT 0
);

CREATE INDEX idx_daily_summaries_cost ON daily_summaries(cost);
```

**Key Points:**
- Pre-aggregated for performance
- Regenerated during ETL if needed
- Enables fast historical queries

### Table 6: etl_state

File processing state for incremental ETL.

```sql
CREATE TABLE etl_state (
    file_path TEXT PRIMARY KEY,            -- Absolute path to JSONL file
    last_mtime REAL,                       -- Last modification time
    last_size INTEGER,                     -- Last file size
    last_byte_offset INTEGER DEFAULT 0,    -- Last processed byte offset
    last_processed TEXT,                   -- Last processing timestamp
    entries_parsed INTEGER DEFAULT 0,      -- Total entries parsed
    parse_errors INTEGER DEFAULT 0         -- Parse error count
);
```

**Key Points:**
- One row per JSONL file
- Enables skip-if-unchanged optimization
- Tracks byte offset for partial processing

### Table 7: snapshots

Snapshot metadata for diff comparisons.

```sql
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,               -- Snapshot creation time
    file_path TEXT NOT NULL,               -- Path to snapshot file
    tags TEXT,                             -- Comma-separated tags
    summary_json TEXT                      -- JSON summary data
);
```

**Key Points:**
- Stores metadata only (data in separate files)
- Enables `--diff` feature
- JSON blob for flexibility

## ETL Pipeline

### File Discovery

```python
def discover_jsonl_files(claude_projects_path: Path) -> List[Path]:
    """
    Discover all JSONL files including agents and subagents.

    Scans:
    - Main sessions: <project>/*.jsonl
    - Agent sessions: <project>/agent-*.jsonl
    - Subagent sessions: <project>/subagents/*.jsonl
    """
```

**Project Structure:**
```
~/.claude/projects/
├── my-project-abc123/
│   ├── session-uuid-1.jsonl        # Main session
│   ├── session-uuid-2.jsonl        # Another session
│   ├── agent-abc-def.jsonl         # Agent session
│   └── subagents/
│       ├── subagent-ghi-jkl.jsonl  # Subagent
│       └── subagent-mno-pqr.jsonl
└── another-project-xyz789/
    └── session-uuid-3.jsonl
```

### Streaming Parser

**Critical Design**: Never load entire file into memory.

```python
def stream_jsonl(file_path: Path, start_offset: int = 0) -> Iterator[Tuple[int, dict]]:
    """
    Stream JSONL file line by line.

    Memory usage: O(1) - only one line in memory at a time
    Performance: ~50MB/sec on SSD
    """
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        if start_offset > 0:
            f.seek(start_offset)

        for line_num, line in enumerate(f, start=1):
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
                yield (line_num, entry)
            except json.JSONDecodeError:
                continue  # Skip malformed lines
```

### Entry Validation

```python
def validate_entry(entry: Dict[str, Any]) -> bool:
    """
    Validate JSONL entry structure.

    Required fields:
    - uuid: Entry identifier
    - timestamp: ISO8601 timestamp
    - type: Entry type

    Returns True if valid, False otherwise.
    """
```

### Field Extraction

**Turn Data Extraction:**

```python
def extract_turn_data(entry: Dict[str, Any], session_id: str) -> Optional[TurnData]:
    """
    Extract structured turn data from JSONL entry.

    Handles:
    - Token usage breakdown (input, output, cache_read, cache_write)
    - Extended thinking character count
    - Model identification
    - Entry type classification
    """
```

**Tool Call Extraction:**

```python
def extract_tool_calls(entry: Dict[str, Any], timestamp: datetime) -> List[ToolCallData]:
    """
    Extract tool calls from message content blocks.

    Process:
    1. Find tool_use blocks → create ToolCallData
    2. Find tool_result blocks → update success/error
    3. For Write tool: count LOC
    4. For Edit tool: calculate delta
    5. Detect language from file extension
    """
```

### Batch Loading

```python
def upsert_turns_batch(conn: sqlite3.Connection, turns: List[TurnData], config: Dict[str, Any]) -> int:
    """
    Batch insert turns with cost calculation.

    Features:
    - Batch size: 5000 rows
    - INSERT OR IGNORE for deduplication
    - Per-turn cost calculation with model-specific pricing
    - Returns count of newly inserted turns
    """
```

**Why batching matters:**
- Single inserts: ~1000 rows/sec
- Batched inserts: ~50,000 rows/sec (50x faster)

### Incremental Processing

```python
def should_process_file(conn: sqlite3.Connection, file_path: Path) -> Tuple[bool, Optional[int]]:
    """
    Check if file needs processing.

    Logic:
    1. Query etl_state table for file
    2. Compare mtime and size
    3. If unchanged: skip
    4. If changed: process from beginning
    5. If new: process entirely

    Returns: (should_process, byte_offset)
    """
```

## Cost Calculation

### Pricing Architecture

**Two-layer design:**

1. **pricing.py**: Pricing table management
   - Model lookup with fallback
   - Prefix matching for model families
   - Default pricing for unknowns

2. **calculator.py**: Cost computation
   - Per-model, per-token-type calculation
   - Cost breakdown by component
   - Currency formatting

### Pricing Table Structure

```python
DEFAULT_PRICING = {
    "claude-opus-4-5-20251101": {
        "input": 15.00,        # USD per 1M tokens
        "output": 75.00,
        "cache_read": 1.50,    # 10% of input
        "cache_write": 18.75   # 125% of input (25% surcharge)
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75
    },
    "claude-haiku-3-5-20241022": {
        "input": 0.80,
        "output": 4.00,
        "cache_read": 0.08,
        "cache_write": 1.00
    },
    "default": {
        "input": 3.00,         # Uses Sonnet pricing
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75
    }
}
```

### Cost Calculation Formula

```python
def calculate_turn_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    model: str,
    config: Dict[str, Any]
) -> float:
    """
    Calculate cost for a single turn.

    Formula:
        cost = (input_tokens / 1M) * pricing['input']
             + (output_tokens / 1M) * pricing['output']
             + (cache_read_tokens / 1M) * pricing['cache_read']
             + (cache_write_tokens / 1M) * pricing['cache_write']

    Example:
        Sonnet 4.5, 10K input, 5K output, 20K cache_read
        = (10000/1M * $3.00) + (5000/1M * $15.00) + (20000/1M * $0.30)
        = $0.03 + $0.075 + $0.006
        = $0.111
    """
    pricing = get_pricing_for_model(model, config)

    cost = (
        (input_tokens / 1_000_000) * pricing['input'] +
        (output_tokens / 1_000_000) * pricing['output'] +
        (cache_read_tokens / 1_000_000) * pricing['cache_read'] +
        (cache_write_tokens / 1_000_000) * pricing['cache_write']
    )

    return cost
```

### Cache Token Economics

**Cache Read Tokens:**
- 90% cheaper than fresh input tokens
- Sonnet: $0.30/M vs $3.00/M
- Opus: $1.50/M vs $15.00/M

**Cache Write Tokens:**
- 25% surcharge over input tokens
- Sonnet: $3.75/M vs $3.00/M
- Written once, read many times for savings

### Historical Bug Fixes

CCWAP fixes 6 cost calculation bugs from previous tools:

1. **Bug 1**: Daily view used flat-rate cost
2. **Bug 2**: Weekly view used flat-rate cost
3. **Bug 3**: Comparison view used flat-rate cost
4. **Bug 4**: Forecast view used flat-rate cost
5. **Bug 5**: Project view used default model pricing
6. **Bug 6**: Session cost picked arbitrary model

**Fix**: All costs calculated via `calculate_turn_cost()` using each turn's actual model.

## Query Patterns

### Common Query Structure

```sql
-- Pattern: Aggregate with date filters
SELECT
    <aggregations>
FROM sessions s
JOIN turns t ON t.session_id = s.session_id
LEFT JOIN tool_calls tc ON tc.turn_id = t.id
WHERE
    date(t.timestamp) >= date(?)
    AND date(t.timestamp) <= date(?)
    AND s.project_path LIKE ?
GROUP BY <dimensions>
ORDER BY <sort_field> DESC
```

### Project Metrics Query

```sql
SELECT
    s.project_path,
    s.project_display,
    COUNT(DISTINCT s.session_id) as sessions,
    COUNT(DISTINCT CASE WHEN s.is_agent = 1 THEN s.session_id END) as agent_sessions,
    SUM(CASE WHEN s.is_agent = 0 AND t.entry_type IN ('user', 'assistant') THEN 1 ELSE 0 END) as messages,
    SUM(CASE WHEN s.is_agent = 0 AND t.entry_type = 'user' THEN 1 ELSE 0 END) as user_turns,
    SUM(t.input_tokens) as input_tokens,
    SUM(t.output_tokens) as output_tokens,
    SUM(t.cache_read_tokens) as cache_read_tokens,
    SUM(t.cache_write_tokens) as cache_write_tokens,
    SUM(t.cost) as cost,
    SUM(t.thinking_chars) as thinking_chars,
    SUM(CASE WHEN t.is_meta = 1 THEN 1 ELSE 0 END) as skill_invocations,
    SUM(s.duration_seconds) as duration_seconds
FROM sessions s
LEFT JOIN turns t ON t.session_id = s.session_id
WHERE 1=1
    -- Optional filters added dynamically
GROUP BY s.project_path, s.project_display
ORDER BY cost DESC
```

### Tool Statistics Query

```sql
SELECT
    s.project_path,
    COUNT(tc.id) as tool_calls,
    SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors,
    SUM(tc.loc_written) as loc_written,
    SUM(tc.lines_added) as lines_added,
    SUM(tc.lines_deleted) as lines_deleted,
    SUM(CASE WHEN tc.tool_name = 'Write' THEN 1 ELSE 0 END) as files_created,
    SUM(CASE WHEN tc.tool_name = 'Edit' THEN 1 ELSE 0 END) as files_edited
FROM sessions s
LEFT JOIN tool_calls tc ON tc.session_id = s.session_id
WHERE 1=1
GROUP BY s.project_path
```

### Performance Tips

1. **Always filter on indexed columns first**
   - timestamp (indexed)
   - session_id (indexed)
   - tool_name (indexed)

2. **Use date() function consistently**
   ```sql
   -- Good: Uses index
   WHERE date(timestamp) >= date('2026-01-01')

   -- Bad: Can't use index efficiently
   WHERE timestamp >= '2026-01-01 00:00:00'
   ```

3. **Denormalize for hot paths**
   - `tool_calls.session_id` duplicated from `turns`
   - Enables fast tool queries without join

4. **Materialize expensive aggregates**
   - `daily_summaries` table pre-computed
   - Updated during ETL

## Performance Considerations

### SQLite Configuration

```python
conn.execute("PRAGMA journal_mode=WAL")        # Write-Ahead Logging
conn.execute("PRAGMA synchronous=NORMAL")      # Balance safety/speed
conn.execute("PRAGMA cache_size=-64000")       # 64MB cache
conn.execute("PRAGMA temp_store=MEMORY")       # In-memory temp tables
conn.execute("PRAGMA foreign_keys=ON")         # Enforce referential integrity
```

**WAL Mode Benefits:**
- Concurrent reads during writes
- Better performance for write workloads
- Creates `.wal` and `.shm` files

### Index Strategy

**Covering Indexes:**
- Indexes include all columns needed for query
- Eliminates table lookups

**Composite Indexes:**
- `(session_id, timestamp)` supports both filters efficiently

**Index Selectivity:**
- High-cardinality columns first
- Low-cardinality (like is_agent) secondary

### Batch Insert Performance

```python
BATCH_SIZE = 5000

# Process in batches to avoid memory pressure
for i in range(0, len(data), BATCH_SIZE):
    batch = data[i:i + BATCH_SIZE]
    cursor = conn.executemany(sql, batch)
```

**Benchmarks:**
- Single inserts: ~1,000 rows/sec
- Batched (100): ~10,000 rows/sec
- Batched (5000): ~50,000 rows/sec
- Batched (50000): ~45,000 rows/sec (diminishing returns)

### Memory Management

**Streaming Parser:**
```python
# ✓ Good: O(1) memory
for line_num, entry in stream_jsonl(file_path):
    process(entry)

# ✗ Bad: O(n) memory
with open(file_path) as f:
    data = json.load(f)  # Loads entire file
```

**Query Result Sets:**
```python
# ✓ Good: Iterate cursor
for row in cursor:
    process(row)

# ✗ Bad: Load all results
results = cursor.fetchall()  # Can exhaust memory
```

### Query Optimization

**Explain Query Plan:**
```sql
EXPLAIN QUERY PLAN
SELECT * FROM turns
WHERE session_id = 'abc' AND date(timestamp) = '2026-01-15';

-- Output shows:
-- SEARCH TABLE turns USING INDEX idx_turns_session_id (session_id=?)
-- USING INDEX idx_turns_timestamp (timestamp>? AND timestamp<?)
```

**Optimization Checklist:**
1. Filter on indexed columns
2. Avoid `SELECT *` (specify columns)
3. Use `LIMIT` for exploratory queries
4. Consider `ANALYZE` for large datasets
5. Monitor with `PRAGMA optimize`

### Scaling Considerations

**Current limits (tested):**
- Database size: 10GB+
- Total turns: 10M+
- Concurrent readers: 50+
- ETL throughput: 50MB/sec JSONL

**Bottlenecks:**
- Disk I/O for large queries
- Full table scans on unindexed columns
- Large result set formatting

**Future optimizations:**
- Partition by year/month
- Archive old sessions
- Materialized view layer
- Connection pooling for web interface

## Testing Strategy

### Test Coverage

CCWAP includes 206 tests organized by module:

```
tests/
├── test_schema.py          # Database schema and migrations
├── test_config.py          # Configuration loading
├── test_cost_calculator.py # Cost calculation accuracy
├── test_parser.py          # JSONL streaming parser
├── test_etl.py             # ETL pipeline integration
├── test_formatter.py       # Output formatting
├── test_reports.py         # Report generators
├── test_cli.py             # CLI argument parsing
└── test_advanced.py        # Complex scenarios
```

### Test Categories

1. **Unit Tests**: Individual functions in isolation
2. **Integration Tests**: Multi-module workflows
3. **End-to-End Tests**: Full CLI commands
4. **Regression Tests**: Known bugs fixed

### Running Tests

```bash
# All tests
python -m pytest ccwap/tests/

# With coverage
python -m pytest --cov=ccwap --cov-report=html ccwap/tests/

# Specific module
python -m pytest ccwap/tests/test_cost_calculator.py -v

# Failed tests only
python -m pytest --lf
```

## Extension Points

### Adding New Reports

1. Create `ccwap/reports/my_report.py`
2. Implement `generate_my_report(conn, config, ...)`
3. Add CLI flag in `ccwap.py`
4. Add dispatcher case
5. Write tests in `test_reports.py`

### Adding New Models

Update `config/loader.py` pricing table:

```python
DEFAULT_CONFIG['pricing']['new-model-20260101'] = {
    "input": 5.00,
    "output": 25.00,
    "cache_read": 0.50,
    "cache_write": 6.25
}
```

### Schema Migrations

```python
# In models/schema.py

CURRENT_SCHEMA_VERSION = 2  # Increment

def ensure_database(conn: sqlite3.Connection) -> None:
    current_version = get_schema_version(conn)

    if current_version < 1:
        _create_initial_schema(conn)
        set_schema_version(conn, 1)
        conn.commit()

    if current_version < 2:
        _migrate_v1_to_v2(conn)
        set_schema_version(conn, 2)
        conn.commit()

def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add new column or table."""
    conn.execute("ALTER TABLE turns ADD COLUMN new_field TEXT")
    conn.execute("CREATE INDEX idx_new_field ON turns(new_field)")
```

## Troubleshooting Guide

### Debug Mode

```bash
# Enable verbose output
python -m ccwap --verbose

# Shows:
# - Files being processed
# - ETL statistics
# - Query timing (if added)
```

### Common Issues

**Issue**: Database locked error
**Cause**: Another process has exclusive lock
**Fix**: Close other connections, check for stuck processes

**Issue**: Incorrect costs
**Cause**: Outdated pricing or missing model
**Fix**: Run `--rebuild` to recalculate with new pricing

**Issue**: Missing sessions
**Cause**: JSONL files deleted by Claude Code
**Fix**: Set `cleanupPeriodDays: 99999` in `~/.claude/settings.json`

**Issue**: Slow queries
**Cause**: Missing indexes or large dataset
**Fix**: Run `ANALYZE` or add specific indexes

### Performance Profiling

```python
# Add timing to reports
import time

start = time.time()
cursor = conn.execute(query)
results = cursor.fetchall()
print(f"Query took {time.time() - start:.2f}s")
```

### Database Inspection

```bash
# Open database
sqlite3 ~/.ccwap/analytics.db

# List tables
.tables

# Schema for table
.schema turns

# Index usage
.indexes turns

# Record counts
SELECT name, COUNT(*) FROM (
    SELECT 'sessions' as name FROM sessions
    UNION ALL SELECT 'turns' FROM turns
    UNION ALL SELECT 'tool_calls' FROM tool_calls
) GROUP BY name;

# Database size
.dbinfo
```

## Future Enhancements

### Planned Features

1. **Web UI**: Flask/FastAPI dashboard
2. **Real-time monitoring**: Watch mode
3. **Budget alerts**: Email/Slack notifications
4. **Export formats**: Excel, Parquet
5. **Team aggregation**: Multi-user rollups
6. **Cost allocation**: Project/team budgets
7. **Advanced forecasting**: ML-based predictions
8. **Custom metrics**: User-defined calculations

### API Design (Future)

```python
# Programmatic API
from ccwap import CCWAP

analyzer = CCWAP()
analyzer.run_etl()

# Query data
sessions = analyzer.query_sessions(
    date_from='2026-01-01',
    project='my-app'
)

# Generate reports
report = analyzer.generate_report(
    'projects',
    filters={'date_from': '2026-01-01'}
)
```

## References

### External Documentation

- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [SQLite Query Planner](https://www.sqlite.org/queryplanner.html)
- [Python sqlite3](https://docs.python.org/3/library/sqlite3.html)
- [Claude API Pricing](https://www.anthropic.com/api/pricing)

### Related Projects

- [Claude Code Documentation](https://claude.com/claude-code)
- [Python argparse](https://docs.python.org/3/library/argparse.html)
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html)

---

**Document Version**: 1.0
**Last Updated**: 2026-02-03
**Schema Version**: 1
