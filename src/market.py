"""
market.py — Morpho-style isolated lending market simulator
============================================================

Models the three loss channels observed in the Resolv/Morpho incident:

1. ORGANIC BAD DEBT (~$4,900 actual)
   Pre-existing wstUSR borrower positions whose collateral value at DEX
   price falls below their debt. Under the static oracle, these are never
   liquidated (oracle still says $1.13), so organic bad debt is only
   *recognised* when we mark-to-DEX at the end. Under D1/D2, the oracle
   reprices → LTV breaches → liquidation at DEX price → shortfall.

2. ARB-LOOP EXTRACTION (~$5.95M actual)
   When oracle >> DEX price, arbitrageurs:
     (a) Buy wstUSR on DEX at $0.03
     (b) Deposit in Morpho, valued at $1.13 by oracle
     (c) Borrow USDC up to LLTV × $1.13 = $0.97
     (d) Withdraw USDC — pure profit
   Each cycle extracts ~$0.97 of real USDC per $0.03 of worthless collateral.
   The protocol's loss = borrowed USDC × (1 - collateral_dex_value / borrowed).

3. PUBLIC ALLOCATOR RE-SUPPLY
   When the USDC pool drains (high utilisation), the allocator automatically
   routes USDC from safe vaults. This refills the pool, which the arb loop
   immediately drains again — a positive feedback loop.

CALIBRATION
-----------
The factual scenario is calibrated so that cumulative bad debt at
t = MANUAL_INTERVENTION_MIN (91 min) ≈ $6M. The key calibration knobs:
  - ARB_DRAIN_FRAC, ARB_DRAIN_CAP → drain speed per block
  - ALLOCATOR_INFLOW_PER_STEP → refill speed per block
  - USDC_POOL_INITIAL → starting pool (sets first-drain duration)

After Gauntlet's manual intervention at t=91 min, the factual scenario
halts new borrows and allocator inflows (modelling the actual response).
"""

from __future__ import annotations


import numpy as np
import pandas as pd
from config import MARKET


class MorphoMarketSim:
    """
    Simulates one Morpho isolated lending market with wstUSR collateral.

    Usage
    -----
    >>> market = MorphoMarketSim()
    >>> for i in range(n_steps):
    ...     market.step(oracle[i], dex[i], regime[i], allow_alloc, allow_borrow)
    >>> print(market.bad_debt)
    """

    def __init__(self, params: MARKET.__class__ = MARKET):
        self.p = params

        # ── Generate borrower cohort ──
        rng = np.random.RandomState(params.BORROWER_SEED)

        # LTV distribution: Beta(5,2) × 0.85 → median ~0.60, right-skewed
        ltv_draws = np.clip(
            rng.beta(params.BORROWER_LTV_ALPHA, params.BORROWER_LTV_BETA,
                     params.N_BORROWERS) * params.BORROWER_LTV_CAP,
            params.BORROWER_LTV_FLOOR,
            params.BORROWER_LTV_CAP
        )

        # Position sizes: log-normal, normalised to TOTAL_COLLATERAL_USD
        mean_size = params.TOTAL_COLLATERAL_USD / params.N_BORROWERS
        coll_draws = rng.lognormal(
            np.log(mean_size), params.BORROWER_SIZE_LOG_SIGMA, params.N_BORROWERS
        )
        coll_draws *= params.TOTAL_COLLATERAL_USD / coll_draws.sum()

        self.positions = pd.DataFrame({
            'collateral_usd': coll_draws,
            'ltv': ltv_draws,
            'debt_usd': coll_draws * ltv_draws,
            'liquidated': False,
        })

        # ── Pool state ──
        self.usdc_pool = params.USDC_POOL_INITIAL
        self.bad_debt = 0.0

        # ── History arrays (one entry per step) ──
        self.bad_debt_history: list[float] = []
        self.usdc_pool_history: list[float] = []
        self.allocator_inflows: list[float] = []
        self.arb_borrows: list[float] = []
        self.arb_total_borrowed = 0.0

    def step(self, oracle_price: float, dex_price: float, regime: float,
             allow_allocator: bool = True, allow_new_borrows: bool = True
             ) -> float:
        """
        Execute one simulation step (= one Ethereum block).

        Parameters
        ----------
        oracle_price : float
            wstUSR oracle price this block (USD).
        dex_price : float
            USR DEX spot price this block (USD).
        regime : float
            0.0 = NORMAL, 1.0 = STRESSED.
        allow_allocator : bool
            If False, Public Allocator cannot route capital in.
        allow_new_borrows : bool
            If False, no new borrows (arb loop is halted).

        Returns
        -------
        float
            Cumulative bad debt after this step.
        """
        p = self.p
        static = 1.13  # wstUSR baseline for ratio calculations

        # ── 1. Revalue collateral at oracle price ──
        price_ratio = oracle_price / static
        eff_collateral = self.positions['collateral_usd'] * price_ratio
        # Guard against division by zero
        eff_ltv = np.where(
            eff_collateral > 0,
            self.positions['debt_usd'] / eff_collateral,
            np.inf
        )

        # ── 2. Liquidations (LTV > LLTV) ──
        to_liq = (eff_ltv > p.LLTV) & (~self.positions['liquidated'])
        if to_liq.any():
            for idx in self.positions[to_liq].index:
                debt = self.positions.loc[idx, 'debt_usd']
                # Liquidation proceeds at DEX price, not oracle
                coll_at_dex = self.positions.loc[idx, 'collateral_usd'] * dex_price
                shortfall = max(0.0, debt - coll_at_dex)
                self.bad_debt += shortfall
                self.positions.loc[idx, 'liquidated'] = True

        # ── 3. Arb loop ──
        arb_borrow = 0.0
        arb_ratio = oracle_price / max(dex_price * static, 0.001)

        if (arb_ratio > p.ARB_PROFIT_THRESHOLD
                and allow_new_borrows
                and self.usdc_pool > p.ARB_MIN_POOL):
            # Drain a fraction of the pool, capped
            arb_borrow = min(self.usdc_pool * p.ARB_DRAIN_FRAC, p.ARB_DRAIN_CAP)
            self.usdc_pool -= arb_borrow
            self.arb_total_borrowed += arb_borrow
            # Loss ≈ borrowed amount × (1 - collateral_value / borrowed)
            # Since collateral is nearly worthless, loss ≈ arb_borrow
            loss_frac = max(0.0, 1.0 - dex_price)
            self.bad_debt += arb_borrow * loss_frac

        self.arb_borrows.append(arb_borrow)

        # ── 4. Public Allocator ──
        allocator_inflow = 0.0
        pool_init = max(p.USDC_POOL_INITIAL, 1.0)
        utilisation = 1.0 - (self.usdc_pool / pool_init)

        if (utilisation > p.ALLOCATOR_UTIL_TRIGGER
                and allow_allocator
                and self.usdc_pool < pool_init * p.ALLOCATOR_POOL_TRIGGER_FRAC):
            allocator_inflow = min(
                p.ALLOCATOR_INFLOW_PER_STEP,
                pool_init * p.ALLOCATOR_INFLOW_FRAC
            )
            self.usdc_pool += allocator_inflow

        self.allocator_inflows.append(allocator_inflow)
        self.bad_debt_history.append(self.bad_debt)
        self.usdc_pool_history.append(self.usdc_pool)

        return self.bad_debt
