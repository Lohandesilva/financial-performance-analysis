-- Metric definitions. One place where each measure is defined, so the
-- dashboard, the Python pipeline and any ad-hoc query agree on what "margin",
-- "ROE" and "implied growth" mean.
--
-- Every view states the universe it runs on in its first WHERE clause. That is
-- deliberate repetition: a query that silently uses the wrong universe returns
-- a plausible number, which is the worst kind of wrong.

-- ---------------------------------------------------------------------------
-- Index position. The two margin figures sit side by side because they answer
-- different questions: the aggregate is what the index earns on a dollar of
-- revenue, the median is what a typical constituent earns, and the gap between
-- them is the weight of the largest companies.
-- ---------------------------------------------------------------------------
create or replace view vw_index_position as
select
    count(*) filter (where in_base)                     as companies,
    sum(market_cap) filter (where in_base)              as index_market_cap,
    count(*) filter (where in_core)                     as core_companies,
    sum(revenue)    filter (where in_core)              as core_revenue,
    sum(ebitda)     filter (where in_core)              as core_ebitda,
    sum(net_income) filter (where in_core)              as core_net_income,
    sum(ebitda)     filter (where in_core)
        / nullif(sum(revenue) filter (where in_core), 0)    as aggregate_ebitda_margin,
    sum(net_income) filter (where in_core)
        / nullif(sum(revenue) filter (where in_core), 0)    as aggregate_net_margin,
    percentile_cont(0.5) within group (order by ebitda_margin)
        filter (where in_margin)                            as median_ebitda_margin,
    percentile_cont(0.5) within group (order by roe)
        filter (where in_core)                              as median_roe,
    percentile_cont(0.5) within group (order by price_to_earnings)
        filter (where in_core)                              as median_pe,
    -- Cap-weighted P/E is total market cap over total earnings, not the average
    -- of the multiples. The average of a ratio is not the ratio of the sums and
    -- the difference here is several turns.
    sum(market_cap) filter (where in_core)
        / nullif(sum(net_income) filter (where in_core), 0) as cap_weighted_pe
from stg_constituents;


-- ---------------------------------------------------------------------------
-- Data-integrity screen, reported rather than applied silently. Rule counts
-- overlap: a row can trip several at once, so they sum to more than the number
-- of rows any universe loses.
-- ---------------------------------------------------------------------------
create or replace view vw_exclusion_reasons as
select 'no_market_data' as rule, count(*) as rows_failing,
       sum(market_cap) as market_cap_affected
from stg_constituents where price is null and market_cap is null
union all
select 'dual_class_secondary', count(*), sum(market_cap)
from stg_constituents where is_dual_class_secondary
union all
select 'negative_trailing_eps', count(*), sum(market_cap)
from stg_constituents where eps <= 0
union all
select 'non_positive_book_equity', count(*), sum(market_cap)
from stg_constituents where price_to_book <= 0
union all
select 'ebitda_not_reported', count(*), sum(market_cap)
from stg_constituents where ebitda is null and price is not null
union all
select 'payout_above_earnings', count(*), sum(market_cap)
from stg_constituents where payout_ratio > 1.0
order by rows_failing desc;


-- ---------------------------------------------------------------------------
-- Sector profitability dispersion.
-- Medians and quartiles rather than means: the margin distribution has a long
-- right tail and a handful of observations would otherwise set the level.
-- The `within_sector_iqr` column is the one to read against
-- `iqr_of_sector_medians` in vw_margin_spread below.
-- ---------------------------------------------------------------------------
create or replace view vw_sector_margins as
select
    sector,
    count(*)                                                        as constituents,
    sum(market_cap)                                                 as market_cap,
    percentile_cont(0.10) within group (order by ebitda_margin)     as p10,
    percentile_cont(0.25) within group (order by ebitda_margin)     as q1,
    percentile_cont(0.50) within group (order by ebitda_margin)     as median_ebitda_margin,
    percentile_cont(0.75) within group (order by ebitda_margin)     as q3,
    percentile_cont(0.90) within group (order by ebitda_margin)     as p90,
    percentile_cont(0.75) within group (order by ebitda_margin)
      - percentile_cont(0.25) within group (order by ebitda_margin) as within_sector_iqr,
    -- Flagged, not filtered. A bank's interest income and a REIT's rental
    -- revenue are not comparable to an operating company's turnover, and
    -- leaving them unmarked is what makes the sector effect look larger than
    -- it is.
    (sector in ('Financials', 'Real Estate'))                       as non_operating_margin
