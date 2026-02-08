"""
JSONL Parser for CCWAP.

Streams JSONL files line-by-line for memory-efficient processing.
Never loads entire file into memory - critical for large files (>100MB).
"""

import json
from pathlib import Path
from typing import Iterator, Tuple, Optional


def stream_jsonl(
    file_path: Path,
    start_offset: int = 0
) -> Iterator[Tuple[int, dict]]:
    """
    Stream JSONL file line by line.

    Yields (line_number, parsed_dict) tuples.
    Skips malformed lines gracefully.
    Never loads entire file into memory.

    CRITICAL: This function MUST stream line-by-line.
    Never use json.load() on the entire file.

    Args:
        file_path: Path to JSONL file
        start_offset: Byte offset to start reading from (for incremental)

    Yields:
        Tuple of (line_number, parsed_entry_dict)

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be opened (e.g., in use on Windows)
    """
    malformed_count = 0

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        if start_offset > 0:
            f.seek(start_offset)

        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                yield (line_num, entry)
            except json.JSONDecodeError:
                malformed_count += 1
                continue

    if malformed_count > 0:
        print(f"Warning: Skipped {malformed_count} malformed lines in {file_path.name}")


def count_lines(file_path: Path) -> int:
    """
    Count total lines in a JSONL file.

    Useful for progress indication.
    """
    count = 0
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for _ in f:
            count += 1
    return count


def get_file_size(file_path: Path) -> int:
    """Get file size in bytes."""
    return file_path.stat().st_size


def get_file_mtime(file_path: Path) -> float:
    """Get file modification time."""
    return file_path.stat().st_mtime


def peek_first_entry(file_path: Path) -> Optional[dict]:
    """
    Read just the first entry from a JSONL file.

    Useful for quick metadata extraction without parsing entire file.
    """
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None
