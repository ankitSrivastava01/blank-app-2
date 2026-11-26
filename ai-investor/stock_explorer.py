"""Streamlit interface for the free Yahoo Finance data source."""

import logging
import os
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from market_data import (PAGE_SIZE, PRICE_RANGES, SECTORS, load_stock_details,
                         load_stock_page, number, period_return)
from indicators import company_indicators
from company_factors import company_factor_rows
from company_profile import render_company_profile, render_company_workforce
from stock_health import stock_health
from beginner_guide import FACTOR_EXPLANATIONS, render_getting_started, render_glossary
from company_sources import load_company_enrichment
from company_growth import load_company_growth, sec_ticker_directory
from company_announcements import load_company_announcements, nse_feed, NSE_DIRECTORY
from price_chart import render_price_chart


def display_number(value, suffix="", prefix=""):
    value = number(value)
    return "Unavailable" if value is None else f"{prefix}{value:,.2f}{suffix}"


def reset_pages():
    st.session_state.stock_page = 0
    clear_stock_selection()


def clear_stock_selection():
    st.session_state.stock_selection = None


def yahoo_error_reason(response):
    """Classify known Yahoo authentication errors without logging response data."""
    try:
        description = response.json()["finance"]["error"]["description"].lower()
    except (AttributeError, KeyError, TypeError, ValueError):
        return "unknown"
    if "invalid crumb" in description:
        return "invalid crumb"
    if "unable to access this feature" in description:
        return "access denied by Yahoo"
    return "unknown"



def render_factor_section(row, company_name):
    st.subheader(f"{row['Factor']}: {company_name}")
    st.write(FACTOR_EXPLANATIONS[row["Factor"]])
    st.markdown("**This company's figures**")
    for reading in row["Company readings"].split("; "):
        st.write(reading)
    st.markdown("**How to read this**")
    st.write(row["How to read"])
    st.caption("Financial amounts use the reporting currency shown; share prices use the quote currency. Unavailable means the provider did not supply a figure.")


