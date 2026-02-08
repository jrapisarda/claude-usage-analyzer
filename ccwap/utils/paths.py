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


def is_session_nested_subagent(file_path: Path) -> bool:
    """
    Check if a file is a subagent nested under a session directory.

    Pattern: <project>/<session-id>/subagents/agent-*.jsonl
    These files should have their tool calls attributed to the parent session
    and should NOT overwrite the parent session metadata.

    Args:
        file_path: Path to the JSONL file

    Returns:
        True if this is a session-nested subagent file
    """
    if file_path.parent.name != 'subagents':
        return False
    parent_dir = file_path.parent.parent.name
    return '-' in parent_dir and len(parent_dir) > 30


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
    Session subagents: <session-id>/subagents/agent-{agent-id}.jsonl
        -> returns <session-id> (parent session) so tool calls are attributed correctly

    Args:
        file_path: Path to the JSONL file

    Returns:
        Session UUID
    """
    name = file_path.stem  # filename without extension

    if name.startswith('agent-'):
        # Check if this is a subagent nested under a session directory
        # Pattern: <project>/<session-id>/subagents/agent-xxx.jsonl
        if file_path.parent.name == 'subagents':
            parent_dir = file_path.parent.parent.name
            # If parent dir looks like a UUID session ID (contains hyphens, not a project path)
            if '-' in parent_dir and len(parent_dir) > 30:
                return parent_dir  # Use parent session ID
        return name[6:]  # Remove 'agent-' prefix

    return name


def get_project_path_from_file(file_path: Path) -> str:
    """
    Get the project path (encoded directory name) from a JSONL file path.

    Handles three layouts:
    - <project>/<session>.jsonl -> <project>
    - <project>/subagents/<agent>.jsonl -> <project>
    - <project>/<session-id>/subagents/<agent>.jsonl -> <project>

    Args:
        file_path: Path to a JSONL file

    Returns:
        The project path (parent directory name)
    """
    # Handle subagents directory
    if file_path.parent.name == 'subagents':
        grandparent = file_path.parent.parent
        # Check if grandparent is a session dir (UUID-like) nested under the project dir
        if '-' in grandparent.name and len(grandparent.name) > 30:
            return grandparent.parent.name  # Go up one more level to project
        return grandparent.name

    return file_path.parent.name
