"""Static U.S. index membership lists for screener filtering.

Generated from public component tables on 2026-07-12. These lists are
local reference data so screener filtering does not depend on live network
requests. Refresh periodically when index providers rebalance.
"""

from __future__ import annotations

US_INDEX_DEFINITIONS = [
    {
        "value": "sp500",
        "label": "S&P 500",
        "source_url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "symbols": frozenset(
            [
                'MMM', 'AOS', 'ABT', 'ABBV', 'ACN', 'ADBE', 'AMD', 'AES', 'AFL', 'A', 'APD', 'ABNB',
                'AKAM', 'ALB', 'ARE', 'ALGN', 'ALLE', 'LNT', 'ALL', 'GOOGL', 'GOOG', 'MO', 'AMZN', 'AMCR',
                'AEE', 'AEP', 'AXP', 'AIG', 'AMT', 'AWK', 'AMP', 'AME', 'AMGN', 'APH', 'ADI', 'AON',
                'APA', 'APO', 'AAPL', 'AMAT', 'APP', 'APTV', 'ACGL', 'ADM', 'ARES', 'ANET', 'AJG', 'AIZ',
                'T', 'ATO', 'ADSK', 'ADP', 'AZO', 'AVB', 'AVY', 'AXON', 'BKR', 'BALL', 'BAC', 'BAX',
                'BDX', 'BRK.B', 'BBY', 'TECH', 'BIIB', 'BLK', 'BX', 'XYZ', 'BNY', 'BA', 'BKNG', 'BSX',
                'BMY', 'AVGO', 'BR', 'BRO', 'BF.B', 'BLDR', 'BG', 'BXP', 'CHRW', 'CDNS', 'CPT', 'COF',
                'CAH', 'CCL', 'CARR', 'CVNA', 'CASY', 'CAT', 'CBOE', 'CBRE', 'CDW', 'COR', 'CNC', 'CNP',
                'CF', 'CRL', 'SCHW', 'CHTR', 'CVX', 'CMG', 'CB', 'CHD', 'CIEN', 'CI', 'CINF', 'CTAS',
                'CSCO', 'C', 'CFG', 'CLX', 'CME', 'CMS', 'KO', 'CTSH', 'COHR', 'COIN', 'CL', 'CMCSA',
                'FIX', 'COP', 'ED', 'STZ', 'CEG', 'COO', 'CPRT', 'GLW', 'CPAY', 'CTVA', 'CSGP', 'COST',
                'CRH', 'CRWD', 'CCI', 'CSX', 'CMI', 'CVS', 'DHR', 'DRI', 'DDOG', 'DVA', 'DECK', 'DE',
                'DELL', 'DAL', 'DVN', 'DXCM', 'FANG', 'DLR', 'DG', 'DLTR', 'D', 'DPZ', 'DASH', 'DOV',
                'DOW', 'DHI', 'DTE', 'DUK', 'DD', 'ETN', 'EBAY', 'ECHO', 'ECL', 'EIX', 'EW', 'EA',
                'ELV', 'EME', 'EMR', 'ETR', 'EOG', 'EQT', 'EFX', 'EQIX', 'EQR', 'ERIE', 'ESS', 'EL',
                'EG', 'EVRG', 'ES', 'EXC', 'EXE', 'EXPE', 'EXPD', 'EXR', 'XOM', 'FFIV', 'FDS', 'FICO',
                'FAST', 'FRT', 'FDX', 'FDXF', 'FIS', 'FITB', 'FSLR', 'FE', 'FISV', 'FLEX', 'F', 'FTNT',
                'FTV', 'FOXA', 'FOX', 'BEN', 'FCX', 'GRMN', 'IT', 'GE', 'GEHC', 'GEV', 'GEN', 'GNRC',
                'GD', 'GIS', 'GM', 'GPC', 'GILD', 'GPN', 'GL', 'GDDY', 'GS', 'HAL', 'HIG', 'HAS',
                'HCA', 'DOC', 'HSIC', 'HSY', 'HPE', 'HLT', 'HD', 'HONA', 'HON', 'HRL', 'HST', 'HWM',
                'HPQ', 'HUBB', 'HUM', 'HBAN', 'HII', 'IBM', 'IEX', 'IDXX', 'ITW', 'INCY', 'IR', 'PODD',
                'INTC', 'IBKR', 'ICE', 'IFF', 'IP', 'INTU', 'ISRG', 'IVZ', 'INVH', 'IQV', 'IRM', 'JBHT',
                'JBL', 'JKHY', 'J', 'JNJ', 'JCI', 'JPM', 'KVUE', 'KDP', 'KEY', 'KEYS', 'KMB', 'KIM',
                'KMI', 'KKR', 'KLAC', 'KHC', 'KR', 'LHX', 'LH', 'LRCX', 'LVS', 'LDOS', 'LEN', 'LII',
                'LLY', 'LIN', 'LYV', 'LMT', 'L', 'LOW', 'LULU', 'LITE', 'LYB', 'MTB', 'MPC', 'MAR',
                'MRSH', 'MLM', 'MRVL', 'MAS', 'MA', 'MKC', 'MCD', 'MCK', 'MDT', 'MRK', 'META', 'MET',
                'MTD', 'MGM', 'MCHP', 'MU', 'MSFT', 'MAA', 'MRNA', 'TAP', 'MDLZ', 'MPWR', 'MNST', 'MCO',
                'MS', 'MOS', 'MSI', 'MSCI', 'NDAQ', 'NTAP', 'NFLX', 'NEM', 'NWSA', 'NWS', 'NEE', 'NKE',
                'NI', 'NDSN', 'NSC', 'NTRS', 'NOC', 'NCLH', 'NRG', 'NUE', 'NVDA', 'NVR', 'NXPI', 'ORLY',
                'OXY', 'ODFL', 'OMC', 'ON', 'OKE', 'ORCL', 'OTIS', 'PCAR', 'PKG', 'PLTR', 'PANW', 'PSKY',
                'PH', 'PAYX', 'PYPL', 'PNR', 'PEP', 'PFE', 'PCG', 'PM', 'PSX', 'PNW', 'PNC', 'PPG',
                'PPL', 'PFG', 'PG', 'PGR', 'PLD', 'PRU', 'PEG', 'PTC', 'PSA', 'PHM', 'PWR', 'QCOM',
                'DGX', 'Q', 'RL', 'RJF', 'RTX', 'O', 'REG', 'REGN', 'RF', 'RSG', 'RMD', 'RVTY',
                'HOOD', 'ROK', 'ROL', 'ROP', 'ROST', 'RCL', 'SPGI', 'CRM', 'SNDK', 'SBAC', 'SLB', 'STX',
                'SRE', 'NOW', 'SHW', 'SPG', 'SWKS', 'SJM', 'SW', 'SNA', 'SOLV', 'SO', 'LUV', 'SWK',
                'SBUX', 'STT', 'STLD', 'STE', 'SYK', 'SMCI', 'SYF', 'SNPS', 'SYY', 'TMUS', 'TROW', 'TTWO',
                'TPR', 'TRGP', 'TGT', 'TEL', 'TDY', 'TER', 'TSLA', 'TXN', 'TPL', 'TXT', 'TMO', 'TJX',
                'TKO', 'TTD', 'TSCO', 'TT', 'TDG', 'TRV', 'TRMB', 'TFC', 'TYL', 'TSN', 'USB', 'UBER',
                'UDR', 'ULTA', 'UNP', 'UAL', 'UPS', 'URI', 'UNH', 'UHS', 'VLO', 'VEEV', 'VTR', 'VLTO',
                'VRSN', 'VRSK', 'VZ', 'VRTX', 'VRT', 'VTRS', 'VICI', 'V', 'VST', 'VMC', 'WRB', 'GWW',
                'WAB', 'WMT', 'DIS', 'WBD', 'WM', 'WAT', 'WEC', 'WFC', 'WELL', 'WST', 'WDC', 'WY',
                'WSM', 'WMB', 'WTW', 'WDAY', 'WYNN', 'XEL', 'XYL', 'YUM', 'ZBRA', 'ZBH', 'ZTS',
            ]
        ),
    },
    {
        "value": "sp100",
        "label": "S&P 100",
        "source_url": "https://en.wikipedia.org/wiki/S%26P_100",
        "symbols": frozenset(
            [
                'AAPL', 'ABBV', 'ABT', 'ACN', 'ADBE', 'AMAT', 'AMD', 'AMGN', 'AMT', 'AMZN', 'AVGO', 'AXP',
                'BA', 'BAC', 'BKNG', 'BLK', 'BMY', 'BNY', 'BRK.B', 'C', 'CAT', 'CL', 'CMCSA', 'COF',
                'COP', 'COST', 'CRM', 'CSCO', 'CVS', 'CVX', 'DE', 'DHR', 'DIS', 'DUK', 'EMR', 'FDX',
                'GD', 'GE', 'GEV', 'GILD', 'GM', 'GOOG', 'GOOGL', 'GS', 'HD', 'HONA', 'IBM', 'INTC',
                'INTU', 'ISRG', 'JNJ', 'JPM', 'KO', 'LIN', 'LLY', 'LMT', 'LOW', 'LRCX', 'MA', 'MCD',
                'MDLZ', 'MDT', 'META', 'MMM', 'MO', 'MRK', 'MS', 'MSFT', 'MU', 'NEE', 'NFLX', 'NKE',
                'NOW', 'NVDA', 'ORCL', 'PEP', 'PFE', 'PG', 'PLTR', 'PM', 'QCOM', 'RTX', 'SBUX', 'SCHW',
                'SO', 'SPG', 'T', 'TMO', 'TMUS', 'TSLA', 'TXN', 'UBER', 'UNH', 'UNP', 'UPS', 'USB',
                'V', 'VZ', 'WFC', 'WMT', 'XOM',
            ]
        ),
    },
    {
        "value": "nasdaq100",
        "label": "Nasdaq 100",
        "source_url": "https://de.wikipedia.org/wiki/Nasdaq-100",
        "symbols": frozenset(
            [
                'AAPL', 'ABNB', 'ADBE', 'ADI', 'ADP', 'ADSK', 'AEP', 'ALAB', 'ALNY', 'AMAT', 'AMD', 'AMGN',
                'AMZN', 'APP', 'ARM', 'ASML', 'AVGO', 'AXON', 'BKNG', 'BKR', 'CCEP', 'CDNS', 'CEG', 'CMCSA',
                'COST', 'CPRT', 'CRWD', 'CRWV', 'CSCO', 'CSX', 'CTAS', 'DASH', 'DDOG', 'DXCM', 'EA', 'EXC',
                'FANG', 'FAST', 'FER', 'FTNT', 'GEHC', 'GILD', 'GOOG', 'GOOGL', 'HON', 'IDXX', 'INTC', 'INTU', 'ISRG',
                'KDP', 'KHC', 'KLAC', 'LIN', 'LITE', 'LRCX', 'MAR', 'MCHP', 'MDLZ', 'MELI', 'META', 'MNST',
                'MPWR', 'MRVL', 'MSFT', 'MSTR', 'MU', 'NBIS', 'NFLX', 'NVDA', 'NXPI', 'ODFL', 'ORLY', 'PANW',
                'PAYX', 'PCAR', 'PDD', 'PEP', 'PLTR', 'PYPL', 'QCOM', 'REGN', 'RLAB', 'ROP', 'ROST', 'SBUX',
                'SHOP', 'SNDK', 'SNPS', 'STX', 'TER', 'TMUS', 'TRI', 'TSLA', 'TTWO', 'TXN', 'VRTX', 'WBD',
                'WDAY', 'WDC', 'WMT', 'XEL',
            ]
        ),
    },
    {
        "value": "dow30",
        "label": "Dow Jones",
        "source_url": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
        "symbols": frozenset(
            [
                'MMM', 'GOOGL', 'AXP', 'AMGN', 'AMZN', 'AAPL', 'BA', 'CAT', 'CVX', 'CSCO', 'KO', 'DIS',
                'GS', 'HD', 'HON', 'IBM', 'JNJ', 'JPM', 'MCD', 'MRK', 'MSFT', 'NKE', 'NVDA', 'PG',
                'CRM', 'SHW', 'TRV', 'UNH', 'V', 'WMT',
            ]
        ),
    },
]

