"""Tests for JSONL parser and field extraction."""

import tempfile
import unittest
from pathlib import Path

from ccwap.etl.parser import stream_jsonl, peek_first_entry
from ccwap.etl.extractor import (
    extract_turn_data,
    extract_tool_calls,
    extract_session_metadata,
    categorize_error,
)
from ccwap.etl.validator import validate_entry, validate_token_count
from ccwap.utils.timestamps import parse_timestamp
from ccwap.utils.loc_counter import count_loc, calculate_edit_delta, detect_language
from ccwap.utils.paths import (
    decode_project_path,
    detect_file_type,
    extract_session_id_from_path,
    get_project_path_from_file,
    is_session_nested_subagent,
)


class TestJSONLParser(unittest.TestCase):
    """Test JSONL streaming parser."""

    def get_fixture_path(self, name: str) -> Path:
        """Get path to test fixture file."""
        return Path(__file__).parent / 'test_fixtures' / name

    def test_stream_valid_jsonl(self):
        """Verify valid JSONL file is parsed correctly."""
        fixture_path = self.get_fixture_path('sample_session.jsonl')
        entries = list(stream_jsonl(fixture_path))

        self.assertEqual(len(entries), 5)
        self.assertEqual(entries[0][1]['uuid'], 'entry-001')
        self.assertEqual(entries[4][1]['uuid'], 'entry-005')

    def test_malformed_lines_skipped(self):
        """Verify malformed JSON lines are skipped without crash."""
        fixture_path = self.get_fixture_path('sample_malformed.jsonl')
        entries = list(stream_jsonl(fixture_path))

        # Should get 3 good entries, skip 2 bad lines
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0][1]['uuid'], 'good-001')
        self.assertEqual(entries[1][1]['uuid'], 'good-002')
        self.assertEqual(entries[2][1]['uuid'], 'good-003')

    def test_empty_file_returns_no_entries(self):
        """Verify empty file is handled gracefully."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('')
            temp_path = Path(f.name)

        try:
            entries = list(stream_jsonl(temp_path))
            self.assertEqual(len(entries), 0)
        finally:
            temp_path.unlink()

    def test_peek_first_entry(self):
        """Verify peek_first_entry returns first valid entry."""
        fixture_path = self.get_fixture_path('sample_session.jsonl')
        entry = peek_first_entry(fixture_path)

        self.assertIsNotNone(entry)
        self.assertEqual(entry['uuid'], 'entry-001')


class TestTimestampParsing(unittest.TestCase):
    """Test timestamp parsing."""

    def test_parse_z_suffix_timestamp(self):
        """Verify UTC Z timestamps are parsed correctly."""
        ts = parse_timestamp("2026-01-15T10:30:00.123Z")
        self.assertIsNotNone(ts)
        self.assertEqual(ts.year, 2026)
        self.assertEqual(ts.month, 1)
        self.assertEqual(ts.day, 15)
        self.assertEqual(ts.hour, 10)
        self.assertEqual(ts.minute, 30)

    def test_parse_none_returns_none(self):
        """Verify None timestamp returns None."""
        self.assertIsNone(parse_timestamp(None))

    def test_parse_invalid_returns_none(self):
        """Verify invalid timestamp returns None."""
        self.assertIsNone(parse_timestamp("not a timestamp"))
        self.assertIsNone(parse_timestamp(""))


class TestFieldExtractor(unittest.TestCase):
    """Test field extraction from entries."""

    def test_extract_turn_data(self):
        """Verify TurnData is extracted correctly."""
        entry = {
            'uuid': 'test-uuid',
            'timestamp': '2026-01-15T10:00:00Z',
            'type': 'assistant',
            'sessionId': 'session-1',
            'message': {
                'model': 'claude-opus-4-5-20251101',
                'usage': {
                    'input_tokens': 100,
                    'output_tokens': 50,
                    'cache_read_input_tokens': 200,
                    'cache_creation_input_tokens': 150,
                },
            },
        }

        turn = extract_turn_data(entry, 'session-1')

        self.assertIsNotNone(turn)
        self.assertEqual(turn.uuid, 'test-uuid')
        self.assertEqual(turn.session_id, 'session-1')
        self.assertEqual(turn.entry_type, 'assistant')
        self.assertEqual(turn.model, 'claude-opus-4-5-20251101')
        self.assertEqual(turn.usage.input_tokens, 100)
        self.assertEqual(turn.usage.output_tokens, 50)
        self.assertEqual(turn.usage.cache_read_tokens, 200)
        self.assertEqual(turn.usage.cache_write_tokens, 150)

    def test_extract_turn_with_thinking(self):
        """Verify thinking chars are counted."""
        entry = {
            'uuid': 'test-uuid',
            'timestamp': '2026-01-15T10:00:00Z',
            'type': 'assistant',
            'message': {
                'content': [
                    {'type': 'thinking', 'thinking': 'This is my thinking process.'},
                    {'type': 'text', 'text': 'Here is my response.'},
                ],
            },
        }

        turn = extract_turn_data(entry, 'session-1')

        self.assertIsNotNone(turn)
        self.assertEqual(turn.thinking_chars, len('This is my thinking process.'))

    def test_extract_tool_calls(self):
        """Verify tool calls are extracted correctly."""
        entry = {
            'timestamp': '2026-01-15T10:00:00Z',
            'message': {
                'content': [
                    {
                        'type': 'tool_use',
                        'id': 'tool-1',
                        'name': 'Write',
                        'input': {
                            'file_path': '/test/file.py',
                            'content': 'def hello():\n    pass\n',
                        },
                    },
                ],
            },
        }

        tool_calls = extract_tool_calls(entry)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].tool_name, 'Write')
        self.assertEqual(tool_calls[0].file_path, '/test/file.py')
        self.assertEqual(tool_calls[0].language, 'Python')
        self.assertGreater(tool_calls[0].loc_written, 0)

    def test_extract_tool_error(self):
        """Verify tool errors are detected from tool_result."""
        entry = {
            'message': {
                'content': [
                    {'type': 'tool_use', 'id': 'tool-1', 'name': 'Bash', 'input': {}},
                    {
                        'type': 'tool_result',
                        'tool_use_id': 'tool-1',
                        'is_error': True,
                        'content': 'File not found: /missing/file',
                    },
                ],
            },
        }

        tool_calls = extract_tool_calls(entry)

        self.assertEqual(len(tool_calls), 1)
        self.assertFalse(tool_calls[0].success)
        self.assertEqual(tool_calls[0].error_category, 'File not found')

    def test_extract_tool_error_from_toolUseResult(self):
        """Verify tool errors are detected from toolUseResult.success."""
        entry = {
            'toolUseResult': {'success': False, 'commandName': 'test-cmd'},
            'message': {
                'content': [
                    {'type': 'tool_use', 'id': 'tool-1', 'name': 'Bash', 'input': {}},
                ],
            },
        }

        tool_calls = extract_tool_calls(entry)

        self.assertEqual(len(tool_calls), 1)
        self.assertFalse(tool_calls[0].success)
        self.assertEqual(tool_calls[0].command_name, 'test-cmd')


class TestSessionMetadata(unittest.TestCase):
    """Test session metadata extraction."""

    def test_extract_session_metadata(self):
        """Verify session metadata is extracted correctly."""
        entries = [
            {
                'timestamp': '2026-01-15T10:00:00Z',
                'version': '2.0.74',
                'gitBranch': 'main',
                'cwd': '/home/user/project',
                'message': {'model': 'claude-opus-4-5-20251101'},
            },
            {
                'timestamp': '2026-01-15T10:05:00Z',
                'message': {'model': 'claude-haiku-3-5-20241022'},
            },
        ]

        metadata = extract_session_metadata(entries)

        self.assertEqual(metadata['cc_version'], '2.0.74')
        self.assertEqual(metadata['git_branch'], 'main')
        self.assertEqual(metadata['cwd'], '/home/user/project')
        self.assertEqual(metadata['duration_seconds'], 300)  # 5 minutes
        self.assertIn('claude-opus-4-5-20251101', metadata['models_used'])
        self.assertIn('claude-haiku-3-5-20241022', metadata['models_used'])


class TestLOCCounting(unittest.TestCase):
    """Test lines of code counting."""

    def test_count_loc_excludes_blanks(self):
        """Verify blank lines are not counted."""
        content = "def foo():\n\n    pass\n\n"
        loc = count_loc(content, 'test.py')
        self.assertEqual(loc, 2)  # def foo(): and pass

    def test_count_loc_excludes_python_comments(self):
        """Verify # comments are not counted."""
        content = "# Comment\ndef foo():\n    # Another comment\n    pass\n"
        loc = count_loc(content, 'test.py')
        self.assertEqual(loc, 2)

    def test_count_loc_excludes_c_style_comments(self):
        """Verify // and /* */ comments are not counted."""
        content = "// Comment\nfunction foo() {\n    /* block */\n    return 1;\n}\n"
        loc = count_loc(content, 'test.js')
        self.assertEqual(loc, 3)

    def test_count_loc_handles_multiline_comments(self):
        """Verify multiline /* */ blocks are not counted."""
        content = "/*\n * Comment\n * block\n */\nfunction foo() {}\n"
        loc = count_loc(content, 'test.js')
        self.assertEqual(loc, 1)

    def test_edit_delta_calculation(self):
        """Verify lines added/deleted are calculated correctly."""
        # Adding lines
        added, deleted = calculate_edit_delta("line1", "line1\nline2\nline3")
        self.assertEqual(added, 2)
        self.assertEqual(deleted, 0)

        # Deleting lines
        added, deleted = calculate_edit_delta("line1\nline2\nline3", "line1")
        self.assertEqual(added, 0)
        self.assertEqual(deleted, 2)

        # Same length
        added, deleted = calculate_edit_delta("old", "new")
        self.assertEqual(added, 0)
        self.assertEqual(deleted, 0)


    def test_count_loc_shell_glob_not_treated_as_comment(self):
        """Verify /* in shell glob paths is not treated as C-style comment."""
        content = "#!/bin/bash\n# comment\nfor f in /tmp/*; do\n  echo $f\ndone\n"
        loc = count_loc(content, 'deploy.sh')
        self.assertEqual(loc, 3)  # for, echo, done

    def test_count_loc_shell_hash_comments(self):
        """Verify # comments are skipped in shell scripts."""
        content = "#!/bin/bash\n# setup\necho hello\n# cleanup\nexit 0\n"
        loc = count_loc(content, 'run.sh')
        self.assertEqual(loc, 2)  # echo, exit

    def test_count_loc_powershell_single_line_comment(self):
        """Verify # comments are skipped in PowerShell."""
        content = "# Comment\nWrite-Host 'hello'\n"
        loc = count_loc(content, 'script.ps1')
        self.assertEqual(loc, 1)

    def test_count_loc_powershell_multiline_comment(self):
        """Verify <# #> multiline comments are skipped in PowerShell."""
        content = "<#\n.SYNOPSIS\n  Does stuff\n#>\nWrite-Host 'hello'\n$x = 1\n"
        loc = count_loc(content, 'script.ps1')
        self.assertEqual(loc, 2)  # Write-Host, $x

    def test_count_loc_powershell_inline_multiline(self):
        """Verify single-line <# #> comment on one line."""
        content = "$x = 1 <# inline comment #>\n$y = 2\n"
        loc = count_loc(content, 'script.ps1')
        self.assertEqual(loc, 2)

    def test_count_loc_batch_comments(self):
        """Verify REM and :: comments are skipped in batch files."""
        content = "REM This is a comment\n:: Another comment\necho hello\n"
        loc = count_loc(content, 'build.bat')
        self.assertEqual(loc, 1)  # echo

    def test_count_loc_html_comment(self):
        """Verify <!-- --> comments are skipped in HTML."""
        content = "<!-- comment -->\n<div>hello</div>\n"
        loc = count_loc(content, 'page.html')
        self.assertEqual(loc, 1)  # <div>

    def test_count_loc_html_multiline_comment(self):
        """Verify multiline <!-- --> blocks are skipped."""
        content = "<!--\n  multiline\n  comment\n-->\n<p>hi</p>\n"
        loc = count_loc(content, 'page.html')
        self.assertEqual(loc, 1)  # <p>

    def test_count_loc_unknown_language_uses_defaults(self):
        """Verify unknown file types use default comment styles."""
        content = "# hash comment\n// slash comment\nactual code\n"
        loc = count_loc(content, 'file.xyz')
        self.assertEqual(loc, 1)  # actual code


