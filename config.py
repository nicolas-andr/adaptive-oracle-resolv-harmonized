"""
config.py — Central parameter file
====================================

Every tunable parameter in the simulation lives here. Nothing is hardcoded
in the simulation logic. To run a sensitivity sweep, import this module and
override individual values.

CALIBRATION TARGET
------------------
The factual scenario must reproduce the empirical outcome:
  - ~$4,900 organic bad debt (pre-existing position shortfalls)
  - ~$6.0M total bad debt by minute 91 (Gauntlet manual intervention)
  - Majority of loss from arb-loop USDC extraction + allocator re-supply
  - Manual curator intervention halts losses at t ≈ 91 min

Sources: Steakhouse blog, Chainalysis/Beosin/PeckShield post-mortems,
Nexus Mutual incident report, on-chain forensic data.
"""

from dataclasses import dataclass
from typing import Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: ON-CHAIN FORENSIC CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
# These are observed facts, not tunable parameters.

@dataclass(frozen=True)
class ExploitTimeline:
    """
    Block-level timestamps from the Resolv USR exploit.
    All times in UTC on March 22, 2026.
    Source: Blockscout, verified tx hashes below.
    """
    # Mint #1: completeSwap(_id=30, _targetAmount=50M USR)
    # Tx: 0xfe37f25efd67d0a4da4afe48509b258df48757b97810b28ce4c649658dc33743
    MINT1_BLOCK: int = 24_710_031
    MINT1_TIMESTAMP: str = "2026-03-22T02:21:35Z"
    MINT1_AMOUNT_USR: float = 50_000_000.0
    MINT1_COLLATERAL_USDC: float = 100_000.0   # Deposited USDC

    # Mint #2: completeSwap(_id=33, _targetAmount=30M USR)
    # Tx: 0x41b6b9376d174165cbd54ba576c8f6675ff966f17609a7b80d27d8652db1f18f
    MINT2_BLOCK: int = 24_710_428
    MINT2_TIMESTAMP: str = "2026-03-22T03:41:47Z"
    MINT2_AMOUNT_USR: float = 30_000_000.0
    MINT2_COLLATERAL_USDC: float = 100_000.0

    # Pre-exploit baseline
    PRE_EXPLOIT_SUPPLY_USR: float = 102_000_000.0  # totalSupply() at block 24,710,030

    # Observed price collapse
    USR_BOTTOM_PRICE: float = 0.025        # Curve pool at ~02:38 UTC
    USR_BOTTOM_TIME_MIN: float = 17.0      # Minutes after Mint #1

    # Key response times (minutes after Mint #1)
    STEAKHOUSE_DETECT_MIN: float = 0.0     # Detected at same block as Mint #1
    STEAKHOUSE_EXIT_MIN: float = 41.0      # Fully exited by 03:02 UTC
    STEAKHOUSE_DETECT_DEVIATION: float = 0.0161  # 1.61% deviation
    GAUNTLET_INTERVENE_MIN: float = 91.0   # Manual intervention ~03:52 UTC
    NINESUMMITS_ACTIVE_HOURS: float = 10.0 # Auto-supplied for 10 hours

    # Actual losses
    MORPHO_TOTAL_BAD_DEBT: float = 6_000_000.0  # ~$6M Gauntlet USDC Core
    ORGANIC_BAD_DEBT: float = 4_900.0            # Before allocator automation
    MORPHO_VAULTS_IMPACTED: int = 15

    # Oracle state
    WSTUSR_ORACLE_PRICE: float = 1.13     # Hardcoded throughout exploit
    USR_ORACLE_STALE_HOURS: float = 15.0  # NAV oracle hadn't updated

    # Contract addresses (for on-chain verification)
    USR_TOKEN: str = "0x66a1E37c9b0eAddca17d3662D6c05F4DECf3e110"
    WSTUSR_TOKEN: str = "0x1202F5C7b4B9E47a1A484E8B270be34dbbC75055"
    ATTACKER: str = "0x04A288a7789DD6Ade935361a4fB1Ec5db513caEd"
    SERVICE_ROLE: str = "0x15CAd41e6BdCaDc7121ce65080489C92CF6de398"
    MORPHO_BLUE: str = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb"


