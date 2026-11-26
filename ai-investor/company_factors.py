"""Company-specific readings for each major price driver."""

from market_data import number
from stock_health import technical_indicators


def company_factor_rows(info, history, quote_currency=""):
    reporting_currency = info.get("financialCurrency") or "currency unavailable"

    def fmt(value, suffix="", factor=1):
        value = number(value)
        return "Unavailable" if value is None else f"{value * factor:,.2f}{suffix}"

    def metric(key, suffix="", factor=1):
        return fmt(info.get(key), suffix, factor)

    def money(key):
        return metric(key, " " + reporting_currency)

    technical = technical_indicators(history)
    return [
        {"Factor": "Company earnings",
         "Company readings": f"Revenue: {money('totalRevenue')}; net income to common: {money('netIncomeToCommon')}; EPS (TTM): {metric('trailingEps', ' ' + quote_currency)}; revenue growth YoY: {metric('revenueGrowth', '%', 100)}; earnings growth YoY: {metric('earningsGrowth', '%', 100)}",
         "How to read": "Compare results with expectations and prior periods. Provider growth figures are quarterly YoY; income totals use the provider's reporting period."},
        {"Factor": "Profitability",
         "Company readings": f"ROE: {metric('returnOnEquity', '%', 100)}; ROA: {metric('returnOnAssets', '%', 100)}; operating margin: {metric('operatingMargins', '%', 100)}; net margin: {metric('profitMargins', '%', 100)}; ROCE: unavailable",
         "How to read": "Compare with industry peers. ROE can be affected by leverage; ROA is a separate measure and does not replace ROCE."},
        {"Factor": "Valuation",
         "Company readings": f"P/E (TTM): {metric('trailingPE', 'x')}; forward P/E: {metric('forwardPE', 'x')}; P/B: {metric('priceToBook', 'x')}; PEG: {metric('trailingPegRatio', 'x')}",
         "How to read": "Consider growth, earnings quality, and peer valuations. Forward ratios use estimates; a low multiple alone does not imply good value."},
        {"Factor": "Debt",
         "Company readings": f"Debt/equity: {metric('debtToEquity', 'x', 0.01)}; total debt: {money('totalDebt')}; cash: {money('totalCash')}; current ratio: {metric('currentRatio', 'x')}; interest coverage: unavailable",
         "How to read": "Assess leverage and liquidity in the context of the sector. Current ratio is not interest coverage; neither ROCE nor interest coverage is supplied by this data source."},
        {"Factor": "Cash flow",
         "Company readings": f"Operating cash flow: {money('operatingCashflow')}; free cash flow: {money('freeCashflow')}",
         "How to read": "Compare cash generation with earnings, investment needs, and debt obligations. Negative free cash flow may reflect investment or operating pressure."},
        {"Factor": "Economic conditions",
         "Company readings": "GDP, inflation, and interest-rate data: unavailable; no economic data feed is connected.",
         "How to read": "Company sensitivity depends on demand, borrowing costs, and its markets. No current economic impact is inferred."},
        {"Factor": "Global markets",
         "Company readings": "Global equity benchmarks, oil prices, and geopolitical developments: unavailable; no global market feed is connected.",
         "How to read": "Exposure depends on the company's trade, input costs, and currency mix. No current global impact is inferred."},
        {"Factor": "Institutional investment",
         "Company readings": f"Institutional ownership: {metric('heldPercentInstitutions', '%', 100)}; FII/FPI and DII flows: unavailable; promoter holding and pledging: unavailable",
         "How to read": "Institutional ownership is a holding snapshot, not buying or selling flows, and is not equivalent to Indian promoter holdings."},
        {"Factor": "Technical trends",
         "Company readings": f"Adjusted close: {fmt(technical['close'], ' ' + quote_currency)}; RSI (14): {fmt(technical['rsi14'])}; MACD (12,26): {fmt(technical['macd'])}; signal (9): {fmt(technical['signal'])}; SMA50: {fmt(technical['sma50'], ' ' + quote_currency)}; SMA200: {fmt(technical['sma200'], ' ' + quote_currency)}; volume: {metric('volume')}; average volume: {metric('averageVolume')}",
         "How to read": "Calculated from available adjusted daily closes. RSI below 30 is not an automatic buy; MACD and averages can lag or give false signals. MACD and its signal are in price units."},
        {"Factor": "News and sentiment",
         "Company readings": "Disabled. No headlines or sentiment are fetched or scored.",
         "How to read": "Orders, regulations, and management announcements can move prices; check company and exchange disclosures separately."},
    ]
