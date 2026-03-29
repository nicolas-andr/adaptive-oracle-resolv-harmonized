"""
figures.py — Publication-quality figure generation
====================================================

Generates six figures for the paper's Resolv case study sections.

Figure 1: Timeline & Oracle Price Paths     (3-panel)
Figure 2: Bad Debt Accumulation             (2-panel)
Figure 3: Oracle–DEX Divergence Regime Map
Figure 4: Counterfactual Comparison Bars    (3-panel)
Figure 5: Sensitivity Heatmap
Figure 6: Monte Carlo Distribution          (2-panel)

All figures are saved to the caller-provided output directory at 300 DPI.
"""

from __future__ import annotations


import numpy as np
from pathlib import Path
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config import COLORS, MPL_STYLE, TIMELINE, ORACLE, GRID
from src.simulation import SimResult


def _apply_style():
    plt.rcParams.update(MPL_STYLE)


def _save_figure(fig: plt.Figure, output_dir: Path, filename: str) -> None:
    """Save a figure with explicit metadata for stable artifact hashing."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_dir / filename,
        dpi=300,
        bbox_inches='tight',
        metadata={'Software': 'adaptive_oracle_code'},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 1: TIMELINE & ORACLE PRICE PATHS
# ═══════════════════════════════════════════════════════════════════════════════

def fig_timeline_oracle_paths(results: dict[str, SimResult], output_dir: Path):
    """
    Three-panel figure:
      A: USR DEX spot price crash
      B: Oracle price under factual / D1 / D2
      C: USR total supply with minting events
    """
    _apply_style()
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    t = results['factual'].time

    # ── Panel A: DEX price ──
    ax = axes[0]
    ax.plot(t, results['factual'].dex_price, color=COLORS['dex_price'],
            linewidth=2, label='USR DEX spot price')
    ax.axhline(1.0, color='gray', ls='--', alpha=0.5, label='$1.00 peg')
    ax.axvline(GRID.MINT1_OFFSET_MIN, color=COLORS['trigger'], ls=':', alpha=0.7, lw=1)
    ax.axvline(GRID.MINT2_OFFSET_MIN, color=COLORS['trigger'], ls=':', alpha=0.7, lw=1)
    ax.axvline(TIMELINE.STEAKHOUSE_EXIT_MIN, color=COLORS['steakhouse'],
               ls='--', alpha=0.5, lw=1)

    ax.annotate('Mint #1\n50M USR', xy=(0.4, 1.0), xytext=(5, 0.78),
                fontsize=9, arrowprops=dict(arrowstyle='->', color='gray'),
                bbox=dict(boxstyle='round,pad=0.3', fc='#fff3cd', alpha=0.8))
    ax.annotate('Mint #2\n30M USR', xy=(80.2, 0.04), xytext=(85, 0.25),
                fontsize=9, arrowprops=dict(arrowstyle='->', color='gray'),
                bbox=dict(boxstyle='round,pad=0.3', fc='#fff3cd', alpha=0.8))
    ax.annotate('Steakhouse\nexit (41 min)', xy=(41, 0.03), xytext=(50, 0.55),
                fontsize=8, color=COLORS['steakhouse'],
                arrowprops=dict(arrowstyle='->', color=COLORS['steakhouse']))
    ax.annotate('Gauntlet\nintervenes (91 min)', xy=(91, 0.04), xytext=(95, 0.45),
                fontsize=8, color=COLORS['factual'],
                arrowprops=dict(arrowstyle='->', color=COLORS['factual']))

    ax.set_ylabel('USR DEX Price (USD)')
    ax.set_title('Panel A: USR DEX Spot Price — Catastrophic Depeg in 17 Minutes')
    ax.set_ylim(-0.02, 1.15)
    ax.legend(loc='upper right')

    # ── Panel B: Oracle prices ──
    ax = axes[1]
    ax.plot(t, results['factual'].oracle, color=COLORS['factual'], lw=2,
            label='Factual: static oracle ($1.13)')
    ax.plot(t, results['D1'].oracle, color=COLORS['D1'], lw=2,
            label=r'$D_1$: DEX-deviation trigger')
    ax.plot(t, results['D2'].oracle, color=COLORS['D2'], lw=2, ls='--',
            label=r'$D_2$: Supply-velocity trigger')
    ax.plot(t, results['factual'].dex_price * ORACLE.WSTUSR_STATIC_PRICE,
            color=COLORS['dex_price'], lw=1, alpha=0.5, ls=':',
            label='wstUSR fair value (DEX-implied)')

    # Mark trigger points
    for cfg, marker, color in [('D1', 'v', COLORS['D1']), ('D2', 's', COLORS['D2'])]:
        tt = results[cfg].trigger_time
        if tt is not None:
            idx = np.argmin(np.abs(t - tt))
            ax.scatter([tt], [results[cfg].oracle[idx]], color=color,
                       marker=marker, s=120, zorder=5, edgecolors='black', lw=0.5)
            lbl = r'$D_1$ trigger' if cfg == 'D1' else r'$D_2$ trigger'
            ax.annotate(f'{lbl}\nt={tt:.1f} min',
                        xy=(tt, results[cfg].oracle[idx]),
                        xytext=(tt + 8, results[cfg].oracle[idx] + 0.15),
                        fontsize=8, color=color,
                        arrowprops=dict(arrowstyle='->', color=color, alpha=0.7))

    ax.set_ylabel('wstUSR Oracle Price (USD)')
    ax.set_title('Panel B: Oracle Price Under Three Configurations')
    ax.set_ylim(-0.05, 1.35)
    ax.legend(loc='upper right', ncol=2)

    # ── Panel C: Supply ──
    ax = axes[2]
    supply_m = results['factual'].supply / 1e6
    ax.plot(t, supply_m, color=COLORS['supply'], lw=2)
    ax.axhline(102, color='gray', ls='--', alpha=0.5, label='Pre-exploit (102M)')
    ax.fill_between(t, 102, supply_m, where=supply_m > 102,
                    alpha=0.2, color=COLORS['supply'], label='Unauthorized minting')

    tt_d2 = results['D2'].trigger_time
    if tt_d2 is not None:
        ax.axvline(tt_d2, color=COLORS['D2'], ls='--', alpha=0.7, lw=1.5)
        ax.annotate(f'$D_2$ triggers\n(49% supply spike)', xy=(tt_d2, 155),
                    xytext=(tt_d2 + 10, 170), fontsize=9, color=COLORS['D2'],
                    arrowprops=dict(arrowstyle='->', color=COLORS['D2']))

    ax.set_ylabel('USR Total Supply (M)')
    ax.set_xlabel('Minutes After Simulation Start (Mint #1 at t = 0.4 min)')
    ax.set_title('Panel C: USR Total Supply — Minting Exploit Signature')
    ax.legend(loc='upper left')

    plt.tight_layout()
    _save_figure(fig, output_dir, 'fig_timeline_oracle_paths.png')
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 2: BAD DEBT ACCUMULATION
# ═══════════════════════════════════════════════════════════════════════════════

def fig_bad_debt_prevented(results: dict[str, SimResult], output_dir: Path):
    """
    Two-panel figure:
      A: Cumulative bad debt over time
      B: Cumulative Public Allocator inflows
    """
    _apply_style()
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    t = results['factual'].time

    # ── Panel A: Bad debt ──
    ax = axes[0]
    for cfg, label, color, ls in [
        ('factual', 'Factual: static oracle', COLORS['factual'], '-'),
        ('D1', r'$D_1$: DEX-deviation trigger', COLORS['D1'], '-'),
        ('D2', r'$D_2$: Supply-velocity trigger', COLORS['D2'], '--'),
    ]:
        ax.plot(t, results[cfg].bad_debt / 1e6, color=color, lw=2,
                label=label, ls=ls)

    ax.fill_between(t, results['D1'].bad_debt / 1e6, results['factual'].bad_debt / 1e6,
                    alpha=0.12, color=COLORS['prevented'], label='Prevented by adaptive oracle')

    # Mark Gauntlet intervention
    ax.axvline(91, color=COLORS['factual'], ls=':', alpha=0.5, lw=1)
    ax.annotate('Gauntlet\nintervenes', xy=(91, results['factual'].bad_debt[
        np.argmin(np.abs(t - 91))] / 1e6), xytext=(97, 4.5),
                fontsize=8, color=COLORS['factual'],
                arrowprops=dict(arrowstyle='->', color=COLORS['factual'], alpha=0.5))

    # Annotate final values
    for cfg, color in [('factual', COLORS['factual']),
                       ('D1', COLORS['D1']), ('D2', COLORS['D2'])]:
        final = results[cfg].final_bad_debt / 1e6
        ax.annotate(f'${final:.2f}M', xy=(t[-1], final),
                    xytext=(t[-1] + 2, final),
                    fontsize=10, fontweight='bold', color=color,
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.8))

    ax.set_ylabel('Cumulative Bad Debt (USD, Millions)')
    ax.set_title('Panel A: Bad Debt Accumulation — Adaptive Oracle Eliminates Arb-Loop Losses')
    ax.legend(loc='upper left')

    # ── Panel B: Allocator inflows ──
    ax = axes[1]
    for cfg, label, color, ls in [
        ('factual', 'Factual: allocator active until t=91', COLORS['factual'], '-'),
        ('D1', r'$D_1$: allocator severed at t≈1 min', COLORS['D1'], '-'),
        ('D2', r'$D_2$: allocator severed at t≈0.4 min', COLORS['D2'], '--'),
    ]:
        cum = np.cumsum(results[cfg].allocator_inflows) / 1e6
        ax.plot(t, cum, color=color, lw=2, label=label, ls=ls)

    ax.fill_between(t, np.cumsum(results['D1'].allocator_inflows) / 1e6,
                    np.cumsum(results['factual'].allocator_inflows) / 1e6,
                    alpha=0.12, color=COLORS['prevented'])

    ax.set_ylabel('Cumulative Allocator Inflows (USD, M)')
    ax.set_xlabel('Minutes After Simulation Start')
    ax.set_title('Panel B: Public Allocator Contagion — Severed by Adaptive Oracle')
    ax.legend(loc='upper left')

    plt.tight_layout()
    _save_figure(fig, output_dir, 'fig_bad_debt_prevented.png')
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 3: ORACLE–DEX DIVERGENCE REGIME MAP
# ═══════════════════════════════════════════════════════════════════════════════

def fig_divergence_regime_map(results: dict[str, SimResult], output_dir: Path):
    """
    Oracle-to-DEX divergence under the static oracle, with RCVG escalation zones.
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(12, 6))
    t = results['factual'].time
    oracle_static = results['factual'].oracle
    dex_implied = results['factual'].dex_price * ORACLE.WSTUSR_STATIC_PRICE
    div_pct = np.abs(oracle_static - dex_implied) / oracle_static * 100

    # Escalation zones (from RCVG framework, Opinion 2)
    zones = [
        (0, 0.5, '#2a9d8f', 'Normal (<0.5%)'),
        (0.5, 1.5, '#e9c46a', 'Warning (0.5–1.5%)'),
        (1.5, 3.0, '#f4a261', 'Defensive freeze (1.5–3%)'),
        (3.0, 10.0, '#e76f51', 'Emergency (3–10%)'),
        (10.0, 100.0, '#e63946', 'Toxic collateral (>10%)'),
    ]
    for lo, hi, clr, lbl in zones:
        ax.axhspan(lo, hi, color=clr, alpha=0.06, label=lbl)

    ax.plot(t, div_pct, color='black', lw=1.5, zorder=5,
            label='Static oracle-to-DEX divergence')

    # Steakhouse detection level
    ax.axhline(1.61, color=COLORS['steakhouse'], lw=1, ls=':', alpha=0.8)
    ax.annotate('Steakhouse detected: 1.61%\n(exited with $0 losses in 41 min)',
                xy=(2, 1.61), xytext=(25, 4), fontsize=9,
                color=COLORS['steakhouse'], fontstyle='italic',
                arrowprops=dict(arrowstyle='->', color=COLORS['steakhouse'], alpha=0.7))

    # D1 threshold
    ax.axhline(2.0, color=COLORS['D1'], lw=1.5, ls='--', alpha=0.8)
    ax.annotate(r'$D_1$ threshold: 2%', xy=(3, 2.0), xytext=(25, 7),
                fontsize=9, color=COLORS['D1'], fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=COLORS['D1'], alpha=0.7))

    tt_d1 = results['D1'].trigger_time
    if tt_d1 is not None:
        ax.axvline(tt_d1, color=COLORS['D1'], ls='--', alpha=0.4, lw=1)

    ax.set_xlabel('Minutes After Simulation Start')
    ax.set_ylabel('Oracle-to-DEX Divergence (%)')
    ax.set_title('Oracle–DEX Divergence with RCVG Escalation Zones')
    ax.set_yscale('symlog', linthresh=5)
    ax.set_ylim(0, 100)
    ax.legend(loc='center right', fontsize=8)

    plt.tight_layout()
    _save_figure(fig, output_dir, 'fig_divergence_regime_map.png')
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 4: COUNTERFACTUAL COMPARISON BARS
# ═══════════════════════════════════════════════════════════════════════════════