TIMELINE = ExploitTimeline()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: SIMULATION GRID
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SimulationGrid:
    """
    Time discretisation for the main simulation.

    We simulate 120 minutes at 12-second resolution (= Ethereum block time).
    This covers Mint #1 (t=0.4 min) through well past Gauntlet's intervention
    (t=91 min), with headroom for comparison.
    """
    BLOCK_TIME_SEC: int = 12          # Ethereum L1 block time
    HORIZON_MINUTES: float = 120.0    # Total simulation window
    MINT1_OFFSET_MIN: float = 0.4     # Mint #1 occurs 0.4 min into simulation
                                       # (gives supply-velocity detector a baseline)
    MINT2_OFFSET_MIN: float = 80.2    # Mint #2 at 03:41:47 UTC (80.2 min after Mint #1)

    @property
    def n_steps(self) -> int:
        return int(self.HORIZON_MINUTES * 60 / self.BLOCK_TIME_SEC)

    @property
    def dt_minutes(self) -> float:
        return self.BLOCK_TIME_SEC / 60.0


GRID = SimulationGrid()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: PRICE PATH PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PricePathParams:
    """
    Parameters for the piecewise-analytic USR DEX price reconstruction.

    The price path has five phases fitted to forensic timestamps.
    This is a *stylized* reconstruction — not tick-level replay data.
    The counterfactual results are insensitive to the exact shape because
    D1 and D2 both trigger within the first ~1 minute (initial-sell phase).

    Phase 1: Pre-mint          [0, MINT1_OFFSET]         flat at $1.00
    Phase 2: Initial sell      (MINT1, MINT1+2 min]      linear $1.00 → $0.90
    Phase 3: Accelerating      (MINT1+2, MINT1+10 min]   power-law $0.90 → $0.30
    Phase 4: Terminal crash    (MINT1+10, 17 min]         exp decay → $0.025
    Phase 5: Post-crash        (17, 120 min]              oscillation $0.03–0.05
    """
    INITIAL_SELL_DURATION_MIN: float = 2.0    # Phase 2 length
    INITIAL_SELL_DROP: float = 0.10           # $1.00 → $0.90

    ACCEL_CRASH_DURATION_MIN: float = 8.0     # Phase 3 length
    ACCEL_CRASH_DROP: float = 0.60            # $0.90 → $0.30
    ACCEL_CRASH_EXPONENT: float = 1.5         # Convexity of crash

    TERMINAL_DECAY_RATE: float = 4.0          # Exponential decay speed
    TERMINAL_FLOOR: float = 0.025             # Curve pool floor price

    POST_CRASH_CENTER: float = 0.04           # Mean post-crash price
    POST_CRASH_AMPLITUDE: float = 0.01        # Oscillation half-width
    POST_CRASH_FREQ: float = 0.1              # Oscillation frequency

    MINT2_DIP_PRICE: float = 0.03             # Temporary dip on Mint #2
    MINT2_DIP_DURATION_MIN: float = 5.0       # How long the Mint #2 dip lasts

    PRICE_FLOOR: float = 0.005                # Absolute minimum price


