"""InvestoAI's Indian equities dashboard."""

import sqlite3

import streamlit as st

import investo_ui as ui
import investo_workspace as workspace

st.set_page_config(page_title="InvestoAI | Indian equity research", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(ellipse at 85% 0%, #122644 0%, #090f1c 46%);
    }
    [data-testid="stMainBlockContainer"] { max-width: 1220px; padding-top: 2.4rem; }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #14223a, #101a2d 75%);
        border: 1px solid #263953;
        border-radius: 14px;
    }
    [data-testid="stCaptionContainer"] { color: #a3b3cc; }
    .investo-masthead { border-bottom: 1px solid #263953; padding-bottom: .9rem; margin-bottom: .9rem; }
    .investo-masthead h1 { font-size: clamp(2rem, 6vw, 3.35rem); line-height: 1.15; margin: 0 0 .35rem; padding: 0; }
    .investo-masthead h1 span { color: #4ee1b4; }
    .investo-masthead p { color: #a3b3cc; margin: 0; }
    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"] { padding-top: 1.3rem; padding-left: 1rem; padding-right: 1rem; }
        [data-testid="stMetricValue"] { font-size: 1.4rem; }
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<header class="investo-masthead">
    <h1>Investo<span>AI</span></h1>
    <p>Indian equity research · NSE &amp; BSE</p>
</header>
""", unsafe_allow_html=True)

PAGES = {
    "Stocks": ui.ranked_stocks,
    "Stock shortlist": ui.stock_shortlist,
    "Stock suggestions": ui.stock_suggestions,
    "Market overview": ui.dashboard,
    "Compare": ui.compare,
    "Calculators": workspace.calculator,
}

page = st.radio("Navigation", list(PAGES), horizontal=True, label_visibility="collapsed", key="market_page")

try:
    PAGES[page]()
except (OSError, sqlite3.Error):
    st.error("Workspace storage could not be accessed. Try again in a moment.")

st.divider()
st.caption("Educational research only. Prices are delayed, and investing involves risk. Dates and times are shown in India Standard Time.")
with st.expander("Investment disclaimer and data sources"):
    st.write(ui.DISCLAIMER)
    st.caption("Directories use exchange listings or Upstox. NSE reports cover the NIFTY 50 dashboard. Yahoo Finance supplies chart data and financial metrics. News comes from Google News and the exchange filing feeds.")
    st.caption("During an outage, available cached snapshots show their original timestamps. Calculations or comparisons requiring missing data will show gaps.")
