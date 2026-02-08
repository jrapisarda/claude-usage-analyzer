"""
ETL package - Extract, Transform, Load pipeline for JSONL files.

Main entry point is run_etl() which orchestrates the full pipeline.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import sqlite3

from ccwap.config.loader import load_config, get_database_path, get_claude_projects_path
from ccwap.models.schema import get_connection, ensure_database
from ccwap.etl.parser import stream_jsonl, get_file_size
from ccwap.etl.extractor import extract_turn_data, extract_tool_calls, extract_session_metadata
from ccwap.etl.validator import validate_entry
from ccwap.etl.incremental import should_process_file, update_file_state
from ccwap.etl.loader import upsert_session, upsert_turns_batch, upsert_tool_calls_batch, get_turn_id_by_uuid, materialize_daily_summaries
from ccwap.utils.paths import (
    detect_file_type,
    extract_session_id_from_path,
    get_project_path_from_file,
    get_project_display_name,
)
from ccwap.utils.progress import print_status, print_verbose, file_progress
from ccwap.models.entities import SessionData


def discover_jsonl_files(claude_projects_path: Path) -> List[Path]:
    """
    Discover all JSONL files including agents and subagents.

    FIXES BUG 8: Explicitly includes agent-*.jsonl and subagents/*.jsonl

    Args:
        claude_projects_path: Path to ~/.claude/projects/

    Returns:
        List of all JSONL file paths
    """
    files = []

    if not claude_projects_path.exists():
        return files

    for project_dir in claude_projects_path.iterdir():
        if not project_dir.is_dir():
            continue

        # Main session files and agent files
        for jsonl_file in project_dir.glob('*.jsonl'):
            files.append(jsonl_file)

        # Subagent files
        subagents_dir = project_dir / 'subagents'
        if subagents_dir.exists():
            for jsonl_file in subagents_dir.glob('*.jsonl'):
                files.append(jsonl_file)

    return files


def process_file(
    conn: sqlite3.Connection,
    file_path: Path,
    config: Dict[str, Any],
    verbose: bool = False
) -> Dict[str, int]:
    """
    Process a single JSONL file.

    Args:
        conn: Database connection
        file_path: Path to JSONL file
        config: Configuration dict
        verbose: Enable verbose output

    Returns:
        Dict with processing stats
    """
    stats = {
        'entries_parsed': 0,
        'turns_inserted': 0,
        'tool_calls_inserted': 0,
        'errors_skipped': 0,
    }

    file_type = detect_file_type(file_path)
    session_id = extract_session_id_from_path(file_path)
    project_path = get_project_path_from_file(file_path)
    project_display = get_project_display_name(project_path)

    # Parse all entries
    entries = []
    turns = []
    turn_tool_calls = {}  # uuid -> list of tool calls

    file_size = get_file_size(file_path)
    show_progress = file_size > 10_000_000  # 10MB

    # Track tool_use_id -> ToolCallData for matching with results
    pending_tool_calls = {}

    for line_num, entry in stream_jsonl(file_path):
        # Validate entry
        validation = validate_entry(entry)
        if not validation:
            stats['errors_skipped'] += 1
            continue

        entries.append(entry)
        stats['entries_parsed'] += 1

        # Extract turn data
        turn = extract_turn_data(entry, session_id)
        if turn:
            turns.append(turn)

            # Extract tool calls for this turn
            tool_calls = extract_tool_calls(entry, turn.timestamp)
            if tool_calls:
                turn_tool_calls[turn.uuid] = tool_calls
                # Track for matching with results in later entries
                for tc in tool_calls:
                    if tc.tool_use_id:
                        pending_tool_calls[tc.tool_use_id] = tc

        # Check for tool_result blocks that match pending tool calls
        # (tool_result comes in user entries AFTER the assistant's tool_use)
        message = entry.get('message', {})
        content = message.get('content', [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'tool_result':
                    tool_use_id = block.get('tool_use_id', '')
                    is_error = block.get('is_error', False)

                    if tool_use_id in pending_tool_calls:
                        tc = pending_tool_calls[tool_use_id]
                        tc.success = not is_error
                        if is_error:
                            from ccwap.etl.extractor import categorize_error
                            result_content = block.get('content', '')
                            error_text = str(result_content)[:500]
                            tc.error_message = error_text
                            tc.error_category = categorize_error(error_text)

        if show_progress and stats['entries_parsed'] % 1000 == 0:
            file_progress(file_path.name, line_num * 100, file_size // 10)  # Rough estimate

    if not entries:
        return stats

    # Extract session metadata
    metadata = extract_session_metadata(entries)

    # Create session object
    is_agent = file_type in ('agent', 'subagent')

    session = SessionData(
        session_id=session_id,
        project_path=project_path,
        project_display=project_display,
        file_path=str(file_path),
        first_timestamp=metadata['first_timestamp'],
        last_timestamp=metadata['last_timestamp'],
        duration_seconds=metadata['duration_seconds'],
        cc_version=metadata['cc_version'],
        git_branch=metadata['git_branch'],
        cwd=metadata['cwd'],
        is_agent=is_agent,
        file_mtime=file_path.stat().st_mtime,
        file_size=file_path.stat().st_size,
        models_used=metadata['models_used'],
    )

    # Insert session
    upsert_session(conn, session)

    # Insert turns with cost calculation
    inserted = upsert_turns_batch(conn, turns, config)
    stats['turns_inserted'] = inserted

    # Insert tool calls (need to link to turn IDs)
    for turn in turns:
        if turn.uuid in turn_tool_calls:
            turn_id = get_turn_id_by_uuid(conn, turn.uuid)
            if turn_id:
                tc_inserted = upsert_tool_calls_batch(
                    conn,
                    turn_tool_calls[turn.uuid],
                    turn_id,
                    session_id
                )
                stats['tool_calls_inserted'] += tc_inserted

    return stats


def run_etl(
    claude_projects_path: Optional[Path] = None,
    force_rebuild: bool = False,
    verbose: bool = False,
    config: Optional[Dict[str, Any]] = None,
    recent_hours: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run the full ETL pipeline.

    Main entry point for ETL processing.

    Args:
        claude_projects_path: Override path to Claude projects
        force_rebuild: Force full re-parse of all files
        verbose: Enable verbose output
        config: Optional config override
        recent_hours: Always process files modified within N hours (for real-time updates)

    Returns:
        Dict with ETL statistics
    """
    if config is None:
        config = load_config()

    if claude_projects_path is None:
        claude_projects_path = get_claude_projects_path(config)

    if not claude_projects_path.exists():
        raise FileNotFoundError(
            f"Claude Code projects directory not found at {claude_projects_path}. "
            "Has Claude Code been run?"
        )

    # Get database connection
    db_path = get_database_path(config)
    conn = get_connection(db_path)
    ensure_database(conn)

    # If force rebuild, truncate all data tables and clear ETL state
    if force_rebuild:
        if verbose:
            print_status("Force rebuild: clearing existing data...")
        conn.execute("DELETE FROM tool_calls")
        conn.execute("DELETE FROM turns")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM etl_state")
        conn.commit()

    # Discover files
    files = discover_jsonl_files(claude_projects_path)

    stats = {
        'files_total': len(files),
        'files_processed': 0,
        'files_skipped': 0,
        'entries_parsed': 0,
        'turns_inserted': 0,
        'tool_calls_inserted': 0,
        'duplicates_skipped': 0,
    }

    if verbose:
        print_status(f"Found {len(files)} JSONL files")

    for file_path in files:
        try:
            # Check if file needs processing
            should_process, _ = should_process_file(conn, file_path, recent_hours)

            if not should_process and not force_rebuild:
                stats['files_skipped'] += 1
                continue

            if verbose:
                print_verbose(f"Processing: {file_path.name}", verbose)

            # Process file within a transaction
            file_stats = process_file(conn, file_path, config, verbose)

            # Update ETL state
            update_file_state(
                conn,
                file_path,
                file_stats['entries_parsed'],
                file_stats['errors_skipped']
            )

            # Accumulate stats
            stats['files_processed'] += 1
            stats['entries_parsed'] += file_stats['entries_parsed']
            stats['turns_inserted'] += file_stats['turns_inserted']
            stats['tool_calls_inserted'] += file_stats['tool_calls_inserted']

            # Commit after each file
            conn.commit()

        except PermissionError:
            # File in use (common on Windows)
            if verbose:
                print_verbose(f"Skipping {file_path.name} (file in use)", verbose)
            stats['files_skipped'] += 1
            continue
        except Exception as e:
            # Log error but continue with next file
            print(f"Warning: Error processing {file_path.name}: {e}")
            conn.rollback()
            continue

    # Materialize daily summaries
    if stats['files_processed'] > 0 or force_rebuild:
        if verbose:
            print_status("Materializing daily summaries...")
        if force_rebuild:
            # Full rebuild: recompute all dates
            conn.execute("DELETE FROM daily_summaries")
            days_updated = materialize_daily_summaries(conn)
        else:
            # Incremental: recompute all dates (safe, fast for SQLite)
            days_updated = materialize_daily_summaries(conn)
        conn.commit()
        stats['daily_summaries_updated'] = days_updated
        if verbose:
            print_status(f"Daily summaries: {days_updated} days updated")

    conn.close()

    if verbose:
        print_status(
            f"ETL complete: {stats['files_processed']} files processed, "
            f"{stats['turns_inserted']} turns inserted"
        )

    return stats


__all__ = [
    'run_etl',
    'discover_jsonl_files',
    'process_file',
]