PRICE_PARAMS = PricePathParams()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: ORACLE CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class OracleConfig:
    """
    Parameters for the dual-regime adaptive oracle.

    D1 (DEX-deviation trigger):
        Enter STRESSED when |oracle - DEX_implied| / oracle > threshold
        for `persistence` consecutive blocks.

    D2 (Supply-velocity trigger):
        Enter STRESSED when (S[t] - S[t-k]) / S[t-k] > threshold
        in a `lookback` block window.

    Both configs share the same EMA convergence parameters once STRESSED.
    """
    # Static oracle (factual scenario)
    WSTUSR_STATIC_PRICE: float = 1.13

    # D1: DEX-deviation trigger
    D1_DEVIATION_THRESHOLD: float = 0.02     # 2%  — calibrated to Steakhouse's 1.61%
    D1_PERSISTENCE_BLOCKS: int = 2           # ~24s — filters single-block noise

    # D2: Supply-velocity trigger
    D2_SUPPLY_THRESHOLD: float = 0.05        # 5%  — impossible for organic stablecoin growth
    D2_LOOKBACK_BLOCKS: int = 1              # Single-block detection (maximum speed)

    # EMA convergence (shared by D1 and D2 once STRESSED)
    # Half-life is adaptive: faster convergence for larger deviations.
    #
    # Deviation ∈ [0, SEVERE)       → h = HALFLIFE_MODERATE  (gentle smoothing)
    # Deviation ∈ [SEVERE, CATASTROPHIC) → h = HALFLIFE_SEVERE   (fast tracking)
    # Deviation ≥ CATASTROPHIC      → h = HALFLIFE_CATASTROPHIC (near-instant)
    #
    # This implements the "catastrophic-deviation bypass" from the paper:
    # for extreme events, the EMA effectively reprices in 1–2 blocks.
    HALFLIFE_MODERATE_MIN: float = 10.0
    HALFLIFE_SEVERE_MIN: float = 2.0
    HALFLIFE_CATASTROPHIC_MIN: float = 0.5   # 30 seconds → ~instant
    SEVERE_DEVIATION: float = 0.10           # 10%
    CATASTROPHIC_DEVIATION: float = 0.50     # 50%


ORACLE = OracleConfig()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: MORPHO MARKET SIMULATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketParams:
    """
    Parameters for the Morpho-style isolated lending market simulator.

    CALIBRATION METHODOLOGY
    -----------------------
    The factual scenario must produce ~$6M bad debt by minute 91.
    We decompose this into two channels:

    1. Organic bad debt (~$4,900):
       Pre-existing wstUSR borrower positions whose LTV exceeds LLTV
       when collateral is marked to DEX value. This is small because
       the static oracle *never reprices*, so only positions that were
       already over LLTV at the start produce organic shortfalls.
       We set initial LTVs well below LLTV (Beta(5,2) × 0.85 ≈ 0.60
       median) so organic shortfalls are near zero under static oracle.

    2. Arb-loop bad debt (~$6M):
       Arbitrageurs deposit worthless wstUSR valued at $1.13 by the
       static oracle, borrow real USDC at up to LLTV, and extract it.
       The pool drains, the allocator re-supplies, the arb drains again.

       To hit $6M in 91 minutes:
         - 91 min × 60s / 12s = ~455 blocks
         - Not all blocks are active (arb needs oracle >> DEX, ~2x)
         - DEX price drops below $0.50 by ~t=3 min → arb profitable from ~t=3
         - Active window: ~88 min = ~440 blocks
         - Target drain per active block: $6M / 440 ≈ $13,600
         - But the pool is finite and refilled by allocator
         - Set: initial pool $3M, allocator refill rate ~$50K/step when
           utilisation > 80%, arb drain = min(2.5% of pool, $15K)
         - This produces a saw-tooth drain+refill pattern that
           accumulates ~$6M total extracted USDC by t=91 min.

    The manual intervention at t=91 min is modelled as a hard cutoff:
    allow_allocator=False and allow_new_borrows=False for t > 91 min.
    """
    # Borrower population
    N_BORROWERS: int = 50
    BORROWER_LTV_ALPHA: float = 5.0     # Beta(α, β) shape for initial LTVs
    BORROWER_LTV_BETA: float = 2.0
    BORROWER_LTV_CAP: float = 0.85      # Max initial LTV (< LLTV=0.86)
    BORROWER_LTV_FLOOR: float = 0.30    # Min initial LTV
    BORROWER_SIZE_LOG_SIGMA: float = 0.8 # Log-normal spread of position sizes
    BORROWER_SEED: int = 42              # RNG seed for position generation

    # Market parameters
    TOTAL_COLLATERAL_USD: float = 12_000_000.0  # Approximate wstUSR in affected vaults
    USDC_POOL_INITIAL: float = 3_000_000.0      # Initial USDC available to borrow
    LLTV: float = 0.86                          # Morpho market parameter

    # Arb-loop parameters
    ARB_PROFIT_THRESHOLD: float = 2.0    # Min oracle/DEX ratio to arb
    ARB_DRAIN_FRAC: float = 0.025        # Fraction of pool drained per block
    ARB_DRAIN_CAP: float = 15_000.0      # Max USDC drained per block
    ARB_MIN_POOL: float = 5_000.0        # Stop arbing when pool below this

    # Public Allocator parameters
    ALLOCATOR_UTIL_TRIGGER: float = 0.80     # Utilisation threshold to trigger re-supply
    ALLOCATOR_POOL_TRIGGER_FRAC: float = 0.20  # Pool-fraction threshold
    ALLOCATOR_INFLOW_PER_STEP: float = 50_000.0  # USDC routed per block
    ALLOCATOR_INFLOW_FRAC: float = 0.015         # Alternative: fraction of initial pool

    # Manual intervention (factual only)
    MANUAL_INTERVENTION_MIN: float = 91.0  # Gauntlet intervenes at t=91 min


