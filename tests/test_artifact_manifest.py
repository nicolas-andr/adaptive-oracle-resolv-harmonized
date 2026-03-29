"""
test_artifact_manifest.py — Verify full-run artifact hashes
===========================================================

Runs the full analysis in a temporary output directory and checks the
generated CSVs and PNGs against the tracked reproducibility manifest.
"""

from __future__ import annotations


from pathlib import Path
from tempfile import TemporaryDirectory

from run import DEFAULT_MANIFEST_PATH, run_pipeline
from src.reproducibility import verify_manifest


def test_artifact_manifest():
    """A full rerun should match the canonical artifact manifest."""
    with TemporaryDirectory() as tmp_dir:
        run_pipeline(skip_mc=False, do_csv=True, output_root=Path(tmp_dir))
        errors = verify_manifest(Path(tmp_dir), DEFAULT_MANIFEST_PATH)
        assert not errors, "\n".join(errors)
