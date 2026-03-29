"""
oracle.py — Dual-regime adaptive oracle
=========================================

Implements three oracle configurations:

Factual
    Static hardcoded price at $1.13 (wstUSR). This is what Morpho actually
    used during the exploit. The oracle never reprices regardless of DEX
    or supply data.

D1 (DEX-deviation trigger)
    Monitors δ(t) = |oracle - DEX_implied_wstusr| / oracle.
    When δ > D1_DEVIATION_THRESHOLD for D1_PERSISTENCE_BLOCKS consecutive
    blocks, the oracle enters STRESSED and begins EMA convergence toward
    the DEX-implied price.

D2 (Supply-velocity trigger)
    Monitors ΔS/S = (supply[t] - supply[t-k]) / supply[t-k].
    When ΔS/S > D2_SUPPLY_THRESHOLD in a D2_LOOKBACK_BLOCKS window,
    the oracle enters STRESSED immediately (zero latency for mint detection).
    EMA convergence then follows the same logic as D1.

EMA CONVERGENCE (shared)
    Once STRESSED, the oracle price converges toward the DEX-implied
    wstUSR price via:

        ema[t] = α × target[t] + (1 - α) × ema[t-1]

    where α = 1 - exp(-ln2 × Δt / h) and h is the half-life.

    The half-life is adaptive to deviation severity:
        δ < SEVERE_DEVIATION       → h = HALFLIFE_MODERATE   (gentle)
        SEVERE ≤ δ < CATASTROPHIC  → h = HALFLIFE_SEVERE     (fast)
        δ ≥ CATASTROPHIC           → h = HALFLIFE_CATASTROPHIC (near-instant)

    This implements the "catastrophic-deviation bypass": for a 97% depeg,
    h ≈ 30 seconds, so the oracle reprices in 1–2 blocks.
"""

from __future__ import annotations


import numpy as np
from config import ORACLE, GRID


def _adaptive_halflife(deviation: float) -> float:
    """
    Return EMA half-life in minutes, adaptive to deviation severity.

    Parameters
    ----------
    deviation : float
        Absolute fractional deviation |oracle - target| / oracle.

    Returns
    -------
    float
        Half-life in minutes.
    """
    if deviation >= ORACLE.CATASTROPHIC_DEVIATION:
        return ORACLE.HALFLIFE_CATASTROPHIC_MIN
    elif deviation >= ORACLE.SEVERE_DEVIATION:
        return ORACLE.HALFLIFE_SEVERE_MIN
    else:
        return ORACLE.HALFLIFE_MODERATE_MIN


def _ema_alpha(halflife_min: float) -> float:
    """
    Compute EMA blending coefficient α from half-life.

    α = 1 - exp(-ln2 × Δt / h)

    where Δt = block time in minutes.
    """
    dt = GRID.dt_minutes
    if halflife_min <= 0:
        return 1.0  # Instant convergence
    return 1.0 - np.exp(-np.log(2) * dt / halflife_min)


def _apply_ema_from(oracle: np.ndarray, dex_price: np.ndarray,
                    regime: np.ndarray, start_idx: int) -> None:
    """
    Apply EMA convergence in-place from start_idx to end of arrays.

    The oracle converges toward dex_price[j] × WSTUSR_STATIC_PRICE
    (the DEX-implied wstUSR value), with adaptive half-life.
    """
    static = ORACLE.WSTUSR_STATIC_PRICE

    for j in range(start_idx, len(oracle)):
        regime[j] = 1.0
        target = dex_price[j] * static
        deviation = abs(static - target) / static
        h = _adaptive_halflife(deviation)
        alpha = _ema_alpha(h)

        if j == start_idx:
            # First STRESSED block: start from the static value
            oracle[j] = static
        else:
            oracle[j] = alpha * target + (1.0 - alpha) * oracle[j - 1]


def build_oracle_path(t: np.ndarray, dex_price: np.ndarray,
                      supply: np.ndarray, config: str
                      ) -> tuple[np.ndarray, np.ndarray, float | None]:
    """
    Build the wstUSR oracle price path for a given configuration.

    Parameters
    ----------
    t : np.ndarray
        Time array in minutes.
    dex_price : np.ndarray
        USR DEX spot price at each time step.
    supply : np.ndarray
        USR totalSupply at each time step.
    config : str
        One of 'factual', 'D1', 'D2'.

    Returns
    -------
    oracle : np.ndarray
        wstUSR oracle price at each step.
    regime : np.ndarray
        0.0 = NORMAL, 1.0 = STRESSED at each step.
    trigger_time : float or None
        Time in minutes when STRESSED was activated, or None.
    """
    n = len(t)
    static = ORACLE.WSTUSR_STATIC_PRICE
    oracle = np.full(n, static)
    regime = np.zeros(n)

    # ── Factual: never reprices ──
    if config == 'factual':
        return oracle, regime, None

    # ── D1: DEX-deviation trigger ──
    elif config == 'D1':
        consecutive = 0
        for i in range(n):
            implied_wstusr = dex_price[i] * static
            deviation = abs(static - implied_wstusr) / static

            if deviation > ORACLE.D1_DEVIATION_THRESHOLD:
                consecutive += 1
                if consecutive >= ORACLE.D1_PERSISTENCE_BLOCKS:
                    _apply_ema_from(oracle, dex_price, regime, i)
                    return oracle, regime, t[i]
            else:
                consecutive = 0

        return oracle, regime, None  # Never triggered

    # ── D2: Supply-velocity trigger ──
    elif config == 'D2':
        k = ORACLE.D2_LOOKBACK_BLOCKS
        for i in range(k, n):
            prev_supply = supply[i - k]
            if prev_supply > 0:
                velocity = (supply[i] - prev_supply) / prev_supply
            else:
                velocity = 0.0

            if velocity > ORACLE.D2_SUPPLY_THRESHOLD:
                _apply_ema_from(oracle, dex_price, regime, i)
                return oracle, regime, t[i]

        return oracle, regime, None  # Never triggered

    else:
        raise ValueError(f"Unknown oracle config: {config!r}")
