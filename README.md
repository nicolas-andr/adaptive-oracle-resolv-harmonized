# Adaptive Oracle: Resolv USR Counterfactual Simulation

**Paper**: *Adaptive Oracle Pricing for Wrapped Assets in DeFi Lending: A Dual-Regime Design with Empirical Validation from the Resolv USR Exploit*

This repository contains the simulation code, parameter configuration, and figure-generation pipeline for the Resolv USR case study (Sections 7–9 of the paper). The code reconstructs the March 22, 2026 exploit timeline, simulates a Morpho-style lending market under three oracle configurations, and produces all six publication-quality figures.

For the consolidated methodology across both local drafts, start with [`METHODOLOGY_HARMONIZED.md`](METHODOLOGY_HARMONIZED.md). It keeps this repo's reproducible calibration as the source of truth while folding in the clearer conceptual framing from the alternate draft.

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <this-repo>
cd resolv-counterfactual

# 2. Create the pinned environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the locked dependencies
pip install -r requirements-lock.txt

# 4. Reproduce the full analysis and verify every tracked artifact
python run.py --csv --verify-manifest

# 5. Figures and CSVs are saved under ./figures and ./data
ls figures/
ls data/

# Optional: one-command workflow
make reproduce

# Optional: skip Monte Carlo for faster iteration
python run.py --no-mc

# Optional: write outputs somewhere else
python run.py --csv --output-root /tmp/resolv-run
```

**Expected runtime**: ~7 seconds on a modern laptop. No GPU, archive node, or external API required.

---

## What This Simulates

On March 22, 2026, an attacker compromised Resolv Labs' AWS KMS environment, stole the `SERVICE_ROLE` private key, and minted **80 million unbacked USR** stablecoins (50M at 02:21 UTC, 30M at 03:41 UTC). USR crashed 97.5% to $0.025 in 17 minutes. Morpho's wstUSR oracle remained hardcoded at $1.13, enabling a deterministic arbitrage loop that generated **~$6M in Morpho bad debt** over 90 minutes before Gauntlet manually intervened. The Public Allocator amplified losses by routing fresh USDC from safe vaults into the drained USR vaults.

We simulate three oracle configurations:

| Config | Trigger | Mechanism | Trigger Time |
|---|---|---|---|
| **Factual** | None (static $1.13), manual halt at 91 min | What actually happened | 91 min (manual) |
| **D₁** | DEX-deviation: δ > 2% for 2 blocks (~24s) | Detects price crash on DEX | ~1.2 min |
| **D₂** | Supply-velocity: ΔS/S > 5% in 1 block (~12s) | Detects unauthorized minting | ~0.4 min |

When either D₁ or D₂ triggers, three concurrent actions fire:
1. Oracle enters `STRESSED` → EMA convergence toward DEX price
2. Public Allocator is severed from affected vaults
3. New borrows against the affected collateral are halted

### Key Results

| Config | Bad Debt | Prevention | What It Means |
|---|---|---|---|
| Factual | **$5.87M** | — | Arb-loop extraction + allocator re-supply |
| D₁ | **$0.83M** | 85.8% total, 100% of arb channel | Residual = honest repricing of impaired positions |
| D₂ | **$0.83M** | 85.8% total, 100% of arb channel | Same residual (triggers faster, same outcome) |

The $0.83M residual under D₁/D₂ is **unavoidable** — it is the genuine liquidation shortfall from pre-existing positions whose collateral became worthless. The adaptive oracle does not prevent this loss; it *surfaces it honestly* rather than hiding it as latent insolvency (which is exactly what the static oracle does). The entire arb-loop extraction channel ($5.04M) is prevented.

---

## Calibration Against Actual Losses

The simulation is calibrated to reproduce the empirical Morpho outcome:

| Metric | Actual (forensic) | Simulated (factual) | Match |
|---|---|---|---|
| Total Morpho bad debt | ~$6.0M | $5.87M | ✓ (97.9%) |
| Organic bad debt pre-automation | ~$4,900 | ~$0 (static oracle hides it) | ✓ (consistent) |
| Manual intervention time | ~91 min (Gauntlet) | 91 min (hard cutoff) | ✓ (by design) |
| Loss channel | Arb loop + allocator | Arb loop + allocator | ✓ |

**How the calibration works**: The factual scenario models Gauntlet's manual intervention as a hard cutoff at t=91 min — after this point, new borrows and allocator inflows are halted. The arb drain rate and allocator refill rate are set so that cumulative extraction reaches ~$6M by minute 91. See `config.py`, Section 5 for exact parameter values and justifications.

---

## Repository Structure

```
resolv-counterfactual/
├── .python-version             # Canonical Python version for pyenv/uv users
├── Makefile                    # `make reproduce` / `make verify`
├── METHODOLOGY_HARMONIZED.md   # Consolidated methodology across local drafts
├── README.md                   # This file
├── requirements.txt            # Direct dependencies
├── requirements-lock.txt       # Exact dependency set for archival reruns
├── reproducibility_manifest.json # Canonical SHA-256 hashes for full-run artifacts
├── run.py                      # Entry point: runs everything
├── config.py                   # ALL parameters in one place (documented)
├── src/
│   ├── __init__.py
│   ├── price_paths.py          # Forensic price & supply reconstruction
│   ├── oracle.py               # Dual-regime oracle logic (factual/D1/D2)
│   ├── market.py               # Morpho market simulator
│   ├── simulation.py           # Orchestrator: runs all configs
│   ├── sensitivity.py          # Threshold sweep & Monte Carlo
│   ├── figures.py              # All figure generation
│   └── reproducibility.py      # Artifact hashing + manifest verification
├── figures/                    # Output: PNGs (generated by run.py)
├── data/                       # Output: CSVs (generated by run.py --csv)
└── tests/
    ├── test_artifact_manifest.py # Full artifact-hash verification
    └── test_determinism.py     # Numerical determinism smoke test
