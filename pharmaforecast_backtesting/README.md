# PharmaForecast Backtesting Fixture Set

## What changed
- Replaced the previous short-history fixtures with a weekly, Monday-aligned pharmacy demand set covering 56 weeks.
- Added 6 DINs with realistic demand behavior:
  - stable demand
  - upward/downward trend
  - mild seasonality
  - moderate noise
- Removed any patient-level fields. No `patient_id` appears anywhere.

## Why this is more realistic
- One row per DIN per Monday-aligned week
- DINs are preserved consistently across all splits
- Quantities are non-negative and vary in realistic pharmacy-like ranges
- Optional fields (`cost_per_unit`, `quantity_on_hand`) are present and occasionally missing

## Prophet path
- Main backtest train windows use 48 to 52 weekly points per DIN
- Rolling-origin steps start at 30 training weeks per DIN
- This is intended to exercise the Prophet eligibility gate instead of validating only fallback behavior

## Known limitations
- This is still synthetic data, so it cannot capture every real pharmacy workflow artifact
- Seasonality is mild rather than extreme
- Inventory values are plausible but simulated, not reconciled to a full procurement engine
