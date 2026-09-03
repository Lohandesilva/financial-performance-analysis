"""Sub-industry to GICS sector mapping.

The source column is labelled `Sector` but carries GICS **sub-industry** — 127
distinct values across 503 rows, a median of two constituents each. Grouping on
it directly makes every dispersion statistic meaningless: with 127 groups and
503 observations, a one-way ANOVA is fitting 126 parameters to 503 points and
will report a large eta-squared on pure noise.

The mapping below rolls sub-industries up to the eleven GICS sectors so the
"does sector explain margin" question can be asked at the level people actually
mean when they ask it. Sub-industry is retained as a second grouping so the
within-sector spread can be read too.

Two assignments are worth flagging because they moved in the March 2023 GICS
revision and are still commonly mis-mapped:

- Transaction & Payment Processing Services (Visa, Mastercard, Fiserv) sits in
  **Financials**, not Information Technology.
- Data Processing & Outsourced Services (Broadridge here) sits in
  **Industrials**, not Information Technology.
"""

from __future__ import annotations

SUBINDUSTRY_TO_SECTOR: dict[str, str] = {
    # --- Energy ---
    "Integrated Oil & Gas": "Energy",
    "Oil & Gas Equipment & Services": "Energy",
    "Oil & Gas Exploration & Production": "Energy",
    "Oil & Gas Refining & Marketing": "Energy",
    "Oil & Gas Storage & Transportation": "Energy",
    # --- Materials ---
    "Commodity Chemicals": "Materials",
    "Construction Materials": "Materials",
    "Copper": "Materials",
    "Fertilizers & Agricultural Chemicals": "Materials",
    "Gold": "Materials",
    "Industrial Gases": "Materials",
    "Metal, Glass & Plastic Containers": "Materials",
    "Paper & Plastic Packaging Products & Materials": "Materials",
    "Specialty Chemicals": "Materials",
    "Steel": "Materials",
    # --- Industrials ---
    "Aerospace & Defense": "Industrials",
    "Agricultural & Farm Machinery": "Industrials",
    "Air Freight & Logistics": "Industrials",
    "Building Products": "Industrials",
    "Cargo Ground Transportation": "Industrials",
    "Construction & Engineering": "Industrials",
    "Construction Machinery & Heavy Transportation Equipment": "Industrials",
    "Data Processing & Outsourced Services": "Industrials",
    "Diversified Support Services": "Industrials",
    "Electrical Components & Equipment": "Industrials",
    "Environmental & Facilities Services": "Industrials",
    "Heavy Electrical Equipment": "Industrials",
    "Human Resource & Employment Services": "Industrials",
    "Industrial Conglomerates": "Industrials",
    "Industrial Machinery & Supplies & Components": "Industrials",
    "Passenger Airlines": "Industrials",
    "Passenger Ground Transportation": "Industrials",
    "Rail Transportation": "Industrials",
    "Research & Consulting Services": "Industrials",
    "Trading Companies & Distributors": "Industrials",
    # --- Consumer Discretionary ---
    "Apparel Retail": "Consumer Discretionary",
    "Apparel, Accessories & Luxury Goods": "Consumer Discretionary",
    "Automobile Manufacturers": "Consumer Discretionary",
    "Automotive Parts & Equipment": "Consumer Discretionary",
    "Automotive Retail": "Consumer Discretionary",
    "Broadline Retail": "Consumer Discretionary",
    "Casinos & Gaming": "Consumer Discretionary",
    "Computer & Electronics Retail": "Consumer Discretionary",
    "Consumer Electronics": "Consumer Discretionary",
    "Distributors": "Consumer Discretionary",
    "Footwear": "Consumer Discretionary",
    "Home Furnishings": "Consumer Discretionary",
    "Home Improvement Retail": "Consumer Discretionary",
    "Homebuilding": "Consumer Discretionary",
    "Hotels, Resorts & Cruise Lines": "Consumer Discretionary",
    "Leisure Products": "Consumer Discretionary",
    "Other Specialty Retail": "Consumer Discretionary",
    "Restaurants": "Consumer Discretionary",
    # --- Consumer Staples ---
    "Agricultural Products & Services": "Consumer Staples",
    "Brewers": "Consumer Staples",
    "Consumer Staples Merchandise Retail": "Consumer Staples",
    "Distillers & Vintners": "Consumer Staples",
    "Drug Retail": "Consumer Staples",
    "Food Distributors": "Consumer Staples",
    "Food Retail": "Consumer Staples",
    "Household Products": "Consumer Staples",
    "Packaged Foods & Meats": "Consumer Staples",
    "Personal Care Products": "Consumer Staples",
    "Soft Drinks & Non-alcoholic Beverages": "Consumer Staples",
    "Tobacco": "Consumer Staples",
    # --- Health Care ---
    "Biotechnology": "Health Care",
    "Health Care Distributors": "Health Care",
    "Health Care Equipment": "Health Care",
    "Health Care Facilities": "Health Care",
    "Health Care Services": "Health Care",
    "Health Care Supplies": "Health Care",
    "Health Care Technology": "Health Care",
    "Life Sciences Tools & Services": "Health Care",
    "Managed Health Care": "Health Care",
    "Pharmaceuticals": "Health Care",
    # --- Financials ---
    "Asset Management & Custody Banks": "Financials",
    "Consumer Finance": "Financials",
    "Diversified Banks": "Financials",
    "Financial Exchanges & Data": "Financials",
    "Insurance Brokers": "Financials",
    "Investment Banking & Brokerage": "Financials",
    "Life & Health Insurance": "Financials",
    "Multi-Sector Holdings": "Financials",
    "Multi-line Insurance": "Financials",
    "Property & Casualty Insurance": "Financials",
    "Regional Banks": "Financials",
    "Reinsurance": "Financials",
    "Transaction & Payment Processing Services": "Financials",
    # --- Information Technology ---
    "Application Software": "Information Technology",
    "Communications Equipment": "Information Technology",
    "Electronic Components": "Information Technology",
    "Electronic Equipment & Instruments": "Information Technology",
    "Electronic Manufacturing Services": "Information Technology",
    "IT Consulting & Other Services": "Information Technology",
    "Internet Services & Infrastructure": "Information Technology",
    "Semiconductor Materials & Equipment": "Information Technology",
    "Semiconductors": "Information Technology",
    "Systems Software": "Information Technology",
    "Technology Distributors": "Information Technology",
    "Technology Hardware, Storage & Peripherals": "Information Technology",
    # --- Communication Services ---
    "Advertising": "Communication Services",
    "Broadcasting": "Communication Services",
    "Cable & Satellite": "Communication Services",
    "Integrated Telecommunication Services": "Communication Services",
    "Interactive Home Entertainment": "Communication Services",
    "Interactive Media & Services": "Communication Services",
    "Movies & Entertainment": "Communication Services",
    "Publishing": "Communication Services",
    "Wireless Telecommunication Services": "Communication Services",
    # --- Utilities ---
    "Electric Utilities": "Utilities",
    "Gas Utilities": "Utilities",
    "Independent Power Producers & Energy Traders": "Utilities",
    "Multi-Utilities": "Utilities",
    "Water Utilities": "Utilities",
    # --- Real Estate ---
    "Data Center REITs": "Real Estate",
    "Health Care REITs": "Real Estate",
    "Hotel & Resort REITs": "Real Estate",
    "Industrial REITs": "Real Estate",
    "Multi-Family Residential REITs": "Real Estate",
    "Office REITs": "Real Estate",
    "Other Specialized REITs": "Real Estate",
    "Real Estate Services": "Real Estate",
    "Retail REITs": "Real Estate",
    "Self-Storage REITs": "Real Estate",
    "Single-Family Residential REITs": "Real Estate",
    "Telecom Tower REITs": "Real Estate",
    "Timber REITs": "Real Estate",
}

# Sectors whose reported "revenue" and "margin" are not comparable to an
# operating company's. Banks and insurers report interest and premium income;
# REITs report rental revenue against a depreciating asset base. They stay in
# the dataset and in the valuation work, but the margin dispersion analysis
# flags them rather than pretending a bank's EBITDA margin means the same thing
# as a software company's.
NON_OPERATING_MARGIN_SECTORS = ("Financials", "Real Estate")


def map_sector(subindustry: str) -> str:
    """Roll a GICS sub-industry up to its sector, loudly if unmapped."""
    try:
        return SUBINDUSTRY_TO_SECTOR[subindustry]
    except KeyError as exc:  # a new constituent would otherwise vanish into "Other"
        raise KeyError(
            f"Unmapped GICS sub-industry {subindustry!r}. Add it to "
            "SUBINDUSTRY_TO_SECTOR rather than defaulting it."
        ) from exc
