"""Yahoo Finance screening and price history; no API key required."""

import math
import ssl
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf
import certifi
from curl_cffi import requests

# Keep Yahoo's cookie/timezone databases in a writable application cache.
yf.set_tz_cache_location(str(Path(tempfile.gettempdir()) / "stock-explorer-yfinance"))

PRICE_RANGES = {
    "All": (0, math.inf),
    "Below 10": (0, 10),
    "10 - 100": (10, 100),
    "100 - 500": (100, 500),
    "500 - 1000": (500, 1000),
    "1000 - 3000": (1000, 3000),
    "3000 - 10000": (3000, 10000),
    "Above 10000": (10000, math.inf),
}
SECTORS = ["All", "Basic Materials", "Communication Services", "Consumer Cyclical",
           "Consumer Defensive", "Energy", "Financial Services", "Healthcare",
           "Industrials", "Real Estate", "Technology", "Utilities"]
PAGE_SIZE = 100


@st.cache_resource(show_spinner=False)
def yahoo_session():
    """Honor Windows' trusted certificate authorities as well as Mozilla's bundle."""
    verify = True
    if sys.platform == "win32":
        certificates = Path(certifi.where()).read_text(encoding="ascii")
        for store in ("ROOT", "CA"):
            for certificate, encoding, trust in ssl.enum_certificates(store):
                if encoding == "x509_asn" and (trust is True or ssl.Purpose.SERVER_AUTH.oid in trust):
                    certificates += ssl.DER_cert_to_PEM_cert(certificate)
        cache = Path(tempfile.gettempdir()) / "stock-explorer-yfinance"
        cache.mkdir(parents=True, exist_ok=True)
        bundle = cache / "trusted-ca.pem"
        bundle.write_text(certificates, encoding="ascii")
        verify = str(bundle)
    return requests.Session(impersonate="chrome", verify=verify, timeout=15)


def screen_query(country, price_range, sector="All", stock_type="All", valuation="All"):
    query = yf.EquityQuery
    parts = [query("eq", ["region", "in" if country == "India" else "us"]),
             query("gt", ["intradayprice", 0])]
    low, high = PRICE_RANGES[price_range]
    if price_range == "Below 10":
        parts.append(query("lt", ["intradayprice", high]))
    elif price_range == "Above 10000":
        parts.append(query("gt", ["intradayprice", low]))
    elif price_range != "All":
        parts.append(query("btwn", ["intradayprice", low, high]))
    if sector != "All":
        parts.append(query("eq", ["sector", sector]))
    # Market-cap thresholds are in each market's local currency.
    mid, large = (50e9, 200e9) if country == "India" else (2e9, 10e9)
    if stock_type == "Large Cap":
        parts.append(query("gte", ["intradaymarketcap", large]))
    elif stock_type == "Mid Cap":
        parts.extend([query("gte", ["intradaymarketcap", mid]),
                      query("lt", ["intradaymarketcap", large])])
    elif stock_type == "Small Cap":
        parts.extend([query("gt", ["intradaymarketcap", 0]),
                      query("lt", ["intradaymarketcap", mid])])
    if valuation == "Value":
        parts.extend([query("gt", ["peratio.lasttwelvemonths", 0]),
                      query("lte", ["peratio.lasttwelvemonths", 20])])
    elif valuation == "Growth":
        parts.append(query("gte", ["epsgrowth.lasttwelvemonths", 15]))
    elif valuation == "Defensive":
        parts.append(query("lte", ["beta", 1]))
    return query("and", parts)


def number(value):
    """Missing provider values stay missing rather than becoming invented metrics."""
    if isinstance(value, dict):
        value = value.get("raw")
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def quote_row(quote, country):
    return {
        "Name": quote.get("longName") or quote.get("shortName") or quote["symbol"],
        "Symbol": quote["symbol"], "Country": country,
        "Currency": quote.get("currency") or ("INR" if country == "India" else "USD"),
        "Price": number(quote.get("regularMarketPrice")),
        "Daily change %": number(quote.get("regularMarketChangePercent")),
        "Market cap": number(quote.get("marketCap")),
        "P/E": number(quote.get("trailingPE")),
        "Sector": quote.get("sector") or "Unavailable",
        "Quote time": quote.get("regularMarketTime"),
    }


@st.cache_data(ttl=300, show_spinner=False)
def load_stock_page(country, price_range="All", sector="All", stock_type="All",
                    valuation="All", page=0):
    result = yf.screen(screen_query(country, price_range, sector, stock_type, valuation),
                       offset=page * PAGE_SIZE, size=PAGE_SIZE,
                       sortField="ticker", sortAsc=True, session=yahoo_session())
    if not isinstance(result, dict) or "quotes" not in result or "total" not in result:
        raise ValueError("Yahoo Finance returned an incomplete screening response.")
    rows = [quote_row(q, country) for q in result["quotes"] if q.get("symbol")]
    return rows, int(result["total"]), datetime.now(timezone.utc).isoformat()


@st.cache_data(ttl=300, show_spinner=False)
def load_stock_details(symbol):
    ticker = yf.Ticker(symbol, session=yahoo_session())
    errors = []
    try:
        info = ticker.get_info() or {}
    except Exception:
        info = {}
        errors.append("Company fundamentals are temporarily unavailable.")
    try:
        history = ticker.history(period="1y", interval="1d", auto_adjust=True,
                                 raise_errors=True, timeout=15)
    except Exception:
        history = pd.DataFrame()
        errors.append("Price history is temporarily unavailable.")
    return info, history, errors


def period_return(history, sessions):
    if history.empty or "Close" not in history:
        return None
    close = history["Close"].dropna()
    if sessions is None:
        if len(close) < 2:
            return None
        start = close.iloc[0]
    else:
        if len(close) <= sessions:
            return None
        start = close.iloc[-sessions - 1]
    return float((close.iloc[-1] / start - 1) * 100) if start else None