class TestLanguageDetection(unittest.TestCase):
    """Test language detection from file extensions."""

    def test_detect_python(self):
        """Verify Python files are detected."""
        self.assertEqual(detect_language('test.py'), 'Python')
        self.assertEqual(detect_language('test.pyw'), 'Python')

    def test_detect_javascript(self):
        """Verify JavaScript files are detected."""
        self.assertEqual(detect_language('test.js'), 'JavaScript')
        self.assertEqual(detect_language('test.jsx'), 'JavaScript')

    def test_detect_typescript(self):
        """Verify TypeScript files are detected."""
        self.assertEqual(detect_language('test.ts'), 'TypeScript')
        self.assertEqual(detect_language('test.tsx'), 'TypeScript')

    def test_detect_shell(self):
        """Verify Shell files are detected."""
        self.assertEqual(detect_language('deploy.sh'), 'Shell')
        self.assertEqual(detect_language('setup.bash'), 'Shell')
        self.assertEqual(detect_language('config.zsh'), 'Shell')

    def test_detect_powershell(self):
        """Verify PowerShell files are detected."""
        self.assertEqual(detect_language('script.ps1'), 'PowerShell')
        self.assertEqual(detect_language('module.psm1'), 'PowerShell')
        self.assertEqual(detect_language('data.psd1'), 'PowerShell')

    def test_detect_batch(self):
        """Verify Batch files are detected."""
        self.assertEqual(detect_language('build.bat'), 'Batch')
        self.assertEqual(detect_language('run.cmd'), 'Batch')

    def test_detect_unknown(self):
        """Verify unknown extensions return None."""
        self.assertIsNone(detect_language('test.xyz'))
        self.assertIsNone(detect_language(None))


