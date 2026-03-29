#!/usr/bin/env python3
"""
run.py — Entry point for the Resolv USR counterfactual simulation.

Usage
-----
    python run.py              # Run the simulation and save figures
    python run.py --no-mc      # Skip Monte Carlo (faster)
    python run.py --csv        # Also export time-series data to CSV
    python run.py --csv --verify-manifest  # Full reproducibility check

Outputs
-------
    figures/fig_*.png          Six publication-quality figures
    data/results_summary.csv   Summary table (if --csv)
    data/timeseries_*.csv      Per-config time series (if --csv)
    stdout                     Formatted summary table
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from config import MC
from src.simulation import run_all, print_summary
from src.sensitivity import run_sensitivity_sweep, run_monte_carlo
from src.figures import generate_all
from src.reproducibility import build_manifest, verify_manifest, write_manifest


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "reproducibility_manifest.json"
CSV_FLOAT_FORMAT = "%.10f"


def export_csv(results, data_dir: Path):
    """Export summary and time-series data to CSV."""
    import pandas as pd

    data_dir.mkdir(parents=True, exist_ok=True)

    # Summary table
    rows = []
    for cfg in ['factual', 'D1', 'D2']:
        r = results[cfg]
        rows.append({
            'config': cfg,
            'final_bad_debt_usd': r.final_bad_debt,
            'trigger_time_min': r.trigger_time,
            'total_allocator_inflow_usd': r.total_allocator_inflow,
            'total_arb_borrowed_usd': r.total_arb_borrowed,
        })
    pd.DataFrame(rows).to_csv(
        data_dir / "results_summary.csv",
        index=False,
        float_format=CSV_FLOAT_FORMAT,
    )

    # Time series per config
    for cfg in ['factual', 'D1', 'D2']:
        r = results[cfg]
        df = pd.DataFrame({
            'time_min': r.time,
            'dex_price': r.dex_price,
            'supply': r.supply,
            'oracle_price': r.oracle,
            'regime': r.regime,
            'bad_debt_cumulative': r.bad_debt,
            'usdc_pool': r.usdc_pool,
            'allocator_inflow': r.allocator_inflows,
            'arb_borrow': r.arb_borrows,
        })
        df.to_csv(
            data_dir / f"timeseries_{cfg}.csv",
            index=False,
            float_format=CSV_FLOAT_FORMAT,
        )

    print(f"CSV data exported to {data_dir}/")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run the adaptive oracle counterfactual analysis."
    )
    parser.add_argument(
        "--no-mc",
        action="store_true",
        help="Skip the Monte Carlo analysis and figure.",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Export summary and time-series CSVs under the output root.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("."),
        help="Directory where generated figures/ and data/ are written.",
    )
    parser.add_argument(
        "--verify-manifest",
        action="store_true",
        help="Compare generated artifacts against the tracked reproducibility manifest.",
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Rewrite the tracked reproducibility manifest from the current full run.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to the reproducibility manifest JSON.",
    )
    return parser.parse_args(argv)


def run_pipeline(skip_mc: bool = False, do_csv: bool = False,
                 output_root: Path = Path(".")):
    """Run the full analysis pipeline and write artifacts."""
    output_root = output_root.resolve()
    figures_dir = output_root / "figures"
    data_dir = output_root / "data"

    t0 = time.time()

    # ── 1. Run main simulation ──
    print("Running Resolv counterfactual simulation...")
    print("  Configs: factual (static oracle), D1 (DEX deviation), D2 (supply velocity)")
    results = run_all()

    for cfg in ['factual', 'D1', 'D2']:
        r = results[cfg]
        tt = f"{r.trigger_time:.2f} min" if r.trigger_time is not None else "never"
        print(f"  {cfg}: bad_debt=${r.final_bad_debt/1e6:.2f}M, trigger={tt}")

    # ── 2. Sensitivity sweep ──
    print("\nRunning D1 sensitivity sweep...")
    sens_data = run_sensitivity_sweep()
    print(f"  Grid: {sens_data[2].shape[0]} thresholds × {sens_data[2].shape[1]} persistence levels")

    # ── 3. Monte Carlo ──
    if skip_mc:
        print("\nSkipping Monte Carlo (--no-mc flag).")
        mc_data = None
    else:
        print(f"\nRunning Monte Carlo (n={MC.N_RUNS:,})...")
        mc_data = run_monte_carlo()
        for cfg in ['factual', 'D1', 'D2']:
            arr = mc_data[cfg]
            print(f"  {cfg}: mean=${arr.mean()/1e6:.2f}M, "
                  f"p95=${np.percentile(arr, 95)/1e6:.2f}M")

    # ── 4. Generate figures ──
    print("\nGenerating figures...")
    if mc_data is not None:
        generate_all(results, sens_data, mc_data, figures_dir)
        print(f"  6 figures saved to {figures_dir}/")
    else:
        # Generate only non-MC figures
        from src.figures import (fig_timeline_oracle_paths, fig_bad_debt_prevented,
                                 fig_divergence_regime_map, fig_counterfactual_bars,
                                 fig_sensitivity_heatmap)
        figures_dir.mkdir(parents=True, exist_ok=True)
        fig_timeline_oracle_paths(results, figures_dir)
        fig_bad_debt_prevented(results, figures_dir)
        fig_divergence_regime_map(results, figures_dir)
        fig_counterfactual_bars(results, figures_dir)
        fig_sensitivity_heatmap(*sens_data, output_dir=figures_dir)
        print(f"  5 figures saved to {figures_dir}/ (MC skipped)")

    # ── 5. Print summary ──
    print_summary(results)

    # ── 6. Optional CSV export ──
    if do_csv:
        export_csv(results, data_dir)

    elapsed = time.time() - t0
    print(f"Total runtime: {elapsed:.1f}s")
    return results, sens_data, mc_data


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    results, _, mc_data = run_pipeline(
        skip_mc=args.no_mc,
        do_csv=args.csv,
        output_root=args.output_root,
    )

    requires_full_run = args.verify_manifest or args.write_manifest
    if requires_full_run and (args.no_mc or not args.csv):
        raise SystemExit(
            "Manifest operations require the full run. Re-run with --csv and without --no-mc."
        )

    manifest_path = args.manifest_path.resolve()
    output_root = args.output_root.resolve()

    if args.write_manifest:
        manifest = build_manifest(output_root, results)
        write_manifest(manifest_path, manifest)
        print(f"Reproducibility manifest updated at {manifest_path}")

    if args.verify_manifest:
        errors = verify_manifest(output_root, manifest_path)
        if errors:
            for error in errors:
                print(f"VERIFY FAIL: {error}", file=sys.stderr)
            raise SystemExit(1)
        print(f"Manifest verification passed for {manifest_path}")


if __name__ == '__main__':
    main()
