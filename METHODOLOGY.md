# Harmonized Methodology

This note consolidates the executable methodology in this repo with the higher-level framing that appeared in an alternate local draft.

The goal is simple: keep one canonical repo while preserving the genuinely useful refinements from the alternate draft and discarding the parts that were just older snapshots.

## Canonical source of truth

- The runnable simulation, calibration, and reproducibility workflow in this repo are authoritative.
- Canonical outputs come from [`reproducibility_manifest.json`](reproducibility_manifest.json).
- Older draft numbers such as `$5.86M`, `$0.84M`, `1.0 min`, and the `$8M` initial USDC pool are superseded by the fixed-step calibrated run in this repo.

## What the alternate draft improved

The alternate draft did not contain newer code or a newer runnable methodology. Its main value was conceptual:

- it made the distinction between **reference value** and **realizable liquidation value** much clearer
- it explained the Resolv incident as a **three-step contagion sequence**:
  1. the oracle stayed stale
  2. the arb loop extracted USDC
  3. the allocator refilled the pool
- it gave a cleaner intuition for why the oracle should **smooth the stressed price** rather than snap directly to the DEX
- it emphasized the need to separate the signal used for **detection** from the value used for **reporting**, avoiding EMA dampening
- it added a more explicit implementation interpretation around Morpho adapters, allocator gating, and optional reserve checks

## Harmonized methodology

### 1. What the oracle is trying to price

The simulation treats a wrapped or synthetic collateral asset as having two relevant values:

- **Reference value**: what the collateral should be worth if its wrapper or backing mechanism is functioning as intended.
- **Realizable value**: what a liquidator can actually sell the collateral for on available DEX liquidity.

Under normal conditions these values are close. Under stress they can diverge sharply, and it is that divergence that creates hidden insolvency and stale-oracle extraction.

### 2. Why Resolv created bad debt

The harmonized view of the Resolv incident is:

1. the wstUSR oracle stayed at `$1.13` while market value collapsed
2. the oracle/DEX gap made deposit-and-borrow arbitrage profitable
3. the Public Allocator interpreted pool depletion as healthy demand and kept routing fresh USDC into the impaired market

This repo's counterfactual is designed to break that chain early, not to prevent the upstream mint exploit itself.

### 3. Oracle state machine

The executable model in this repo remains the same:

- `factual`: static oracle at `$1.13`, with manual intervention at `t = 91` minutes
- `D1`: DEX-deviation trigger, followed by EMA convergence
- `D2`: supply-velocity trigger, followed by the same EMA convergence

Once `D1` or `D2` fires, three concurrent actions are modeled:

1. the oracle enters `STRESSED`
2. allocator inflows are severed
3. new borrows are halted

### 4. Why smoothing is still the right stressed-price mechanism

The alternate draft's intuition is compatible with the runnable model:

- snapping directly from the reference value to the DEX value would cluster liquidations into one shock
- EMA convergence still reprices toward realizable value, but does so in a way that better reflects how a defensive oracle would respond in practice
- the detector should look at the **raw dislocation signal**, while the stressed oracle reports the **smoothed value**

That separation is preserved in the code.

### 5. Trigger interpretation

The current calibrated timeline is:

- `D2` fires in the mint block, at `t = 0.4` min on the simulation clock
- `D1` fires at `t = 1.2` min on the simulation clock

Because the simulation intentionally starts `0.4` minutes before Mint #1, the practical interpretation is:

- `D2` reacts immediately to the exploit's supply anomaly
- `D1` reacts within the first minute after Mint #1

This resolves the apparent mismatch between older prose that said "1.0 min" or "24--60 seconds" and the current fixed-step calibrated run.

### 6. Integration interpretation

The alternate draft's Chainlink-oriented language is best read as an integration mapping, not as something the simulation directly depends on.

The harmonized interpretation is:

- the code models an **oracle adapter surface** compatible with Morpho-style markets
- allocator severance is a first-class part of the defensive response
- reserve checks and product mappings such as PoR, Data Streams, Automation, or SVR are **conceptual extensions**, not required to reproduce the counterfactual figures in this repo

### 7. Canonical current outputs

The current calibrated run in this repo produces:

