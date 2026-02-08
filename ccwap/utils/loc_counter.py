"""
Lines of Code (LOC) counting for CCWAP.

Counts non-blank, non-comment lines with language-specific detection.
Uses a data-driven LanguageConfig registry so adding a new language
requires only one new entry — no logic changes.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class LanguageConfig:
    """Comment-style configuration for a programming language.

    To add a new language, append a LanguageConfig to the LANGUAGES list.
    EXTENSION_TO_LANGUAGE and LANGUAGE_TO_CONFIG are derived automatically.
    """
    name: str
    extensions: List[str]
    line_comments: List[str] = field(default_factory=list)
    multiline_comments: List[Tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Language registry — add new languages here
# ---------------------------------------------------------------------------
LANGUAGES: List[LanguageConfig] = [
    # --- Scripting ---
    LanguageConfig(
        name='Python',
        extensions=['.py', '.pyw'],
        line_comments=['#'],
        multiline_comments=[('"""', '"""'), ("'''", "'''")],
    ),
    LanguageConfig(
        name='Shell',
        extensions=['.sh', '.bash', '.zsh', '.fish'],
        line_comments=['#'],
        multiline_comments=[],          # Shell has no multi-line comments
    ),
    LanguageConfig(
        name='PowerShell',
        extensions=['.ps1', '.psm1', '.psd1'],
        line_comments=['#'],
        multiline_comments=[('<#', '#>')],
    ),
    LanguageConfig(
        name='Batch',
        extensions=['.bat', '.cmd'],
        line_comments=['REM ', '::'],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='Ruby',
        extensions=['.rb'],
        line_comments=['#'],
        multiline_comments=[('=begin', '=end')],
    ),
    LanguageConfig(
        name='Perl',
        extensions=['.pl', '.pm'],
        line_comments=['#'],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='Lua',
        extensions=['.lua'],
        line_comments=['--'],
        multiline_comments=[('--[[', ']]')],
    ),
    LanguageConfig(
        name='R',
        extensions=['.r', '.R'],
        line_comments=['#'],
        multiline_comments=[],
    ),

    # --- C-family ---
    LanguageConfig(
        name='JavaScript',
        extensions=['.js', '.mjs', '.cjs', '.jsx'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='TypeScript',
        extensions=['.ts', '.tsx'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Java',
        extensions=['.java'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Go',
        extensions=['.go'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Rust',
        extensions=['.rs'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='C++',
        extensions=['.cpp', '.cc', '.cxx', '.hpp', '.hxx'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='C',
        extensions=['.c', '.h'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='C#',
        extensions=['.cs'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Swift',
        extensions=['.swift'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Kotlin',
        extensions=['.kt', '.kts'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Scala',
        extensions=['.scala'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Dart',
        extensions=['.dart'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='PHP',
        extensions=['.php'],
        line_comments=['//', '#'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Groovy',
        extensions=['.groovy'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Gradle',
        extensions=['.gradle'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='V',
        extensions=['.v'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Zig',
        extensions=['.zig'],
        line_comments=['//'],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='Nim',
        extensions=['.nim'],
        line_comments=['#'],
        multiline_comments=[('#[', ']#')],
    ),

    # --- SQL ---
    LanguageConfig(
        name='SQL',
        extensions=['.sql'],
        line_comments=['--'],
        multiline_comments=[('/*', '*/')],
    ),

    # --- Functional ---
    LanguageConfig(
        name='Haskell',
        extensions=['.hs'],
        line_comments=['--'],
        multiline_comments=[('{-', '-}')],
    ),
    LanguageConfig(
        name='OCaml',
        extensions=['.ml'],
        line_comments=[],
        multiline_comments=[('(*', '*)')],
    ),
    LanguageConfig(
        name='F#',
        extensions=['.fs', '.fsx'],
        line_comments=['//'],
        multiline_comments=[('(*', '*)')],
    ),
    LanguageConfig(
        name='Elixir',
        extensions=['.ex', '.exs'],
        line_comments=['#'],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='Erlang',
        extensions=['.erl', '.hrl'],
        line_comments=['%'],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='Clojure',
        extensions=['.clj'],
        line_comments=[';'],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='ClojureScript',
        extensions=['.cljs'],
        line_comments=[';'],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='VisualBasic',
        extensions=['.vb'],
        line_comments=["'"],
        multiline_comments=[],
    ),

    # --- Markup / Web ---
    LanguageConfig(
        name='HTML',
        extensions=['.html', '.htm'],
        line_comments=[],
        multiline_comments=[('<!--', '-->')],
    ),
    LanguageConfig(
        name='XML',
        extensions=['.xml'],
        line_comments=[],
        multiline_comments=[('<!--', '-->')],
    ),
    LanguageConfig(
        name='CSS',
        extensions=['.css'],
        line_comments=[],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='SCSS',
        extensions=['.scss'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='SASS',
        extensions=['.sass'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='LESS',
        extensions=['.less'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Vue',
        extensions=['.vue'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/'), ('<!--', '-->')],
    ),
    LanguageConfig(
        name='Svelte',
        extensions=['.svelte'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/'), ('<!--', '-->')],
    ),

    # --- Data / Config ---
    LanguageConfig(
        name='Markdown',
        extensions=['.md'],
        line_comments=[],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='JSON',
        extensions=['.json'],
        line_comments=[],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='YAML',
        extensions=['.yaml', '.yml'],
        line_comments=['#'],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='TOML',
        extensions=['.toml'],
        line_comments=['#'],
        multiline_comments=[],
    ),
    LanguageConfig(
        name='Terraform',
        extensions=['.tf'],
        line_comments=['#', '//'],
        multiline_comments=[('/*', '*/')],
    ),
    LanguageConfig(
        name='Protobuf',
        extensions=['.proto'],
        line_comments=['//'],
        multiline_comments=[('/*', '*/')],
    ),
]

# ---------------------------------------------------------------------------
# Derived lookup tables — rebuilt automatically from LANGUAGES
# ---------------------------------------------------------------------------
EXTENSION_TO_LANGUAGE: Dict[str, str] = {}
LANGUAGE_TO_CONFIG: Dict[str, LanguageConfig] = {}

for _lang in LANGUAGES:
    LANGUAGE_TO_CONFIG[_lang.name] = _lang
    for _ext in _lang.extensions:
        EXTENSION_TO_LANGUAGE[_ext] = _lang.name

# Default comment styles for unknown file types
_DEFAULT_LINE_COMMENTS = ['#', '//', '--']
_DEFAULT_MULTILINE_COMMENTS: List[Tuple[str, str]] = [('/*', '*/')]


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

    Uses the LanguageConfig registry for language-specific comment detection.
    For unknown languages, falls back to common defaults (#, //, --, /* */).

    Args:
        content: The source code content
        file_path: Optional file path for language detection

    Returns:
        Number of non-blank, non-comment lines
    """
    if not content:
        return 0

    language = detect_language(file_path)
    config = LANGUAGE_TO_CONFIG.get(language) if language else None

    if config:
        line_comments = config.line_comments
        multiline_pairs = config.multiline_comments
    else:
        line_comments = _DEFAULT_LINE_COMMENTS
        multiline_pairs = _DEFAULT_MULTILINE_COMMENTS

    lines = content.split('\n')
    loc = 0
    in_multiline = False
    multiline_end: Optional[str] = None

    for line in lines:
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # ---- Inside a multi-line comment ----
        if in_multiline:
            assert multiline_end is not None
            if multiline_end in stripped:
                in_multiline = False
                # Check for code after the closing delimiter
                after = stripped.split(multiline_end, 1)[1].strip()
                if after and not _starts_with_any(after, line_comments):
                    loc += 1
            continue

        # ---- Check for multi-line comment starts ----
        found_multiline = False
        for ml_start, ml_end in multiline_pairs:
            if ml_start not in stripped:
                continue

            before = stripped.split(ml_start, 1)[0].strip()
            after_start = stripped.split(ml_start, 1)[1]

            # Does it close on the same line?
            if ml_end in after_start:
                after_close = after_start.split(ml_end, 1)[1].strip()
                if before or (after_close and not _starts_with_any(after_close, line_comments)):
                    loc += 1
                found_multiline = True
                break

            # Opens but doesn't close — enter multi-line state
            in_multiline = True
            multiline_end = ml_end
            if before:
                loc += 1
            found_multiline = True
            break

        if found_multiline:
            continue

        # ---- Skip single-line comments ----
        if _starts_with_any(stripped, line_comments):
            continue

        # It's code
        loc += 1

    return loc


def _starts_with_any(text: str, prefixes: List[str]) -> bool:
    """Check if text starts with any of the given prefixes."""
    return any(text.startswith(p) for p in prefixes) if prefixes else False


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
