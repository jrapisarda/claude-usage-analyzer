"""
Path utilities for CCWAP.

Handles project path encoding/decoding and file type detection.
"""

import urllib.parse
from pathlib import Path
from typing import Optional


def decode_project_path(encoded: str) -> str:
    """
    Decode percent-encoded project path to human-readable name.

    Claude Code encodes project paths in directory names using percent-encoding.
    e.g., "C%3A%5CUsers%5Cname%5Cproject" -> "C:\\Users\\name\\project"

    Args:
        encoded: Percent-encoded path string

    Returns:
        Decoded path string, or the input if decoding fails
    """
    try:
        decoded = urllib.parse.unquote(encoded)
        # Extract just the final directory name for display
        return Path(decoded).name
    except Exception:
        return encoded


def get_project_display_name(project_path: str) -> str:
    """
    Get a human-readable display name for a project.

    Args:
        project_path: The encoded or raw project path

    Returns:
        Short display name suitable for reports
    """
    decoded = decode_project_path(project_path)

    # If the decoded name is still a full path, get just the last component
    if '/' in decoded or '\\' in decoded:
        return Path(decoded).name

    return decoded


def detect_file_type(file_path: Path) -> str:
    """
    Detect whether a JSONL file is main session, agent, or subagent.

    File type affects how data is counted:
    - main: Full session, messages and costs counted
    - agent: Agent-spawned session, costs counted but messages excluded
    - subagent: Subagent session, same handling as agent

    Args:
        file_path: Path to the JSONL file

    Returns:
        'main', 'agent', or 'subagent'
    """
    name = file_path.name

    if name.startswith('agent-'):
        return 'agent'

    if 'subagents' in str(file_path):
        return 'subagent'

    return 'main'


def extract_session_id_from_path(file_path: Path) -> str:
    """
    Extract session ID from JSONL filename.

    Main sessions: {uuid}.jsonl
    Agent sessions: agent-{uuid}.jsonl

    Args:
        file_path: Path to the JSONL file

    Returns:
        Session UUID
    """
    name = file_path.stem  # filename without extension

    if name.startswith('agent-'):
        return name[6:]  # Remove 'agent-' prefix

    return name


def get_project_path_from_file(file_path: Path) -> str:
    """
    Get the project path (encoded directory name) from a JSONL file path.

    Args:
        file_path: Path to a JSONL file

    Returns:
        The project path (parent directory name)
    """
    # Handle subagents directory
    if file_path.parent.name == 'subagents':
        return file_path.parent.parent.name

    return file_path.parent.name
