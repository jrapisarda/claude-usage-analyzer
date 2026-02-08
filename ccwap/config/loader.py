"""
Configuration loading for CCWAP.

Handles loading configuration from ~/.ccwap/config.json with sensible defaults.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import copy

# Default configuration with all pricing tiers
DEFAULT_CONFIG: Dict[str, Any] = {
    "database_path": "~/.ccwap/analytics.db",
    "snapshots_path": "~/.ccwap/snapshots",
    "claude_projects_path": "~/.claude/projects",

    # Pricing table: cost per 1M tokens
    "pricing": {
        "claude-opus-4-6": {
            "input": 5.00,
            "output": 25.00,
            "cache_read": 0.50,
            "cache_write": 6.25
        },
        "claude-opus-4-5-20251101": {
            "input": 15.00,
            "output": 75.00,
            "cache_read": 1.50,
            "cache_write": 18.75
        },
        "claude-sonnet-4-5-20250929": {
            "input": 3.00,
            "output": 15.00,
            "cache_read": 0.30,
            "cache_write": 3.75
        },
        "claude-sonnet-4-20250514": {
            "input": 3.00,
            "output": 15.00,
            "cache_read": 0.30,
            "cache_write": 3.75
        },
        "claude-3-5-sonnet-20241022": {
            "input": 3.00,
            "output": 15.00,
            "cache_read": 0.30,
            "cache_write": 3.75
        },
        "claude-haiku-3-5-20241022": {
            "input": 0.80,
            "output": 4.00,
            "cache_read": 0.08,
            "cache_write": 1.00
        },
        "claude-haiku-4-5-20251001": {
            "input": 1.00,
            "output": 5.00,
            "cache_read": 0.10,
            "cache_write": 1.25
        },
        # Default pricing for unknown models (uses Sonnet pricing)
        "default": {
            "input": 3.00,
            "output": 15.00,
            "cache_read": 0.30,
            "cache_write": 3.75
        }
    },

    # Budget alerts (optional)
    "budget_alerts": {
        "daily_warning": None,
        "weekly_warning": None,
        "monthly_warning": None
    },

    # Display options
    "display": {
        "color_enabled": True,
        "progress_threshold_mb": 10,
        "table_max_width": 120
    },

    # Pricing version for audit trail
    "pricing_version": "2026-02-01"
}


def get_config_path() -> Path:
    """Get path to config file."""
    return Path.home() / ".ccwap" / "config.json"


def get_database_path(config: Dict[str, Any]) -> Path:
    """Get expanded database path from config."""
    return Path(config["database_path"]).expanduser()


def get_snapshots_path(config: Dict[str, Any]) -> Path:
    """Get expanded snapshots path from config."""
    return Path(config["snapshots_path"]).expanduser()


def get_claude_projects_path(config: Dict[str, Any]) -> Path:
    """Get expanded Claude projects path from config."""
    return Path(config["claude_projects_path"]).expanduser()


def load_config() -> Dict[str, Any]:
    """
    Load configuration from file, merging with defaults.

    Returns a complete configuration with all default values filled in.
    User config overrides defaults where specified.
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)

            # Deep merge pricing table
            if 'pricing' in user_config:
                for model, prices in user_config['pricing'].items():
                    if model in config['pricing']:
                        config['pricing'][model].update(prices)
                    else:
                        config['pricing'][model] = prices

            # Shallow merge other sections
            for key in ['budget_alerts', 'display']:
                if key in user_config and isinstance(user_config[key], dict):
                    config[key].update(user_config[key])

            # Direct override for simple values
            for key in ['database_path', 'snapshots_path', 'claude_projects_path', 'pricing_version']:
                if key in user_config:
                    config[key] = user_config[key]

        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse config file: {e}")
        except Exception as e:
            print(f"Warning: Error loading config: {e}")

    return config


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def get_model_pricing(model: Optional[str], config: Dict[str, Any]) -> Dict[str, float]:
    """
    Get pricing for a specific model.

    Attempts exact match first, then prefix matching, finally falls back to default.
    """
    if not model:
        return config['pricing']['default']

    pricing = config['pricing']

    # Exact match
    if model in pricing:
        return pricing[model]

    # Prefix match for model families
    # e.g., "claude-sonnet-4-20250514-extra" should match "claude-sonnet-4-20250514"
    for known_model in pricing:
        if known_model == 'default':
            continue
        # Check if the known model is a prefix of the actual model
        if model.startswith(known_model):
            return pricing[known_model]
        # Or if they share a common base (before the date suffix)
        base = known_model.rsplit('-', 1)[0]
        if model.startswith(base):
            return pricing[known_model]

    # Fallback to default with warning
    print(f"Warning: Unknown model '{model}', using default pricing")
    return pricing['default']


def check_claude_settings() -> Optional[str]:
    """
    Check Claude Code settings for cleanupPeriodDays.

    Returns a warning message if cleanupPeriodDays is not set high enough,
    or None if settings are OK.
    """
    settings_path = Path.home() / '.claude' / 'settings.json'

    if not settings_path.exists():
        return (
            "WARNING: ~/.claude/settings.json not found.\n"
            "         Set 'cleanupPeriodDays: 99999' to prevent JSONL deletion!"
        )

    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)

        cleanup = settings.get('cleanupPeriodDays', 30)
        if cleanup < 365:
            return (
                f"WARNING: cleanupPeriodDays is {cleanup} days.\n"
                "         JSONL files will be deleted after this period!\n"
                "         Set to 99999 in ~/.claude/settings.json to preserve data."
            )

    except Exception:
        pass  # Don't warn on parsing errors

    return None
