# Materialized Aggregates Rollout

This project now supports optional materialized aggregate tables for high-cardinality Explorer analytics.

## Feature flag

Set in `~/.ccwap/config.json`:

```json
{
  "feature_flags": {
    "analytics_materialized_enabled": true
  }
}
```

Default is `false`.

## Backfill

Run once after upgrading schema:

```bash
python scripts/backfill_materialized_analytics.py
```

This rebuilds:
- `turns_agg_daily`
- `tool_calls_agg_daily`
- `sessions_agg_daily`

## Validation against snapshots

Before enabling the flag in production:

1. Keep `analytics_materialized_enabled` set to `false`.
2. Capture baseline outputs for key Explorer slices (projects, models, languages, date trends).
3. Run the backfill script.
4. Enable `analytics_materialized_enabled`.
5. Re-run the same slices and compare against the baseline.

Expected: same totals and group/split distributions (allowing minor floating-point rounding noise only).