from stg_constituents
where in_margin
group by sector
order by median_ebitda_margin desc;


-- ---------------------------------------------------------------------------
-- The variance decomposition, in SQL. eta-squared is the between-sector share
-- of total sum of squares; omega-squared corrects it for the number of groups,
-- which matters because the correction is large when groups are many and thin.
-- ---------------------------------------------------------------------------
create or replace view vw_margin_variance_decomposition as
with base as (
    select sector, ebitda_margin from stg_constituents where in_margin
),
grand as (
    select avg(ebitda_margin) as grand_mean, count(*) as n from base
),
by_sector as (
    select sector, count(*) as n_g, avg(ebitda_margin) as mean_g from base group by sector
),
sums as (
    select
        (select sum(power(ebitda_margin - g.grand_mean, 2)) from base, grand g) as ss_total,
        (select sum(n_g * power(mean_g - g.grand_mean, 2)) from by_sector, grand g) as ss_between,
        (select count(*) from by_sector) as k,
        (select n from grand) as n
)
select
    k                                               as groups,
    n                                               as observations,
    ss_between / ss_total                           as eta_squared,
    (ss_between - (k - 1) * ((ss_total - ss_between) / (n - k)))
        / (ss_total + ((ss_total - ss_between) / (n - k)))  as omega_squared,
    1 - ss_between / ss_total                       as share_within_sector
from sums;


-- ---------------------------------------------------------------------------
-- The spread comparison in units a reader can price: if the typical sector is
-- internally wider than the sectors are from each other, then knowing the
-- sector tells you less than knowing the position within it.
-- ---------------------------------------------------------------------------
create or replace view vw_margin_spread as
select
    percentile_cont(0.50) within group (order by within_sector_iqr)  as median_within_sector_iqr,
    percentile_cont(0.75) within group (order by median_ebitda_margin)
      - percentile_cont(0.25) within group (order by median_ebitda_margin)
                                                                     as iqr_of_sector_medians,
    max(median_ebitda_margin) - min(median_ebitda_margin)            as range_of_sector_medians
from vw_sector_margins;


-- ---------------------------------------------------------------------------
-- Price-to-book decomposition. Exact, not fitted:
--
--     log(P/B) = log(ROE) + log(P/E)
--
-- so the variance of the book multiple splits into a return component, a
-- valuation component and the covariance between them. It answers "does the
-- market pay for quality" more cleanly than any regression can here, because
-- both candidate regressors are algebraic rearrangements of the multiples.
-- ---------------------------------------------------------------------------
create or replace view vw_book_multiple_decomposition as
with logs as (
    select ln(price_to_book) as log_pb, ln(roe) as log_roe, ln(price_to_earnings) as log_pe
    from stg_constituents
    where in_core and roe > 0
)
select
    count(*)                                    as n,
    var_samp(log_pb)                            as var_log_pb,
    var_samp(log_roe)                           as var_log_roe,
    var_samp(log_pe)                            as var_log_pe,
    2 * covar_samp(log_roe, log_pe)             as covariance_term,
    var_samp(log_roe)  / var_samp(log_pb)       as share_from_roe,
    var_samp(log_pe)   / var_samp(log_pb)       as share_from_valuation,
    2 * covar_samp(log_roe, log_pe) / var_samp(log_pb) as share_from_covariance,
    corr(log_roe, log_pe)                       as corr_log_roe_log_pe,
    max(abs(log_pb - log_roe - log_pe))         as identity_max_residual
from logs;


-- ---------------------------------------------------------------------------
-- Implied growth screen.
--
--   fundable  = ROE x (1 - payout)                Gordon sustainable growth
--   priced in = r - (E/P) x b                     Gordon inverted at a constant
--                                                 terminal payout b
--
-- Both parameters are held in a one-row assumptions table rather than inlined,
-- so a sweep is a single UPDATE and no view has to be edited.
-- ---------------------------------------------------------------------------
drop table if exists valuation_assumptions;
create table valuation_assumptions (
    cost_of_equity    numeric not null,
    terminal_payout   numeric not null,
    gap_threshold     numeric not null,
    roe_ceiling       numeric not null,   -- above this the SGR stops binding
    pe_ceiling        numeric not null    -- above this E/P is ~0 and the gap is mechanical
);
insert into valuation_assumptions values (0.09, 0.45, 0.02, 0.40, 100);

