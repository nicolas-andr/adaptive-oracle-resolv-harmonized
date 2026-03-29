"""
sensitivity.py — Threshold sweep & Monte Carlo
=================================================

Two analyses that test robustness of the counterfactual claim:

1. SENSITIVITY HEATMAP (Figure 5)
   Sweeps D1's (threshold, persistence) space and estimates the bad debt
   for each combination. Uses a reduced-form model:
     bad_debt ≈ (trigger_time / 91) × $6M
   This is valid because bad debt is roughly linear in exposure time
   (the arb loop runs at a nearly constant drain rate once profitable).

2. MONTE CARLO (Figure 6)
   Simulates 200 randomised depeg scenarios with varying severity and
   speed to demonstrate that the adaptive oracle compresses bad debt
   across the full distribution, not just for Resolv-specific parameters.
   Uses a reduced-form bad-debt estimator for computational efficiency.
"""

from __future__ import annotations


import numpy as np
from config import (
    GRID, ORACLE, SENSITIVITY as SENS, MonteCarloParams as MCP,
    MC, TIMELINE
)
from src.price_paths import build_usr_dex_price_path


# ═══════════════════════════════════════════════════════════════════════════════
# SENSITIVITY HEATMAP
# ═══════════════════════════════════════════════════════════════════════════════

def run_sensitivity_sweep() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Sweep D1 deviation threshold × block persistence requirement.

    For each (threshold, persistence) pair, we find the trigger time on
    the Resolv price path and estimate bad debt as:

        bad_debt ≈ max(FLOOR, trigger_time / 91 × $6M)

    Returns
    -------
    thresholds : np.ndarray, shape (n_thresholds,)
        Deviation thresholds in absolute fraction (e.g. 0.02 = 2%).
    persistence_blocks : np.ndarray, shape (n_persistence,)
        Number of consecutive blocks required.
    bad_debt_grid : np.ndarray, shape (n_thresholds, n_persistence)
        Estimated bad debt in USD for each (threshold, persistence) pair.
    """
    thresholds = np.arange(SENS.THRESHOLD_START, SENS.THRESHOLD_STOP + 1e-9,
                           SENS.THRESHOLD_STEP)
    persistence_range = np.arange(SENS.PERSISTENCE_START, SENS.PERSISTENCE_STOP + 1)

    # Build the price path once
    t, dex = build_usr_dex_price_path()
    static = ORACLE.WSTUSR_STATIC_PRICE

    bad_debt_grid = np.zeros((len(thresholds), len(persistence_range)))

    for i, thresh in enumerate(thresholds):
        for j, n_blocks in enumerate(persistence_range):
            # Find trigger time for this (threshold, persistence) combo
            consecutive = 0
            trigger_time_min = GRID.HORIZON_MINUTES  # Default: never triggered

            for k in range(len(t)):
                implied = dex[k] * static
                dev = abs(static - implied) / static
                if dev > thresh:
                    consecutive += 1
                    if consecutive >= n_blocks:
                        trigger_time_min = t[k]
                        break
                else:
                    consecutive = 0

            # Estimate bad debt (linear in exposure time, with floor)
            if trigger_time_min <= 2.0:
                # Triggered before arb loop becomes profitable
                bd = SENS.FAST_TRIGGER_FLOOR_USD
            else:
                bd = min(
                    SENS.ACTUAL_BAD_DEBT_USD,
                    trigger_time_min / SENS.ACTUAL_RESPONSE_TIME_MIN * SENS.ACTUAL_BAD_DEBT_USD
                )
            bad_debt_grid[i, j] = bd

    return thresholds, persistence_range, bad_debt_grid


# ═══════════════════════════════════════════════════════════════════════════════
# MONTE CARLO
# ═══════════════════════════════════════════════════════════════════════════════

def run_monte_carlo() -> dict[str, np.ndarray]:
    """
    Monte Carlo across randomised depeg scenarios.

    Each run draws:
      - depeg_severity ∈ [0.05, 0.60]  (fraction of price lost)
      - depeg_speed ∈ [5, 120] minutes  (time to reach trough)
      - supply_shock ∈ {True, False}    (30% probability)

    For each run, we estimate bad debt under three configs using
    a reduced-form model:

    Factual:
        bad_debt ≈ min(exposure_time, 91) × severity × drain_rate
        (exposure capped at 91 min = Gauntlet intervention)

    D1:
        Trigger time = first block where price deviation > 2%.
        bad_debt ≈ trigger_time × severity × (drain_rate / 20)

    D2:
        If supply shock: trigger in same block → near-zero BD.
        If no supply shock: falls back to D1-like with 70% reduction.

    Returns
    -------
    dict with keys 'factual', 'D1', 'D2', 'severities', 'speeds'
        Each value is np.ndarray of shape (N_RUNS,).
    """
    rng = np.random.RandomState(MC.SEED)

    severities = rng.uniform(*MC.DEPEG_SEVERITY_RANGE, MC.N_RUNS)
    speeds = rng.uniform(*MC.DEPEG_SPEED_RANGE_MIN, MC.N_RUNS)
    has_supply_shock = rng.random(MC.N_RUNS) < MC.SUPPLY_SHOCK_PROB

    results = {
        'factual': np.zeros(MC.N_RUNS),
        'D1': np.zeros(MC.N_RUNS),
        'D2': np.zeros(MC.N_RUNS),
        'severities': severities,
        'speeds': speeds,
    }

    for run in range(MC.N_RUNS):
        sev = severities[run]
        spd = speeds[run]
        shock = has_supply_shock[run]

        # Build per-run price path
        t_mc = np.arange(MC.N_STEPS, dtype=float) * (MC.HORIZON_MINUTES / MC.N_STEPS)
        price = np.ones(MC.N_STEPS)
        for k in range(MC.N_STEPS):
            if t_mc[k] <= 0:
                price[k] = 1.0
            elif t_mc[k] <= spd:
                frac = t_mc[k] / spd
                price[k] = 1.0 - sev * frac ** 1.2
            else:
                price[k] = 1.0 - sev + 0.02 * rng.randn()
            price[k] = max(price[k], 0.01)

        # ── Factual ──
        # Exposure capped at Gauntlet intervention time
        exposure = min(spd + 30, TIMELINE.GAUNTLET_INTERVENE_MIN)
        results['factual'][run] = exposure * sev * MC.FACTUAL_DRAIN_RATE_PER_MIN_PER_SEVERITY

        # ── D1: find trigger time ──
        d1_trigger = None
        for k in range(1, MC.N_STEPS):
            dev = abs(1.0 - price[k])
            if dev > ORACLE.D1_DEVIATION_THRESHOLD:
                d1_trigger = t_mc[k]
                break
        trigger_t = d1_trigger if d1_trigger is not None else MC.HORIZON_MINUTES
        results['D1'][run] = max(0, trigger_t * sev * MC.D1_DRAIN_RATE_PER_MIN_PER_SEVERITY)

        # ── D2: supply-shock or fallback ──
        if shock:
            # Supply shock → trigger in same block → near-zero exposure
            results['D2'][run] = sev * MC.D2_DRAIN_RATE_WHEN_TRIGGERED
        else:
            # No supply shock → falls back to D1-like but with some benefit
            # from other safety layers
            results['D2'][run] = results['factual'][run] * MC.D2_FALLBACK_REDUCTION

    return results
