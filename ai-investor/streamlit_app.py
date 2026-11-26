"""Entry point for the US and India market research dashboards."""

import streamlit as st

st.set_page_config(page_title="AI Market Research", page_icon="📈", layout="wide")

st.navigation([
    st.Page("us_research.py", title="US market research", default=True),
    st.Page("india_dashboard.py", title="India stock dashboard", url_path="india"),
]).run()
