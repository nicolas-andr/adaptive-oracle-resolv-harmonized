"""
reproducibility.py — Artifact hashing and runtime capture
=========================================================

Utilities for verifying that a full simulation rerun reproduced the
canonical CSV and PNG artifacts tracked by this repository.
"""

from __future__ import annotations


import hashlib
import json
import platform
import sys
from pathlib import Path

import matplotlib
import numpy
import pandas

from src.simulation import SimResult


CANONICAL_ARTIFACTS = (
    "data/results_summary.csv",
    "data/timeseries_D1.csv",
    "data/timeseries_D2.csv",
    "data/timeseries_factual.csv",
    "figures/fig_bad_debt_prevented.png",
    "figures/fig_counterfactual_bars.png",
    "figures/fig_divergence_regime_map.png",
    "figures/fig_monte_carlo_generic.png",
    "figures/fig_sensitivity_heatmap.png",
    "figures/fig_timeline_oracle_paths.png",
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_metadata() -> dict[str, object]:
    """Capture the runtime used to generate canonical artifacts."""
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "dependencies": {
            "numpy": numpy.__version__,
            "pandas": pandas.__version__,
            "matplotlib": matplotlib.__version__,
        },
    }


def results_snapshot(results: dict[str, SimResult]) -> dict[str, dict[str, float | None]]:
    """Capture compact summary metrics for auditability."""
    snapshot: dict[str, dict[str, float | None]] = {}
    for cfg in ("factual", "D1", "D2"):
        result = results[cfg]
        snapshot[cfg] = {
            "final_bad_debt_usd": result.final_bad_debt,
            "trigger_time_min": result.trigger_time,
            "total_allocator_inflow_usd": result.total_allocator_inflow,
            "total_arb_borrowed_usd": result.total_arb_borrowed,
        }
    return snapshot


def build_manifest(output_root: Path, results: dict[str, SimResult]) -> dict[str, object]:
    """Build a manifest for the canonical full-analysis artifact set."""
    output_root = output_root.resolve()
    artifacts = {}
    for relative_path in CANONICAL_ARTIFACTS:
        artifact_path = output_root / relative_path
        if not artifact_path.exists():
            raise FileNotFoundError(f"Missing artifact: {artifact_path}")
        artifacts[relative_path] = sha256_file(artifact_path)

    return {
        "schema_version": 1,
        "runtime": runtime_metadata(),
        "results": results_snapshot(results),
        "artifacts": artifacts,
    }


def write_manifest(manifest_path: Path, manifest: dict[str, object]) -> None:
    """Write a manifest JSON file with stable formatting."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def load_manifest(manifest_path: Path) -> dict[str, object]:
    """Load a manifest from disk."""
    return json.loads(manifest_path.read_text())


def verify_manifest(output_root: Path, manifest_path: Path) -> list[str]:
    """Return a list of verification errors, or an empty list on success."""
    output_root = output_root.resolve()
    manifest = load_manifest(manifest_path)
    expected = manifest.get("artifacts", {})
    errors: list[str] = []

    for relative_path, expected_hash in expected.items():
        artifact_path = output_root / relative_path
        if not artifact_path.exists():
            errors.append(f"Missing artifact: {relative_path}")
            continue

        actual_hash = sha256_file(artifact_path)
        if actual_hash != expected_hash:
            errors.append(
                f"Hash mismatch for {relative_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

    return errors
