"""Plain-language explanations shared by the company views."""

import streamlit as st

FACTOR_EXPLANATIONS = {
    "Company earnings": "How much the company sells and how much profit it earns. Revenue is sales before costs; profit is what remains after expenses.",
    "Profitability": "How efficiently the company turns its sales, assets, and investors' money into profit.",
    "Valuation": "How the share price compares with the company's earnings and assets. A low share price alone does not mean a company is inexpensive.",
    "Debt": "How much the company owes and whether it can meet its payments. Borrowing can support growth, but it also creates obligations.",
    "Cash flow": "Money actually moving into and out of the business. Reported profit and available cash can be different.",
    "Economic conditions": "Changes in the wider economy, such as rising prices or borrowing costs, can affect a company's customers and expenses.",
    "Global markets": "Events outside the company's home market can affect its costs, exports, and investors' confidence.",
    "Institutional investment": "Ownership and trading by large investors, such as mutual funds and pension funds. Ownership shows what they hold; flows show what they buy or sell.",
    "Technical trends": "Patterns in past share prices and trading activity. These describe market behaviour and do not tell us what will happen next.",
    "News and sentiment": "New information and investors' reactions can move prices quickly. This app currently keeps news switched off.",
}


def render_getting_started():
    with st.expander("New to stocks? Start here"):
        st.write("A share is a small ownership stake in a company. This app helps you learn about companies and compare their figures.")
        st.markdown("1. Choose a price range and country. Leave the other filters on **All** if you are unsure.\n2. Pick a company from the stock dropdown. Use **Next page** to see more matches.\n3. Read **Company Profile** to understand the business, then **Overview** for its score and **Price & Performance** for its chart. Explore the earnings, profitability, valuation, debt, cash flow, ownership, technical trends, and market context tabs to understand each topic.")
        st.write("Changing filters clears your selection. 'Unavailable' means the data source did not return a figure; it does not mean zero or a bad company.")


def render_glossary():
    with st.expander("Understand the terms"):
        terms = [
            ("Revenue and profit", "Revenue is sales before costs. Profit is the amount remaining after expenses."),
            ("EPS — earnings per share", "The company's earnings allocated to each share. A negative EPS means a loss per share."),
            ("P/E — price-to-earnings", "Share price divided by annual earnings per share. A P/E of 20 means the price is 20 times those earnings, not a guaranteed 20-year payback."),
            ("P/B — price-to-book", "Share price compared with net assets per share recorded in the accounts. Accounting values can differ from market values."),
            ("ROE / ROA / ROCE", "Return on equity, assets, and capital employed measure different aspects of profitability. They are not the return you earn on your shares."),
            ("Margin", "Profit as a share of revenue. A 10% net margin means 10 in profit for every 100 in revenue."),
            ("Debt/equity and current ratio", "Debt/equity compares borrowing with shareholders' equity. Current ratio compares short-term assets with short-term amounts owed."),
            ("Cash flow and free cash flow", "Operating cash flow is cash from running the business. Free cash flow accounts for spending on long-term assets."),
            ("Dividend yield", "Annual dividends compared with the share price. Dividends and share prices can change."),
            ("SMA50 / SMA200", "The average closing price over the latest 50 or 200 trading sessions. A trading session is normally one day the market is open."),
            ("RSI / MACD", "RSI describes the balance of recent price gains and losses. MACD compares two price averages to describe momentum. Neither is a reliable buy/sell instruction on its own."),
            ("Beta", "Historical sensitivity to market movements. A beta above 1 suggests greater market sensitivity, not a guarantee of future moves."),
            ("TTM / YoY / x", "Trailing twelve months / year over year / times. YoY compares a period with the same period a year earlier. A ratio of 1.5x means 1.5 times."),
            ("FII/FPI / DII", "Foreign institutional or portfolio investors / domestic institutional investors. These are groups of large investors."),
            ("PEG", "A price-to-earnings ratio considered alongside an earnings-growth estimate. Its meaning depends on the growth assumptions."),
        ]
        for term, explanation in terms:
            st.markdown(f"**{term}:** {explanation}")
