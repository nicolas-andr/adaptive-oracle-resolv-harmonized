# Changelog

## v1.0.2 — 2026-03-29

Methodology harmonization release.

### Documentation
- Added `METHODOLOGY_HARMONIZED.md` to consolidate the executable methodology in this repo with the stronger conceptual framing from the alternate local draft
- Updated the README and methodology docs to point to the harmonized note as the canonical cross-draft overview
- Aligned the paper draft's Resolv counterfactual numbers and calibration parameters with the reproducible fixed-step run in this repo

## v1.0.1 — 2026-03-29

Reproducibility hardening release.

### Reproducibility
- Added `.python-version`, `requirements-lock.txt`, and `Makefile` for a single pinned rerun path
- Added `reproducibility_manifest.json` support with SHA-256 verification for all canonical CSV and PNG artifacts
- Added `tests/test_artifact_manifest.py` to validate a clean full rerun against the tracked manifest
- Switched figure rendering to the Agg backend with `DejaVu Serif` so PNG output is stable across machines
- Fixed the simulation time grid to use exact 12-second steps instead of `linspace(..., endpoint=True)` drift

### Calibrated outputs after fixed-step grid
- Factual: $5.87M bad debt (calibrated to ~$6M actual)
- D₁: $0.83M residual (trigger at 1.2 min), 85.8% reduction
- D₂: $0.83M residual (trigger at 0.4 min), 85.8% reduction

## v1.0.0 — 2026-03-29

Initial release accompanying the paper submission.

### Simulation
- Three oracle configurations: factual (static), D₁ (DEX-deviation), D₂ (supply-velocity)
- Morpho market simulator with arb-loop, allocator, and 50-borrower cohort
- Factual scenario calibrated to ~$6M actual Morpho loss with manual intervention modelled at t=91 min
- D₁ sensitivity sweep: 20 thresholds × 10 persistence levels
- Monte Carlo: 200 randomised depeg scenarios

### Figures
- Fig 1: Timeline & oracle price paths (3-panel)
- Fig 2: Bad debt accumulation (2-panel)
- Fig 3: Oracle–DEX divergence with RCVG escalation zones
- Fig 4: Counterfactual comparison bars (3-panel)
- Fig 5: Sensitivity heatmap
- Fig 6: Monte Carlo distribution (2-panel)

### Key Results
- Factual: $5.86M bad debt (calibrated to ~$6M actual)
- D₁: $0.84M residual (trigger at 1.0 min), 85.7% reduction
- D₂: $0.84M residual (trigger at 0.4 min), 85.7% reduction
- 100% of arb-loop extraction channel eliminated by both configs
- Deterministic: `python -m tests.test_determinism` passes
