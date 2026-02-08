"""
Sessions report for CCWAP.

Generates the --sessions, --session, and --replay views.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_currency, format_tokens,
    format_table, format_duration, bold, colorize, Colors
)


def generate_sessions_list(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    project_filter: Optional[str] = None,
    color_enabled: bool = True,
    limit: int = 20
) -> str:
    """
    Generate list of recent sessions.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        project_filter: Project name filter
        color_enabled: Whether to apply colors
        limit: Max sessions to show
    """
    lines = []
    lines.append(bold("RECENT SESSIONS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build query with filters
    filters = []
    params = []

    if date_from:
        filters.append("date(first_timestamp) >= date(?)")
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        filters.append("date(first_timestamp) <= date(?)")
        params.append(date_to.strftime('%Y-%m-%d'))
    if project_filter:
        filters.append("project_display LIKE ?")
        params.append(f"%{project_filter}%")

    where_clause = " AND ".join(filters) if filters else "1=1"
    params.append(limit)

    cursor = conn.execute(f"""
        SELECT
            s.session_id,
            s.project_display,
            s.first_timestamp,
            s.last_timestamp,
            s.duration_seconds,
            s.is_agent,
            s.cc_version,
            COUNT(t.id) as turns,
            SUM(t.cost) as cost,
            COUNT(DISTINCT t.model) as model_count,
            SUM(CASE WHEN t.is_sidechain = 1 THEN 1 ELSE 0 END) as sidechain_turns
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE {where_clause}
        GROUP BY s.session_id
        ORDER BY s.first_timestamp DESC
        LIMIT ?
    """, params)

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo sessions found."

    # Prepare table
    headers = ['ID', 'Project', 'Started', 'Dur', 'Turns', 'Cost', 'Models', 'SC', 'Type']
    alignments = ['l', 'l', 'l', 'r', 'r', 'r', 'r', 'r', 'l']
    table_rows = []

    for r in rows:
        session_id = r['session_id'][:8] + '...'  # Truncate UUID
        project = r['project_display'] or 'Unknown'
        if len(project) > 25:
            project = project[:22] + '...'

        timestamp = r['first_timestamp']
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                started = dt.strftime('%Y-%m-%d %H:%M')
            except:
                started = timestamp[:16]
        else:
            started = 'N/A'

        duration = format_duration(r['duration_seconds'] or 0)
        turns = format_number(r['turns'] or 0)
        cost = format_currency(r['cost'] or 0)

        model_count = str(r['model_count'] or 0)
        sidechain_turns = r['sidechain_turns'] or 0
        sc_str = str(sidechain_turns)
        if sidechain_turns > 0:
            sc_str = colorize(sc_str, Colors.CYAN, color_enabled)

        session_type = 'Agent' if r['is_agent'] else 'Main'
        if r['is_agent']:
            session_type = colorize(session_type, Colors.CYAN, color_enabled)

        table_rows.append([session_id, project, started, duration, turns, cost, model_count, sc_str, session_type])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    return '\n'.join(lines)


def generate_session_detail(
    conn: sqlite3.Connection,
    session_id: str,
    config: Dict[str, Any],
    color_enabled: bool = True
) -> str:
    """
    Generate detailed view of a single session.

    Args:
        conn: Database connection
        session_id: Session ID to show
        config: Configuration dict
        color_enabled: Whether to apply colors
    """
    # Find session (support partial ID match)
    cursor = conn.execute("""
        SELECT * FROM sessions
        WHERE session_id LIKE ?
        LIMIT 1
    """, (f"{session_id}%",))

    session = cursor.fetchone()

    if not session:
        return f"Session not found: {session_id}"

    lines = []
    full_id = session['session_id']
    lines.append(bold(f"SESSION DETAIL: {full_id[:8]}...", color_enabled))
    lines.append("=" * 60)
    lines.append("")

    # Session metadata
    lines.append(bold("METADATA", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Session ID:    {full_id}")
    lines.append(f"Project:       {session['project_display'] or 'Unknown'}")
    lines.append(f"Path:          {session['project_path']}")
    lines.append(f"Started:       {session['first_timestamp']}")
    lines.append(f"Duration:      {format_duration(session['duration_seconds'] or 0)}")
    lines.append(f"CC Version:    {session['cc_version'] or 'Unknown'}")
    lines.append(f"Git Branch:    {session['git_branch'] or 'N/A'}")
    lines.append(f"Type:          {'Agent' if session['is_agent'] else 'Main Session'}")
    lines.append("")

    # Turn statistics
    cursor = conn.execute("""
        SELECT
            COUNT(*) as turns,
            SUM(CASE WHEN entry_type = 'user' THEN 1 ELSE 0 END) as user_turns,
            SUM(CASE WHEN entry_type = 'assistant' THEN 1 ELSE 0 END) as assistant_turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read,
            SUM(cache_write_tokens) as cache_write,
            SUM(thinking_chars) as thinking_chars,
            SUM(cost) as cost
        FROM turns
        WHERE session_id = ?
    """, (full_id,))

    stats = cursor.fetchone()

    lines.append(bold("TURN STATISTICS", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Total turns:       {format_number(stats['turns'] or 0)}")
    lines.append(f"User turns:        {format_number(stats['user_turns'] or 0)}")
    lines.append(f"Assistant turns:   {format_number(stats['assistant_turns'] or 0)}")
    lines.append(f"Thinking chars:    {format_number(stats['thinking_chars'] or 0)}")
    lines.append("")

    lines.append(bold("TOKEN USAGE", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Input tokens:      {format_tokens(stats['input_tokens'] or 0)}")
    lines.append(f"Output tokens:     {format_tokens(stats['output_tokens'] or 0)}")
    lines.append(f"Cache read:        {format_tokens(stats['cache_read'] or 0)}")
    lines.append(f"Cache write:       {format_tokens(stats['cache_write'] or 0)}")
    lines.append(f"Total cost:        {format_currency(stats['cost'] or 0)}")
    lines.append("")

    # Tool calls summary
    cursor = conn.execute("""
        SELECT
            tool_name,
            COUNT(*) as calls,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls
        WHERE session_id = ?
        GROUP BY tool_name
        ORDER BY calls DESC
    """, (full_id,))

    tool_rows = cursor.fetchall()

    if tool_rows:
        lines.append(bold("TOOL USAGE", color_enabled))
        lines.append("-" * 40)
        for r in tool_rows:
            errors = r['errors'] or 0
            error_str = f" ({errors} errors)" if errors > 0 else ""
            if errors > 0:
                error_str = colorize(error_str, Colors.RED, color_enabled)
            lines.append(f"{r['tool_name']:20} {format_number(r['calls']):>5}{error_str}")
        lines.append("")

    # Complexity metrics
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT model) as unique_models,
            SUM(CASE WHEN is_sidechain = 1 THEN 1 ELSE 0 END) as sidechain_turns
        FROM turns
        WHERE session_id = ?
    """, (full_id,))

    complexity = cursor.fetchone()

    # Get unique tool count
    tool_cursor = conn.execute("""
        SELECT COUNT(DISTINCT tool_name) as unique_tools
        FROM tool_calls
        WHERE session_id = ?
    """, (full_id,))
    tool_complexity = tool_cursor.fetchone()

    lines.append(bold("COMPLEXITY METRICS", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Unique models:     {complexity['unique_models'] or 0}")
    lines.append(f"Unique tools:      {tool_complexity['unique_tools'] or 0}")
    lines.append(f"Sidechain turns:   {complexity['sidechain_turns'] or 0}")

    return '\n'.join(lines)


def generate_session_replay(
    conn: sqlite3.Connection,
    session_id: str,
    config: Dict[str, Any],
    color_enabled: bool = True
) -> str:
    """
    Generate turn-by-turn replay of a session.

    Args:
        conn: Database connection
        session_id: Session ID to replay
        config: Configuration dict
        color_enabled: Whether to apply colors
    """
    # Find session
    cursor = conn.execute("""
        SELECT * FROM sessions
        WHERE session_id LIKE ?
        LIMIT 1
    """, (f"{session_id}%",))

    session = cursor.fetchone()

    if not session:
        return f"Session not found: {session_id}"

    full_id = session['session_id']
    lines = []
    lines.append(bold(f"SESSION REPLAY: {full_id[:8]}...", color_enabled))
    lines.append(f"Project: {session['project_display']}")
    lines.append("=" * 60)
    lines.append("")

    # Get all turns
    cursor = conn.execute("""
        SELECT
            id as turn_id,
            entry_type,
            timestamp,
            model,
            input_tokens,
            output_tokens,
            cost,
            is_meta
        FROM turns
        WHERE session_id = ?
        ORDER BY timestamp
    """, (full_id,))

    turns = cursor.fetchall()

    for i, t in enumerate(turns, 1):
        entry_type = t['entry_type']
        timestamp = t['timestamp']

        # Format timestamp
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M:%S')
            except:
                time_str = timestamp[11:19] if len(timestamp) > 19 else '??:??:??'
        else:
            time_str = '??:??:??'

        # Entry type indicator
        if entry_type == 'user':
            type_str = colorize("[USER]", Colors.CYAN, color_enabled)
        elif entry_type == 'assistant':
            type_str = colorize("[ASST]", Colors.GREEN, color_enabled)
        else:
            type_str = f"[{entry_type.upper()[:4]}]"

        # Meta indicator (skills)
        meta_str = " (skill)" if t['is_meta'] else ""

        # Token/cost info
        tokens = (t['input_tokens'] or 0) + (t['output_tokens'] or 0)
        cost = t['cost'] or 0

        lines.append(f"Turn {i:3} | {time_str} {type_str}{meta_str}")
        lines.append(f"         | Model: {t['model'] or 'N/A'} | Tokens: {format_tokens(tokens)} | Cost: {format_currency(cost)}")

        # Get tool calls for this turn
        tc_cursor = conn.execute("""
            SELECT tool_name, success, file_path
            FROM tool_calls
            WHERE turn_id = ?
        """, (t['turn_id'],))

        tools = tc_cursor.fetchall()
        if tools:
            for tc in tools:
                status = colorize("OK", Colors.GREEN, color_enabled) if tc['success'] else colorize("ERR", Colors.RED, color_enabled)
                file_path = f" ({tc['file_path']})" if tc['file_path'] else ""
                lines.append(f"         | Tool: {tc['tool_name']} [{status}]{file_path}")

        lines.append("")

    # Summary
    total_cost = sum(t['cost'] or 0 for t in turns)
    lines.append("=" * 60)
    lines.append(f"Total turns: {len(turns)} | Total cost: {format_currency(total_cost)}")

    return '\n'.join(lines)
