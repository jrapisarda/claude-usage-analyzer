# I built a full analytics dashboard to track my Claude Code spending, productivity, and model performance

I've been using Claude Code heavily across multiple projects and realized I had no idea where my money was going, which models were most efficient, or whether my workflows were actually improving over time. So I built **CCWAP** (Claude Code Workflow Analytics Platform) -- a local analytics dashboard that parses your Claude Code session logs and turns them into actionable insights.

## What it does

CCWAP reads the JSONL session files that Claude Code already saves to `~/.claude/projects/`, runs them through an ETL pipeline into a local SQLite database, and gives you two ways to explore the data:

- **26 CLI reports** directly in your terminal
- **A 19-page web dashboard** with interactive charts, drill-downs, and real-time monitoring

Everything runs locally. No data leaves your machine.

## The Dashboard

The web frontend is built with React + TypeScript + Tailwind + shadcn/ui, served by a FastAPI backend. Here's what you get:

**Cost Analysis** -- See exactly where your money goes. Costs are broken down per-model, per-project, per-branch, even per-session. The pricing engine handles all current models (Opus 4.6/4.5, Sonnet 4.5/4, Haiku) with separate rates for input, output, cache read, and cache write tokens. No flat-rate estimates -- actual per-turn cost calculation.

**Session Detail / Replay** -- Drill into any session to see a turn-by-turn timeline. Each turn shows errors, truncations, sidechain branches, and model switches. You can see tool distribution (how many Read vs Write vs Bash calls), cost by model, and session metadata like duration and CC version.

**Experiment Comparison (A/B Testing)** -- This is the feature I'm most proud of. You can tag sessions (e.g., "opus-only" vs "sonnet-only", or "v2.7" vs "v2.8") and compare them side-by-side with bar charts, radar plots, and a full delta table showing metrics like cost, LOC written, error rate, tool calls, and thinking characters -- with percentage changes highlighted.

**Productivity Metrics** -- Track LOC written per session, cost per KLOC, tool success rates, and error rates. The LOC counter supports 50+ programming languages and filters out comments and blank lines for accurate counts.

**Deep Analytics** -- Extended thinking character tracking, truncation analysis with cost impact, cache tier breakdowns (ephemeral 5-min vs 1-hour), sidechain overhead, and skill/agent spawn patterns.

**Model Comparison** -- Compare Opus vs Sonnet vs Haiku across cost, speed, LOC output, error rates, and cache efficiency. Useful for figuring out which model actually delivers the best value for your workflow.

**More pages**: Project breakdown, branch-level analytics, activity heatmaps (hourly/daily patterns), workflow bottleneck detection, prompt efficiency analysis, and a live WebSocket monitor that shows costs ticking up in real-time.

## The CLI

If you prefer the terminal, every metric is also available as a CLI report:

```
python -m ccwap                  # Summary with all-time totals
python -m ccwap --daily          # 30-day rolling breakdown
python -m ccwap --cost-breakdown # Cost by token type per model
python -m ccwap --efficiency     # LOC/session, cost/KLOC
python -m ccwap --models         # Model comparison table
python -m ccwap --experiments    # A/B tag comparison
python -m ccwap --forecast       # Monthly spend projection
python -m ccwap --thinking       # Extended thinking analytics
python -m ccwap --branches       # Cost & efficiency per git branch
python -m ccwap --all            # Everything at once
```

## Some things I learned building this

- **The CLI has zero external dependencies.** Pure Python 3.10+ stdlib. No pip install needed for the core tool. The web dashboard adds FastAPI + React but the CLI works standalone.
- **Incremental ETL** -- It only processes new/modified files, so re-running is fast even with hundreds of sessions.
- **The cross-product JOIN trap** is real. When you JOIN sessions + turns + tool_calls, aggregates explode because it's N turns x M tool_calls per session. Cost me a full day of debugging inflated numbers. Subqueries are the fix.
- **Agent sessions nest** -- Claude Code spawns subagent sessions in subdirectories. The ETL recursively discovers these so agent costs are properly attributed.

## Numbers

- 19 web dashboard pages
- 26 CLI report types
- 17 backend API route modules
- 700+ automated tests
- 7-table normalized SQLite schema
- 50+ languages for LOC counting
- Zero external dependencies (CLI)

## Tech Stack

| Layer | Tech |
|-------|------|
| CLI | Python 3.10+ (stdlib only) |
| Database | SQLite (WAL mode) |
| Backend | FastAPI + aiosqlite |
| Frontend | React 19 + TypeScript + Vite |
| Charts | Recharts |
| Tables | TanStack Table |
| UI | shadcn/ui + Tailwind CSS |
| State | TanStack Query |
| Real-time | WebSocket |

## How to try it

```bash
git clone https://github.com/YOUR_USERNAME/claude-usage-analyzer
cd claude-usage-analyzer
python -m ccwap              # CLI reports (zero deps)
python -m ccwap serve        # Launch web dashboard
```

Requires Python 3.10+ and an existing Claude Code installation (it reads from `~/.claude/projects/`).

---

If you're spending real money on Claude Code and want to understand where it's going, this might be useful. Happy to answer questions or take feature requests.
