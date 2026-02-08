"""
Lines of Code (LOC) counting for CCWAP.

Counts non-blank, non-comment lines with language-specific detection.
Uses a state machine approach for accurate multi-line comment handling.
"""

from pathlib import Path
from typing import Optional, Tuple

# Language detection by file extension
EXTENSION_TO_LANGUAGE = {
    '.py': 'Python',
    '.pyw': 'Python',
    '.js': 'JavaScript',
    '.mjs': 'JavaScript',
    '.cjs': 'JavaScript',
    '.ts': 'TypeScript',
    '.tsx': 'TypeScript',
    '.jsx': 'JavaScript',
    '.java': 'Java',
    '.go': 'Go',
    '.rs': 'Rust',
    '.cpp': 'C++',
    '.cc': 'C++',
    '.cxx': 'C++',
    '.c': 'C',
    '.h': 'C',
    '.hpp': 'C++',
    '.hxx': 'C++',
    '.cs': 'C#',
    '.rb': 'Ruby',
    '.php': 'PHP',
    '.swift': 'Swift',
    '.kt': 'Kotlin',
    '.kts': 'Kotlin',
    '.scala': 'Scala',
    '.sql': 'SQL',
    '.sh': 'Shell',
    '.bash': 'Shell',
    '.zsh': 'Shell',
    '.fish': 'Shell',
    '.ps1': 'PowerShell',
    '.psm1': 'PowerShell',
    '.md': 'Markdown',
    '.json': 'JSON',
    '.yaml': 'YAML',
    '.yml': 'YAML',
    '.toml': 'TOML',
    '.xml': 'XML',
    '.html': 'HTML',
    '.htm': 'HTML',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.sass': 'SASS',
    '.less': 'LESS',
    '.vue': 'Vue',
    '.svelte': 'Svelte',
    '.lua': 'Lua',
    '.r': 'R',
    '.R': 'R',
    '.pl': 'Perl',
    '.pm': 'Perl',
    '.ex': 'Elixir',
    '.exs': 'Elixir',
    '.erl': 'Erlang',
    '.hrl': 'Erlang',
    '.clj': 'Clojure',
    '.cljs': 'ClojureScript',
    '.hs': 'Haskell',
    '.ml': 'OCaml',
    '.fs': 'F#',
    '.fsx': 'F#',
    '.dart': 'Dart',
    '.nim': 'Nim',
    '.zig': 'Zig',
    '.v': 'V',
    '.vb': 'VisualBasic',
    '.groovy': 'Groovy',
    '.gradle': 'Gradle',
    '.tf': 'Terraform',
    '.proto': 'Protobuf',
}


def detect_language(file_path: Optional[str]) -> Optional[str]:
    """
    Detect programming language from file extension.

    Args:
        file_path: Path to the file

    Returns:
        Language name or None if unknown
    """
    if not file_path:
        return None

    ext = Path(file_path).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)


def count_loc(content: str, file_path: Optional[str] = None) -> int:
    """
    Count lines of code, excluding blanks and comments.

    Uses a state machine approach for accurate multi-line comment detection.
    Handles Python, C-style, Shell, and SQL comments.

    Args:
        content: The source code content
        file_path: Optional file path for language detection

    Returns:
        Number of non-blank, non-comment lines
    """
    if not content:
        return 0

    language = detect_language(file_path)
    lines = content.split('\n')
    loc = 0
    in_multiline_comment = False
    multiline_style = None  # 'python_double', 'python_single', 'c_style'

    for line in lines:
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Handle ongoing multiline comments
        if in_multiline_comment:
            if multiline_style == 'c_style' and '*/' in stripped:
                in_multiline_comment = False
                # Check if there's code after the comment end
                after_comment = stripped.split('*/', 1)[1].strip()
                if after_comment and not after_comment.startswith('//') and not after_comment.startswith('#'):
                    loc += 1
            elif multiline_style == 'python_double' and '"""' in stripped:
                in_multiline_comment = False
            elif multiline_style == 'python_single' and "'''" in stripped:
                in_multiline_comment = False
            continue

        # Check for C-style multiline comment start /* ... */
        if '/*' in stripped:
            before_comment = stripped.split('/*', 1)[0].strip()
            after_start = stripped.split('/*', 1)[1]

            # Check if comment closes on same line
            if '*/' in after_start:
                after_comment = after_start.split('*/', 1)[1].strip()
                # Line has code if there's content before or after the comment
                if before_comment or (after_comment and not after_comment.startswith('//')):
                    loc += 1
                continue

            # Multiline comment starts
            in_multiline_comment = True
            multiline_style = 'c_style'
            # Count line if there's code before the comment
            if before_comment:
                loc += 1
            continue

        # Check for Python docstrings/multiline strings
        if language == 'Python':
            if stripped.startswith('"""') or stripped == '"""':
                if stripped.count('"""') == 1:
                    in_multiline_comment = True
                    multiline_style = 'python_double'
                    continue
                elif stripped.count('"""') >= 2:
                    # Single-line docstring like """text"""
                    continue
            if stripped.startswith("'''") or stripped == "'''":
                if stripped.count("'''") == 1:
                    in_multiline_comment = True
                    multiline_style = 'python_single'
                    continue
                elif stripped.count("'''") >= 2:
                    continue

        # Skip single-line comments
        if stripped.startswith('#'):
            continue
        if stripped.startswith('//'):
            continue
        if stripped.startswith('--'):  # SQL
            continue
        if stripped.startswith('/*') and '*/' in stripped:
            # Already handled above
            continue

        # It's code
        loc += 1

    return loc


def calculate_edit_delta(old_string: str, new_string: str) -> Tuple[int, int]:
    """
    Calculate lines added and deleted in an Edit operation.

    Args:
        old_string: Original text being replaced
        new_string: New text replacing the original

    Returns:
        Tuple of (lines_added, lines_deleted)
    """
    old_lines = len(old_string.split('\n')) if old_string else 0
    new_lines = len(new_string.split('\n')) if new_string else 0

    if new_lines > old_lines:
        return (new_lines - old_lines, 0)
    elif old_lines > new_lines:
        return (0, old_lines - new_lines)
    else:
        return (0, 0)