MARKET = MarketParams()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: MONTE CARLO PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MonteCarloParams:
    """
    Parameters for the generic depeg Monte Carlo (Figure 6).
    These simulate a range of depeg severities and speeds to show
    that the adaptive oracle compresses bad debt across scenarios.
    """
    N_RUNS: int = 200
    SEED: int = 2026
    DEPEG_SEVERITY_RANGE: Tuple[float, float] = (0.05, 0.60)
    DEPEG_SPEED_RANGE_MIN: Tuple[float, float] = (5.0, 120.0)
    SUPPLY_SHOCK_PROB: float = 0.30
    SUPPLY_SHOCK_RANGE: Tuple[float, float] = (0.10, 0.80)
    HORIZON_MINUTES: float = 150.0
    N_STEPS: int = 750

    # Scaling factors for reduced-form bad debt estimation
    # (used in the MC because full market sim per path is expensive)
    FACTUAL_DRAIN_RATE_PER_MIN_PER_SEVERITY: float = 40_000.0
    D1_DRAIN_RATE_PER_MIN_PER_SEVERITY: float = 2_000.0
    D2_DRAIN_RATE_WHEN_TRIGGERED: float = 1_000.0
    D2_FALLBACK_REDUCTION: float = 0.30  # Reduction vs factual when no supply shock


MC = MonteCarloParams()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: SENSITIVITY SWEEP PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SensitivityParams:
    """
    Parameters for the D1 threshold sensitivity heatmap (Figure 5).
    Sweeps deviation threshold × block persistence.
    """
    THRESHOLD_START: float = 0.005  # 0.5%
    THRESHOLD_STOP: float = 0.10    # 10%
    THRESHOLD_STEP: float = 0.005   # 0.5% increments

    PERSISTENCE_START: int = 1
    PERSISTENCE_STOP: int = 10      # inclusive

    # For the heatmap: bad debt is proportional to time-until-trigger.
    # The actual $6M accumulated over 91 minutes, so:
    #   bad_debt ≈ (trigger_time / 91) × $6M
    # With a floor of $50K for very fast triggers (some organic BD + 1-block arb).
    ACTUAL_BAD_DEBT_USD: float = 6_000_000.0
    ACTUAL_RESPONSE_TIME_MIN: float = 91.0
    FAST_TRIGGER_FLOOR_USD: float = 50_000.0


SENSITIVITY = SensitivityParams()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: FIGURE STYLE
# ═══════════════════════════════════════════════════════════════════════════════

COLORS = {
    'factual':      '#e63946',   # Red — what actually happened
    'D1':           '#2a9d8f',   # Teal — DEX-deviation trigger
    'D2':           '#264653',   # Dark blue — supply-velocity trigger
    'dex_price':    '#457b9d',   # Steel blue — DEX spot price
    'supply':       '#e76f51',   # Coral — supply path
    'allocator':    '#f4a261',   # Amber — allocator inflows
    'prevented':    '#2a9d8f',   # Teal — prevented losses (same as D1)
    'steakhouse':   '#6a4c93',   # Purple — Steakhouse benchmark
    'trigger':      '#ff6b35',   # Orange — trigger markers
}

MPL_STYLE = {
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'font.family': 'DejaVu Serif',
    'font.size': 11,
    'axes.titlesize': 13,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 9,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linewidth': 0.5,
}
