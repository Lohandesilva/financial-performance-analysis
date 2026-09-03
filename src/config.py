"""Project configuration and the valuation assumptions the analysis rests on.

Every parameter that is not observable in the extract lives here with a stated
basis. Nothing downstream hard-codes a number, and every assumption that could
move a conclusion is swept in `screen.py`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
TABLES = OUTPUTS / "tables"
EXTRACTS = ROOT / "dashboard" / "extracts"

SOURCE_FILE = RAW / "sp500_constituents_financials.csv"
SOURCE_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies-financials/"
    "main/data/constituents-financials.csv"
)

RANDOM_SEED = 20260214

# --- Valuation assumptions --------------------------------------------------
# The extract has no forecasts and no discount rate, so the cost of equity has
# to be supplied. It is the only parameter the growth screen is genuinely
# sensitive to, which is why the screen is re-run across the whole range in
# `screen.sweep_cost_of_equity` rather than quoted at a single point.

COST_OF_EQUITY = 0.09          # long-run US large-cap nominal required return
COST_OF_EQUITY_SWEEP = (0.07, 0.08, 0.09, 0.10, 0.11, 0.12)

# Gordon growth inverts to g = r - E/P only under a full-payout assumption.
# The screen therefore compares implied *sustainable* growth (ROE x retention)
# against the growth a constant-payout Gordon model needs to justify the price.
TERMINAL_PAYOUT = 0.45         # long-run S&P 500 payout ratio, used in the inversion

# Disagreement threshold for the screen: percentage points of annual growth
# between what the balance sheet can fund and what the price requires.
GROWTH_GAP_THRESHOLD = 0.02

# --- Data-integrity screen --------------------------------------------------
# The screen removes observations where a derived quantity is *undefined or
# arithmetically impossible*, not observations that are merely extreme. A
# company on 90x earnings is expensive, not wrong, and excluding it would select
# the sample towards the answer. Extreme-but-real values are flagged and
# winsorised in the regression instead; the flag counts are reported.

MIN_PE = 0.0                   # P/E must be strictly positive: E <= 0 has no yield
MIN_PB = 0.0                   # non-positive book equity inverts the ROE identity
MAX_PB = 250.0                 # beyond this, book is so near zero that E/B is noise
MAX_PAYOUT_RATIO = 1.00        # above 1.0 the retention ratio, and so g, turns negative
MAX_EBITDA_MARGIN = 1.00       # EBITDA above revenue is an input error, not a margin
MIN_EBITDA_MARGIN = -1.00

# Flagged but retained. These mark values that are real and reportable but that
# would dominate an unweighted regression.
FLAG_HIGH_PE = 100.0
FLAG_HIGH_PS = 30.0

# Winsorisation applied to the regression inputs only, never to the reported
# medians. Two-sided, at these percentiles.
WINSOR_LOWER = 0.01
WINSOR_UPPER = 0.99

# --- Presentation -----------------------------------------------------------
# The source `Sector` column is GICS sub-industry, not sector. Groups thinner
# than this are not reported on their own; see sectors.py.
MIN_GROUP_SIZE = 5
