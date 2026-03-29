"""
simulation.py — Orchestrator
==============================

Runs the Morpho market simulation under each oracle configuration and
returns structured results for figure generation.

KEY DESIGN DECISION: MANUAL INTERVENTION IN FACTUAL
----------------------------------------------------
In reality, Gauntlet manually intervened at t ≈ 91 minutes after Mint #1.
We model this as a hard cutoff: after t = 91 min, the factual scenario
sets allow_allocator=False and allow_new_borrows=False. This ensures the
factual bad debt converges to ~$6M rather than growing indefinitely.

For D1 and D2, the oracle itself triggers STRESSED (and the concurrent
actions) within the first minute, so the manual intervention never becomes
relevant — the arb loop is already dead.
"""

from __future__ import annotations


from dataclasses import dataclass
import numpy as np

from config import GRID, MARKET, ORACLE
from src.price_paths import build_usr_dex_price_path, build_usr_supply_path
from src.oracle import build_oracle_path
from src.market import MorphoMarketSim


@dataclass
class SimResult:
    """Container for one simulation run."""
    config: str                    # 'factual', 'D1', 'D2'
    time: np.ndarray               # minutes
    dex_price: np.ndarray          # USR DEX price
    supply: np.ndarray             # USR totalSupply
    oracle: np.ndarray             # wstUSR oracle price
    regime: np.ndarray             # 0=NORMAL, 1=STRESSED
    trigger_time: float | None     # minutes when STRESSED activated
    bad_debt: np.ndarray           # cumulative bad debt per step
    usdc_pool: np.ndarray          # USDC pool per step
    allocator_inflows: np.ndarray  # allocator inflow per step
    arb_borrows: np.ndarray        # arb borrow per step
    final_bad_debt: float
    total_allocator_inflow: float
    total_arb_borrowed: float


def run_single(config: str) -> SimResult:
    """
    Run the full simulation for one oracle configuration.

    Parameters
    ----------
    config : str
        'factual', 'D1', or 'D2'.

    Returns
    -------
    SimResult
        Structured results including all time series and summary metrics.
    """
    # ── Build input paths ──
    t, dex_price = build_usr_dex_price_path()
    _, supply = build_usr_supply_path()
    oracle, regime, trigger_time = build_oracle_path(t, dex_price, supply, config)

    # ── Run market simulation ──
    market = MorphoMarketSim()

    for i in range(len(t)):
        ti = t[i]

        if config == 'factual':
            # Model Gauntlet's manual intervention at t=91 min:
            # after this point, new borrows and allocator are halted.
            past_intervention = (ti > MARKET.MANUAL_INTERVENTION_MIN)
            is_stressed = False  # Oracle never enters STRESSED
            allow_alloc = not past_intervention
            allow_borrow = not past_intervention
        else:
            # D1/D2: oracle-driven actions
            is_stressed = regime[i] > 0
            allow_alloc = not is_stressed
            allow_borrow = not is_stressed

        market.step(
            oracle_price=oracle[i],
            dex_price=dex_price[i],
            regime=regime[i],
            allow_allocator=allow_alloc,
            allow_new_borrows=allow_borrow,
        )

    return SimResult(
        config=config,
        time=t,
        dex_price=dex_price,
        supply=supply,
        oracle=oracle,
        regime=regime,
        trigger_time=trigger_time,
        bad_debt=np.array(market.bad_debt_history),
        usdc_pool=np.array(market.usdc_pool_history),
        allocator_inflows=np.array(market.allocator_inflows),
        arb_borrows=np.array(market.arb_borrows),
        final_bad_debt=market.bad_debt,
        total_allocator_inflow=sum(market.allocator_inflows),
        total_arb_borrowed=market.arb_total_borrowed,
    )


def run_all() -> dict[str, SimResult]:
    """
    Run all three oracle configurations and return results.

    Returns
    -------
    dict mapping config name → SimResult
    """
    results = {}
    for config in ['factual', 'D1', 'D2']:
        results[config] = run_single(config)
    return results


def print_summary(results: dict[str, SimResult]) -> None:
    """Print a formatted summary table to stdout."""
    print()
    print("=" * 78)
    print("COUNTERFACTUAL SIMULATION RESULTS")
    print("=" * 78)
    print(f"{'Config':<28} {'Bad Debt':>12} {'Trigger':>12} {'Allocator':>14} {'Prevented':>10}")
    print("-" * 78)

    factual_bd = results['factual'].final_bad_debt

    for config, label in [
        ('factual', 'Factual (static oracle)'),
        ('D1', 'D1: DEX-deviation trigger'),
        ('D2', 'D2: Supply-velocity trigger'),
    ]:
        r = results[config]
        tt = f"{r.trigger_time:.1f} min" if r.trigger_time is not None else "Never"
        bd = f"${r.final_bad_debt / 1e6:.2f}M"
        alloc = f"${r.total_allocator_inflow / 1e6:.2f}M"
        if config != 'factual' and factual_bd > 0:
            pct = f"{(1 - r.final_bad_debt / factual_bd) * 100:.1f}%"
        else:
            pct = "—"
        print(f"{label:<28} {bd:>12} {tt:>12} {alloc:>14} {pct:>10}")

    print("=" * 78)
    print(f"\nCalibration target: ~${MARKET.MANUAL_INTERVENTION_MIN:.0f}-min "
          f"factual bad debt should be ≈ $6M (actual Morpho loss).")
    print(f"Manual intervention modelled at t = {MARKET.MANUAL_INTERVENTION_MIN} min "
          f"(Gauntlet).\n")
