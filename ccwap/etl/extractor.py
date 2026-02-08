"""
Field Extractor for CCWAP.

Extracts structured data from parsed JSONL entries.
Handles all entry types and content blocks.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from ccwap.models.entities import TurnData, ToolCallData, TokenUsage
from ccwap.utils.timestamps import parse_timestamp
from ccwap.utils.loc_counter import count_loc, calculate_edit_delta, detect_language


def extract_turn_data(entry: Dict[str, Any], session_id: str) -> Optional[TurnData]:
    """
    Extract TurnData from a JSONL entry.

    Handles all entry types: user, assistant, queue-operation, file-history-snapshot

    Args:
        entry: Parsed JSONL entry dict
        session_id: Session ID for this turn

    Returns:
        TurnData object or None if entry is invalid
    """
    uuid = entry.get('uuid')
    if not uuid:
        return None

    timestamp_str = entry.get('timestamp')
    timestamp = parse_timestamp(timestamp_str)
    if not timestamp:
        return None

    entry_type = entry.get('type', 'unknown')
    message = entry.get('message', {})
    usage = message.get('usage', {})

    # Extract token usage
    token_usage = TokenUsage(
        input_tokens=usage.get('input_tokens', 0) or 0,
        output_tokens=usage.get('output_tokens', 0) or 0,
        cache_read_tokens=usage.get('cache_read_input_tokens', 0) or 0,
        cache_write_tokens=usage.get('cache_creation_input_tokens', 0) or 0,
        ephemeral_5m_tokens=usage.get('cache_creation', {}).get('ephemeral_5m_input_tokens', 0) or 0,
        ephemeral_1h_tokens=usage.get('cache_creation', {}).get('ephemeral_1h_input_tokens', 0) or 0,
    )

    # Calculate thinking chars from thinking blocks
    thinking_chars = 0
    content = message.get('content', [])
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'thinking':
                thinking_text = block.get('thinking', '')
                thinking_chars += len(thinking_text) if thinking_text else 0

    # Extract user prompt preview (first 500 chars of user message text)
    user_prompt_preview = None
    if entry_type == 'user' and isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and block.get('type') == 'text':
                text_parts.append(block.get('text', ''))
        if text_parts:
            user_prompt_preview = ' '.join(text_parts)[:500]
    elif entry_type == 'user' and isinstance(content, str):
        user_prompt_preview = content[:500]

    return TurnData(
        uuid=uuid,
        session_id=session_id,
        timestamp=timestamp,
        entry_type=entry_type,
        parent_uuid=entry.get('parentUuid'),
        model=message.get('model'),
        usage=token_usage,
        stop_reason=message.get('stop_reason'),
        service_tier=usage.get('service_tier'),
        is_sidechain=entry.get('isSidechain', False),
        is_meta=entry.get('isMeta', False),
        source_tool_use_id=entry.get('sourceToolUseID'),
        thinking_chars=thinking_chars,
        user_type=entry.get('userType'),
        user_prompt_preview=user_prompt_preview,
    )


def extract_tool_calls(entry: Dict[str, Any], timestamp: Optional[datetime] = None) -> List[ToolCallData]:
    """
    Extract all tool calls from an entry's message content.

    Handles both tool_use blocks and their corresponding tool_result blocks.

    Args:
        entry: Parsed JSONL entry dict
        timestamp: Timestamp to assign to tool calls

    Returns:
        List of ToolCallData objects
    """
    tool_calls = []
    message = entry.get('message', {})
    content = message.get('content', [])

    if not isinstance(content, list):
        return tool_calls

    # Build mapping of tool_use_id to tool_call data
    tool_use_map = {}

    for block in content:
        if not isinstance(block, dict):
            continue

        block_type = block.get('type')

        if block_type == 'tool_use':
            tool_use_id = block.get('id', '')
            tool_name = block.get('name', 'unknown')
            input_data = block.get('input', {})

            # Extract file_path for relevant tools
            file_path = None
            if tool_name in ('Write', 'Edit', 'Read', 'Glob', 'Grep'):
                file_path = input_data.get('file_path')
            elif tool_name == 'Bash':
                # Try to extract file paths from command
                file_path = input_data.get('file_path')

            # Calculate input size
            input_size = len(str(input_data))

            # For Write tool, capture output size (content length) and LOC
            output_size = 0
            loc_written = 0
            if tool_name == 'Write':
                write_content = input_data.get('content', '')
                output_size = len(write_content)
                loc_written = count_loc(write_content, file_path)

            # For Edit tool, calculate lines added/deleted and LOC written
            lines_added = 0
            lines_deleted = 0
            if tool_name == 'Edit':
                old_string = input_data.get('old_string', '')
                new_string = input_data.get('new_string', '')
                lines_added, lines_deleted = calculate_edit_delta(old_string, new_string)
                # Count LOC in the new content written by this edit
                new_loc = count_loc(new_string, file_path)
                old_loc = count_loc(old_string, file_path)
                loc_written = max(0, new_loc - old_loc)

            tool_use_map[tool_use_id] = ToolCallData(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                file_path=file_path,
                input_size=input_size,
                output_size=output_size,
                loc_written=loc_written,
                lines_added=lines_added,
                lines_deleted=lines_deleted,
                language=detect_language(file_path),
                timestamp=timestamp,
            )

        elif block_type == 'tool_result':
            tool_use_id = block.get('tool_use_id', '')
            is_error = block.get('is_error', False)
            result_content = block.get('content', '')

            if tool_use_id in tool_use_map:
                tool_call = tool_use_map[tool_use_id]
                tool_call.success = not is_error
                if is_error:
                    # Truncate error message to 500 chars
                    error_text = str(result_content)[:500]
                    tool_call.error_message = error_text
                    tool_call.error_category = categorize_error(error_text)

    # Also check toolUseResult for success status (most reliable source)
    tool_use_result = entry.get('toolUseResult', {})
    if isinstance(tool_use_result, dict):
        success = tool_use_result.get('success', True)
        command_name = tool_use_result.get('commandName')

        # Apply to all tool calls in this entry
        for tool_call in tool_use_map.values():
            if success is False:
                tool_call.success = False
            if command_name:
                tool_call.command_name = command_name

    return list(tool_use_map.values())


def categorize_error(error_text: str) -> str:
    """
    Categorize error message into predefined categories.

    Categories help with aggregated error analysis.
    """
    error_lower = error_text.lower()

    if 'file not found' in error_lower or 'no such file' in error_lower:
        return 'File not found'
    if 'permission denied' in error_lower:
        return 'Permission denied'
    if 'syntax error' in error_lower or 'syntaxerror' in error_lower:
        return 'Syntax error'
    if 'timeout' in error_lower or 'timed out' in error_lower:
        return 'Timeout'
    if 'connection' in error_lower or 'network' in error_lower:
        return 'Connection error'
    if 'exit code' in error_lower or 'exited with' in error_lower:
        return 'Exit code non-zero'
    if 'not unique' in error_lower or 'unique' in error_lower:
        return 'Not unique'

    return 'Other'


def extract_session_metadata(
    entries: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Extract session-level metadata from entries.

    Captures: version, git_branch, cwd, timestamps, etc.

    Args:
        entries: List of parsed JSONL entry dicts

    Returns:
        Dict with session metadata
    """
    first_timestamp = None
    last_timestamp = None
    cc_version = None
    git_branch = None
    cwd = None
    models_used = set()

    for entry in entries:
        # Extract timestamps
        ts = parse_timestamp(entry.get('timestamp'))
        if ts:
            if first_timestamp is None or ts < first_timestamp:
                first_timestamp = ts
            if last_timestamp is None or ts > last_timestamp:
                last_timestamp = ts

        # Extract version (should be consistent across entries)
        if not cc_version and entry.get('version'):
            cc_version = entry.get('version')

        # Extract git branch
        if not git_branch and entry.get('gitBranch'):
            git_branch = entry.get('gitBranch')

        # Extract cwd
        if not cwd and entry.get('cwd'):
            cwd = entry.get('cwd')

        # Track models used
        message = entry.get('message', {})
        model = message.get('model')
        if model:
            models_used.add(model)

    duration = 0
    if first_timestamp and last_timestamp:
        duration = int((last_timestamp - first_timestamp).total_seconds())

    return {
        'first_timestamp': first_timestamp,
        'last_timestamp': last_timestamp,
        'duration_seconds': duration,
        'cc_version': cc_version,
        'git_branch': git_branch,
        'cwd': cwd,
        'models_used': models_used,
    }


def is_agent_entry(entry: Dict[str, Any]) -> bool:
    """Check if an entry is from an agent session."""
    return entry.get('type') == 'assistant' and entry.get('sourceToolUseID') is not None
