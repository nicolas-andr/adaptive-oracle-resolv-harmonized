"""
test_determinism.py — Verify reproducibility
==============================================

Runs the full simulation twice and asserts bit-identical results.

Usage
-----
    python -m tests.test_determinism
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from src.simulation import run_all


def test_determinism():
    """Two runs must produce identical numerical results."""
    print("Run 1...")
    r1 = run_all()
    print("Run 2...")
    r2 = run_all()

    for cfg in ['factual', 'D1', 'D2']:
        assert r1[cfg].final_bad_debt == r2[cfg].final_bad_debt, \
            f"{cfg}: bad_debt mismatch {r1[cfg].final_bad_debt} vs {r2[cfg].final_bad_debt}"
        assert r1[cfg].trigger_time == r2[cfg].trigger_time, \
            f"{cfg}: trigger_time mismatch"
        np.testing.assert_array_equal(r1[cfg].bad_debt, r2[cfg].bad_debt)
        np.testing.assert_array_equal(r1[cfg].oracle, r2[cfg].oracle)
        np.testing.assert_array_equal(r1[cfg].allocator_inflows, r2[cfg].allocator_inflows)
        print(f"  {cfg}: PASS (bad_debt=${r1[cfg].final_bad_debt/1e6:.4f}M)")

    print("\nAll determinism checks passed.")


if __name__ == '__main__':
    test_determinism()
