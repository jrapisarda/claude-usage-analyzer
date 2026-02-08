"""
Progress indication utilities for CCWAP.

Simple progress indicators using carriage return for CLI output.
No external dependencies - stdlib only.
"""

import sys
from typing import Optional


def progress_bar(
    current: int,
    total: int,
    width: int = 40,
    prefix: str = 'Progress'
) -> None:
    """
    Display a simple progress bar using carriage return.

    Args:
        current: Current progress value
        total: Total value for 100%
        width: Width of the bar in characters
        prefix: Text to show before the bar
    """
    if total == 0:
        return

    percent = current / total
    filled = int(width * percent)
    bar = '=' * filled + '-' * (width - filled)

    sys.stdout.write(f'\r{prefix}: [{bar}] {percent:.1%} ({current}/{total})')
    sys.stdout.flush()

    if current >= total:
        sys.stdout.write('\n')


def file_progress(
    file_name: str,
    bytes_processed: int,
    total_bytes: int
) -> None:
    """
    Display file processing progress.

    Only displays if file is large enough to warrant progress indication.

    Args:
        file_name: Name of file being processed
        bytes_processed: Bytes processed so far
        total_bytes: Total file size
    """
    if total_bytes == 0:
        return

    percent = (bytes_processed / total_bytes) * 100
    sys.stdout.write(f'\r  Processing {file_name}: {percent:.0f}%')
    sys.stdout.flush()

    if bytes_processed >= total_bytes:
        sys.stdout.write('\n')


class ProgressTracker:
    """
    Context manager for tracking progress of multiple items.

    Usage:
        with ProgressTracker(total=100, prefix="Files") as tracker:
            for item in items:
                process(item)
                tracker.update()
    """

    def __init__(
        self,
        total: int,
        prefix: str = 'Progress',
        show_threshold: int = 3
    ):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items
            prefix: Prefix text for progress display
            show_threshold: Only show progress if total >= this value
        """
        self.total = total
        self.prefix = prefix
        self.show_threshold = show_threshold
        self.current = 0
        self.should_show = total >= show_threshold

    def __enter__(self):
        if self.should_show:
            progress_bar(0, self.total, prefix=self.prefix)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.should_show:
            sys.stdout.write('\n')
        return False

    def update(self, increment: int = 1) -> None:
        """Update progress by increment."""
        self.current += increment
        if self.should_show:
            progress_bar(self.current, self.total, prefix=self.prefix)


def print_status(message: str, end: str = '\n') -> None:
    """Print a status message."""
    print(message, end=end, flush=True)


def print_verbose(message: str, verbose: bool = False) -> None:
    """Print a message only if verbose mode is enabled."""
    if verbose:
        print(message, flush=True)
