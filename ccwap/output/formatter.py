"""
Output formatting for CCWAP.

Handles ASCII tables, colors, and CLI output formatting.
All stdlib - no external dependencies.
"""

import os
import sys
from typing import List, Optional, Any, Union

# Enable ANSI colors on Windows
if sys.platform == 'win32':
    os.system('')  # Triggers VT100 emulation


class Colors:
    """ANSI escape codes for terminal colors."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Foreground colors
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'


def colorize(text: str, color: str, enabled: bool = True) -> str:
    """Apply color if enabled."""
    if not enabled:
        return text
    return f"{color}{text}{Colors.RESET}"


def bold(text: str, enabled: bool = True) -> str:
    """Make text bold."""
    if not enabled:
        return text
    return f"{Colors.BOLD}{text}{Colors.RESET}"


def dim(text: str, enabled: bool = True) -> str:
    """Make text dim/gray."""
    if not enabled:
        return text
    return f"{Colors.DIM}{text}{Colors.RESET}"


# Formatting functions
def format_currency(value: float, include_sign: bool = False) -> str:
    """Format as currency with 2 decimal places."""
    if include_sign and value > 0:
        return f"+${value:,.2f}"
    return f"${value:,.2f}"


def format_number(value: Union[int, float], decimals: int = 0) -> str:
    """Format number with thousands separator."""
    if decimals > 0:
        return f"{value:,.{decimals}f}"
    return f"{int(value):,}"


def format_percentage(value: float, precision: int = 1) -> str:
    """Format as percentage."""
    return f"{value:.{precision}f}%"


def format_tokens(value: int) -> str:
    """Format token count with K/M suffix for large numbers."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def format_duration(seconds: int) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def format_delta(
    current: float,
    previous: float,
    is_lower_better: bool = False,
    color_enabled: bool = True
) -> str:
    """
    Format a delta value with color and direction.

    Args:
        current: Current period value
        previous: Previous period value
        is_lower_better: If True, negative delta is green (e.g., errors, cost)
        color_enabled: Whether to apply colors
    """
    if previous == 0:
        if current == 0:
            return "N/A"
        return "+inf" if current > 0 else "-inf"

    delta = current - previous
    pct = ((current - previous) / previous) * 100

    sign = '+' if delta >= 0 else ''

    # Determine color
    if abs(pct) < 0.1:
        color = Colors.GRAY
    elif is_lower_better:
        color = Colors.GREEN if delta < 0 else Colors.RED
    else:
        color = Colors.GREEN if delta > 0 else Colors.RED

    result = f"{sign}{pct:.1f}%"
    return colorize(result, color, color_enabled)


def create_bar(value: float, max_value: float, width: int = 20) -> str:
    """Create ASCII progress bar."""
    if max_value == 0:
        return ' ' * width

    ratio = min(1.0, value / max_value)
    filled = int(ratio * width)

    return '\u2588' * filled + '\u2591' * (width - filled)


def format_table(
    headers: List[str],
    rows: List[List[Any]],
    alignments: Optional[List[str]] = None,
    color_enabled: bool = True
) -> str:
    """
    Format data as an ASCII table.

    Args:
        headers: Column headers
        rows: List of row tuples/lists
        alignments: List of 'l', 'r', or 'c' for each column
        color_enabled: Whether to apply colors to headers
    """
    if not rows:
        return "No data to display."

    # Convert all cells to strings
    str_rows = [[str(cell) for cell in row] for row in rows]

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            # Strip ANSI codes for width calculation
            clean_cell = strip_ansi(cell)
            col_widths[i] = max(col_widths[i], len(clean_cell))

    # Default alignments (right for numbers, left for text)
    if alignments is None:
        alignments = ['l'] * len(headers)

    # Build format functions
    def align_cell(text: str, width: int, align: str) -> str:
        clean_text = strip_ansi(text)
        padding_needed = width - len(clean_text)
        if align == 'r':
            return ' ' * padding_needed + text
        elif align == 'c':
            left_pad = padding_needed // 2
            right_pad = padding_needed - left_pad
            return ' ' * left_pad + text + ' ' * right_pad
        else:  # left
            return text + ' ' * padding_needed

    lines = []

    # Header
    header_cells = [
        align_cell(h, col_widths[i], alignments[i])
        for i, h in enumerate(headers)
    ]
    header_line = ' \u2502 '.join(header_cells)
    if color_enabled:
        header_line = bold(header_line)
    lines.append(header_line)

    # Separator
    sep_line = '\u2500\u253c\u2500'.join('\u2500' * w for w in col_widths)
    lines.append(sep_line)

    # Rows
    for row in str_rows:
        row_cells = [
            align_cell(cell, col_widths[i], alignments[i])
            for i, cell in enumerate(row)
        ]
        lines.append(' \u2502 '.join(row_cells))

    return '\n'.join(lines)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def print_header(text: str, char: str = '=', color_enabled: bool = True) -> str:
    """Create a header line."""
    line = char * 60
    return f"{line}\n  {text}\n{line}"


def print_section(title: str, color_enabled: bool = True) -> str:
    """Create a section header."""
    return f"\n{bold(title, color_enabled)}\n{'-' * len(title)}"
