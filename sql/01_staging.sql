-- Staging model for the constituent fundamentals analysis.
-- PostgreSQL. Loads the raw extract, casts it, rolls GICS sub-industry up to
-- sector, and derives the same fundamentals as src/derive.py so the SQL and the
-- Python path can be reconciled row for row.
--
-- Load the raw file first, e.g.
--   \copy raw_sp500_financials from 'data/raw/sp500_constituents_financials.csv' with (format csv, header true)

drop table if exists dim_gics_sector cascade;
drop table if exists stg_constituents cascade;

-- ---------------------------------------------------------------------------
-- The source column named "Sector" carries GICS *sub-industry*: 127 distinct
-- values across 503 rows. Grouping on it directly makes every dispersion
-- statistic meaningless, so it is rolled up here. The mapping lives in a table
-- rather than a CASE expression so a new constituent produces a NULL join that
-- the assertion at the bottom of this file catches, instead of silently
-- landing in an "Other" bucket.
-- ---------------------------------------------------------------------------
create table dim_gics_sector (
    sub_industry text primary key,
    sector       text not null
);

-- src/sectors.py is the single definition of the mapping; `make analysis`
-- writes it out so this table and the Python path cannot drift apart. Two
-- assignments moved in the March 2023 GICS revision and are still commonly
-- mis-mapped: Transaction & Payment Processing Services belongs to Financials,
-- and Data Processing & Outsourced Services to Industrials.
\copy dim_gics_sector from 'outputs/tables/gics_sector_mapping.csv' with (format csv, header true)

create table stg_constituents as
with raw as (
    select
        trim("Symbol")                              as symbol,
        trim("Name")                                as company_name,
        trim("Sector")                              as sub_industry,
        cast("Price"           as numeric(18, 4))   as price,
        cast("Price/Earnings"  as numeric(18, 6))   as price_to_earnings,
        cast("Dividend Yield"  as numeric(18, 6))   as dividend_yield,
        cast("Earnings/Share"  as numeric(18, 4))   as eps,
        cast("52 Week Low"     as numeric(18, 4))   as week52_low,
        cast("52 Week High"    as numeric(18, 4))   as week52_high,
        cast("Market Cap"      as numeric(24, 2))   as market_cap,
        cast("EBITDA"          as numeric(24, 2))   as ebitda,
        cast("Price/Sales"     as numeric(18, 6))   as price_to_sales,
        cast("Price/Book"      as numeric(18, 6))   as price_to_book
    from raw_sp500_financials
),

typed as (
    select
        r.*,
        s.sector,
        -- A missing dividend yield means the vendor recorded no dividend, not
        -- that the value is unknown: every payer has the field populated. The
        -- coalesce is therefore a claim about the world and is logged as such
        -- in the Python pipeline's data-quality block.
        coalesce(r.dividend_yield, 0)                                as dividend_yield_filled,
        -- Alphabet, Fox and News Corp each list two share classes against one
        -- set of accounts. The junior class is flagged, not deleted, so the
        -- count of affected rows stays visible downstream.
        (r.symbol in ('GOOG', 'FOX', 'NWS'))                         as is_dual_class_secondary
    from raw r
    left join dim_gics_sector s on s.sub_industry = r.sub_industry
),

-- ---------------------------------------------------------------------------
-- Derived fundamentals. Each is an accounting identity, not an estimate:
--
--   shares      = market cap / price
--   revenue     = market cap / (P/S)      because P/S = (M/S) / (Rev/S) = M / Rev
--   book equity = market cap / (P/B)      same per-share cancellation
--   net income  = EPS x shares
--   ROE         = (P/B) / (P/E)           = (P/B) x (E/P) = E/B; price cancels
--   payout      = (D/P) x (P/E)           = D/E;            price cancels
--   E/P         = 1 / (P/E)
--   g_sustain   = ROE x (1 - payout)      Gordon sustainable growth
-- ---------------------------------------------------------------------------
derived as (
    select
        t.*,
        market_cap / nullif(price, 0)                               as shares_outstanding,
        market_cap / nullif(price_to_sales, 0)                      as revenue,
        market_cap / nullif(price_to_book, 0)                       as book_equity,
        eps * (market_cap / nullif(price, 0))                       as net_income,
        price_to_book / nullif(price_to_earnings, 0)                as roe,
        dividend_yield_filled * price_to_earnings                   as payout_ratio,
        1.0 / nullif(price_to_earnings, 0)                          as earnings_yield
    from typed t
)