- factual: `$5.8724M` bad debt
- `D1`: `$0.8314M`
- `D2`: `$0.8314M`
- prevention: `85.8%`

Those numbers are the ones to cite when discussing the executable analysis in this repo.

## Simulation details

### 1. What the executable model includes

The runnable simulation models a single Morpho-style isolated lending market with:

- **Collateral asset**: wstUSR, using a factual oracle value of `$1.13`
- **Borrow asset**: USDC
- **50 pre-existing borrower positions** with heterogeneous LTVs
- **An arb-loop agent** that exploits oracle-DEX divergence
- **A Public Allocator agent** that re-supplies USDC when utilization is high
- **Three oracle configurations**: `factual`, `D1`, and `D2`

It does **not** model:

- multiple Morpho markets or cross-market contagion
- individual arbitrage transactions, gas auctions, or MEV competition
- full Curve AMM state dynamics
- positions opened during the exploit itself

The purpose is to isolate the lending-market contagion channel created by a stale collateral oracle.

### 2. Loss channels in the simulation

The code separates three mechanisms:

#### Organic bad debt

Pre-existing borrowers can become genuinely undercollateralized once the oracle reprices collateral downward. Under `D1` and `D2`, these positions are liquidated against the stressed DEX-implied value, producing the residual `~$0.83M` shortfall. That is the "honest" insolvency that the adaptive oracle surfaces.

Under the factual static oracle, that insolvency remains hidden because the oracle never reprices before manual intervention.

#### Arb-loop extraction

When the oracle is sufficiently above realizable DEX value, the model allows a reduced-form arbitrage loop that repeatedly borrows USDC against overstated collateral. In the code this channel is active only while:

- the oracle/DEX dislocation is above the profit threshold
- new borrows remain allowed
- enough pool liquidity remains available

Under `D1` and `D2`, the trigger disables new borrows and cuts off this channel early.

#### Allocator re-supply

The Public Allocator is modeled as adding fresh USDC when utilization is high and the market appears depleted. In the factual path this creates the reinforcing loop observed in the incident:

1. arbs drain the pool
2. allocator capital refills it
3. arbs extract again

Under `D1` and `D2`, allocator inflows are severed at trigger time.

### 3. Calibration and price-path design

The factual path is calibrated to land near the observed Morpho loss:

- factual bad debt: `$5.8724M`
- empirical target: `~$6M`
- manual intervention: `t = 91 min`

The main calibration levers are the initial USDC pool, arb drain speed, allocator refill speed, and intervention time. The discrete `12`-second block grid means the simulation is intentionally approximate rather than tuned to hit `$6.00M` exactly.

The USR DEX path is piecewise analytic, with a flat pre-mint period, an early linear selloff, an accelerating crash, a terminal collapse, and a low-price post-crash regime. The most important point is that both `D1` and `D2` trigger during the early phase of the crash, so the counterfactual result is driven far more by early detection than by the exact late-crash shape.

### 4. Claims, assumptions, and limits

The strongest code-backed claim in this repo is narrow:

- under either `D1` or `D2`, the oracle-driven arbitrage extraction channel is severed within the first minute of the exploit timeline

The exact dollar values remain calibration-dependent, but the directional result is robust across reasonable parameter changes because:

- the supply spike is far above any plausible detection threshold
- the DEX dislocation crosses the `D1` threshold quickly
- both triggers act before the long tail of allocator-assisted extraction dominates losses

Important limits remain:

- the price path is stylized rather than a tick-level replay
- arbitrage is modeled as an aggregate drain rate rather than transaction-by-transaction behavior
- allocator routing is reduced-form
- residual organic bad debt depends on the modeled borrower cohort
- the analysis is a downstream lending-defense counterfactual, not a claim that the oracle prevents the upstream mint exploit

## What was intentionally not merged

- The alternate repo's looser dependency setup was not adopted.
- Older calibration text based on the pre-fix time grid was not preserved.
- Conceptual product mappings were not turned into code claims unless they are explicitly modeled here.

## Recommended reading order

1. [`README.md`](README.md) for the rerun workflow
2. [`METHODOLOGY.md`](METHODOLOGY.md) for the consolidated narrative and simulation assumptions
3. [`reproducibility_manifest.json`](reproducibility_manifest.json) for canonical outputs
