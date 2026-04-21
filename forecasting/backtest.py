from __future__ import annotations

import argparse
from pathlib import Path

from forecasting.backtest_core import BacktestRunConfig, BacktestRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a single PharmaForecast backtest.")
    parser.add_argument("--train", required=True, type=Path, help="Path to the training CSV.")
    parser.add_argument("--actual", required=True, type=Path, help="Path to the actual CSV.")
    parser.add_argument("--name", required=True, help="Backtest name.")
    parser.add_argument("--model-version", required=True, help="Model version label.")
    parser.add_argument("--outdir", required=True, type=Path, help="Output directory for artifacts.")
    parser.add_argument(
        "--forecast-horizon",
        required=True,
        type=int,
        help="Number of forecast periods in the matching actual CSV.",
    )
    parser.add_argument(
        "--stock-levels",
        type=Path,
        default=None,
        help="Optional CSV with din,quantity_on_hand for stockout risk evaluation.",
    )
    parser.add_argument(
        "--minimum-history-points",
        type=int,
        default=8,
        help="Minimum history threshold used for anomaly detection.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    runner = BacktestRunner()
    config = BacktestRunConfig(
        train_path=args.train,
        actual_path=args.actual,
        backtest_name=args.name,
        model_version=args.model_version,
        outdir=args.outdir,
        forecast_horizon=args.forecast_horizon,
        stock_levels_path=args.stock_levels,
        minimum_history_points=args.minimum_history_points,
    )
    runner.run(config)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