select
    d.*,
    ebitda     / nullif(revenue, 0)                                 as ebitda_margin,
    net_income / nullif(revenue, 0)                                 as net_margin,
    1 - payout_ratio                                                as retention_ratio,
    roe * (1 - payout_ratio)                                        as sustainable_growth,
    revenue / nullif(book_equity, 0)                                as asset_turnover_proxy,
    (price - week52_low) / nullif(week52_high - week52_low, 0)      as range_position,

    -- Universe flags. Three nested universes rather than one "clean" table: a
    -- company with negative book equity is unusable for ROE and perfectly
    -- usable for an EBITDA margin, and collapsing both decisions into one
    -- filter throws away observations for no reason.
    (price is not null and market_cap is not null
     and not (symbol in ('GOOG', 'FOX', 'NWS')))                    as in_base,

    (price is not null and market_cap is not null
     and not (symbol in ('GOOG', 'FOX', 'NWS'))
     and revenue > 0
     and ebitda is not null
     and ebitda / nullif(revenue, 0) between -1.0 and 1.0)          as in_margin,

    (price is not null and market_cap is not null
     and not (symbol in ('GOOG', 'FOX', 'NWS'))
     and eps > 0
     and price_to_earnings > 0
     and price_to_book > 0 and price_to_book <= 250
     and dividend_yield_filled * price_to_earnings <= 1.0)          as in_returns
from derived d;

alter table stg_constituents add primary key (symbol);
create index on stg_constituents (sector, sub_industry);

-- in_core is the intersection of the two, held as a generated column so no
-- downstream query can define it differently from the Python pipeline.
alter table stg_constituents
    add column in_core boolean generated always as (in_margin and in_returns) stored;

create index on stg_constituents (in_core);


-- ---------------------------------------------------------------------------
-- Assertions. Every one of these should return zero failures. If it does not,
-- the source has changed shape and the derivations downstream are no longer
-- safe to read.
-- ---------------------------------------------------------------------------
select 'unmapped_sub_industry' as check_name, count(*) as failures
from stg_constituents where sector is null

union all
-- Market capitalisation must equal price times the share count it implies.
select 'shares_identity_broken', count(*)
from stg_constituents
where price is not null and market_cap is not null
  and abs(shares_outstanding * price - market_cap) > 1.0

union all
-- The source never reports a negative P/E: where trailing EPS is negative it
-- nulls the multiple instead. If that ever changes, the loss-making
-- constituents stop being identifiable by the EPS sign alone.
select 'negative_pe_present', count(*)
from stg_constituents where price_to_earnings < 0

union all
-- P/E is computed by the vendor as price / EPS, which makes the two routes to
-- net income the same expression. This assertion is a tripwire on that: if it
-- ever fails, M/(P/E) and EPS x shares have become independent and both should
-- be reported.
select 'pe_not_price_over_eps', count(*)
from stg_constituents
where price_to_earnings is not null and eps <> 0
  and abs(price_to_earnings - price / eps) > 0.001

union all
select 'duplicate_symbol', count(*) - count(distinct symbol) from stg_constituents

union all
-- Every retained ROE must reproduce net income over book equity to rounding.
select 'roe_identity_broken', count(*)
from stg_constituents
where in_returns and abs(roe - net_income / nullif(book_equity, 0)) > 0.0001;