class TestPathUtilities(unittest.TestCase):
    """Test path utilities."""

    def test_decode_project_path(self):
        """Verify percent-encoded paths are decoded."""
        encoded = "C%3A%5CUsers%5Cname%5Cproject"
        decoded = decode_project_path(encoded)
        self.assertEqual(decoded, 'project')

    def test_detect_file_type_main(self):
        """Verify main session files are detected."""
        path = Path('/project/abc123.jsonl')
        self.assertEqual(detect_file_type(path), 'main')

    def test_detect_file_type_agent(self):
        """Verify agent files are detected."""
        path = Path('/project/agent-abc123.jsonl')
        self.assertEqual(detect_file_type(path), 'agent')

    def test_detect_file_type_subagent(self):
        """Verify subagent files are detected."""
        path = Path('/project/subagents/abc123.jsonl')
        self.assertEqual(detect_file_type(path), 'subagent')

    def test_extract_session_id(self):
        """Verify session ID extraction from filename."""
        self.assertEqual(
            extract_session_id_from_path(Path('abc123.jsonl')),
            'abc123'
        )
        self.assertEqual(
            extract_session_id_from_path(Path('agent-abc123.jsonl')),
            'abc123'
        )

    def test_extract_session_id_nested_subagent_any_filename(self):
        """Nested subagent files should map to parent session ID regardless of filename."""
        parent_session_id = '123e4567-e89b-12d3-a456-426614174000'
        path = Path(f'/project/{parent_session_id}/subagents/unit-test-writer.jsonl')
        self.assertEqual(
            extract_session_id_from_path(path),
            parent_session_id
        )

    def test_extract_session_id_legacy_subagent_dir_not_misclassified(self):
        """Legacy <project>/subagents/agent-*.jsonl should not use project dir as session ID."""
        project_name = 'my-very-long-project-name-with-hyphens-123456789012345'
        path = Path(f'/root/{project_name}/subagents/agent-a11e909.jsonl')
        self.assertEqual(
            extract_session_id_from_path(path),
            'a11e909'
        )

    def test_is_session_nested_subagent_false_for_legacy_subagent_dir(self):
        """Legacy <project>/subagents files are not session-nested subagents."""
        project_name = 'my-very-long-project-name-with-hyphens-123456789012345'
        path = Path(f'/root/{project_name}/subagents/agent-a11e909.jsonl')
        self.assertFalse(is_session_nested_subagent(path))

    def test_is_session_nested_subagent_true_for_session_uuid_dir(self):
        """<project>/<session-uuid>/subagents files are session-nested subagents."""
        parent_session_id = '123e4567-e89b-12d3-a456-426614174000'
        path = Path(f'/root/project/{parent_session_id}/subagents/unit-test-writer.jsonl')
        self.assertTrue(is_session_nested_subagent(path))

    def test_get_project_path_from_file_legacy_subagent_dir(self):
        """Legacy subagent files should resolve project path to project dir name."""
        project_name = 'my-very-long-project-name-with-hyphens-123456789012345'
        path = Path(f'/root/{project_name}/subagents/agent-a11e909.jsonl')
        self.assertEqual(get_project_path_from_file(path), project_name)


