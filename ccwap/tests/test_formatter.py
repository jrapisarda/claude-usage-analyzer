"""Tests for output formatter."""

import unittest

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens, format_percentage,
    format_duration, format_delta, format_table, create_bar, strip_ansi,
    Colors, colorize, bold
)


class TestCurrencyFormatting(unittest.TestCase):
    """Test currency formatting."""

    def test_format_currency_basic(self):
        """Verify basic currency formatting."""
        self.assertEqual(format_currency(0), "$0.00")
        self.assertEqual(format_currency(1.5), "$1.50")
        self.assertEqual(format_currency(1234.56), "$1,234.56")

    def test_format_currency_large(self):
        """Verify large currency values."""
        self.assertEqual(format_currency(1000000), "$1,000,000.00")


class TestNumberFormatting(unittest.TestCase):
    """Test number formatting."""

    def test_format_number_basic(self):
        """Verify basic number formatting."""
        self.assertEqual(format_number(0), "0")
        self.assertEqual(format_number(1000), "1,000")
        self.assertEqual(format_number(1234567), "1,234,567")

    def test_format_number_decimals(self):
        """Verify decimal formatting."""
        self.assertEqual(format_number(1.234, 2), "1.23")


class TestTokenFormatting(unittest.TestCase):
    """Test token count formatting."""

    def test_format_tokens_small(self):
        """Verify small token counts."""
        self.assertEqual(format_tokens(500), "500")
        self.assertEqual(format_tokens(999), "999")

    def test_format_tokens_thousands(self):
        """Verify thousands formatting."""
        self.assertEqual(format_tokens(1000), "1.0K")
        self.assertEqual(format_tokens(15000), "15.0K")
        self.assertEqual(format_tokens(999999), "1000.0K")

    def test_format_tokens_millions(self):
        """Verify millions formatting."""
        self.assertEqual(format_tokens(1000000), "1.0M")
        self.assertEqual(format_tokens(1500000), "1.5M")


class TestDurationFormatting(unittest.TestCase):
    """Test duration formatting."""

    def test_format_duration_seconds(self):
        """Verify seconds formatting."""
        self.assertEqual(format_duration(30), "30s")
        self.assertEqual(format_duration(59), "59s")

    def test_format_duration_minutes(self):
        """Verify minutes formatting."""
        self.assertEqual(format_duration(60), "1m 0s")
        self.assertEqual(format_duration(90), "1m 30s")

    def test_format_duration_hours(self):
        """Verify hours formatting."""
        self.assertEqual(format_duration(3600), "1h 0m")
        self.assertEqual(format_duration(3660), "1h 1m")


class TestDeltaFormatting(unittest.TestCase):
    """Test delta/change formatting."""

    def test_format_delta_increase(self):
        """Verify increase formatting."""
        result = format_delta(100, 80, color_enabled=False)
        self.assertEqual(result, "+25.0%")

    def test_format_delta_decrease(self):
        """Verify decrease formatting."""
        result = format_delta(80, 100, color_enabled=False)
        self.assertEqual(result, "-20.0%")

    def test_format_delta_zero_previous(self):
        """Verify handling of zero previous value."""
        result = format_delta(100, 0, color_enabled=False)
        self.assertEqual(result, "+inf")

    def test_format_delta_both_zero(self):
        """Verify handling of both zero."""
        result = format_delta(0, 0, color_enabled=False)
        self.assertEqual(result, "N/A")


class TestTableFormatting(unittest.TestCase):
    """Test table formatting."""

    def test_format_table_basic(self):
        """Verify basic table formatting."""
        headers = ['Name', 'Value']
        rows = [['foo', '100'], ['bar', '200']]

        result = format_table(headers, rows, color_enabled=False)

        self.assertIn('Name', result)
        self.assertIn('Value', result)
        self.assertIn('foo', result)
        self.assertIn('100', result)

    def test_format_table_empty(self):
        """Verify empty table handling."""
        headers = ['Name', 'Value']
        rows = []

        result = format_table(headers, rows, color_enabled=False)
        self.assertEqual(result, "No data to display.")

    def test_format_table_alignment(self):
        """Verify alignment works."""
        headers = ['Left', 'Right']
        rows = [['a', 'b']]
        alignments = ['l', 'r']

        result = format_table(headers, rows, alignments, color_enabled=False)
        self.assertIn('Left', result)


class TestBarChart(unittest.TestCase):
    """Test bar chart creation."""

    def test_create_bar_full(self):
        """Verify full bar."""
        bar = create_bar(100, 100, width=10)
        self.assertEqual(len(bar), 10)

    def test_create_bar_half(self):
        """Verify half bar."""
        bar = create_bar(50, 100, width=10)
        self.assertEqual(len(bar), 10)

    def test_create_bar_empty(self):
        """Verify empty bar."""
        bar = create_bar(0, 100, width=10)
        self.assertEqual(len(bar), 10)


class TestColorFunctions(unittest.TestCase):
    """Test color helper functions."""

    def test_colorize_enabled(self):
        """Verify colorize with colors enabled."""
        result = colorize("test", Colors.RED, enabled=True)
        self.assertIn('\033[', result)
        self.assertIn('test', result)

    def test_colorize_disabled(self):
        """Verify colorize with colors disabled."""
        result = colorize("test", Colors.RED, enabled=False)
        self.assertEqual(result, "test")

    def test_strip_ansi(self):
        """Verify ANSI code stripping."""
        colored = colorize("test", Colors.RED, enabled=True)
        stripped = strip_ansi(colored)
        self.assertEqual(stripped, "test")


if __name__ == '__main__':
    unittest.main()
