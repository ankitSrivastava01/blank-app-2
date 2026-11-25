"""Twelve company indicators, with explicit Yahoo field units and missing values."""

from market_data import number


def company_indicators(info, fallback_pe=None):
    def scaled(key, factor=1):
        value = number(info.get(key))
        return None if value is None else value * factor

    return [
        ("P/E (TTM)", number(info.get("trailingPE", fallback_pe)), "x", False,
         "Price relative to trailing earnings per share. Compare with sector peers; a negative value reflects losses."),
        ("Price / book", scaled("priceToBook"), "x", False,
         "Price relative to book equity per share. Its usefulness varies by industry and accounting methods."),
        ("EPS (TTM)", scaled("trailingEps"), "", True,
         "Earnings per share over the trailing twelve months. A negative value indicates a loss per share."),
        ("Return on equity", scaled("returnOnEquity", 100), "%", False,
         "Profit relative to shareholder equity. Debt and small or negative equity can distort this measure."),
        ("Return on assets", scaled("returnOnAssets", 100), "%", False,
         "Profit relative to assets. Compare companies with similar business models and asset requirements."),
        ("Debt / equity", scaled("debtToEquity", 0.01), "x", False,
         "Debt relative to shareholder equity. Higher values generally mean more leverage; sector norms differ."),
        ("Current ratio", scaled("currentRatio"), "x", False,
         "Current assets divided by current liabilities. Shows short-term liquidity; asset quality also matters."),
        ("Net profit margin", scaled("profitMargins", 100), "%", False,
         "The share of revenue retained as net profit. Compare margins across similar companies and periods."),
        ("Revenue growth (YoY)", scaled("revenueGrowth", 100), "%", False,
         "Provider-reported quarterly revenue growth against the same quarter a year earlier. Not a five-year growth rate."),
        ("Earnings growth (YoY)", scaled("earningsGrowth", 100), "%", False,
         "Provider-reported quarterly earnings growth against the same quarter a year earlier. Small bases can magnify changes."),
        ("Dividend yield (trailing)", scaled("trailingAnnualDividendYield", 100), "%", False,
         "Trailing annual dividends relative to price. Past dividends do not guarantee future payments."),
        ("Beta", scaled("beta"), "", False,
         "Historical sensitivity to the market benchmark. Above 1 suggests greater market sensitivity, not total risk."),
    ]