class TestErrorCategorization(unittest.TestCase):
    """Test error message categorization."""

    def test_categorize_file_not_found(self):
        """Verify file not found errors are categorized."""
        self.assertEqual(
            categorize_error("Error: File not found: /path/to/file"),
            'File not found'
        )

    def test_categorize_permission_denied(self):
        """Verify permission errors are categorized."""
        self.assertEqual(
            categorize_error("Permission denied: /root/file"),
            'Permission denied'
        )

    def test_categorize_timeout(self):
        """Verify timeout errors are categorized."""
        self.assertEqual(
            categorize_error("Command timed out after 30 seconds"),
            'Timeout'
        )

    def test_categorize_other(self):
        """Verify unknown errors get 'Other' category."""
        self.assertEqual(
            categorize_error("Something weird happened"),
            'Other'
        )


class TestValidation(unittest.TestCase):
    """Test validation functions."""

    def test_validate_entry_valid(self):
        """Verify valid entry passes validation."""
        entry = {
            'uuid': 'test-uuid',
            'timestamp': '2026-01-15T10:00:00Z',
        }
        result = validate_entry(entry)
        self.assertTrue(result)

    def test_validate_entry_missing_uuid(self):
        """Verify entry without UUID fails validation."""
        entry = {'timestamp': '2026-01-15T10:00:00Z'}
        result = validate_entry(entry)
        self.assertFalse(result)
        self.assertIn('uuid', result.reason.lower())

    def test_validate_entry_invalid_timestamp(self):
        """Verify entry with invalid timestamp fails validation."""
        entry = {'uuid': 'test', 'timestamp': 'not-a-date'}
        result = validate_entry(entry)
        self.assertFalse(result)
        self.assertIn('timestamp', result.reason.lower())

    def test_validate_token_count(self):
        """Verify token count validation."""
        self.assertEqual(validate_token_count(100), 100)
        self.assertEqual(validate_token_count(None), 0)
        self.assertEqual(validate_token_count(-50), 0)
        self.assertEqual(validate_token_count('invalid'), 0)


if __name__ == '__main__':
    unittest.main()
