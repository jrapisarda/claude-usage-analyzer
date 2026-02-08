"""
Snapshot management for CCWAP.

Handles creating and comparing snapshots for the --diff feature.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens, format_delta,
    format_table, bold, colorize, Colors
)


def create_snapshot(
    conn: sqlite3.Connection,
    snapshot_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Create a snapshot of current analytics state.

    Args:
        conn: Database connection
        snapshot_path: Path to save snapshot (optional)

    Returns:
        Snapshot data dict
    """
    now = datetime.now()

    # Gather all-time statistics
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read,
            SUM(cache_write_tokens) as cache_write,
            SUM(cost) as cost
        FROM turns
    """)
    totals = cursor.fetchone()

    # Tool call stats
    tc_cursor = conn.execute("""
        SELECT
            COUNT(*) as tool_calls,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
            SUM(loc_written) as loc_written
        FROM tool_calls
    """)
    tc_stats = tc_cursor.fetchone()

    # Project breakdown
    proj_cursor = conn.execute("""
        SELECT
            s.project_display,
            SUM(t.cost) as cost,
            COUNT(DISTINCT s.session_id) as sessions
        FROM sessions s
        JOIN turns t ON t.session_id = s.session_id
        GROUP BY s.project_display
        ORDER BY cost DESC
        LIMIT 20
    """)
    projects = {r['project_display']: {'cost': r['cost'], 'sessions': r['sessions']}
                for r in proj_cursor.fetchall()}

    snapshot = {
        'version': 1,
        'created_at': now.isoformat(),
        'totals': {
            'sessions': totals['sessions'] or 0,
            'turns': totals['turns'] or 0,
            'input_tokens': totals['input_tokens'] or 0,
            'output_tokens': totals['output_tokens'] or 0,
            'cache_read': totals['cache_read'] or 0,
            'cache_write': totals['cache_write'] or 0,
            'cost': totals['cost'] or 0,
            'tool_calls': tc_stats['tool_calls'] or 0,
            'errors': tc_stats['errors'] or 0,
            'loc_written': tc_stats['loc_written'] or 0,
        },
        'projects': projects,
    }

    # Save to file if path provided
    if snapshot_path:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        with open(snapshot_path, 'w') as f:
            json.dump(snapshot, f, indent=2)

    # Also save to database
    file_path_str = str(snapshot_path) if snapshot_path else f"snapshot_{now.strftime('%Y%m%d_%H%M%S')}.json"
    conn.execute("""
        INSERT INTO snapshots (timestamp, file_path, summary_json)
        VALUES (?, ?, ?)
    """, (now.isoformat(), file_path_str, json.dumps(snapshot)))
    conn.commit()

    return snapshot


def load_snapshot(snapshot_path: Path) -> Optional[Dict[str, Any]]:
    """Load a snapshot from file."""
    if not snapshot_path.exists():
        return None

    with open(snapshot_path, 'r') as f:
        return json.load(f)


def compare_snapshots(
    current: Dict[str, Any],
    previous: Dict[str, Any],
    color_enabled: bool = True
) -> str:
    """
    Compare two snapshots and generate a diff report.

    Args:
        current: Current snapshot
        previous: Previous snapshot to compare against
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("SNAPSHOT COMPARISON", color_enabled))
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Previous: {previous.get('created_at', 'Unknown')}")
    lines.append(f"Current:  {current.get('created_at', 'Unknown')}")
    lines.append("")

    prev_totals = previous.get('totals', {})
    curr_totals = current.get('totals', {})

    # Comparison table
    headers = ['Metric', 'Previous', 'Current', 'Change']
    alignments = ['l', 'r', 'r', 'r']
    table_rows = []

    metrics = [
        ('Sessions', 'sessions', format_number),
        ('Turns', 'turns', format_number),
        ('Input Tokens', 'input_tokens', format_tokens),
        ('Output Tokens', 'output_tokens', format_tokens),
        ('Cache Read', 'cache_read', format_tokens),
        ('Total Cost', 'cost', format_currency),
        ('Tool Calls', 'tool_calls', format_number),
        ('Errors', 'errors', format_number),
        ('LOC Written', 'loc_written', format_number),
    ]

    for label, key, fmt in metrics:
        prev_val = prev_totals.get(key, 0)
        curr_val = curr_totals.get(key, 0)
        delta = format_delta(curr_val, prev_val, color_enabled)

        table_rows.append([label, fmt(prev_val), fmt(curr_val), delta])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # New/changed projects
    prev_projects = previous.get('projects', {})
    curr_projects = current.get('projects', {})

    new_projects = set(curr_projects.keys()) - set(prev_projects.keys())
    if new_projects:
        lines.append("")
        lines.append(bold("NEW PROJECTS", color_enabled))
        lines.append("-" * 40)
        for project in list(new_projects)[:5]:
            cost = curr_projects[project].get('cost', 0)
            lines.append(f"{project[:30]:30} {format_currency(cost)}")

    return '\n'.join(lines)


def generate_diff(
    conn: sqlite3.Connection,
    snapshot_file: str,
    config: Dict[str, Any],
    color_enabled: bool = True
) -> str:
    """
    Generate diff report between current state and a snapshot file.

    Args:
        conn: Database connection
        snapshot_file: Path to snapshot file
        config: Configuration dict
        color_enabled: Whether to apply colors
    """
    snapshot_path = Path(snapshot_file)

    previous = load_snapshot(snapshot_path)
    if not previous:
        return f"Error: Snapshot file not found: {snapshot_file}"

    # Create current snapshot (without saving)
    current = create_snapshot(conn)

    return compare_snapshots(current, previous, color_enabled)