def render_app():
    st.markdown('''<div class="hero"><div class="badge">India &amp; US stocks</div>
        <h1 style="margin:0;">India &amp; US Stock Explorer</h1>
        <p>Understand a company, explore its share price, and learn what the numbers mean.</p></div>''', unsafe_allow_html=True)
    st.session_state.setdefault("stock_page", 0)
    with st.sidebar:
        render_getting_started()
        st.subheader("Stock Filters")
        country = st.session_state.get("stock_country", "All")
        currency = {"India": "\u20b9", "USA": "$"}.get(country, "\u20b9 / $")

        def price_label(option):
            if option == "All":
                return "All prices"
            if option.startswith("Below"):
                return f"Below {currency}10"
            if option.startswith("Above"):
                return f"Above {currency}10,000"
            low, high = PRICE_RANGES[option]
            return f"{currency}{low:,} - {currency}{high:,}"

        price = st.selectbox("Price range", list(PRICE_RANGES), key="stock_price_range",
                             format_func=price_label, on_change=reset_pages,
                             help="The quoted price of one share. A lower share price does not necessarily mean better value.")
        st.caption("INR for India; USD for USA. Prices are not currency converted.")
        country = st.selectbox("Country", ["All", "India", "USA"], key="stock_country",
                               format_func=lambda x: "India & USA" if x == "All" else x,
                               on_change=reset_pages, help="Choose the listing market. Indian stocks use rupees (INR); US stocks use dollars (USD).")
        sector = st.selectbox("Sector", SECTORS, on_change=reset_pages,
                              help="A group of businesses doing similar work, such as technology or healthcare.")
        stock_type = st.selectbox("Stock type", ["All", "Large Cap", "Mid Cap", "Small Cap"],
                                  on_change=reset_pages, help="Groups companies by market value, not the price of one share. The size thresholds differ between India and the US.")
        valuation = st.selectbox("Valuation style", ["All", "Value", "Growth", "Defensive"],
                                 on_change=reset_pages, help="Optional research filters: Value uses a lower positive earnings multiple; Growth uses earnings growth; Defensive uses historical market sensitivity. These labels do not guarantee value, growth, or safety.")
        with st.expander("What do these filters mean?"):
            st.write("Value: positive price-to-earnings ratio up to 20. Growth: the provider's annual EPS growth measure of at least 15%. Defensive: beta up to 1. These are simple screening rules; leave All selected to explore without them.")
        if st.button("Refresh market data"):
            load_stock_page.clear()
            load_stock_details.clear()
            load_company_enrichment.clear()
            load_company_growth.clear()
            sec_ticker_directory.clear()
            load_company_announcements.clear()
            nse_feed.clear()
            clear_stock_selection()
            st.rerun()

    countries = ["India", "USA"] if country == "All" else [country]
    rows, totals, failures = [], {}, []
    page = st.session_state.stock_page
    with st.spinner("Loading matching stocks..."):
        for market in countries:
            try:
                quotes, total, _ = load_stock_page(market, price, sector, stock_type, valuation, page)
                rows.extend(quotes)
                totals[market] = total
            except Exception as exc:
                failures.append(market)
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                logging.getLogger(__name__).error(
                    "Yahoo stock screening failed for %s: %s (HTTP status: %s; reason: %s)",
                    market, type(exc).__name__, status_code or "unavailable",
                    yahoo_error_reason(response),
                )
                st.error(f"Could not load {market} stocks from Yahoo Finance. The service may be unavailable or rate limited. Use Refresh market data to retry.")

    if failures and totals:
        st.warning("Only the markets that loaded successfully are shown. Retry to see both markets.")

    previous, status, following = st.sidebar.columns([1, 1, 1])
    if previous.button("Previous page", disabled=page == 0):
        st.session_state.stock_page -= 1
        clear_stock_selection()
        st.rerun()
    status.caption(f"Page {page + 1} · Up to {PAGE_SIZE} stocks per country per page")
    more = any(total > (page + 1) * PAGE_SIZE for total in totals.values())
    if following.button("Next page", disabled=not more):
        st.session_state.stock_page += 1
        clear_stock_selection()
        st.rerun()
    if not rows:
        if not failures:
            st.info("No stocks on this page match your filters. Widen the filters or return to the previous page.")

    stocks = pd.DataFrame(rows, columns=["Name", "Symbol", "Country", "Currency", "Price",
                                        "Daily change %", "Market cap", "P/E", "Sector", "Quote time"]).drop_duplicates("Symbol")
    if not stocks.empty:
        low, high = PRICE_RANGES[price]
        stock_prices = pd.to_numeric(stocks["Price"], errors="coerce")
        matches = stock_prices.gt(0) & stock_prices.between(low, high)
        if price == "Below 10":
            matches &= stock_prices.lt(high)
        elif price == "Above 10000":
            matches &= stock_prices.gt(low)
        stocks = stocks[matches]

    selected_symbol = None
    if not stocks.empty:
        options = stocks["Symbol"].tolist()
        labels = {}
        for row in stocks.to_dict("records"):
            symbol_currency = {"INR": "\u20b9", "USD": "$"}.get(row["Currency"], row["Currency"] + " ")
            labels[row["Symbol"]] = f"{row['Name']} ({row['Symbol']}) — {display_number(row['Price'], prefix=symbol_currency)}"
        selected_symbol = st.selectbox(
            "Selected stock", options, index=None, format_func=labels.get,
            placeholder="Select a stock to view its health score, performance, and AI",
            key="stock_selection",
        )
    if not selected_symbol:
        if stocks.empty and rows:
            st.info("No stocks match the selected price range. Choose another range.")
        return
    symbol = selected_symbol
    fallback = stocks[stocks["Symbol"] == symbol].iloc[0].to_dict()

    st.subheader("Stock Details")
    with st.spinner(f"Loading {symbol}..."):
        info, history, errors = load_stock_details(symbol)
    for error in errors:
        st.warning(error)
    if not info and history.empty and not fallback:
        st.info("No data returned for this ticker. Check the symbol or try again later.")
        return
    currency_code = info.get("currency") or fallback.get("Currency", "")
    currency_symbol = {"INR": "\u20b9", "USD": "$"}.get(currency_code, currency_code + " ")
    name = info.get("longName") or fallback.get("Name") or symbol
    price_value = number(info.get("currentPrice")) or number(info.get("regularMarketPrice")) or fallback.get("Price")
    st.write(f"**{name} ({symbol})** · {currency_code}")
    quote_time = info.get("regularMarketTime") or fallback.get("Quote time")
    if number(quote_time):
        st.caption("Quote timestamp: " + datetime.fromtimestamp(float(quote_time), timezone.utc).strftime("%d %b %Y %H:%M UTC"))
    indicators = company_indicators(info, fallback.get("P/E"))
    health = stock_health(info, history)
    with st.spinner("Checking additional company sources..."):
        enrichment = load_company_enrichment(symbol, info.get("website") or "")
    tabs = st.tabs(['1. Company Overview', '2. Profitability', '3. Valuation', '4. Debt & Liquidity', '5. Cash Flow', '6. Ownership', '7. Technical Trends', '8. Market Context', '9. Price & Performance', '10. AI Briefing', '11. Company Size & Workforce', '12. Announcements'])

    with tabs[0]:
        st.subheader("Overview")
        cols = st.columns(2)
        cols[0].metric("Price", display_number(price_value, prefix=currency_symbol), help="The latest available quoted price of one share. Quotes may be delayed.")
        cols[1].metric("Market cap", display_number(info.get("marketCap", fallback.get("Market cap")), prefix=currency_symbol), help="Market capitalisation: share price multiplied by shares outstanding. This measures company size, not its cash or profit.")
        st.write(f"**Sector:** {info.get('sector') or fallback.get('Sector', 'Unavailable')}")

        st.metric("Stock Health Score", "Insufficient data" if health["overall"] is None else f"{health['overall']:.0f} / 100",
                  help="An app-defined screening score combining fundamentals, valuation, momentum, and risk, each weighted 25%.")
        st.caption(f"Based on {health['available']} of {health['applicable']} applicable checks. Higher scores mean more of the app's screening conditions are met; this is not a price forecast or buy/sell signal.")
        st.write("The score combines business performance, valuation, price trends, and risk measures. A score of 70/100 does not mean a 70% chance of profit or a 70% return. 'Insufficient data' means there is too little information to calculate it.")
        render_glossary()
        with st.expander("How the score is calculated"):
            st.write("Fundamentals, valuation, momentum, and risk each carry 25% weight. Within each group, available checks have equal weight. A total is shown only when all four groups have data and at least two-thirds of applicable checks are available. Missing values are excluded, not scored as zero.")
            st.write("These fixed thresholds are app heuristics, not industry averages or SEBI ratings. Debt/equity and current ratio are excluded for financial companies. ROCE, cash flow, promoter pledging, institutional flows, economic conditions, and news are not included.")
            for check in health["checks"]:
                st.markdown(f"- **{check['Factor']} · {check['Indicator']}:** {check['Rule']}. {check['Status']}.")


    with tabs[0]:
        render_company_profile(info, fallback, enrichment)

    factors = {row["Factor"]: row for row in company_factor_rows(info, history, currency_code)}
    topics = ["Company earnings", "Profitability", "Valuation", "Debt", "Cash flow", "Institutional investment", "Technical trends"]
    for tab, topic in zip([tabs[0], *tabs[1:7]], topics):
        with tab:
            render_factor_section(factors[topic], name)
            if topic == "Company earnings":
                st.markdown("### Growth from sources other than Yahoo")
                with st.spinner("Checking official growth disclosures..."):
                    growth = load_company_growth(symbol, info.get("website") or "", fallback.get("Country"))
                if growth["records"]:
                    st.dataframe(pd.DataFrame(growth["records"]), hide_index=True, width="stretch",
                                 column_config={"Source URL": st.column_config.LinkColumn("Source link", display_text="Open source")})
                else:
                    st.info(growth["error"] or "No supported independent growth figures were found for this company.")
                st.caption("YoY means the change from the same period a year earlier. SEC rows compare annual filings in the same currency and accounting concept; Indian company report rows compare quarters. Negative or zero prior values do not produce a meaningful growth percentage. Differences from Yahoo can reflect different periods, currencies, definitions, rounding, or later restatements. These figures do not change the app's existing health score.")
    with tabs[7]:
        for topic in ["Economic conditions", "Global markets"]:
            render_factor_section(factors[topic], name)
        st.caption("News remains disabled. These market factors describe possible influences, not a live assessment of their impact on this company.")

    with tabs[8]:
        st.subheader("Price History")
        st.caption("The line shows how the daily closing price changed over the past year. Prices are adjusted for stock splits and dividends so dates can be compared. Hover over the line to read a date and price.")
        if history.empty or "Close" not in history or history["Close"].dropna().empty:
            st.info("Price history is unavailable for this ticker.")
        else:
            render_price_chart(history, currency_code, symbol)
            cols = st.columns(4)
            return_help = {
                "1D": "Price change over the last trading day, calculated from adjusted daily closing prices.",
                "1W": "Price change over the last 5 trading days, about one week. Weekends and market holidays are not counted.",
                "1M": "Price change over the last 21 trading days, about one month. Weekends and market holidays are not counted.",
                "Available 1Y": "Price change from the first to the last available adjusted close within the past year. A newer stock may have less than a full year of history.",
            }
            for col, label, sessions in zip(cols, ["1D", "1W", "1M", "Available 1Y"], [1, 5, 21, None]):
                col.metric(label, display_number(period_return(history, sessions), "%"),
                           help=return_help[label] + " +5% means the price rose 5%; -5% means it fell 5%. Unavailable means there is not enough price history.")
            st.caption("Returns use adjusted daily closes: 1, 5, and 21 trading sessions. The 1Y figure uses the available history within the last year.")
            st.caption("1D means one trading day, 1W about one week, and 1M about one month. For example, +5% means a value of 100 became 105 over that period, before fees and taxes. Past changes do not predict future returns.")


    with tabs[9]:
        st.subheader("AI Briefing")
        st.caption("Optional: get a plain-language explanation of the available company figures. The briefing can make mistakes; check important details against company reports.")
        if st.button("Generate AI briefing"):
            try:
                from groq import Groq
                api_key = os.getenv("GROQ_API_KEY", "")
                if not api_key:
                    try:
                        api_key = st.secrets["GROQ_API_KEY"]
                    except (KeyError, FileNotFoundError):
                        api_key = ""
                if not api_key:
                    st.info("AI briefings have not been enabled for this app yet. You can still use the company profile, score, chart, and factor explanations.")
                else:
                    metrics = {label: {"value": value, "unit": currency_code if use_currency else suffix}
                               for label, value, suffix, use_currency, _ in indicators}
                    metrics.update({"Price": price_value, "Currency": currency_code})
                    metrics["App screening score (not a forecast)"] = health["overall"]
                    response = Groq(api_key=api_key).chat.completions.create(
                        model="llama-3.3-70b-versatile", max_tokens=220,
                        messages=[{"role": "system", "content": "Explain this company to a beginner in under 140 words using plain language. Expand acronyms and explain what important numbers mean. Use only supplied metrics. Mention missing values. An app screening score is not a probability or return forecast. Do not invent figures, forecast prices, or give buy/sell recommendations."},
                                  {"role": "user", "content": f"Company: {name} ({symbol}). Provider metrics: {metrics}"}])
                    st.write(response.choices[0].message.content)
            except Exception:
                st.warning("The AI briefing is unavailable right now. Please try again later.")


    with tabs[10]:
        render_company_workforce(info, fallback, enrichment)

    with tabs[11]:
        st.subheader(f"Company Announcements: {name}")
        st.write("Read updates filed by the company, such as results, board decisions, and regulatory reports. An announcement is information to review, not a buy or sell signal.")
        if st.toggle("Load recent company announcements", key=f"announcements_{symbol}"):
            with st.spinner("Loading official company updates..."):
                updates = load_company_announcements(symbol, name, fallback.get("Country"))
            if updates["error"]:
                st.warning(updates["error"])
            elif updates["records"]:
                st.dataframe(pd.DataFrame(updates["records"]), hide_index=True, width="stretch",
                             column_config={"Source URL": st.column_config.LinkColumn("Announcement link", display_text="Read original")})
            else:
                st.info("No matching updates were returned by the connected source.")
            st.caption(updates["note"])
        st.markdown(f"Source directory: [NSE official RSS feeds]({NSE_DIRECTORY}). US listings use SEC EDGAR.")
        st.caption("Only announcement titles, dates, and original links are displayed. Results are cached for 10 minutes; Refresh market data retries the sources. No full articles are fetched and no sentiment score is generated.")

    st.caption("Market data: Yahoo Finance. Additional company details link to their own sources. Missing data is marked unavailable. Figures may cover different reporting periods. Educational research only; the score and past prices do not predict future returns.")
