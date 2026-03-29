# Simulation Methodology

This document explains the design decisions, assumptions, and limitations of the counterfactual simulation in detail. It is intended for reviewers and researchers who want to understand exactly what the code does and does not claim.

For a consolidated methodology note that also captures the clearer conceptual framing from the alternate local draft, see [`METHODOLOGY_HARMONIZED.md`](METHODOLOGY_HARMONIZED.md). This file remains the code-facing simulation reference.

---

## 1. What We Simulate

We model a single Morpho-style isolated lending market with:

- **Collateral asset**: wstUSR (wrapped staked USR), oracle price $1.13
- **Borrow asset**: USDC
- **50 pre-existing borrower positions** with heterogeneous LTVs
- **An arb-loop agent** that exploits oracle–DEX divergence
- **A Public Allocator agent** that re-supplies USDC when utilisation is high
- **Three oracle configurations** (factual / D₁ / D₂)

We do **not** simulate:
- Multiple Morpho markets or cross-market contagion (only one market)
- Individual arb transactions (we model aggregate drain rate)
- Curve pool AMM dynamics (we use a reconstructed price path)
- Gas price competition or MEV (not relevant to the claim)
- Positions created during the exploit (only pre-existing)

## 2. Loss Channels

### 2.1 Organic bad debt

Pre-existing borrower positions have collateral valued at $1.13 (wstUSR) and debt in USDC. When the oracle reprices collateral downward (D₁/D₂), some positions breach the LLTV of 0.86 and are liquidated. The liquidation proceeds are at the DEX price, so the shortfall is:

    shortfall = debt - (collateral_quantity × DEX_price)

Under the **static oracle** (factual), no repricing occurs, so no liquidations are triggered. The organic loss is "hidden" as latent insolvency.

Under **D₁/D₂**, the oracle reprices within the first minute. Positions breach LLTV and are liquidated at the (low) DEX price, producing ~$0.83M in genuine shortfall. This is the "honest loss" that the adaptive oracle surfaces.

### 2.2 Arb-loop extraction

When `oracle_price / (DEX_price × 1.13) > 2.0` (the arb profit threshold), the simulation models an aggregate arb drain:

1. Arb borrows `min(2.5% of pool, $15K)` USDC per block
2. Pool shrinks
3. Bad debt increases by `arb_borrow × (1 - DEX_price)` (since collateral is nearly worthless)

This runs every block as long as:
- The arb ratio exceeds the threshold
- `allow_new_borrows` is True
- The pool has more than $5K remaining

Under D₁/D₂, `allow_new_borrows` is set to False at trigger time, halting the arb loop.

### 2.3 Allocator re-supply

When pool utilisation exceeds 80% and the pool is below 20% of its initial value, the allocator injects $50K per block. Under D₁/D₂, `allow_allocator` is set to False at trigger time.

In the factual scenario, the allocator runs until Gauntlet's manual intervention at t=91 min. This creates a saw-tooth pattern: arb drains the pool → allocator refills → arb drains again.

## 3. Calibration

### Target: $5.87M factual bad debt ≈ $6M actual

The simulation's factual bad debt ($5.87M) closely matches the empirical Morpho loss (~$6M). The calibration knobs are:

| Knob | Effect | Setting |
|---|---|---|
| `USDC_POOL_INITIAL` | Sets first-drain duration | $3M |
| `ARB_DRAIN_FRAC` / `ARB_DRAIN_CAP` | Drain speed per block | 2.5% / $15K |
| `ALLOCATOR_INFLOW_PER_STEP` | Refill speed | $50K |
| `MANUAL_INTERVENTION_MIN` | When losses stop | 91 min |

The product of these parameters yields ~$6M total extraction over 91 minutes. The sensitivity to each parameter is monotonic and intuitive:
- Higher drain rate → faster loss accumulation
- Higher allocator inflow → more total loss (more refill cycles)
- Earlier intervention → less total loss

### Why not $6.00M exactly?

The simulation uses discrete blocks (12-second steps), so the cumulative drain is jagged rather than smooth. The $5.87M result is within 2.2% of the $6M target, which is well within the uncertainty of the forensic estimate itself.

## 4. Price Path Reconstruction

The USR DEX price path is a **piecewise-analytic function** with five phases:

```
Phase 1 (Pre-mint):       t ∈ [0, 0.4]      → $1.00 (flat)
Phase 2 (Initial sell):   t ∈ (0.4, 2.4]     → linear $1.00 → $0.90
Phase 3 (Accel crash):    t ∈ (2.4, 10.4]    → power-law $0.90 → $0.30
Phase 4 (Terminal crash): t ∈ (10.4, 17.0]   → exp-decay → $0.025
Phase 5 (Post-crash):     t ∈ (17.0, 120.0]  → oscillation $0.03–$0.05
```

**Critical insight**: The counterfactual results depend almost entirely on Phase 2. Both D₁ (2% deviation for 2 blocks) and D₂ (5% supply spike) trigger during Phase 2, when the price has dropped only ~5–10%. The exact shape of Phases 3–5 affects the factual bad-debt magnitude but NOT the trigger times or the adaptive-oracle outcomes. The sensitivity heatmap (Figure 5) demonstrates this robustness.

## 5. What the Simulation Claims

**Strong claim**: Under either D₁ or D₂, the arb-loop extraction channel that produced the vast majority of Morpho's losses would have been completely severed within the first minute. This is robust to reasonable parameter variation because:
1. The supply spike (49% in one block) is orders of magnitude above any plausible false-positive threshold
2. The DEX deviation exceeds 2% within ~1 minute of the mint
3. Both signals are far above threshold, so small calibration changes don't move the result

**Weaker claim**: The exact dollar amounts ($5.87M factual, $0.83M counterfactual) depend on calibration parameters. The *ratio* (85.8% prevention) is robust; the absolute numbers have ±20% uncertainty from the forensic estimates.

**Not claimed**: That the adaptive oracle would prevent the Resolv exploit itself. The oracle is a downstream defense for lending markets; it cannot stop upstream minting exploits. What it prevents is the *secondary contagion* through stale-oracle arbitrage.

## 6. Assumptions and Limitations

| Assumption | Impact if wrong | Mitigation |
|---|---|---|
| Arb loop starts when oracle/DEX > 2× | If arbs are more aggressive, losses are higher; trigger times unchanged | Threshold is conservative (arbs may act at 1.5×) |
| Allocator routes $50K/block | Higher rate → higher factual loss, same counterfactual | Sensitivity is monotonic |
| 50 pre-existing borrowers | More/fewer → different organic BD magnitude | Only affects residual, not arb channel |
| Price path is stylised | Exact crash shape affects factual magnitude | Trigger times in Phase 2 are robust |
| D₂ lookback = 1 block | Longer lookback → slightly later trigger | Even 5-block lookback triggers < 1 min |
| Manual intervention at 91 min | Earlier/later changes factual BD | Documented in Gauntlet post-mortem |
