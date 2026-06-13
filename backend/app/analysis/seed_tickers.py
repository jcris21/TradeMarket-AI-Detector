"""100-ticker diversified seed universe for analysis_tickers.

This is the single source of truth for the analysis ticker universe.
Zero imports from db/ or app/ — pure data only.
"""

SEED_VERSION: str = "v1"

LEGACY_TICKERS: frozenset[str] = frozenset(
    {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}
)

SEED_TICKERS: list[dict[str, str]] = [
    # Technology (16)
    {"ticker": "AAPL", "sector": "Technology", "sub_sector": "Large Cap Tech"},
    {"ticker": "MSFT", "sector": "Technology", "sub_sector": "Large Cap Tech"},
    {"ticker": "NVDA", "sector": "Technology", "sub_sector": "Semiconductor"},
    {"ticker": "AVGO", "sector": "Technology", "sub_sector": "Semiconductor"},
    {"ticker": "ORCL", "sector": "Technology", "sub_sector": "Enterprise Software"},
    {"ticker": "CRM", "sector": "Technology", "sub_sector": "Enterprise Software"},
    {"ticker": "AMD", "sector": "Technology", "sub_sector": "Semiconductor"},
    {"ticker": "INTC", "sector": "Technology", "sub_sector": "Semiconductor"},
    {"ticker": "QCOM", "sector": "Technology", "sub_sector": "Semiconductor"},
    {"ticker": "TXN", "sector": "Technology", "sub_sector": "Semiconductor"},
    {"ticker": "ADBE", "sector": "Technology", "sub_sector": "Enterprise Software"},
    {"ticker": "NOW", "sector": "Technology", "sub_sector": "Enterprise Software"},
    {"ticker": "PANW", "sector": "Technology", "sub_sector": "Cybersecurity"},
    {"ticker": "SNOW", "sector": "Technology", "sub_sector": "Cloud Data"},
    {"ticker": "MU", "sector": "Technology", "sub_sector": "Semiconductor"},
    {"ticker": "AMAT", "sector": "Technology", "sub_sector": "Semiconductor Equipment"},
    # Communication Services (10)
    {"ticker": "GOOGL", "sector": "Communication Services", "sub_sector": "Search & Advertising"},
    {"ticker": "META", "sector": "Communication Services", "sub_sector": "Social Media"},
    {"ticker": "NFLX", "sector": "Communication Services", "sub_sector": "Streaming"},
    {"ticker": "DIS", "sector": "Communication Services", "sub_sector": "Media & Entertainment"},
    {"ticker": "CMCSA", "sector": "Communication Services", "sub_sector": "Telecom & Media"},
    {"ticker": "T", "sector": "Communication Services", "sub_sector": "Telecom"},
    {"ticker": "VZ", "sector": "Communication Services", "sub_sector": "Telecom"},
    {"ticker": "SNAP", "sector": "Communication Services", "sub_sector": "Social Media"},
    {"ticker": "SPOT", "sector": "Communication Services", "sub_sector": "Streaming"},
    {"ticker": "TMUS", "sector": "Communication Services", "sub_sector": "Telecom"},
    # Consumer Discretionary (10)
    {"ticker": "AMZN", "sector": "Consumer Discretionary", "sub_sector": "E-commerce"},
    {"ticker": "TSLA", "sector": "Consumer Discretionary", "sub_sector": "EV & Auto"},
    {"ticker": "HD", "sector": "Consumer Discretionary", "sub_sector": "Home Improvement"},
    {"ticker": "MCD", "sector": "Consumer Discretionary", "sub_sector": "Restaurants"},
    {"ticker": "NKE", "sector": "Consumer Discretionary", "sub_sector": "Sportswear"},
    {"ticker": "SBUX", "sector": "Consumer Discretionary", "sub_sector": "Restaurants"},
    {"ticker": "LOW", "sector": "Consumer Discretionary", "sub_sector": "Home Improvement"},
    {"ticker": "TGT", "sector": "Consumer Discretionary", "sub_sector": "Retail"},
    {"ticker": "BKNG", "sector": "Consumer Discretionary", "sub_sector": "Online Travel"},
    {"ticker": "GM", "sector": "Consumer Discretionary", "sub_sector": "Auto"},
    # Consumer Staples (8)
    {"ticker": "WMT", "sector": "Consumer Staples", "sub_sector": "Retail"},
    {"ticker": "PG", "sector": "Consumer Staples", "sub_sector": "Consumer Products"},
    {"ticker": "KO", "sector": "Consumer Staples", "sub_sector": "Beverages"},
    {"ticker": "PEP", "sector": "Consumer Staples", "sub_sector": "Beverages"},
    {"ticker": "COST", "sector": "Consumer Staples", "sub_sector": "Wholesale Retail"},
    {"ticker": "PM", "sector": "Consumer Staples", "sub_sector": "Tobacco"},
    {"ticker": "MO", "sector": "Consumer Staples", "sub_sector": "Tobacco"},
    {"ticker": "CL", "sector": "Consumer Staples", "sub_sector": "Consumer Products"},
    # Healthcare (13)
    {"ticker": "JNJ", "sector": "Healthcare", "sub_sector": "Pharma & Devices"},
    {"ticker": "LLY", "sector": "Healthcare", "sub_sector": "Pharmaceuticals"},
    {"ticker": "UNH", "sector": "Healthcare", "sub_sector": "Health Insurance"},
    {"ticker": "ABBV", "sector": "Healthcare", "sub_sector": "Pharmaceuticals"},
    {"ticker": "MRK", "sector": "Healthcare", "sub_sector": "Pharmaceuticals"},
    {"ticker": "PFE", "sector": "Healthcare", "sub_sector": "Pharmaceuticals"},
    {"ticker": "TMO", "sector": "Healthcare", "sub_sector": "Lab Equipment"},
    {"ticker": "ABT", "sector": "Healthcare", "sub_sector": "Medical Devices"},
    {"ticker": "DHR", "sector": "Healthcare", "sub_sector": "Life Sciences"},
    {"ticker": "BMY", "sector": "Healthcare", "sub_sector": "Pharmaceuticals"},
    {"ticker": "AMGN", "sector": "Healthcare", "sub_sector": "Biotech"},
    {"ticker": "GILD", "sector": "Healthcare", "sub_sector": "Biotech"},
    {"ticker": "ISRG", "sector": "Healthcare", "sub_sector": "Medical Robots"},
    # Financials (12)
    {"ticker": "JPM", "sector": "Financials", "sub_sector": "Banking"},
    {"ticker": "V", "sector": "Financials", "sub_sector": "Payment Processing"},
    {"ticker": "BAC", "sector": "Financials", "sub_sector": "Banking"},
    {"ticker": "MA", "sector": "Financials", "sub_sector": "Payment Processing"},
    {"ticker": "WFC", "sector": "Financials", "sub_sector": "Banking"},
    {"ticker": "GS", "sector": "Financials", "sub_sector": "Investment Banking"},
    {"ticker": "MS", "sector": "Financials", "sub_sector": "Investment Banking"},
    {"ticker": "BLK", "sector": "Financials", "sub_sector": "Asset Management"},
    {"ticker": "AXP", "sector": "Financials", "sub_sector": "Financial Services"},
    {"ticker": "C", "sector": "Financials", "sub_sector": "Banking"},
    {"ticker": "SCHW", "sector": "Financials", "sub_sector": "Brokerage"},
    {"ticker": "PYPL", "sector": "Financials", "sub_sector": "Fintech"},
    # Industrials (10)
    {"ticker": "CAT", "sector": "Industrials", "sub_sector": "Heavy Machinery"},
    {"ticker": "HON", "sector": "Industrials", "sub_sector": "Diversified Industrial"},
    {"ticker": "UNP", "sector": "Industrials", "sub_sector": "Railroad"},
    {"ticker": "RTX", "sector": "Industrials", "sub_sector": "Aerospace & Defense"},
    {"ticker": "LMT", "sector": "Industrials", "sub_sector": "Defense"},
    {"ticker": "GE", "sector": "Industrials", "sub_sector": "Aerospace"},
    {"ticker": "DE", "sector": "Industrials", "sub_sector": "Agricultural Machinery"},
    {"ticker": "UPS", "sector": "Industrials", "sub_sector": "Logistics"},
    {"ticker": "FDX", "sector": "Industrials", "sub_sector": "Logistics"},
    {"ticker": "ETN", "sector": "Industrials", "sub_sector": "Electrical Equipment"},
    # Energy (7)
    {"ticker": "XOM", "sector": "Energy", "sub_sector": "Oil & Gas"},
    {"ticker": "CVX", "sector": "Energy", "sub_sector": "Oil & Gas"},
    {"ticker": "COP", "sector": "Energy", "sub_sector": "Oil & Gas"},
    {"ticker": "SLB", "sector": "Energy", "sub_sector": "Oil Services"},
    {"ticker": "EOG", "sector": "Energy", "sub_sector": "Oil & Gas"},
    {"ticker": "MPC", "sector": "Energy", "sub_sector": "Refining"},
    {"ticker": "PSX", "sector": "Energy", "sub_sector": "Refining"},
    # Materials (5)
    {"ticker": "LIN", "sector": "Materials", "sub_sector": "Industrial Gases"},
    {"ticker": "SHW", "sector": "Materials", "sub_sector": "Paints & Coatings"},
    {"ticker": "FCX", "sector": "Materials", "sub_sector": "Copper Mining"},
    {"ticker": "NEM", "sector": "Materials", "sub_sector": "Gold Mining"},
    {"ticker": "APD", "sector": "Materials", "sub_sector": "Specialty Chemicals"},
    # Real Estate (5)
    {"ticker": "AMT", "sector": "Real Estate", "sub_sector": "Cell Tower REIT"},
    {"ticker": "PLD", "sector": "Real Estate", "sub_sector": "Industrial REIT"},
    {"ticker": "EQIX", "sector": "Real Estate", "sub_sector": "Data Center REIT"},
    {"ticker": "SPG", "sector": "Real Estate", "sub_sector": "Retail REIT"},
    {"ticker": "O", "sector": "Real Estate", "sub_sector": "Net Lease REIT"},
    # Utilities (4)
    {"ticker": "NEE", "sector": "Utilities", "sub_sector": "Electric Utilities"},
    {"ticker": "DUK", "sector": "Utilities", "sub_sector": "Electric Utilities"},
    {"ticker": "SO", "sector": "Utilities", "sub_sector": "Electric Utilities"},
    {"ticker": "AEP", "sector": "Utilities", "sub_sector": "Electric Utilities"},
]