create or replace view vw_growth_screen as
select
    c.symbol,
    c.company_name,
    c.sector,
    c.market_cap,
    c.roe,
    c.payout_ratio,
    c.price_to_earnings,
    c.earnings_yield,
    c.sustainable_growth,
    a.cost_of_equity - c.earnings_yield * a.terminal_payout        as priced_in_growth,
    c.sustainable_growth
        - (a.cost_of_equity - c.earnings_yield * a.terminal_payout) as growth_gap,
    -- Above the ROE ceiling, sustained buybacks have shrunk book equity to the
    -- point where it no longer constrains growth, and ROE x retention returns a
    -- rate in the hundreds of percent. Above the P/E ceiling the earnings yield
    -- is near zero and the gap is a statement about the denominator.
    (c.roe <= a.roe_ceiling and c.price_to_earnings <= a.pe_ceiling) as in_screen,
    case
        when c.sustainable_growth
             - (a.cost_of_equity - c.earnings_yield * a.terminal_payout) < -a.gap_threshold
            then 'priced above what it can fund'
        when c.sustainable_growth
             - (a.cost_of_equity - c.earnings_yield * a.terminal_payout) > a.gap_threshold
            then 'can fund more than priced in'
        else 'broadly consistent'
    end                                                             as verdict
from stg_constituents c
cross join valuation_assumptions a
where c.in_core
order by growth_gap;


-- Sector composition of the deficit list. If the flagged names cluster in
-- high-payout sectors then the screen is reading distribution policy, not
-- mispricing, and the output should be described that way.
create or replace view vw_growth_deficit_by_sector as
select
    sector,
    count(*)                                    as flagged,
    sum(market_cap)                             as market_cap,
    avg(payout_ratio)                           as mean_payout,
    avg(roe)                                    as mean_roe,
    avg(growth_gap)                             as mean_gap
from vw_growth_screen
where in_screen and verdict = 'priced above what it can fund'
group by sector
order by flagged desc;


-- ---------------------------------------------------------------------------
-- Peer benchmarking within a sector. Ranks are computed inside the sector
-- because the question is which of these is the better holding against its own
-- alternatives, not whether the sector is attractive.
-- ---------------------------------------------------------------------------
create or replace view vw_peer_benchmark as
with ranked as (
    select
        symbol, company_name, sector, sub_industry, market_cap,
        ebitda_margin, net_margin, roe, price_to_earnings, earnings_yield,
        percent_rank() over (partition by sector order by ebitda_margin)   as rank_margin,
        percent_rank() over (partition by sector order by roe)             as rank_roe,
        percent_rank() over (partition by sector order by earnings_yield)  as rank_earnings_yield
    from stg_constituents
    where in_core
)
select
    r.*,
    (rank_margin + rank_roe + rank_earnings_yield) / 3.0    as composite_rank,
    case
        when rank_margin >= 0.5 and rank_roe >= 0.5 and rank_earnings_yield >= 0.5
            then 'quality at a discount'
        when rank_margin >= 0.5 and rank_roe >= 0.5
            then 'quality, fully priced'
        when rank_earnings_yield >= 0.5
            then 'cheap on price alone'
        else 'expensive without the quality'
    end                                                     as classification
from ranked r
order by sector, composite_rank desc;


-- ---------------------------------------------------------------------------
-- Assertions on the metric layer.
-- ---------------------------------------------------------------------------
select 'payout_identity_broken' as check_name, count(*) as failures
from stg_constituents
where in_core and abs(payout_ratio - dividend_yield_filled * price_to_earnings) > 1e-9

union all
-- Retention and payout must sum to one for every retained row.
select 'retention_not_complement_of_payout', count(*)
from stg_constituents where in_core and abs(retention_ratio + payout_ratio - 1) > 1e-9

union all
-- The log identity underlying the decomposition, checked directly.
select 'book_multiple_identity_broken', count(*)
from stg_constituents
where in_core and roe > 0
  and abs(ln(price_to_book) - ln(roe) - ln(price_to_earnings)) > 1e-9

union all
-- Every screened row must sit in exactly one verdict bucket.
select 'growth_screen_verdict_missing', count(*)
from vw_growth_screen where verdict is null;