```

---

## Parameter Reference

All tunable parameters live in [`config.py`](config.py). The file is organised into eight sections, each documented with justifications and sources. Below is a summary of the most important knobs.

If you want the narrative version of why these design choices exist, see [`METHODOLOGY_HARMONIZED.md`](METHODOLOGY_HARMONIZED.md) first and then come back here for the concrete simulation assumptions.

### On-Chain Forensic Constants (Section 1)

These are observed facts, not tunable. They anchor the simulation to reality.

| Parameter | Value | Source |
|---|---|---|
| Mint #1 block | 24,710,031 | Tx `0xfe37f2...3743` |
| Mint #1 amount | 50,000,000 USR | `completeSwap(_targetAmount)` |
| Mint #2 block | 24,710,428 | Tx `0x41b6b9...f18f` |
| Pre-exploit supply | 102,000,000 USR | `totalSupply()` at block 24,710,030 |
| USR floor price | $0.025 | Curve pool at ~02:38 UTC |
| Steakhouse exit time | 41 min after Mint #1 | Steakhouse blog post |
| Steakhouse detection | 1.61% deviation | Steakhouse blog post |
| Gauntlet intervention | 91 min after Mint #1 | Post-mortem reports |
| Actual Morpho bad debt | ~$6,000,000 | Chainalysis, Nexus Mutual |
| Organic bad debt | ~$4,900 | CleanSky, Binance post-mortem |
| wstUSR oracle price | $1.13 (hardcoded) | Morpho market state |

### Oracle Parameters (Section 4)

| Parameter | Value | Justification |
|---|---|---|
| D1 deviation threshold | 2% | Just above Steakhouse's 1.61% detection |
| D1 persistence | 2 blocks (~24s) | Filters single-block noise |
| D2 supply threshold | 5% | No stablecoin grows 5%/block organically |
| D2 lookback | 1 block | Single-block detection for max speed |
| EMA half-life (catastrophic, δ>50%) | 0.5 min | Near-instant convergence |
| EMA half-life (severe, δ>10%) | 2.0 min | Fast tracking |
| EMA half-life (moderate) | 10.0 min | Gentle smoothing |

### Market Simulation (Section 5)

| Parameter | Value | Calibration rationale |
|---|---|---|
| Total collateral | $12M | Approximate wstUSR in affected vaults |
| Initial USDC pool | $3M | Chosen so arb+allocator ≈ $6M by t=91 |
| LLTV | 0.86 | Morpho market parameter |
| Arb drain rate | 2.5%/block, cap $15K | Produces ~$67K/min drain |
| Allocator inflow | $50K/block | Re-supplies pool for continued arb |
| Manual intervention | t = 91 min | Models Gauntlet's actual response |

### Price Path (Section 3)

The DEX price is a piecewise-analytic function fitted to five forensic anchors. The counterfactual results are **insensitive** to the exact crash shape because D₁ and D₂ trigger during the first phase (linear $1.00 → $0.90), before the later phases matter.

---

## Figures Produced

| # | Filename | Paper Location | Description |
|---|---|---|---|
| 1 | `fig_timeline_oracle_paths.png` | Section 8.1 | 3-panel: DEX crash, oracle paths (F/D₁/D₂), supply spike |
| 2 | `fig_bad_debt_prevented.png` | Section 8.2 | 2-panel: cumulative bad debt, allocator inflows |
| 3 | `fig_divergence_regime_map.png` | Section 8.4 | Divergence with RCVG escalation zones |
| 4 | `fig_counterfactual_bars.png` | Section 8.3 | Bar comparison: debt, allocator, latency |
| 5 | `fig_sensitivity_heatmap.png` | Section 8.5 | D₁ threshold × persistence sweep |
| 6 | `fig_monte_carlo_generic.png` | Section 8.6 | Distribution + scatter across 200 scenarios |

---

## Reproducibility

The canonical CSVs and figures are committed in this repository on purpose. They are treated as audited artifacts, not disposable scratch outputs.

### Locked rerun

The canonical reproduction target is the pinned Python 3.11.6 environment described by [`.python-version`](.python-version) and [`requirements-lock.txt`](requirements-lock.txt). The easiest end-to-end check is:

```bash
make reproduce
```

This will:

1. create `.venv`
2. install the exact locked dependency set
3. run `python run.py --csv --verify-manifest`
4. run both reproducibility tests

If you prefer the manual route:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
python run.py --csv --verify-manifest
python -m tests.test_determinism
python -m tests.test_artifact_manifest
```

