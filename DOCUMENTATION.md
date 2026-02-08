# CCWAP Documentation Index

Complete documentation for the Claude Code Workflow Analytics Platform.

## Getting Started

### For New Users

1. **[Quick Start Guide](QUICKSTART.md)** - Get up and running in 5 minutes
   - Installation steps
   - First commands
   - Common tasks
   - Example workflows

2. **[README.md](README.md)** - Main documentation
   - Feature overview
   - Complete CLI reference
   - Configuration guide
   - Usage examples
   - FAQ and troubleshooting

### For Developers

3. **[Architecture Documentation](ARCHITECTURE.md)** - Technical deep-dive
   - System architecture
   - Module structure
   - Database schema details
   - ETL pipeline design
   - Cost calculation methodology
   - Query patterns
   - Performance optimization
   - Testing strategy

## Documentation Structure

### User Documentation

| Document | Purpose | Audience |
|----------|---------|----------|
| [QUICKSTART.md](QUICKSTART.md) | Get started in 5 minutes | New users |
| [README.md](README.md) | Complete feature reference | All users |
| Examples section in README | Real-world usage patterns | All users |
| CLI reference in README | All command-line flags | All users |
| Configuration section | Customization options | All users |

### Technical Documentation

| Document | Purpose | Audience |
|----------|---------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design and internals | Developers |
| Database schema section | Table structures and indexes | Developers, DBAs |
| ETL pipeline section | Data processing flow | Developers |
| Cost calculation section | Pricing methodology | Developers, Analysts |
| Performance section | Optimization techniques | Developers |

### Code Documentation

All Python modules include comprehensive inline documentation:

- **Module docstrings**: Purpose and overview
- **Function docstrings**: Parameters, returns, examples
- **Class docstrings**: Responsibilities and usage
- **Complex logic comments**: Explanation of non-obvious code

## Key Concepts

### Data Flow

```
JSONL Files → ETL Pipeline → SQLite Database → Reports
```

1. **JSONL Files**: Raw session logs from Claude Code
2. **ETL Pipeline**: Streaming parser + extraction + loading
3. **SQLite Database**: 7-table normalized schema
4. **Reports**: SQL queries + formatting + output

### Cost Calculation

CCWAP uses accurate per-model, per-token-type pricing:

```python
cost = (input_tokens / 1M × input_price) +
       (output_tokens / 1M × output_price) +
       (cache_read_tokens / 1M × cache_read_price) +
       (cache_write_tokens / 1M × cache_write_price)
```

