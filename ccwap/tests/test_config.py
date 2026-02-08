"""Tests for configuration loading."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ccwap.config.loader import (
    load_config,
    get_model_pricing,
    DEFAULT_CONFIG,
    get_database_path,
    get_snapshots_path,
)


class TestConfigLoading(unittest.TestCase):
    """Test configuration loading."""

    def test_default_config_structure(self):
        """Verify default config has required keys."""
        required_keys = [
            'database_path',
            'snapshots_path',
            'claude_projects_path',
            'pricing',
            'budget_alerts',
            'display',
            'pricing_version',
        ]
        for key in required_keys:
            self.assertIn(key, DEFAULT_CONFIG)

    def test_default_pricing_has_required_models(self):
        """Verify default pricing includes all required models."""
        required_models = [
            'claude-opus-4-5-20251101',
            'claude-sonnet-4-5-20250929',
            'claude-sonnet-4-20250514',
            'claude-3-5-sonnet-20241022',
            'claude-haiku-3-5-20241022',
            'default',
        ]
        for model in required_models:
            self.assertIn(model, DEFAULT_CONFIG['pricing'])

    def test_pricing_has_all_token_types(self):
        """Verify each model pricing has all token types."""
        required_types = ['input', 'output', 'cache_read', 'cache_write']

        for model, pricing in DEFAULT_CONFIG['pricing'].items():
            for token_type in required_types:
                self.assertIn(token_type, pricing,
                    f"Model {model} missing {token_type}")

    def test_load_config_returns_defaults(self):
        """Verify load_config returns defaults when no config file exists."""
        with mock.patch('ccwap.config.loader.get_config_path') as mock_path:
            mock_path.return_value = Path('/nonexistent/config.json')
            config = load_config()

        self.assertIsNotNone(config)
        self.assertIn('pricing', config)
        self.assertEqual(config['pricing']['default']['input'], 3.00)

    def test_load_config_merges_user_config(self):
        """Verify user config overrides defaults."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            user_config = {
                "pricing": {
                    "default": {
                        "input": 5.00
                    }
                }
            }
            with open(config_path, 'w') as f:
                json.dump(user_config, f)

            with mock.patch('ccwap.config.loader.get_config_path') as mock_path:
                mock_path.return_value = config_path
                config = load_config()

            # User override should be applied
            self.assertEqual(config['pricing']['default']['input'], 5.00)
            # Other defaults should still exist
            self.assertEqual(config['pricing']['default']['output'], 15.00)

    def test_path_expansion(self):
        """Verify path expansion works correctly."""
        config = DEFAULT_CONFIG.copy()

        db_path = get_database_path(config)
        self.assertIsInstance(db_path, Path)
        self.assertFalse(str(db_path).startswith('~'))

        snap_path = get_snapshots_path(config)
        self.assertIsInstance(snap_path, Path)
        self.assertFalse(str(snap_path).startswith('~'))


class TestModelPricing(unittest.TestCase):
    """Test model pricing lookup."""

    def test_exact_model_match(self):
        """Verify exact model name returns correct pricing."""
        config = load_config()
        pricing = get_model_pricing('claude-opus-4-5-20251101', config)

        self.assertEqual(pricing['input'], 15.00)
        self.assertEqual(pricing['output'], 75.00)
        self.assertEqual(pricing['cache_read'], 1.50)
        self.assertEqual(pricing['cache_write'], 18.75)

    def test_sonnet_pricing(self):
        """Verify Sonnet model pricing."""
        config = load_config()
        pricing = get_model_pricing('claude-sonnet-4-20250514', config)

        self.assertEqual(pricing['input'], 3.00)
        self.assertEqual(pricing['output'], 15.00)
        self.assertEqual(pricing['cache_read'], 0.30)
        self.assertEqual(pricing['cache_write'], 3.75)

    def test_haiku_pricing(self):
        """Verify Haiku model pricing."""
        config = load_config()
        pricing = get_model_pricing('claude-haiku-3-5-20241022', config)

        self.assertEqual(pricing['input'], 0.80)
        self.assertEqual(pricing['output'], 4.00)
        self.assertEqual(pricing['cache_read'], 0.08)
        self.assertEqual(pricing['cache_write'], 1.00)

    def test_unknown_model_returns_default(self):
        """Verify unknown model falls back to default pricing."""
        config = load_config()

        # Capture print output to verify warning
        with mock.patch('builtins.print') as mock_print:
            pricing = get_model_pricing('claude-unknown-model-v99', config)

        # Should return default pricing
        self.assertEqual(pricing['input'], 3.00)
        self.assertEqual(pricing['output'], 15.00)

        # Should print warning
        mock_print.assert_called()
        warning_msg = str(mock_print.call_args)
        self.assertIn('Unknown model', warning_msg)

    def test_none_model_returns_default(self):
        """Verify None model returns default pricing."""
        config = load_config()
        pricing = get_model_pricing(None, config)

        self.assertEqual(pricing['input'], 3.00)

    def test_empty_string_model_returns_default(self):
        """Verify empty string model returns default pricing."""
        config = load_config()
        pricing = get_model_pricing('', config)

        self.assertEqual(pricing['input'], 3.00)


if __name__ == '__main__':
    unittest.main()
