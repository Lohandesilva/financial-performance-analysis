# Source data

Not committed. `make data` fetches it.

**S&P 500 constituent financials** — 503 rows, 14 fields, one row per index
constituent. Price, market capitalisation, EBITDA, trailing EPS, dividend yield,
the 52-week range and four valuation multiples. No income statement, no balance
sheet, no filing date.

- Source: https://github.com/datasets/s-and-p-500-companies-financials
- File: `constituents-financials.csv` → saved here as `sp500_constituents_financials.csv`
- Licence: Public Domain Dedication and Licence (PDDL), per the publisher

## This is a snapshot, and it is not dated

The file carries no as-of column and the publisher overwrites it in place, so
the vintage has to be inferred from the prices themselves rather than read off.
Two things are certain from the contents: the prices are recent enough to sit
well above any historical vintage of this dataset that is still circulating, and
they are not live. Anything read from this file is a single point in time and
should never be quoted as a current market level.

The one internal clue to the vintage is the pattern in the missing rows, below.

## Known quirks

**`Sector` is not sector.** The column holds GICS **sub-industry**: 127 distinct
values across 503 rows, a median of two constituents each. Grouping on it as
though it were one of the eleven GICS sectors inflates every dispersion
statistic. `src/sectors.py` holds the roll-up and fails loudly on an unmapped
value rather than defaulting it.

**Seventeen rows carry no market data at all.** Two are dot-suffixed share-class
tickers (`BRK.B`, `BF.B`) that commonly fail a vendor symbol lookup. Several of
the rest are companies that have left the index through acquisition or
take-private — Hess, Catalent and Marathon Oil among them — which means the
constituent roster and the price vector were assembled at different times. A
handful are neither, so the gap is vendor coverage rather than a clean rule.

**`Price/Earnings` is never negative.** Where trailing EPS is negative the vendor
nulls the multiple instead: all 28 rows with a missing P/E and a present price
have negative EPS. So "P/E is missing" means "the company lost money", and
treating that missingness as random biases the retained sample towards
profitability. The pipeline separates the two and reports the count.

**`EBITDA` is missing for 43 rows,** and the absence is structural rather than
random: it is almost entirely banks, brokers and asset managers, for whom
interest expense is a cost of goods rather than a financing item and EBITDA is
not a meaningful measure. They are excluded from the margin work by rule and
retained everywhere else.

**`Dividend Yield` is blank on 104 rows.** In this source that means no dividend
recorded, not unknown — every payer has the field populated. The pipeline fills
zero and logs the count.

**Three companies appear twice.** Alphabet, Fox and News Corp each list two share
classes against one set of accounts. The junior class is flagged and excluded
from the analysis universes so one company is not counted as two.
