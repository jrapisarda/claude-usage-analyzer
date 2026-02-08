"""
Tests for cost calculation.

These tests verify the accuracy of cost calculations which is THE critical
requirement of CCWAP. The old tool had 6 bugs related to cost calculation.
"""

import unittest
from ccwap.cost.calculator import (
    calculate_turn_cost,
    calculate_session_cost,
    calculate_cost_breakdown,
)
from ccwap.cost.pricing import (
    get_pricing_for_model,
    is_opus_model,
    is_haiku_model,
    get_pricing_tier,
)
from ccwap.config.loader import load_config


class TestOpusCostCalculation(unittest.TestCase):
    """Test Opus model cost calculation - most expensive tier."""

    def setUp(self):
        self.config = load_config()

    def test_opus_cost_from_requirements(self):
        """
        Verify exact cost calculation for Opus model from requirements doc.

        Sample: 10 input, 31971 cache_write, 12832 cache_read, 3 output tokens
        Expected: $0.619079

        Breakdown:
        - Input: 10/1M * $15.00 = $0.000150
        - Output: 3/1M * $75.00 = $0.000225
        - Cache Read: 12832/1M * $1.50 = $0.019248
        - Cache Write: 31971/1M * $18.75 = $0.599456
        - Total: $0.619079
        """
        cost = calculate_turn_cost(
            input_tokens=10,
            output_tokens=3,
            cache_read_tokens=12832,
            cache_write_tokens=31971,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        # Should be within 1 cent of $0.619079
        self.assertAlmostEqual(cost, 0.619079, delta=0.01)

    def test_opus_cost_breakdown(self):
        """Verify Opus cost breakdown matches expected per-component costs."""
        breakdown = calculate_cost_breakdown(
            input_tokens=10,
            output_tokens=3,
            cache_read_tokens=12832,
            cache_write_tokens=31971,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        self.assertAlmostEqual(breakdown['input_cost'], 0.000150, places=6)
        self.assertAlmostEqual(breakdown['output_cost'], 0.000225, places=6)
        self.assertAlmostEqual(breakdown['cache_read_cost'], 0.019248, places=5)
        self.assertAlmostEqual(breakdown['cache_write_cost'], 0.599456, places=4)

    def test_opus_output_is_most_expensive(self):
        """Verify Opus output tokens are correctly priced at $75/MTok."""
        # 1000 output tokens should cost $0.075
        cost = calculate_turn_cost(
            input_tokens=0,
            output_tokens=1000,
            cache_read_tokens=0,
            cache_write_tokens=0,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        expected = 1000 / 1_000_000 * 75.00
        self.assertAlmostEqual(cost, expected, places=6)

    def test_opus_4_6_cost_calculation(self):
        """Verify Opus 4.6 cost calculation with known token counts."""
        cost = calculate_turn_cost(
            input_tokens=10,
            output_tokens=3,
            cache_read_tokens=12832,
            cache_write_tokens=31971,
            model='claude-opus-4-6',
            config=self.config
        )

        # Opus 4.6 pricing: $5 input, $25 output, $0.50 cache_read, $6.25 cache_write
        # Input: 10/1M * $5.00 = $0.000050
        # Output: 3/1M * $25.00 = $0.000075
        # Cache Read: 12832/1M * $0.50 = $0.006416
        # Cache Write: 31971/1M * $6.25 = $0.199819
        # Total: $0.206360
        expected = 0.206360
        self.assertAlmostEqual(cost, expected, delta=0.01)

    def test_opus_4_6_cost_breakdown(self):
        """Verify Opus 4.6 cost breakdown matches expected per-component costs."""
        breakdown = calculate_cost_breakdown(
            input_tokens=10,
            output_tokens=3,
            cache_read_tokens=12832,
            cache_write_tokens=31971,
            model='claude-opus-4-6',
            config=self.config
        )

        self.assertAlmostEqual(breakdown['input_cost'], 0.000050, places=6)
        self.assertAlmostEqual(breakdown['output_cost'], 0.000075, places=6)
        self.assertAlmostEqual(breakdown['cache_read_cost'], 0.006416, places=5)
        self.assertAlmostEqual(breakdown['cache_write_cost'], 0.199819, places=4)

    def test_opus_4_6_output_pricing(self):
        """Verify Opus 4.6 output tokens are priced at $25/MTok."""
        cost = calculate_turn_cost(
            input_tokens=0,
            output_tokens=1000,
            cache_read_tokens=0,
            cache_write_tokens=0,
            model='claude-opus-4-6',
            config=self.config
        )

        expected = 1000 / 1_000_000 * 25.00
        self.assertAlmostEqual(cost, expected, places=6)


class TestSonnetCostCalculation(unittest.TestCase):
    """Test Sonnet model cost calculation - middle tier."""

    def setUp(self):
        self.config = load_config()

    def test_sonnet_is_5x_cheaper_than_opus_4_5_for_output(self):
        """Verify Sonnet output is 5x cheaper than Opus 4.5."""
        tokens = 10000

        opus_cost = calculate_turn_cost(
            input_tokens=0,
            output_tokens=tokens,
            cache_read_tokens=0,
            cache_write_tokens=0,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        sonnet_cost = calculate_turn_cost(
            input_tokens=0,
            output_tokens=tokens,
            cache_read_tokens=0,
            cache_write_tokens=0,
            model='claude-sonnet-4-20250514',
            config=self.config
        )

        # Opus 4.5 output: $75/MTok, Sonnet output: $15/MTok
        # Ratio should be 5:1
        ratio = opus_cost / sonnet_cost
        self.assertAlmostEqual(ratio, 5.0, places=1)

    def test_opus_4_6_cheaper_than_opus_4_5(self):
        """Verify Opus 4.6 is cheaper than Opus 4.5."""
        tokens = 10000

        opus_4_5_cost = calculate_turn_cost(
            input_tokens=tokens,
            output_tokens=tokens,
            cache_read_tokens=tokens,
            cache_write_tokens=tokens,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        opus_4_6_cost = calculate_turn_cost(
            input_tokens=tokens,
            output_tokens=tokens,
            cache_read_tokens=tokens,
            cache_write_tokens=tokens,
            model='claude-opus-4-6',
            config=self.config
        )

        self.assertLess(opus_4_6_cost, opus_4_5_cost)

    def test_sonnet_pricing_all_variants(self):
        """Verify all Sonnet variants use same pricing."""
        sonnet_models = [
            'claude-sonnet-4-5-20250929',
            'claude-sonnet-4-20250514',
            'claude-3-5-sonnet-20241022',
        ]

        costs = []
        for model in sonnet_models:
            cost = calculate_turn_cost(
                input_tokens=1000,
                output_tokens=1000,
                cache_read_tokens=1000,
                cache_write_tokens=1000,
                model=model,
                config=self.config
            )
            costs.append(cost)

        # All Sonnet variants should have same cost
        for cost in costs[1:]:
            self.assertAlmostEqual(costs[0], cost, places=6)


class TestHaikuCostCalculation(unittest.TestCase):
    """Test Haiku model cost calculation - cheapest tier."""

    def setUp(self):
        self.config = load_config()

    def test_haiku_is_cheapest(self):
        """Verify Haiku is cheaper than Sonnet and Opus."""
        tokens = 10000

        haiku_cost = calculate_turn_cost(
            input_tokens=tokens,
            output_tokens=tokens,
            cache_read_tokens=tokens,
            cache_write_tokens=tokens,
            model='claude-haiku-3-5-20241022',
            config=self.config
        )

        sonnet_cost = calculate_turn_cost(
            input_tokens=tokens,
            output_tokens=tokens,
            cache_read_tokens=tokens,
            cache_write_tokens=tokens,
            model='claude-sonnet-4-20250514',
            config=self.config
        )

        opus_cost = calculate_turn_cost(
            input_tokens=tokens,
            output_tokens=tokens,
            cache_read_tokens=tokens,
            cache_write_tokens=tokens,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        self.assertLess(haiku_cost, sonnet_cost)
        self.assertLess(sonnet_cost, opus_cost)


class TestUnknownModelHandling(unittest.TestCase):
    """Test handling of unknown models."""

    def setUp(self):
        self.config = load_config()

    def test_unknown_model_uses_default(self):
        """Verify unknown models fall back to Sonnet (default) pricing."""
        # Calculate with unknown model
        unknown_cost = calculate_turn_cost(
            input_tokens=1000,
            output_tokens=1000,
            cache_read_tokens=1000,
            cache_write_tokens=1000,
            model='claude-unknown-future-model-v99',
            config=self.config
        )

        # Calculate with explicit default
        default_cost = calculate_turn_cost(
            input_tokens=1000,
            output_tokens=1000,
            cache_read_tokens=1000,
            cache_write_tokens=1000,
            model='default',
            config=self.config
        )

        # Should match (both use default/Sonnet pricing)
        self.assertAlmostEqual(unknown_cost, default_cost, places=6)

    def test_none_model_uses_default(self):
        """Verify None model returns non-zero cost using default."""
        cost = calculate_turn_cost(
            input_tokens=1000,
            output_tokens=1000,
            cache_read_tokens=0,
            cache_write_tokens=0,
            model=None,
            config=self.config
        )

        # Should have some cost
        self.assertGreater(cost, 0)


class TestSessionCostCalculation(unittest.TestCase):
    """Test session-level cost aggregation."""

    def setUp(self):
        self.config = load_config()

    def test_session_cost_equals_sum_of_turns(self):
        """Verify session cost = sum(turn costs) exactly."""
        turns = [
            {
                'input_tokens': 1000,
                'output_tokens': 500,
                'cache_read_tokens': 200,
                'cache_write_tokens': 100,
                'model': 'claude-opus-4-5-20251101'
            },
            {
                'input_tokens': 800,
                'output_tokens': 600,
                'cache_read_tokens': 300,
                'cache_write_tokens': 150,
                'model': 'claude-sonnet-4-20250514'
            },
            {
                'input_tokens': 500,
                'output_tokens': 400,
                'cache_read_tokens': 100,
                'cache_write_tokens': 50,
                'model': 'claude-haiku-3-5-20241022'
            },
        ]

        # Calculate via session method
        session_cost = calculate_session_cost(turns, self.config)

        # Calculate sum of individual turns
        individual_sum = 0.0
        for turn in turns:
            individual_sum += calculate_turn_cost(
                input_tokens=turn['input_tokens'],
                output_tokens=turn['output_tokens'],
                cache_read_tokens=turn['cache_read_tokens'],
                cache_write_tokens=turn['cache_write_tokens'],
                model=turn['model'],
                config=self.config
            )

        # Must match exactly
        self.assertAlmostEqual(session_cost, individual_sum, places=10)

    def test_multi_model_session_uses_correct_per_turn_pricing(self):
        """Verify sessions with mixed models use correct per-turn pricing."""
        # Session with one Opus turn and one Haiku turn
        opus_turn = {
            'input_tokens': 0,
            'output_tokens': 1000,
            'cache_read_tokens': 0,
            'cache_write_tokens': 0,
            'model': 'claude-opus-4-5-20251101'
        }
        haiku_turn = {
            'input_tokens': 0,
            'output_tokens': 1000,
            'cache_read_tokens': 0,
            'cache_write_tokens': 0,
            'model': 'claude-haiku-3-5-20241022'
        }

        session_cost = calculate_session_cost([opus_turn, haiku_turn], self.config)

        # Opus output: 1000/1M * $75 = $0.075
        # Haiku output: 1000/1M * $4 = $0.004
        # Total should be $0.079
        expected = 0.075 + 0.004
        self.assertAlmostEqual(session_cost, expected, places=6)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases in cost calculation."""

    def setUp(self):
        self.config = load_config()

    def test_zero_tokens_zero_cost(self):
        """Verify zero tokens produces exactly $0.00 cost."""
        cost = calculate_turn_cost(
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        self.assertEqual(cost, 0.0)

    def test_negative_tokens_treated_as_zero(self):
        """Verify negative token counts are treated as zero."""
        cost = calculate_turn_cost(
            input_tokens=-100,
            output_tokens=-50,
            cache_read_tokens=-25,
            cache_write_tokens=-10,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        self.assertEqual(cost, 0.0)

    def test_none_token_values_treated_as_zero(self):
        """Verify None token values are treated as zero."""
        cost = calculate_turn_cost(
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        self.assertEqual(cost, 0.0)

    def test_very_large_token_counts(self):
        """Verify handling of very large token counts."""
        # 10 million tokens of each type
        cost = calculate_turn_cost(
            input_tokens=10_000_000,
            output_tokens=10_000_000,
            cache_read_tokens=10_000_000,
            cache_write_tokens=10_000_000,
            model='claude-opus-4-5-20251101',
            config=self.config
        )

        # 10M * ($15 + $75 + $1.50 + $18.75) / 1M = $1102.50
        expected = 10 * (15.00 + 75.00 + 1.50 + 18.75)
        self.assertAlmostEqual(cost, expected, places=2)

    def test_empty_session_zero_cost(self):
        """Verify empty session has zero cost."""
        cost = calculate_session_cost([], self.config)
        self.assertEqual(cost, 0.0)


class TestPricingHelpers(unittest.TestCase):
    """Test pricing helper functions."""

    def setUp(self):
        self.config = load_config()

    def test_is_opus_model(self):
        """Verify Opus model detection."""
        self.assertTrue(is_opus_model('claude-opus-4-5-20251101'))
        self.assertTrue(is_opus_model('claude-opus-4-6'))
        self.assertTrue(is_opus_model('CLAUDE-OPUS-something'))
        self.assertFalse(is_opus_model('claude-sonnet-4-20250514'))
        self.assertFalse(is_opus_model(None))

    def test_is_haiku_model(self):
        """Verify Haiku model detection."""
        self.assertTrue(is_haiku_model('claude-haiku-3-5-20241022'))
        self.assertTrue(is_haiku_model('CLAUDE-HAIKU-something'))
        self.assertFalse(is_haiku_model('claude-sonnet-4-20250514'))
        self.assertFalse(is_haiku_model(None))

    def test_get_pricing_tier(self):
        """Verify pricing tier detection."""
        self.assertEqual(get_pricing_tier('claude-opus-4-5-20251101'), 'opus')
        self.assertEqual(get_pricing_tier('claude-opus-4-6'), 'opus')
        self.assertEqual(get_pricing_tier('claude-sonnet-4-20250514'), 'sonnet')
        self.assertEqual(get_pricing_tier('claude-haiku-3-5-20241022'), 'haiku')
        self.assertEqual(get_pricing_tier('unknown-model'), 'unknown')
        self.assertEqual(get_pricing_tier(None), 'unknown')


if __name__ == '__main__':
    unittest.main()