def fig_counterfactual_bars(results: dict[str, SimResult], output_dir: Path):
    """
    Three-panel bar chart: bad debt, allocator inflows, trigger latency.
    """
    _apply_style()
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    configs = ['factual', 'D1', 'D2']
    labels = ['Factual:\nStatic Oracle',
              r'$D_1$: DEX' + '\nDeviation\nTrigger',
              r'$D_2$: Supply' + '\nVelocity\nTrigger']
    colors = [COLORS['factual'], COLORS['D1'], COLORS['D2']]

    # Panel A: Bad debt
    ax = axes[0]
    vals = [results[c].final_bad_debt / 1e6 for c in configs]
    bars = ax.bar(labels, vals, color=colors, alpha=0.85, edgecolor='black', lw=0.5)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f'${val:.2f}M', ha='center', fontsize=10, fontweight='bold')
    ax.set_ylabel('Bad Debt (USD, Millions)')
    ax.set_title('Total Bad Debt')

    # Panel B: Allocator inflows
    ax = axes[1]
    vals = [results[c].total_allocator_inflow / 1e6 for c in configs]
    bars = ax.bar(labels, vals, color=colors, alpha=0.85, edgecolor='black', lw=0.5)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f'${val:.2f}M', ha='center', fontsize=10, fontweight='bold')
    ax.set_ylabel('Allocator Inflows (USD, M)')
    ax.set_title('Public Allocator Contagion')

    # Panel C: Trigger latency
    ax = axes[2]
    trig = [TIMELINE.GAUNTLET_INTERVENE_MIN,
            results['D1'].trigger_time or 120,
            results['D2'].trigger_time or 120]
    bars = ax.bar(labels, trig, color=colors, alpha=0.85, edgecolor='black', lw=0.5)
    for bar, val in zip(bars, trig):
        lbl = f'{val:.0f} min (manual)' if val > 60 else f'{val:.1f} min'
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                lbl, ha='center', fontsize=9, fontweight='bold')
    ax.set_ylabel('Time to Response (minutes)')
    ax.set_title('Detection / Intervention Latency')
    ax.set_ylim(0, 110)

    plt.suptitle('Counterfactual Analysis: Resolv USR Exploit Under Adaptive Oracle',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    _save_figure(fig, output_dir, 'fig_counterfactual_bars.png')
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 5: SENSITIVITY HEATMAP
# ═══════════════════════════════════════════════════════════════════════════════

def fig_sensitivity_heatmap(thresholds: np.ndarray, persistence: np.ndarray,
                            bad_debt_grid: np.ndarray, output_dir: Path):
    """
    D1 sensitivity: bad debt vs (deviation threshold, block persistence).
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 7))

    im = ax.imshow(bad_debt_grid / 1e6, aspect='auto', cmap='RdYlGn_r', origin='lower',
                   extent=[persistence[0] - 0.5, persistence[-1] + 0.5,
                           thresholds[0] * 100 - 0.25, thresholds[-1] * 100 + 0.25],
                   vmin=0, vmax=6)

    ax.set_xlabel('Block Persistence Requirement (blocks)')
    ax.set_ylabel('Deviation Threshold (%)')
    ax.set_xticks(range(int(persistence[0]), int(persistence[-1]) + 1))
    ax.set_title(r'$D_1$ Sensitivity: Estimated Bad Debt (USD M) vs. Threshold & Persistence')

    fig.colorbar(im, ax=ax, label='Estimated Bad Debt (USD, Millions)')

    # Mark chosen operating point
    ax.plot(2, 2.0, 'w*', markersize=15, markeredgecolor='black', markeredgewidth=1.5)
    ax.annotate('Chosen: 2%, 2 blocks\n(~$0.05M bad debt)',
                xy=(2, 2.0), xytext=(4, 3.5), fontsize=10,
                color='white', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='white', lw=2),
                bbox=dict(boxstyle='round', fc='#264653', alpha=0.9))

    plt.tight_layout()
    _save_figure(fig, output_dir, 'fig_sensitivity_heatmap.png')
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 6: MONTE CARLO
# ═══════════════════════════════════════════════════════════════════════════════

def fig_monte_carlo(mc_results: dict[str, np.ndarray], output_dir: Path):
    """
    Two-panel: bad-debt distribution & severity–bad-debt scatter.
    """
    _apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    n_runs = len(mc_results['factual'])

    # ── Panel A: Distribution ──
    ax = axes[0]
    for cfg, label, color in [
        ('factual', 'Static oracle', COLORS['factual']),
        ('D1', r'$D_1$: DEX trigger', COLORS['D1']),
        ('D2', r'$D_2$: Supply trigger', COLORS['D2']),
    ]:
        data = mc_results[cfg] / 1e6
        ax.hist(data, bins=30, alpha=0.5, color=color, label=label,
                edgecolor='black', lw=0.3)
        ax.axvline(np.mean(data), color=color, ls='--', lw=1.5)

    ax.set_xlabel('Bad Debt (USD, Millions)')
    ax.set_ylabel('Frequency')
    ax.set_title(f'Monte Carlo: Bad Debt Distribution (n={n_runs})')
    ax.legend()

    # ── Panel B: Scatter ──
    ax = axes[1]
    sev = mc_results['severities']
    for cfg, label, color, marker in [
        ('factual', 'Static oracle', COLORS['factual'], 'o'),
        ('D1', r'$D_1$: DEX trigger', COLORS['D1'], '^'),
        ('D2', r'$D_2$: Supply trigger', COLORS['D2'], 's'),
    ]:
        data = mc_results[cfg] / 1e6
        ax.scatter(sev, data, color=color, alpha=0.4, s=20, marker=marker, label=label)

    ax.set_xlabel('Depeg Severity (fraction)')
    ax.set_ylabel('Bad Debt (USD, Millions)')
    ax.set_title('Depeg Severity vs. Bad Debt: Adaptive Oracle Compresses Tail')
    ax.legend()

    plt.tight_layout()
    _save_figure(fig, output_dir, 'fig_monte_carlo_generic.png')
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE: GENERATE ALL
# ═══════════════════════════════════════════════════════════════════════════════

def generate_all(results: dict[str, SimResult],
                 sens_data: tuple, mc_data: dict, output_dir: Path):
    """Generate all six figures."""
    output_dir.mkdir(parents=True, exist_ok=True)

    fig_timeline_oracle_paths(results, output_dir)
    fig_bad_debt_prevented(results, output_dir)
    fig_divergence_regime_map(results, output_dir)
    fig_counterfactual_bars(results, output_dir)

    thresholds, persistence, grid = sens_data
    fig_sensitivity_heatmap(thresholds, persistence, grid, output_dir)

    fig_monte_carlo(mc_data, output_dir)
