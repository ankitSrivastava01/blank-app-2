import streamlit as st
import yfinance as yf
from groq import Groq
from html import escape
import os
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Market Brief", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
    :root { --ink: #263a32; --muted: #68776f; --accent: #6f9c7a; --line: #d9e2dc; }
    .stApp { background: linear-gradient(135deg, #f4f6f4 0%, #edf3ee 55%, #f7f8f6 100%); color: var(--ink); }
    [data-testid="stHeader"] { background: transparent; }
    h1, h2, h3 { color: var(--ink); letter-spacing: 0 !important; }
    h1 { font-family: Georgia, serif; font-size: 2.65rem; }
    [data-testid="stMetric"] { background: rgba(248,251,248,.88); border: 1px solid var(--line); border-radius: 6px; padding: 16px 18px; }
    [data-testid="stMetricLabel"] p { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--ink); }
    .stButton > button { background: var(--ink); color: white; border: 0; border-radius: 4px; min-height: 42px; }
    .stButton > button:hover { background: #466b50; color: white; border-color: #466b50; }
    div[data-baseweb="select"] > div { border-color: var(--line); border-radius: 4px; }
    .eyebrow { color: var(--accent); font-size: .75rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
    .subtle { color: var(--muted); }
    .news-item { padding: 13px 0; border-bottom: 1px solid var(--line); }
    .news-item a { color: var(--ink); font-weight: 650; text-decoration: none; }
    .news-item a:hover { color: var(--accent); }
    @media (max-width: 640px) { h1 { font-size: 2rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)

COMPANIES = {
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "NVIDIA": "NVDA",
    "Amazon": "AMZN",
    "Alphabet (Google)": "GOOGL",
    "Meta Platforms": "META",
    "Tesla": "TSLA",
    "Berkshire Hathaway": "BRK-B",
    "JPMorgan Chase": "JPM",
    "Costco": "COST",
}


@st.cache_data(ttl=900, show_spinner=False)
def load_company_data(symbol):
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="1y", auto_adjust=True)
    news = ticker.news
    return history, news


def article_details(article):
    content = article.get("content", article)
    title = content.get("title") or article.get("title") or "Untitled article"
    canonical = content.get("canonicalUrl") or {}
    link = canonical.get("url") if isinstance(canonical, dict) else canonical
    link = link or article.get("link") or ""
    provider = content.get("provider") or article.get("publisher") or {}
    if isinstance(provider, dict):
        provider = provider.get("displayName") or provider.get("name") or ""
    published = content.get("pubDate") or article.get("providerPublishTime")
    if isinstance(published, (int, float)):
        published = datetime.fromtimestamp(published, timezone.utc).strftime("%b %d, %Y")
    elif isinstance(published, str):
        try:
            published = datetime.fromisoformat(published.replace("Z", "+00:00")).strftime("%b %d, %Y")
        except ValueError:
            published = ""
    else:
        published = ""
    return title, link, provider, published


st.markdown('<div class="eyebrow">Company research · Market data</div>', unsafe_allow_html=True)
st.title("Market Brief")
st.markdown("A focused view of company performance, headlines, and AI-assisted context.")

company = st.selectbox("Choose a company", list(COMPANIES), label_visibility="collapsed")
symbol = COMPANIES[company]

try:
    with st.spinner(f"Loading {company} market data..."):
        history, news = load_company_data(symbol)
except Exception as error:
    st.error(f"Market data could not be loaded: {error}")
    st.stop()

if history.empty or "Close" not in history:
    st.warning("No recent price history is available for this company. Try again later.")
    st.stop()

prices = history["Close"].dropna()
latest_price = float(prices.iloc[-1])
last_date = prices.index[-1].strftime("%b %d, %Y")

def return_since(days):
    cutoff = prices.index[-1] - timedelta(days=days)
    earlier = prices.loc[prices.index <= cutoff]
    if earlier.empty:
        if days >= 350:
            return (latest_price / float(prices.iloc[0]) - 1) * 100
        return None
    return (latest_price / float(earlier.iloc[-1]) - 1) * 100


one_month = return_since(30)
six_months = return_since(182)
one_year = return_since(365)
st.caption(f"{company} · {symbol} · Latest close {last_date} · USD · Delayed market data")

metric_columns = st.columns(4)
metric_columns[0].metric("Latest close", f"${latest_price:,.2f}")
for column, label, value in zip(metric_columns[1:], ("1 month", "6 months", "1 year"), (one_month, six_months, one_year)):
    column.metric(label, "N/A" if value is None else f"{value:+.2f}%")

left, right = st.columns([1.5, 1], gap="large")
with left:
    st.subheader("Price history")
    st.caption("Adjusted closing price · past 12 months")
    st.line_chart(prices.rename("Price (USD)"), color="#78a985", height=310)

with right:
    st.subheader("Latest headlines")
    if not news:
        st.info("No recent headlines were returned for this company.")
    for article in news[:6]:
        title, link, provider, published = article_details(article)
        if link:
            st.markdown(f'<div class="news-item"><a href="{escape(link, quote=True)}" target="_blank">{escape(title)}</a><br><span class="subtle">{escape(str(provider))} · {escape(published)}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown(f"**{title}**  \n{provider} · {published}")

st.divider()
st.subheader("AI company briefing")
st.markdown("A concise, source-aware summary of the selected company's recent performance and headlines.")
api_key = os.getenv("GROQ_API_KEY", "")
if not api_key:
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        api_key = ""
if not api_key:
    st.info("Add a GROQ_API_KEY secret to enable AI briefings. Market data and headlines work without it.")
elif st.button("Generate AI briefing", type="primary"):
    headline_context = "\n".join(f"- {article_details(item)[0]}" for item in news[:6]) or "No headlines available."
    performance_context = ", ".join(
        f"{label}: {value:+.2f}%" for label, value in (("1 month", one_month), ("6 months", six_months), ("1 year", one_year)) if value is not None
    ) or "Price return data unavailable."
    prompt = f"""Write a brief, balanced educational company update for {company} ({symbol}).
Observed price performance: {performance_context}. Latest close: ${latest_price:.2f} as of {last_date}.
Recent headlines:
{headline_context}

Use only these supplied facts. Separate observed facts from possible interpretation, state when headlines provide limited context, and note that past performance does not predict future results. Do not tell the reader to buy, sell, or hold. Keep it under 180 words."""
    try:
        with st.spinner("Preparing the company briefing..."):
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You provide neutral financial education, not personalized investment advice."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )
        st.markdown(response.choices[0].message.content)
    except Exception as error:
        st.error(f"Groq could not generate the briefing: {error}")

st.caption("For educational research only, not investment advice. Prices and headlines may be delayed or incomplete. Verify information with primary sources before making financial decisions.")
