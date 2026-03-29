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


def _compact_panel_title(ax: plt.Axes, label: str, title: str) -> None:
    """Apply a short left-aligned panel title."""
    ax.set_title(f'{label}. {title}', loc='left', pad=8, fontweight='bold')


def _binned_quantiles(x: np.ndarray, y: np.ndarray, n_bins: int = 28
                      ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Summarize y by x-bin using 10/50/90 percentiles for cleaner plotting."""
    edges = np.linspace(float(np.min(x)), float(np.max(x)), n_bins + 1)
    centers = []
    q10 = []
    q50 = []
    q90 = []

    for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        upper_inclusive = i == len(edges) - 2
        mask = (x >= lo) & ((x <= hi) if upper_inclusive else (x < hi))
        if not np.any(mask):
            continue
        values = y[mask]
        centers.append(0.5 * (lo + hi))
        q10.append(float(np.quantile(values, 0.10)))
        q50.append(float(np.quantile(values, 0.50)))
        q90.append(float(np.quantile(values, 0.90)))

    return (
        np.asarray(centers),
        np.asarray(q10),
        np.asarray(q50),
        np.asarray(q90),
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
    fig, axes = plt.subplots(3, 1, figsize=(11.5, 9.4), sharex=True)
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

    ax.text(4.5, 0.88, 'Mint #1\n50M USR', fontsize=8.5, va='top',
            bbox=dict(boxstyle='round,pad=0.25', fc='#fff3cd', ec='none', alpha=0.9))
    ax.text(84.5, 0.28, 'Mint #2\n30M USR', fontsize=8.5, va='bottom',
            bbox=dict(boxstyle='round,pad=0.25', fc='#fff3cd', ec='none', alpha=0.9))
    ax.text(TIMELINE.STEAKHOUSE_EXIT_MIN + 1.0, 0.65, 'Steakhouse exit',
            fontsize=8, color=COLORS['steakhouse'], va='top')
    ax.text(TIMELINE.GAUNTLET_INTERVENE_MIN + 1.0, 0.56, 'Gauntlet halt',
            fontsize=8, color=COLORS['factual'], va='top')

    ax.set_ylabel('USR DEX Price (USD)')
    _compact_panel_title(ax, 'A', 'USR DEX Price Path')
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

    trigger_lines = []
    for cfg, marker, color in [('D1', 'v', COLORS['D1']), ('D2', 's', COLORS['D2'])]:
        tt = results[cfg].trigger_time
        if tt is not None:
            idx = np.argmin(np.abs(t - tt))
            ax.axvline(tt, color=color, ls=':', alpha=0.35, lw=1)
            ax.scatter([tt], [results[cfg].oracle[idx]], color=color,
                       marker=marker, s=120, zorder=5, edgecolors='black', lw=0.5)
            trigger_lines.append((cfg, tt, color))

    if trigger_lines:
        trigger_text = '\n'.join(
            f"{cfg} trigger: t={tt:.1f} min" for cfg, tt, _ in trigger_lines
        )
        ax.text(0.03, 0.17, trigger_text, transform=ax.transAxes,
                fontsize=8, va='bottom',
                bbox=dict(boxstyle='round,pad=0.25', fc='white', ec='none', alpha=0.85))

    ax.set_ylabel('wstUSR Oracle Price (USD)')
    _compact_panel_title(ax, 'B', 'Oracle Paths')
    ax.set_ylim(-0.05, 1.35)
    ax.legend(loc='upper right', ncol=2, fontsize=8)

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
        ax.text(tt_d2 + 10, 171, r'$D_2$ trigger' + '\n49% supply jump',
                fontsize=8.5, color=COLORS['D2'], va='top')

    ax.set_ylabel('USR Total Supply (M)')
    ax.set_xlabel('Minutes After Simulation Start (Mint #1 at t = 0.4 min)')
    _compact_panel_title(ax, 'C', 'USR Supply Path')
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
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 7.4), sharex=True)
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
                    alpha=0.12, color=COLORS['prevented'], label='Prevented losses')

    # Mark Gauntlet intervention
    ax.axvline(91, color=COLORS['factual'], ls=':', alpha=0.5, lw=1)
    ax.text(93, 5.0, 'Gauntlet\nmanual halt', fontsize=8,
            color=COLORS['factual'], va='top')

    ax.set_ylabel('Cumulative Bad Debt (USD, Millions)')
    _compact_panel_title(ax, 'A', 'Bad Debt Accumulation')
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
    _compact_panel_title(ax, 'B', 'Public Allocator Inflows')

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
    zone_label_y = [0.25, 1.0, 2.2, 6.0, 32.0]
    for lo, hi, clr, lbl in zones:
        ax.axhspan(lo, hi, color=clr, alpha=0.06)

    ax.plot(t, div_pct, color='black', lw=1.5, zorder=5,
            label='Static oracle-to-DEX divergence')

    for (_, _, _, lbl), y in zip(zones, zone_label_y):
        ax.text(118.5, y, lbl, ha='right', va='center', fontsize=7.8,
                bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.7))

    # Steakhouse detection level
    ax.axhline(1.61, color=COLORS['steakhouse'], lw=1, ls=':', alpha=0.8)
    ax.text(25, 3.2, 'Steakhouse: 1.61%\nzero losses after exit',
            fontsize=8.5, color=COLORS['steakhouse'], fontstyle='italic')

    # D1 threshold
    ax.axhline(2.0, color=COLORS['D1'], lw=1.5, ls='--', alpha=0.8)
    ax.text(25, 7.2, r'$D_1$ threshold: 2%', fontsize=8.5,
            color=COLORS['D1'], fontweight='bold')

    tt_d1 = results['D1'].trigger_time
    if tt_d1 is not None:
        ax.axvline(tt_d1, color=COLORS['D1'], ls='--', alpha=0.4, lw=1)
        ax.text(tt_d1 + 0.8, 55, r'$D_1$ trigger', fontsize=8,
                color=COLORS['D1'], rotation=90, va='center')

    ax.set_xlabel('Minutes After Simulation Start')
    ax.set_ylabel('Oracle-to-DEX Divergence (%)')
    ax.set_title('Oracle–DEX Divergence and Escalation Zones')
    ax.set_yscale('symlog', linthresh=5)
    ax.set_ylim(0, 100)

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
    labels = ['Factual', r'$D_1$', r'$D_2$']
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

    plt.suptitle('Counterfactual Comparison', fontsize=13, fontweight='bold', y=1.01)
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
    ax.annotate('Chosen point\n2%, 2 blocks',
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
    Two-panel: bad-debt distribution & severity-response quantile bands.
    """
    _apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    n_runs = len(mc_results['factual'])
    sev = mc_results['severities']
    min_bad_debt = min(float(np.min(mc_results[cfg])) for cfg in ['factual', 'D1', 'D2']) / 1e6
    max_bad_debt = max(float(np.max(mc_results[cfg])) for cfg in ['factual', 'D1', 'D2']) / 1e6
    bins = np.logspace(np.log10(min_bad_debt * 0.9), np.log10(max_bad_debt * 1.05), 37)

    # ── Panel A: Distribution ──
    ax = axes[0]
    for cfg, label, color in [
        ('factual', 'Static oracle', COLORS['factual']),
        ('D1', r'$D_1$: DEX trigger', COLORS['D1']),
        ('D2', r'$D_2$: Supply trigger', COLORS['D2']),
    ]:
        data = mc_results[cfg] / 1e6
        ax.hist(data, bins=bins, alpha=0.18, color=color, label=label,
                histtype='stepfilled')
        ax.axvline(np.mean(data), color=color, ls='--', lw=1.2)

    ax.set_xlabel('Bad Debt (USD, Millions)')
    ax.set_ylabel('Frequency')
    ax.set_xscale('log')
    ax.set_title(f'Bad Debt Distribution ({n_runs:,} scenarios)')
    ax.legend()

    # ── Panel B: Severity summary ──
    ax = axes[1]
    for cfg, label, color in [
        ('factual', 'Static oracle', COLORS['factual']),
        ('D1', r'$D_1$: DEX trigger', COLORS['D1']),
        ('D2', r'$D_2$: Supply trigger', COLORS['D2']),
    ]:
        data = mc_results[cfg] / 1e6
        centers, q10, q50, q90 = _binned_quantiles(sev, data)
        ax.fill_between(centers, q10, q90, color=color, alpha=0.10)
        ax.plot(centers, q50, color=color, lw=2, label=label)

    ax.set_xlabel('Depeg Severity (fraction)')
    ax.set_ylabel('Bad Debt (USD, Millions)')
    ax.set_yscale('log')
    ax.set_title('Severity vs. Bad Debt (median, 10-90% band)')

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