### Determinism

All random draws use explicit `numpy.random.RandomState(seed)` calls documented in each function. Numerical results are deterministic across reruns, and the repository also tracks a full artifact manifest for the PNG and CSV outputs generated by the pinned environment.

```bash
python -m tests.test_determinism
# Expected output:
#   factual: PASS (bad_debt=$5.8724M)
#   D1: PASS (bad_debt=$0.8314M)
#   D2: PASS (bad_debt=$0.8314M)
#   All determinism checks passed.
```

`python run.py --csv --verify-manifest` compares the generated artifact hashes to [`reproducibility_manifest.json`](reproducibility_manifest.json). This is stricter than the numerical smoke test because it also verifies CSV formatting and figure rendering.

### What is reconstructed vs. observed

| Data | Method | Limitation |
|---|---|---|
| USR DEX price path | Piecewise-analytic, fitted to 5 anchors | Not tick-level replay |
| USR totalSupply | Step function at forensic block numbers | Exact |
| Morpho market state | Calibrated to $6M total + $4,900 organic | Not position-level |
| Arb loop drain rate | Calibrated aggregate | Not individual tx replay |

### Reproducing from on-chain data

To replace the reconstructed price path with actual tick data:

1. Get an Ethereum archive node (Alchemy/QuickNode)
2. Pull `get_dy(USR_idx, USDC_idx, 1e18)` from the Curve USR/USDC pool at every block from 24,709,900 to 24,713,000
3. Pull `totalSupply()` from USR token `0x66a1E37c9b0eAddca17d3662D6c05F4DECf3e110` at each block
4. Replace `build_usr_dex_price_path()` in `src/price_paths.py` with a CSV loader

See `cursor_prompt_resolv_counterfactual.md` in the paper repo for detailed web3.py extraction scripts.

---

## Key Design Decisions

### Why the factual caps at 91 minutes

In reality, Gauntlet manually intervened at t≈91 min (03:52 UTC). Without modelling this, the factual scenario would show unlimited bad debt growth, making the comparison unfair to the "do nothing" baseline. The paper's argument is not "the adaptive oracle is better than *never intervening*" — it is "the adaptive oracle is better than *waiting 91 minutes for manual human intervention*."

### Why D₁ and D₂ have the same residual bad debt

Both trigger before the arb loop becomes profitable (the oracle hasn't diverged enough from the DEX price for the deposit-at-oracle / borrow-at-par arbitrage to work). The $0.83M residual is from **pre-existing positions** whose collateral genuinely lost value. D₂ triggers 48 seconds earlier than D₁, but both are early enough to sever the arb loop before it starts.

### Why the Monte Carlo uses reduced-form bad debt

The full market simulation (with borrower cohort, arb loop, and allocator) runs per-block for 120 minutes. Running this 200 times would be slower. Instead, the MC uses a linear approximation: `bad_debt ≈ exposure_time × severity × drain_rate`. This is valid because the arb loop operates at a roughly constant drain rate once the oracle-DEX gap exceeds the profit threshold.

---

## License

This code accompanies an academic paper. Please cite appropriately if you use it.