US_INDEX_DEFINITIONS.extend([
    {
        "value": "nasdaq_composite",
        "label": "Nasdaq",
        "source_url": "https://www.investing.com/indices/nasdaq-composite",
        "symbols": frozenset(),
    },
    {
        "value": "sp500_vix",
        "label": "S&P 500 VIX",
        "source_url": "https://www.investing.com/indices/volatility-s-p-500",
        "symbols": frozenset(),
    },
    {
        "value": "nyse_amex_composite",
        "label": "NYSE AMEX Composite",
        "source_url": "https://www.investing.com/indices/nyse-market-composite",
        "symbols": frozenset(),
    },
    {
        "value": "nyse_composite",
        "label": "NYSE Composite",
        "source_url": "https://www.investing.com/indices/nyse-composite",
        "symbols": frozenset(),
    },
    {
        "value": "small_cap_2000",
        "label": "Small Cap 2000",
        "source_url": "https://www.investing.com/indices/smallcap-2000",
        "symbols": frozenset(),
        "max_market_cap": 15_000,
    },
    {
        "value": "dj_utility",
        "label": "DJ Utility",
        "source_url": "https://www.investing.com/indices/dj-utility-average",
        "symbols": frozenset(),
        "sectors": frozenset(["Utilities"]),
    },
    {
        "value": "dj_composite",
        "label": "DJ Composite",
        "source_url": "https://www.investing.com/indices/dj-composite-average",
        "symbols": frozenset(),
    },
    {
        "value": "dj_transportation",
        "label": "DJ Transportation",
        "source_url": "https://www.investing.com/indices/dj-transportation-average",
        "symbols": frozenset(),
        "sectors": frozenset(["Industrials", "Transportation"]),
    },
    {
        "value": "sp500_information_technology",
        "label": "S&P 500 Information Technology",
        "source_url": "https://www.investing.com/indices/s-p-500-information-technology",
        "symbols": frozenset(),
        "sectors": frozenset(["Information Technology", "Technology"]),
    },
    {
        "value": "sp500_utilities",
        "label": "S&P 500 Utilities",
        "source_url": "https://www.investing.com/indices/s-p-500-utilities",
        "symbols": frozenset(),
        "sectors": frozenset(["Utilities"]),
    },
    {
        "value": "sp500_telecom_services",
        "label": "S&P 500 Telecom Services",
        "source_url": "https://www.investing.com/indices/s-p-500-telecom-services",
        "symbols": frozenset(),
        "sectors": frozenset(["Communication Services", "Telecom Services", "Telecommunications"]),
    },
    {
        "value": "sp500_materials",
        "label": "S&P 500 Materials",
        "source_url": "https://www.investing.com/indices/s-p-500-materials",
        "symbols": frozenset(),
        "sectors": frozenset(["Materials", "Basic Materials"]),
    },
    {
        "value": "sp500_real_estate",
        "label": "S&P 500 Real Estate",
        "source_url": "https://www.investing.com/indices/s-p-500-real-estate",
        "symbols": frozenset(),
        "sectors": frozenset(["Real Estate"]),
    },
    {
        "value": "nq_bank",
        "label": "NQ Bank",
        "source_url": "https://www.investing.com/indices/nasdaq-bank",
        "symbols": frozenset(),
        "sectors": frozenset(["Financials", "Finance", "Banks"]),
    },
    {
        "value": "nq_financial_100",
        "label": "NQ Financial 100",
        "source_url": "https://www.investing.com/indices/nasdaq-financial-100",
        "symbols": frozenset(),
        "sectors": frozenset(["Financials", "Finance"]),
    },
    {
        "value": "nq_other_finance",
        "label": "NQ Other Finance",
        "source_url": "https://www.investing.com/indices/nasdaq-other-finance",
        "symbols": frozenset(),
        "sectors": frozenset(["Financials", "Finance"]),
    },
    {
        "value": "nq_industrial",
        "label": "NQ Industrial",
        "source_url": "https://www.investing.com/indices/nasdaq-industrial",
        "symbols": frozenset(),
        "sectors": frozenset(["Industrials"]),
    },
    {
        "value": "nq_insurance",
        "label": "NQ Insurance",
        "source_url": "https://www.investing.com/indices/nasdaq-insurance",
        "symbols": frozenset(),
        "sectors": frozenset(["Financials", "Finance", "Insurance"]),
    },
    {
        "value": "nq_computer",
        "label": "NQ Computer",
        "source_url": "https://www.investing.com/indices/nnasdaq-computer",
        "symbols": frozenset(),
        "sectors": frozenset(["Information Technology", "Technology"]),
    },
    {
        "value": "nq_transportation",
        "label": "NQ Transportation",
        "source_url": "https://www.investing.com/indices/nasdaq-transportation",
        "symbols": frozenset(),
        "sectors": frozenset(["Industrials", "Transportation"]),
    },
    {
        "value": "nq_telecommunications",
        "label": "NQ Telecommunications",
        "source_url": "https://www.investing.com/indices/nasdaq-telecommunications",
        "symbols": frozenset(),
        "sectors": frozenset(["Communication Services", "Telecom Services", "Telecommunications"]),
    },
    {
        "value": "nq_biotechnology",
        "label": "NQ Biotechnology",
        "source_url": "https://www.investing.com/indices/nasdaq-biotechnology",
        "symbols": frozenset(),
        "sectors": frozenset(["Health Care", "Healthcare", "Biotechnology"]),
    },
    {
        "value": "nq_internet",
        "label": "NQ Internet",
        "source_url": "https://www.investing.com/indices/nasdaq-internet",
        "symbols": frozenset(),
        "sectors": frozenset([
            "Communication Services",
            "Consumer Discretionary",
            "Consumer Cyclical",
            "Information Technology",
            "Technology",
        ]),
    },
    {
        "value": "kbw_bank",
        "label": "KBW Bank",
        "source_url": "https://www.investing.com/indices/kbw-bank",
        "symbols": frozenset(),
        "sectors": frozenset(["Financials", "Finance", "Banks"]),
    },
    {
        "value": "phlx_semiconductor",
        "label": "PHLX Semiconductor",
        "source_url": "https://www.investing.com/indices/phlx-semiconductor",
        "symbols": frozenset(),
        "sectors": frozenset(["Information Technology", "Technology", "Semiconductors"]),
    },
    {
        "value": "nasdaq_health_care",
        "label": "NASDAQ Health Care",
        "source_url": "https://www.investing.com/indices/nasdaq-health-care",
        "symbols": frozenset(),
        "sectors": frozenset(["Health Care", "Healthcare"]),
    },
    {
        "value": "nasdaq_next_gen_100",
        "label": "Nasdaq Next Gen 100",
        "source_url": "https://www.investing.com/indices/nasdaq-next-gen-100",
        "symbols": frozenset(),
    },
    {
        "value": "nyse_financials",
        "label": "NYSE Financials",
        "source_url": "https://www.investing.com/indices/nyse-financials",
        "symbols": frozenset(),
        "sectors": frozenset(["Financials", "Finance"]),
    },
    {
        "value": "dj_financials",
        "label": "DJ Financials",
        "source_url": "https://www.investing.com/indices/dj-financials",
        "symbols": frozenset(),
        "sectors": frozenset(["Financials", "Finance"]),
    },
    {
        "value": "dj_health_care",
        "label": "DJ Health Care",
        "source_url": "https://www.investing.com/indices/dj-health-care",
        "symbols": frozenset(),
        "sectors": frozenset(["Health Care", "Healthcare"]),
    },
    {
        "value": "dj_industrials",
        "label": "DJ Industrials",
        "source_url": "https://www.investing.com/indices/dj-industrials",
        "symbols": frozenset(),
        "sectors": frozenset(["Industrials"]),
    },
    {
        "value": "dj_telecom",
        "label": "DJ Telecom",
        "source_url": "https://www.investing.com/indices/dj-telecommunications",
        "symbols": frozenset(),
        "sectors": frozenset(["Communication Services", "Telecom Services", "Telecommunications"]),
    },
    {
        "value": "dj_utilities",
        "label": "DJ Utilities",
        "source_url": "https://www.investing.com/indices/dj-utilities",
        "symbols": frozenset(),
        "sectors": frozenset(["Utilities"]),
    },
    {
        "value": "dj_oil_gas",
        "label": "DJ Oil&Gas",
        "source_url": "https://www.investing.com/indices/dj-oil---gas",
        "symbols": frozenset(),
        "sectors": frozenset(["Energy", "Oil & Gas"]),
    },
    {
        "value": "dj_technology",
        "label": "DJ Technology",
        "source_url": "https://www.investing.com/indices/dj-technology",
        "symbols": frozenset(),
        "sectors": frozenset(["Information Technology", "Technology"]),
    },
    {
        "value": "nyse_tmt",
        "label": "NYSE TMT",
        "source_url": "https://www.investing.com/indices/nyse-tmt",
        "symbols": frozenset(),
    },
    {
        "value": "dj_consumer_goods",
        "label": "DJ Consumer Goods",
        "source_url": "https://www.investing.com/indices/dj-consumer-goods",
        "symbols": frozenset(),
        "sectors": frozenset(["Consumer Staples", "Consumer Defensive"]),
    },
    {
        "value": "nyse_energy",
        "label": "NYSE Energy",
        "source_url": "https://www.investing.com/indices/nyse-energy",
        "symbols": frozenset(),
        "sectors": frozenset(["Energy"]),
    },
    {
        "value": "sp500_consumer_staples",
        "label": "S&P 500 Consumer Staples",
        "source_url": "https://www.investing.com/indices/s-p-500-consumer-staples",
        "symbols": frozenset(),
        "sectors": frozenset(["Consumer Staples", "Consumer Defensive"]),
    },
    {
        "value": "nyse_healthcare",
        "label": "NYSE Healthcare",
        "source_url": "https://www.investing.com/indices/nyse-healthcare",
        "symbols": frozenset(),
        "sectors": frozenset(["Health Care", "Healthcare"]),
    },
    {
        "value": "dj_basic_materials",
        "label": "DJ Basic Materials",
        "source_url": "https://www.investing.com/indices/dj-basic-materials",
        "symbols": frozenset(),
        "sectors": frozenset(["Materials", "Basic Materials"]),
    },
    {
        "value": "dj_us_select_insurance",
        "label": "DJ U.S. Select Insurance",
        "source_url": "https://www.investing.com/indices/dj-u.s.-select-insurance",
        "symbols": frozenset(),
        "sectors": frozenset(["Financials", "Finance", "Insurance"]),
    },
    {
        "value": "dj_us_select_telecommunications",
        "label": "DJ U.S. Select Telecommunications",
        "source_url": "https://www.investing.com/indices/dj-us-select-telecom",
        "symbols": frozenset(),
        "sectors": frozenset(["Communication Services", "Telecom Services", "Telecommunications"]),
    },
    {
        "value": "sp500_financials",
        "label": "S&P 500 Financials",
        "source_url": "https://www.investing.com/indices/s-p-500-financial",
        "symbols": frozenset(),
        "sectors": frozenset(["Financials", "Finance"]),
    },
    {
        "value": "sp500_energy",
        "label": "S&P 500 Energy",
        "source_url": "https://www.investing.com/indices/s-p-500-energy",
        "symbols": frozenset(),
        "sectors": frozenset(["Energy"]),
    },
    {
        "value": "sp500_health_care",
        "label": "S&P 500 Health Care",
        "source_url": "https://www.investing.com/indices/s-p-500-health-care",
        "symbols": frozenset(),
        "sectors": frozenset(["Health Care", "Healthcare"]),
    },
    {
        "value": "sp500_consumer_discretionary",
        "label": "S&P 500 Consumer Discretionary",
        "source_url": "https://www.investing.com/indices/s-p-500-consumer-discretionary",
        "symbols": frozenset(),
        "sectors": frozenset(["Consumer Discretionary", "Consumer Cyclical"]),
    },
    {
        "value": "sp500_industrials",
        "label": "S&P 500 Industrials",
        "source_url": "https://www.investing.com/indices/s-p-500-industrials",
        "symbols": frozenset(),
        "sectors": frozenset(["Industrials"]),
    },
    {
        "value": "dj_consumer_services",
        "label": "DJ Consumer Services",
        "source_url": "https://www.investing.com/indices/dj-consumer-services",
        "symbols": frozenset(),
        "sectors": frozenset(["Consumer Discretionary", "Consumer Cyclical", "Communication Services"]),
    },
])

