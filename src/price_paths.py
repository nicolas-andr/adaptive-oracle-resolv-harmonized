"""
price_paths.py — Forensic price & supply reconstruction
=========================================================

Builds the USR DEX price path and totalSupply path from forensic timestamps.

METHODOLOGY
-----------
The DEX price is reconstructed as a piecewise-analytic function fitted to
five observed anchor points:

  t = 0.0 min   →  $1.00   (peg, pre-mint)
  t = 0.4 min   →  $1.00   (Mint #1 fires; price hasn't reacted yet)
  t ~ 2.4 min   →  $0.90   (initial selling pressure)
  t ~10.4 min   →  $0.30   (accelerating crash, arb pressure)
  t  =17.0 min  →  $0.025  (Curve pool, observed)
  t > 17   min  →  $0.03–0.05  (dead-cat bounces, Mint #2 dip)

Between anchors we interpolate with linear / power-law / exponential
functions whose shapes are documented in config.PricePathParams.

WHY THIS IS ACCEPTABLE FOR THE COUNTERFACTUAL
----------------------------------------------
Both D1 and D2 trigger within the first ~1 minute, during Phase 2
(linear decline from $1.00 to $0.90). The exact shape of the later
crash phases affects the *magnitude* of bad debt under the static
oracle but does NOT affect the *trigger time* of the adaptive oracles,
which is the paper's central claim. The sensitivity analysis (Figure 5)
confirms robustness across a wide parameter range.
"""

from __future__ import annotations


import numpy as np
from config import GRID, PRICE_PARAMS as PP, TIMELINE


def build_simulation_time_grid() -> np.ndarray:
    """
    Build the canonical fixed-step simulation grid.

    We intentionally use `arange * dt` instead of `linspace(..., endpoint=True)`
    so the spacing is exactly one Ethereum block (12 seconds) at every step.
    """
    return np.arange(GRID.n_steps, dtype=float) * GRID.dt_minutes


def build_usr_dex_price_path() -> tuple[np.ndarray, np.ndarray]:
    """
    Reconstruct USR DEX price path.

    Returns
    -------
    t : np.ndarray, shape (n_steps,)
        Time in minutes from simulation start (not from Mint #1).
    price : np.ndarray, shape (n_steps,)
        USR spot price in USD.
    """
    n = GRID.n_steps
    t = build_simulation_time_grid()
    price = np.ones(n)

    MINT1 = GRID.MINT1_OFFSET_MIN
    MINT2 = GRID.MINT2_OFFSET_MIN

    for i, ti in enumerate(t):
        if ti <= MINT1:
            # Phase 1: Pre-mint. Peg is stable.
            price[i] = 1.00

        elif ti <= MINT1 + PP.INITIAL_SELL_DURATION_MIN:
            # Phase 2: Initial selling pressure after mint.
            # Linear decline: $1.00 → $(1-DROP) over DURATION minutes.
            frac = (ti - MINT1) / PP.INITIAL_SELL_DURATION_MIN
            price[i] = 1.00 - PP.INITIAL_SELL_DROP * frac

        elif ti <= MINT1 + PP.INITIAL_SELL_DURATION_MIN + PP.ACCEL_CRASH_DURATION_MIN:
            # Phase 3: Accelerating crash (power-law convex decline).
            frac = (ti - MINT1 - PP.INITIAL_SELL_DURATION_MIN) / PP.ACCEL_CRASH_DURATION_MIN
            start_price = 1.00 - PP.INITIAL_SELL_DROP  # $0.90
            price[i] = start_price - PP.ACCEL_CRASH_DROP * frac ** PP.ACCEL_CRASH_EXPONENT

        elif ti <= TIMELINE.USR_BOTTOM_TIME_MIN:
            # Phase 4: Terminal crash (exponential decay to floor).
            phase3_end = MINT1 + PP.INITIAL_SELL_DURATION_MIN + PP.ACCEL_CRASH_DURATION_MIN
            remaining = TIMELINE.USR_BOTTOM_TIME_MIN - phase3_end
            frac = (ti - phase3_end) / max(remaining, 0.01)
            start_price = 1.00 - PP.INITIAL_SELL_DROP - PP.ACCEL_CRASH_DROP  # $0.30
            price[i] = start_price * np.exp(-PP.TERMINAL_DECAY_RATE * frac) + PP.TERMINAL_FLOOR

        elif ti <= MINT2:
            # Phase 5a: Post-crash oscillation before Mint #2.
            price[i] = PP.POST_CRASH_CENTER + PP.POST_CRASH_AMPLITUDE * np.sin(
                PP.POST_CRASH_FREQ * (ti - TIMELINE.USR_BOTTOM_TIME_MIN)
            )

        elif ti <= MINT2 + PP.MINT2_DIP_DURATION_MIN:
            # Phase 5b: Temporary dip from Mint #2.
            price[i] = PP.MINT2_DIP_PRICE

        else:
            # Phase 5c: Post-Mint-#2 stabilisation.
            price[i] = PP.POST_CRASH_CENTER - 0.005 + PP.POST_CRASH_AMPLITUDE * 0.5 * np.sin(
                0.05 * (ti - MINT2 - PP.MINT2_DIP_DURATION_MIN)
            )

    price = np.maximum(price, PP.PRICE_FLOOR)
    return t, price


def build_usr_supply_path() -> tuple[np.ndarray, np.ndarray]:
    """
    Reconstruct USR totalSupply path.

    Pre-exploit:  102M USR
    After Mint #1: 152M USR  (t = MINT1_OFFSET_MIN)
    After Mint #2: 182M USR  (t = MINT2_OFFSET_MIN)

    Returns
    -------
    t : np.ndarray, shape (n_steps,)
    supply : np.ndarray, shape (n_steps,)
        USR total supply in tokens.
    """
    n = GRID.n_steps
    t = build_simulation_time_grid()
    supply = np.full(n, TIMELINE.PRE_EXPLOIT_SUPPLY_USR)

    MINT1 = GRID.MINT1_OFFSET_MIN
    MINT2 = GRID.MINT2_OFFSET_MIN

    for i, ti in enumerate(t):
        if ti < MINT1:
            supply[i] = TIMELINE.PRE_EXPLOIT_SUPPLY_USR
        elif ti < MINT2:
            supply[i] = TIMELINE.PRE_EXPLOIT_SUPPLY_USR + TIMELINE.MINT1_AMOUNT_USR
        else:
            supply[i] = (TIMELINE.PRE_EXPLOIT_SUPPLY_USR
                         + TIMELINE.MINT1_AMOUNT_USR
                         + TIMELINE.MINT2_AMOUNT_USR)

    return t, supply