See [Cost Calculation section in ARCHITECTURE.md](ARCHITECTURE.md#cost-calculation) for details.

### Database Schema

7 tables provide comprehensive session tracking:

1. **sessions** - Session metadata
2. **turns** - Individual JSONL entries with token usage
3. **tool_calls** - Tool invocations with success/error tracking
4. **experiment_tags** - User-defined labels for A/B testing
5. **daily_summaries** - Materialized daily aggregates
6. **etl_state** - File processing state
7. **snapshots** - Snapshot metadata for diffs

See [Database Schema section in ARCHITECTURE.md](ARCHITECTURE.md#database-schema) for full details.

## Finding Information

### By Task

**I want to...**

- **Install CCWAP** → [QUICKSTART.md - Installation](QUICKSTART.md#installation)
- **Run my first report** → [QUICKSTART.md - First Steps](QUICKSTART.md#first-steps)
- **Understand a CLI flag** → [README.md - CLI Reference](README.md#cli-reference)
- **Configure pricing** → [README.md - Configuration](README.md#configuration)
- **Track experiments** → [README.md - Experiment Tags](README.md#experiment-tags)
- **Compare time periods** → [README.md - Comparison & Trends](README.md#comparison--trends)
- **Troubleshoot errors** → [README.md - Troubleshooting](README.md#troubleshooting)
- **Understand the architecture** → [ARCHITECTURE.md](ARCHITECTURE.md)
- **Modify the code** → [ARCHITECTURE.md - Module Structure](ARCHITECTURE.md#module-structure)
- **Add a new report** → [ARCHITECTURE.md - Extension Points](ARCHITECTURE.md#extension-points)
- **Optimize queries** → [ARCHITECTURE.md - Query Patterns](ARCHITECTURE.md#query-patterns)

### By Role

**As a User, I need to:**
- [Install and run CCWAP](QUICKSTART.md)
- [Learn all available commands](README.md#cli-reference)
- [Configure pricing and budgets](README.md#configuration)
- [Track my usage and costs](README.md#example-workflows)
- [Compare different workflows](README.md#experiment-tracking)

**As a Developer, I need to:**
- [Understand the architecture](ARCHITECTURE.md#system-overview)
- [Learn the module structure](ARCHITECTURE.md#module-structure)
- [Understand data flow](ARCHITECTURE.md#data-flow)
- [Work with the database](ARCHITECTURE.md#database-schema)
- [Add new features](ARCHITECTURE.md#extension-points)
- [Optimize performance](ARCHITECTURE.md#performance-considerations)

**As a Data Analyst, I need to:**
- [Understand cost calculations](ARCHITECTURE.md#cost-calculation)
- [Know the database schema](ARCHITECTURE.md#database-schema)
- [Write custom queries](ARCHITECTURE.md#query-patterns)
- [Export data for analysis](README.md#output-options)

## Examples by Use Case

### Daily Monitoring

```bash
# Morning check
python -m ccwap --today

# End of day review
python -m ccwap --today --daily
```

See: [README.md - Daily Cost Monitoring](README.md#daily-cost-monitoring)

### Project Analysis

```bash
# Find expensive projects
python -m ccwap --projects --sort cost

# Analyze specific project
python -m ccwap --projects --project my-app
```

See: [README.md - Project Analysis](README.md#project-analysis)

### Experiment Tracking

```bash
# Tag experiments
python -m ccwap --tag baseline --from 2026-01-15 --to 2026-01-21
python -m ccwap --tag experiment --from 2026-01-22 --to 2026-01-28

# Compare
python -m ccwap --compare-tags baseline experiment
```

See: [README.md - Experiment Tracking](README.md#experiment-tracking)

### Error Investigation

```bash
# View recent errors
python -m ccwap --errors --this-week

# Check error trends
python -m ccwap --trend error_rate --last 4w
```

See: [README.md - Error Investigation](README.md#error-investigation)

## Reference Documentation

### CLI Commands

Complete reference: [README.md - CLI Reference](README.md#cli-reference)

**Most Used Commands:**
- `--daily` - Daily breakdown
- `--projects` - Project metrics
- `--weekly` - Weekly totals
- `--tools` - Tool usage
- `--errors` - Error analysis

### Configuration Options

Complete reference: [README.md - Configuration](README.md#configuration)

**Key Settings:**
- `pricing` - Per-model token pricing
- `budget_alerts` - Spending thresholds
- `display` - Output customization

### Database Tables

Complete reference: [ARCHITECTURE.md - Database Schema](ARCHITECTURE.md#database-schema)

**Core Tables:**
- `sessions` - Session metadata
- `turns` - Token usage and costs
- `tool_calls` - Tool invocations

### Module Functions

All modules have comprehensive inline documentation:

- `ccwap.etl.parser` - JSONL streaming
- `ccwap.etl.extractor` - Field extraction
- `ccwap.etl.loader` - Database loading
- `ccwap.cost.calculator` - Cost computation
- `ccwap.reports.*` - Report generation

## Advanced Topics

### Database Internals

- [Schema design rationale](ARCHITECTURE.md#database-schema)
- [Index strategy](ARCHITECTURE.md#performance-considerations)
- [Query optimization](ARCHITECTURE.md#query-patterns)
- [WAL mode benefits](ARCHITECTURE.md#sqlite-configuration)

### ETL Pipeline

- [Streaming architecture](ARCHITECTURE.md#streaming-parser)
- [Incremental processing](ARCHITECTURE.md#incremental-processing)
- [Deduplication strategy](ARCHITECTURE.md#batch-loading)
- [Error handling](ARCHITECTURE.md#entry-validation)

### Cost Accuracy

- [Pricing table structure](ARCHITECTURE.md#pricing-table-structure)
- [Per-model lookup](ARCHITECTURE.md#cost-calculation-formula)
- [Cache token economics](ARCHITECTURE.md#cache-token-economics)
- [Historical bug fixes](ARCHITECTURE.md#historical-bug-fixes)

### Performance Tuning

- [Batch insert optimization](ARCHITECTURE.md#batch-insert-performance)
- [Memory management](ARCHITECTURE.md#memory-management)
- [Query optimization](ARCHITECTURE.md#query-optimization)
- [Scaling considerations](ARCHITECTURE.md#scaling-considerations)

## Code Examples

### Using CCWAP as a Library

```python
# Future API (planned)
from ccwap import CCWAP

analyzer = CCWAP()
analyzer.run_etl()

sessions = analyzer.query_sessions(
    date_from='2026-01-01',
    project='my-app'
)

report = analyzer.generate_report('projects')
```

See: [ARCHITECTURE.md - API Design](ARCHITECTURE.md#api-design-future)

### Custom Queries

```python
import sqlite3
from pathlib import Path

db_path = Path.home() / '.ccwap' / 'analytics.db'
conn = sqlite3.connect(str(db_path))

cursor = conn.execute("""
    SELECT project_display, SUM(cost)
    FROM sessions s
    JOIN turns t ON t.session_id = s.session_id
    WHERE date(t.timestamp) >= date('now', '-7 days')
    GROUP BY project_display
""")

for row in cursor:
    print(f"{row[0]}: ${row[1]:.2f}")
```

See: [ARCHITECTURE.md - Query Patterns](ARCHITECTURE.md#query-patterns)

## Contributing

Interested in contributing? See these sections:

- [Module structure](ARCHITECTURE.md#module-structure) - Understand the codebase
- [Extension points](ARCHITECTURE.md#extension-points) - Where to add features
- [Testing strategy](ARCHITECTURE.md#testing-strategy) - How we test
- [Development guide](ARCHITECTURE.md#development) - Setup and workflow

## Support Resources

### Documentation
- This index
- README.md (user guide)
- QUICKSTART.md (getting started)
- ARCHITECTURE.md (technical reference)

### Code
- Inline docstrings (all modules)
- Type hints (all functions)
- Comments (complex logic)

### Testing
- 206 tests covering all features
- Test fixtures for common scenarios
- Integration tests for end-to-end flows

### Help
- FAQ in README.md
- Troubleshooting guide in ARCHITECTURE.md
- GitHub issues (for bugs and features)

## Document Versions

| Document | Last Updated | Version |
|----------|-------------|---------|
| README.md | 2026-02-03 | 1.0 |
| ARCHITECTURE.md | 2026-02-03 | 1.0 |
| QUICKSTART.md | 2026-02-03 | 1.0 |
| DOCUMENTATION.md | 2026-02-03 | 1.0 |

## Quick Navigation

**For Users:**
[Quick Start](QUICKSTART.md) → [CLI Reference](README.md#cli-reference) → [Configuration](README.md#configuration) → [Examples](README.md#example-workflows)

**For Developers:**
[Architecture](ARCHITECTURE.md#system-overview) → [Module Structure](ARCHITECTURE.md#module-structure) → [Database Schema](ARCHITECTURE.md#database-schema) → [Extension Points](ARCHITECTURE.md#extension-points)

**For Troubleshooting:**
[FAQ](README.md#faq) → [Troubleshooting](README.md#troubleshooting) → [Performance](ARCHITECTURE.md#performance-considerations) → [Debugging](ARCHITECTURE.md#troubleshooting-guide)

---

**Questions?** Check the [FAQ in README.md](README.md#faq) or [open an issue](link-to-issues).