_INVESTING_US_INDEX_ORDER = [
    "dow30",
    "sp500",
    "nasdaq_composite",
    "nasdaq100",
    "sp500_vix",
    "sp100",
    "nyse_amex_composite",
    "nyse_composite",
    "small_cap_2000",
    "dj_utility",
    "dj_composite",
    "dj_transportation",
    "sp500_information_technology",
    "sp500_utilities",
    "sp500_telecom_services",
    "sp500_materials",
    "sp500_real_estate",
    "nq_bank",
    "nq_financial_100",
    "nq_other_finance",
    "nq_industrial",
    "nq_insurance",
    "nq_computer",
    "nq_transportation",
    "nq_telecommunications",
    "nq_biotechnology",
    "nq_internet",
    "kbw_bank",
    "phlx_semiconductor",
    "nasdaq_health_care",
    "nasdaq_next_gen_100",
    "nyse_financials",
    "dj_financials",
    "dj_health_care",
    "dj_industrials",
    "dj_telecom",
    "dj_utilities",
    "dj_oil_gas",
    "dj_technology",
    "nyse_tmt",
    "dj_consumer_goods",
    "nyse_energy",
    "sp500_consumer_staples",
    "nyse_healthcare",
    "dj_basic_materials",
    "dj_us_select_insurance",
    "dj_us_select_telecommunications",
    "sp500_financials",
    "sp500_energy",
    "sp500_health_care",
    "sp500_consumer_discretionary",
    "sp500_industrials",
    "dj_consumer_services",
]
_INDEX_ORDER_LOOKUP = {value: idx for idx, value in enumerate(_INVESTING_US_INDEX_ORDER)}
US_INDEX_DEFINITIONS.sort(key=lambda item: _INDEX_ORDER_LOOKUP.get(item["value"], len(_INDEX_ORDER_LOOKUP)))
US_INDEX_DEFINITIONS = [item for item in US_INDEX_DEFINITIONS if item["symbols"]]

US_INDEX_OPTIONS = [{"label": "All Indices", "value": ""}] + [
    {"label": item["label"], "value": item["value"]}
    for item in US_INDEX_DEFINITIONS
]

_SYMBOLS_BY_INDEX = {item["value"]: item["symbols"] for item in US_INDEX_DEFINITIONS}
_FILTERABLE_INDEX_VALUES = {
    item["value"]
    for item in US_INDEX_DEFINITIONS
    if item["symbols"]
}


def row_matches_index(row: dict, index_value: str | None) -> bool:
    """Return True when a screener row belongs to the selected index."""
    if not index_value:
        return True
    symbols = _SYMBOLS_BY_INDEX.get(index_value)
    if symbols and str(row.get("symbol") or "").upper() in symbols:
        return True
    if not symbols:
        return True
    return False


def row_matches_any_index(row: dict, index_values: list[str] | tuple[str, ...] | None) -> bool:
    """Return True when a row belongs to at least one selected index."""
    selected = [value for value in (index_values or []) if value]
    if not selected:
        return True
    filterable = [value for value in selected if value in _FILTERABLE_INDEX_VALUES]
    if not filterable:
        return True
    return any(row_matches_index(row, value) for value in filterable)
