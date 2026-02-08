"""
Real-time file watcher for CCWAP ETL pipeline.

Provides background monitoring of Claude Code session files for real-time updates.
"""

import time
import signal
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta

from ccwap.config.loader import load_config, get_database_path, get_claude_projects_path
from ccwap.models.schema import get_connection, ensure_database
from ccwap.etl import discover_jsonl_files, process_file
from ccwap.etl.incremental import update_file_state, clear_file_state
from ccwap.utils.progress import print_status


class FileWatcher:
    """
    Watches Claude Code project files for changes and triggers ETL updates.

    Uses polling-based approach for cross-platform compatibility.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        poll_interval: int = 5,
        verbose: bool = False,
        recent_hours: int = 24
    ):
        """
        Initialize the file watcher.

        Args:
            config: Configuration dict (loads default if None)
            poll_interval: Seconds between file system polls
            verbose: Enable verbose output
            recent_hours: Always process files modified within this many hours
        """
        self.config = config or load_config()
        self.poll_interval = poll_interval
        self.verbose = verbose
        self.recent_hours = recent_hours
        self.running = False
        self._file_states: Dict[str, tuple] = {}  # path -> (mtime, size)
        self._last_etl_stats: Dict[str, Any] = {}

    def _get_file_state(self, file_path: Path) -> tuple:
        """Get current mtime and size for a file."""
        try:
            stat = file_path.stat()
            return (stat.st_mtime, stat.st_size)
        except (OSError, FileNotFoundError):
            return (0, 0)

    def _is_recent_file(self, file_path: Path) -> bool:
        """Check if file was modified within recent_hours."""
        try:
            mtime = file_path.stat().st_mtime
            cutoff = datetime.now() - timedelta(hours=self.recent_hours)
            file_time = datetime.fromtimestamp(mtime)
            return file_time > cutoff
        except (OSError, FileNotFoundError):
            return False

    def _scan_for_changes(self, claude_projects_path: Path) -> list:
        """
        Scan for changed files since last poll.

        Returns list of paths that have changed.
        """
        changed = []
        files = discover_jsonl_files(claude_projects_path)

        current_paths = set()
        for file_path in files:
            path_str = str(file_path)
            current_paths.add(path_str)

            current_state = self._get_file_state(file_path)
            previous_state = self._file_states.get(path_str)

            if previous_state is None or current_state != previous_state:
                changed.append(file_path)
                self._file_states[path_str] = current_state
            elif self._is_recent_file(file_path):
                # Always include recent files in case they're being actively written
                changed.append(file_path)

        # Track removed files (for cleanup if needed)
        removed = set(self._file_states.keys()) - current_paths
        for path_str in removed:
            del self._file_states[path_str]

        return changed

    def _process_changed_files(
        self,
        conn,
        changed_files: list,
        on_update: Optional[Callable] = None
    ) -> Dict[str, int]:
        """
        Process changed files through ETL.

        Args:
            conn: Database connection
            changed_files: List of file paths to process
            on_update: Optional callback after each file

        Returns:
            Dict with processing statistics
        """
        stats = {
            'files_processed': 0,
            'entries_parsed': 0,
            'turns_inserted': 0,
            'tool_calls_inserted': 0,
        }

        for file_path in changed_files:
            try:
                # Clear previous state to force reprocessing
                clear_file_state(conn, file_path)

                if self.verbose:
                    print_status(f"Processing: {file_path.name}")

                file_stats = process_file(conn, file_path, self.config, self.verbose)

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

                conn.commit()

                if on_update:
                    on_update(file_path, file_stats)

            except PermissionError:
                if self.verbose:
                    print_status(f"Skipping {file_path.name} (file in use)")
                continue
            except Exception as e:
                if self.verbose:
                    print(f"Warning: Error processing {file_path.name}: {e}")
                conn.rollback()
                continue

        return stats

    def run_once(self) -> Dict[str, Any]:
        """
        Run a single scan and process cycle.

        Returns:
            Dict with scan statistics
        """
        claude_projects_path = get_claude_projects_path(self.config)

        if not claude_projects_path.exists():
            return {'error': f"Claude projects path not found: {claude_projects_path}"}

        db_path = get_database_path(self.config)
        conn = get_connection(db_path)
        ensure_database(conn)

        try:
            changed_files = self._scan_for_changes(claude_projects_path)

            if changed_files:
                stats = self._process_changed_files(conn, changed_files)
                stats['files_changed'] = len(changed_files)
                self._last_etl_stats = stats
                return stats
            else:
                return {'files_changed': 0, 'message': 'No changes detected'}
        finally:
            conn.close()

    def watch(
        self,
        on_update: Optional[Callable] = None,
        on_cycle: Optional[Callable] = None
    ):
        """
        Start continuous watching mode.

        Args:
            on_update: Callback when a file is updated (file_path, stats)
            on_cycle: Callback after each poll cycle (cycle_stats)
        """
        self.running = True

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            print("\nStopping watcher...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        claude_projects_path = get_claude_projects_path(self.config)

        if not claude_projects_path.exists():
            print(f"Error: Claude projects path not found: {claude_projects_path}")
            return

        db_path = get_database_path(self.config)

        print_status(f"Watching for changes (poll interval: {self.poll_interval}s)")
        print_status(f"Recent file threshold: {self.recent_hours}h")
        print_status(f"Press Ctrl+C to stop")
        print()

        cycle_count = 0
        while self.running:
            cycle_count += 1
            cycle_start = datetime.now()

            try:
                conn = get_connection(db_path)
                ensure_database(conn)

                changed_files = self._scan_for_changes(claude_projects_path)

                if changed_files:
                    if self.verbose:
                        print_status(f"Cycle {cycle_count}: {len(changed_files)} files changed")

                    stats = self._process_changed_files(conn, changed_files, on_update)
                    stats['cycle'] = cycle_count
                    stats['timestamp'] = datetime.now().isoformat()
                    self._last_etl_stats = stats

                    if on_cycle:
                        on_cycle(stats)
                    elif stats['turns_inserted'] > 0:
                        print_status(
                            f"[{datetime.now().strftime('%H:%M:%S')}] "
                            f"Processed {stats['files_processed']} files, "
                            f"{stats['turns_inserted']} turns inserted"
                        )

                conn.close()

            except Exception as e:
                print(f"Error in watch cycle: {e}")

            # Sleep until next poll
            elapsed = (datetime.now() - cycle_start).total_seconds()
            sleep_time = max(0, self.poll_interval - elapsed)

            if self.running and sleep_time > 0:
                time.sleep(sleep_time)

        print_status("Watcher stopped")

    def stop(self):
        """Stop the watcher."""
        self.running = False


def force_scan_recent(
    config: Optional[Dict[str, Any]] = None,
    hours: int = 24,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Force re-scan of recently modified files.

    This clears ETL state for files modified within the specified hours,
    forcing them to be reprocessed on the next ETL run.

    Args:
        config: Configuration dict
        hours: Process files modified within this many hours
        verbose: Enable verbose output

    Returns:
        Dict with scan statistics
    """
    config = config or load_config()
    claude_projects_path = get_claude_projects_path(config)

    if not claude_projects_path.exists():
        return {'error': f"Claude projects path not found: {claude_projects_path}"}

    db_path = get_database_path(config)
    conn = get_connection(db_path)
    ensure_database(conn)

    cutoff = datetime.now() - timedelta(hours=hours)
    files = discover_jsonl_files(claude_projects_path)

    cleared = 0
    for file_path in files:
        try:
            mtime = file_path.stat().st_mtime
            file_time = datetime.fromtimestamp(mtime)

            if file_time > cutoff:
                clear_file_state(conn, file_path)
                cleared += 1
                if verbose:
                    print_status(f"Cleared state: {file_path.name}")
        except (OSError, FileNotFoundError):
            continue

    conn.commit()
    conn.close()

    return {
        'files_scanned': len(files),
        'files_cleared': cleared,
        'cutoff_hours': hours,
        'message': f"Cleared ETL state for {cleared} recent files"
    }


def run_watch_mode(
    poll_interval: int = 5,
    verbose: bool = False,
    recent_hours: int = 24
):
    """
    Run the watcher in continuous mode.

    Args:
        poll_interval: Seconds between polls
        verbose: Enable verbose output
        recent_hours: Always process files modified within this many hours
    """
    watcher = FileWatcher(
        poll_interval=poll_interval,
        verbose=verbose,
        recent_hours=recent_hours
    )
    watcher.watch()


__all__ = [
    'FileWatcher',
    'force_scan_recent',
    'run_watch_mode',
]
