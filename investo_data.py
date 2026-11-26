"""Indian equity providers. Every result carries its source and fetch time."""

import csv
import gzip
import json
import logging
import re
import sqlite3
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO, StringIO
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf

from investo_store import snapshot
from market_data import number, yahoo_session

IST = ZoneInfo("Asia/Kolkata")
NSE = "https://nsearchives.nseindia.com"
BSE_API = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_FILINGS = "https://www.bseindia.com/corporates/ann.html"
NSE_FILINGS = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
NSE_RESULTS = "https://www.nseindia.com/companies-listing/corporate-integrated-filing"
BSE_RESULTS = "https://www.bseindia.com/corporates/Comp_Resultsnew.aspx"
YAHOO = "Yahoo Finance · delayed daily data"
INDEXES = {"NIFTY 50": "^NSEI", "SENSEX": "^BSESN"}
STARTER = [
    ("RELIANCE", "Reliance Industries Limited", "500325", "INE002A01018"),
    ("TCS", "Tata Consultancy Services Limited", "532540", "INE467B01029"),
    ("INFY", "Infosys Limited", "500209", "INE009A01021"),
    ("HDFCBANK", "HDFC Bank Limited", "500180", "INE040A01034"),
    ("SBIN", "State Bank of India", "500112", "INE062A01020"),
    ("ICICIBANK", "ICICI Bank Limited", "532174", "INE090A01021"),
]
LOG = logging.getLogger(__name__)


def get(url, params=None, bse=False):
    headers = {"Accept-Language": "en-IN,en;q=0.9"}
    if bse:
        headers["Referer"] = "https://www.bseindia.com/"
    response = yahoo_session().get(url, params=params, headers=headers, timeout=5)
    response.raise_for_status()
    return response


def result(data=None, source="Unavailable", fetched=None, stale=False):
    return dict(data=data, source=source, fetched=fetched, stale=stale)


def last_good(key, providers, max_days):
    for source, load in providers:
        try:
            data = load()
        except Exception as exc:
            LOG.info("%s failed for %s (%s)", source, key, type(exc).__name__)
            continue
        try:
            _, fetched = snapshot(key, {"data": data, "source": source})
        except (OSError, sqlite3.Error):
            LOG.warning("Could not save market snapshot for %s", key)
            fetched = datetime.now(timezone.utc).isoformat()
        return result(data, source, fetched)
    try:
        cached, fetched = snapshot(key)
        if cached is not None and datetime.now(timezone.utc) - datetime.fromisoformat(fetched) <= timedelta(days=max_days):
            return result(cached["data"], cached["source"], fetched, stale=True)
    except (OSError, ValueError, sqlite3.Error):
        LOG.warning("Could not read market snapshot for %s", key)
    return result()


def equity(exchange, symbol, name, isin, code=""):
    symbol, isin, code = str(symbol or "").strip().upper(), str(isin or "").strip().upper(), str(code or "").strip()
    name = str(name or "").strip()
    if not re.fullmatch(r"INE[A-Z0-9]{9}", isin) or isin[7:9] != "01" or not name:
        return None
    if exchange == "BSE" and not re.fullmatch(r"[0-9]{6}", code):
        return None
    if not re.fullmatch(r"[A-Z0-9&._-]{1,35}", symbol):
        return None
    return dict(exchange=exchange, symbol=symbol, name=name, isin=isin, code=code,
                ticker=f"{symbol}.NS" if exchange == "NSE" else f"{code}.BO",
                alias=f"{symbol}.BO" if exchange == "BSE" and symbol != code else "")


def equity_directory(rows, minimum):
    by_ticker = {row["ticker"]: row for row in rows if row}
    if len(by_ticker) < minimum:
        raise ValueError("Incomplete equity directory")
    return list(by_ticker.values())


def nse_directory(segment):
    path = "/content/equities/EQUITY_L.csv" if segment == "Mainboard" else "/emerge/corporates/content/SME_EQUITY_L.csv"
    reader = csv.DictReader(StringIO(get(NSE + path).content.decode("utf-8-sig", errors="replace")))
    rows = []
    for raw in reader:
        row = {k.strip().upper().replace("_", " "): (v or "").strip() for k, v in raw.items() if k is not None}
        rows.append(equity("NSE", row.get("SYMBOL"), row.get("NAME OF COMPANY") or row.get("COMPANY NAME"),
                           row.get("ISIN NUMBER") or row.get("ISIN")))
    return equity_directory(rows, 500 if segment == "Mainboard" else 50)


def bse_directory():
    payload = get(BSE_API + "/ListofScripData/w", bse=True,
                  params=dict(Group="", segment="Equity", status="Active", scripcode="", industry="")).json()
    return equity_directory((equity("BSE", r.get("scrip_id") or r.get("SCRIP_CD"),
                      r.get("Issuer_Name") or r.get("Security_Name"), r.get("ISIN_NUMBER"), r.get("SCRIP_CD"))
                      for r in payload), 1000)


def broker_directory(exchange):
    response = get(f"https://assets.upstox.com/market-quote/instruments/exchange/{exchange}.json.gz")
    content = gzip.decompress(response.content) if response.content.startswith(b"\x1f\x8b") else response.content
    return equity_directory((equity(exchange, r.get("trading_symbol") or r.get("exchange_token"), r.get("name"),
                                   r.get("isin"), r.get("exchange_token") if exchange == "BSE" else "")
                             for r in json.loads(content) if r.get("segment") == f"{exchange}_EQ"), 500)


@st.cache_data(ttl=900, max_entries=2, show_spinner=False)
def directory(exchange):
    if exchange == "BSE":
        feeds = [last_good("directory:BSE", [("BSE active equities", bse_directory),
                                            ("Upstox · BSE tradable instruments", lambda: broker_directory("BSE"))], 30)]
    else:
        feeds = [last_good(f"directory:NSE:{segment}", [(f"NSE {segment} equities", lambda: nse_directory(segment))], 30)
                 for segment in ("Mainboard", "SME")]
        if any(feed["data"] is None or feed["stale"] for feed in feeds):
            feeds.append(last_good("directory:NSE:broker", [("Upstox · NSE tradable instruments", lambda: broker_directory("NSE"))], 30))
    rows = {}
    for feed in feeds:
        for row in feed["data"] or []:
            rows.setdefault(row["ticker"], row)
    if not rows:
        starter = [equity(exchange, symbol, name, isin, code if exchange == "BSE" else "")
                   for symbol, name, code, isin in STARTER]
        return [result(starter, "Built-in starter list · limited coverage")], starter
    return feeds, list(rows.values())


def history_frame(data):
    if not data:
        return pd.DataFrame()
    frame = pd.DataFrame(data).set_index("Date")
    frame.index = pd.to_datetime(frame.index)
    return frame


@st.cache_data(ttl=600, max_entries=400, show_spinner=False)
def history(symbol, alias=""):
    def load(provider_symbol):
        frame = yf.Ticker(provider_symbol, session=yahoo_session()).history(
            period="1y", interval="1d", auto_adjust=False, actions=False, raise_errors=True, timeout=6)
        frame = frame[["Open", "High", "Low", "Close", "Volume"]].sort_index()
        frame = frame.replace([float("inf"), -float("inf")], float("nan")).dropna(subset=["Open", "High", "Low", "Close"])
        frame = frame[frame[["Open", "High", "Low", "Close"]].gt(0).all(axis=1)]
        frame.index = pd.to_datetime(frame.index).date
        frame = frame.loc[~frame.index.duplicated(keep="last")]
        now = datetime.now(IST)
        frame = frame.loc[frame.index <= now.date() if now.hour >= 16 else frame.index < now.date()]
        if frame.empty:
            raise ValueError("No complete daily bars")
        return [dict(Date=day.isoformat(), **{k: number(v) for k, v in fields.items()})
                for day, fields in frame.to_dict("index").items()]
    return last_good(f"history:{symbol}", [(YAHOO, lambda s=s: load(s)) for s in dict.fromkeys(filter(None, (alias, symbol)))], 14)


def histories(instruments):
    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(zip(instruments, pool.map(history, instruments.keys(), instruments.values())))


def latest_quote(feed):
    rows = feed["data"] or []
    if not rows:
        return None, None, None
    close = rows[-1]["Close"]
    change = 100 * (close / rows[-2]["Close"] - 1) if len(rows) > 1 else None
    return close, change, rows[-1]["Date"]


def recent_trading_candidates():
    today = datetime.now(IST).date()
    return [day for i in range(10) if (day := today - timedelta(days=i)).weekday() < 5][:4]


def latest_report(load):
    for day in recent_trading_candidates():
        try:
            return load(day)
        except Exception as exc:
            LOG.debug("Report for %s unavailable (%s)", day, type(exc).__name__)
    raise ValueError("No recent exchange report")


@st.cache_data(ttl=900, show_spinner=False)
def nifty_close():
    def report(day):
        frame = pd.read_csv(BytesIO(get(f"{NSE}/content/indices/ind_close_all_{day:%d%m%Y}.csv").content))
        frame.columns = frame.columns.str.strip()
        row = frame.loc[frame["Index Name"].str.strip().eq("Nifty 50")].iloc[0]
        close, change = number(row["Closing Index Value"]), number(row["Change(%)"])
        if not close or close < 0:
            raise ValueError("Missing index close")
        return dict(close=close, change=change, date=day.isoformat())
    return last_good("nifty_close", [("NSE daily index report", lambda: latest_report(report))], 7)


@st.cache_data(ttl=1800, show_spinner=False)
def nifty_members():
    def load():
        table = pd.read_csv(BytesIO(get("https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv").content))
        rows = [dict(symbol=str(row.Symbol), name=str(row["Company Name"]), sector=str(row.Industry))
                for _, row in table.iterrows() if isinstance(row.Symbol, str)]
        if len(rows) != 50 or len({row["symbol"] for row in rows}) != 50:
            raise ValueError("Incomplete index membership")
        return rows
    return last_good("nifty_members", [("NSE Indices · NIFTY 50 constituents", load)], 30)


@st.cache_data(ttl=900, show_spinner=False)
def market_movers(symbols):
    def report(day):
        content = get(f"{NSE}/content/cm/BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip").content
        frame = pd.read_csv(BytesIO(content), compression="zip", dtype={"TckrSymb": str})
        frame = frame[frame["TckrSymb"].isin(symbols) & frame["SctySrs"].isin(["EQ", "BE", "BZ"])]
        rows = []
        for row in frame.drop_duplicates("TckrSymb").itertuples(index=False):
            close, previous = number(row.ClsPric), number(row.PrvsClsgPric)
            if close and close > 0 and previous and previous > 0:
                rows.append(dict(symbol=row.TckrSymb, close=close, change=100 * (close / previous - 1)))
        if len(rows) < len(symbols) * 0.8:
            raise ValueError("Insufficient mover coverage")
        return dict(rows=rows, date=day.isoformat())

    def yahoo():
        data = yf.download([f"{symbol}.NS" for symbol in symbols], period="5d", interval="1d",
                           auto_adjust=False, group_by="column", progress=False, threads=5,
                           session=yahoo_session(), timeout=6)["Close"].sort_index()
        now = datetime.now(IST)
        if now.hour < 16:
            data = data[data.index.date < now.date()]
        rows = []
        for symbol in symbols:
            ticker = f"{symbol}.NS"
            if ticker in data and len(data) >= 2:
                previous, close = map(number, data[ticker].iloc[-2:])
                if previous and previous > 0 and close and close > 0:
                    rows.append(dict(symbol=symbol, close=close, change=100 * (close / previous - 1)))
        if not rows:
            raise ValueError("Missing comparable closes")
        return dict(rows=rows, date=data.index[-1].date().isoformat())

    return last_good("movers:" + ",".join(symbols),
                     [("NSE final equity bhavcopy", lambda: latest_report(report)), (YAHOO, yahoo)], 7)


@st.cache_data(ttl=900, show_spinner=False)
def nse_ranked_prices():
    def report(day):
        content = get(f"{NSE}/content/cm/BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip").content
        frame = pd.read_csv(BytesIO(content), compression="zip", dtype={"TckrSymb": str})
        frame = frame[frame["SctySrs"].isin(["EQ", "BE", "BZ", "SM", "ST"])]
        rows = {}
        for row in frame.itertuples(index=False):
            close, previous = number(row.ClsPric), number(row.PrvsClsgPric)
            if isinstance(row.TckrSymb, str) and close and close > 0 and previous and previous > 0:
                rows.setdefault(row.TckrSymb, dict(close=close, change=100 * (close / previous - 1)))
        if len(rows) < 500:
            raise ValueError("Incomplete exchange report")
        return dict(rows=rows, date=day.isoformat())
    return last_good("nse_ranked_prices", [("NSE final equity bhavcopy", lambda: latest_report(report))], 7)


def company_key(name):
    words = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    return re.sub(r"\s+(?:ltd|limited)$", "", words)


def timestamp(value):
    if not value:
        return None
    for parse in (parsedate_to_datetime, datetime.fromisoformat,
                  lambda raw: datetime.strptime(raw, "%d-%b-%Y %H:%M:%S"),
                  lambda raw: datetime.strptime(raw, "%d-%b-%Y")):
        try:
            time = parse(value.strip())
            return (time if time.tzinfo else time.replace(tzinfo=IST)).astimezone(IST).isoformat()
        except (ValueError, TypeError, AttributeError):
            continue
    return None


def rss_rows(content, exchange_feed=False):
    if len(content) > 5_000_000 or re.search(rb"<!\s*(?:DOCTYPE|ENTITY)", content, re.I):
        raise ValueError("Unexpected RSS content")
    channel = ET.fromstring(content).find("channel")
    if channel is None:
        raise ValueError("Invalid RSS feed")
    rows = []
    for item in channel.findall("item"):
        title, url = item.findtext("title", "").strip(), item.findtext("link", "").strip()
        parts = urlsplit(url)
        allowed = {"nsearchives.nseindia.com", "archives.nseindia.com", "www.nseindia.com", "www.nseindia.in", "nseindia.com"} if exchange_feed else {"news.google.com"}
        if not title or parts.scheme not in {"https", "http"} or parts.hostname not in allowed:
            continue
        description = item.findtext("description", "")
        subject = re.search(r"\bSUBJECT\s*:\s*([^|<]+)", description, re.I)
        headline = f"{title} · {' '.join(subject[1].split()[:20])}" if exchange_feed and subject else title
        symbol = re.search(r"\bSYMBOL\s*:\s*([A-Z0-9&._-]+)\b", description, re.I)
        rows.append(dict(title=headline, company=company_key(title), symbol=symbol[1].upper() if symbol else "",
                         published=timestamp(item.findtext("pubDate")),
                         publisher="NSE" if exchange_feed else item.findtext("source", "Google News"), url=url))
    return rows


@st.cache_data(ttl=600, max_entries=200, show_spinner=False)
def headlines(company=""):
    query = f'"{company_key(company)}" (NSE OR BSE OR stock OR shares)' if company else "Indian stock market (NSE OR BSE OR Nifty OR Sensex)"
    return last_good("news:" + company_key(company), [("Google News RSS", lambda: rss_rows(get(
        "https://news.google.com/rss/search", dict(q=query, hl="en-IN", gl="IN", ceid="IN:en")).content)[:20])], 3)


@st.cache_data(ttl=600, max_entries=2, show_spinner=False)
def nse_filings(kind):
    path = "Online_announcements.xml" if kind == "Announcements" else "Financial_Results.xml"
    def load():
        rows = rss_rows(get(f"{NSE}/content/RSS/{path}").content, exchange_feed=True)
        for row in rows:
            row["kind"] = kind
        return rows
    return last_good(f"filings:NSE:{kind}", [(f"NSE RSS · {kind}", load)], 3)


@st.cache_data(ttl=600, max_entries=200, show_spinner=False)
def bse_filings(code=""):
    def load():
        today = datetime.now(IST).date()
        start = today - timedelta(days=30 if code else 2)
        url = BSE_API + "/AnnSubCategoryGetData/w"
        params = dict(pageno=1, strCat="-1", strPrevDate=start.strftime("%Y%m%d"),
                      strScrip=code, strSearch="P", strToDate=today.strftime("%Y%m%d"), strType="C", subcategory="")
        def page(category):
            payload = get(url, dict(params, strCat=category), bse=True).json()["Table"]
            if not isinstance(payload, list):
                raise ValueError("Invalid BSE filings response")
            return payload

        raw = page("-1")
        try:
            raw += page("Result")
        except Exception as exc:
            LOG.info("BSE results category unavailable (%s)", type(exc).__name__)
        rows = {}
        for row in raw:
            if code and str(row.get("SCRIP_CD")) != code:
                continue
            title = row.get("NEWSSUB") or row.get("HEADLINE")
            if not title:
                continue
            attachment = str(row.get("ATTACHMENTNAME") or "")
            link = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{quote(attachment, safe='')}" if attachment else BSE_FILINGS
            category = " ".join(str(row.get(field) or "") for field in ("CATEGORYNAME", "SUBCATNAME"))
            kind = "Financial results" if re.search(r"\b(?:results?|financial results)\b", category, re.I) or re.search(r"\bfinancial results\b", title, re.I) else "Announcements"
            rows[row.get("NEWSID") or title] = dict(title=title, url=link, publisher="BSE",
                published=timestamp(row.get("DissemDT") or row.get("NEWS_DT")), kind=kind)
        return sorted(rows.values(), key=lambda row: row["published"] or "", reverse=True)
    return last_good(f"filings:BSE:{code}", [("BSE corporate filings", load)], 3)


def statement_value(frame, period, *labels):
    for label in labels:
        if label in frame.index and period in frame.columns:
            value = number(frame.at[label, period])
            if value is not None:
                return value
    return None


def growth(current, prior):
    return 100 * (current / prior - 1) if current is not None and prior is not None and prior > 0 else None


@st.cache_data(ttl=3600, max_entries=300, show_spinner=False)
def fundamentals(symbol, alias=""):
    def load(provider_symbol):
        ticker = yf.Ticker(provider_symbol, session=yahoo_session())
        try:
            info = ticker.get_info() or {}
        except Exception:
            info = {}
        statements = {}
        for key, method in [("income", ticker.get_income_stmt), ("balance", ticker.get_balance_sheet)]:
            try:
                statements[key] = method(freq="yearly", pretty=True)
            except Exception:
                statements[key] = pd.DataFrame()
        income, balance = statements["income"], statements["balance"]
        periods = sorted(income.columns, reverse=True)
        if not periods and not info.get("quoteType") and balance.empty:
            raise ValueError("No company fundamentals")
        fiscal = periods[0] if periods else None
        prior = periods[1] if len(periods) > 1 and 300 <= (fiscal - periods[1]).days <= 430 else None
        balance_period = max(balance.columns, default=None)
        revenue = statement_value(income, fiscal, "Total Revenue", "Operating Revenue")
        net = statement_value(income, fiscal, "Net Income", "Net Income Common Stockholders")
        ebit = statement_value(income, fiscal, "EBIT")
        assets = statement_value(balance, fiscal, "Total Assets")
        liabilities = statement_value(balance, fiscal, "Current Liabilities")
        prior_assets = statement_value(balance, prior, "Total Assets")
        prior_liabilities = statement_value(balance, prior, "Current Liabilities")
        capital = assets - liabilities if assets is not None and liabilities is not None else None
        if capital is not None and prior_assets is not None and prior_liabilities is not None:
            capital = (capital + prior_assets - prior_liabilities) / 2
        else:
            capital = None
        roe = number(info.get("returnOnEquity"))
        debt = statement_value(balance, balance_period, "Total Debt")
        currency = info.get("financialCurrency") or info.get("currency") or "Unspecified"
        return dict(sector=info.get("sector") or "Unclassified", currency=currency,
                    fiscal=fiscal.date().isoformat() if fiscal is not None else None,
                    balance_date=balance_period.date().isoformat() if balance_period is not None else None,
                    metrics={"P/E (TTM)": number(info.get("trailingPE")), "EPS (TTM)": number(info.get("trailingEps")),
                             "ROE (%)": roe * 100 if roe is not None else None,
                             "ROCE (%)": 100 * ebit / capital if ebit is not None and capital and capital > 0 else None,
                             "Debt (annual)": debt, "Revenue (annual)": revenue, "Net profit (annual)": net,
                             "Revenue growth (%)": growth(revenue, statement_value(income, prior, "Total Revenue", "Operating Revenue")),
                             "Profit growth (%)": growth(net, statement_value(income, prior, "Net Income", "Net Income Common Stockholders"))})
    return last_good(f"fundamentals:{symbol}", [("Yahoo Finance · reported fundamentals", lambda s=s: load(s))
                     for s in dict.fromkeys(filter(None, (alias, symbol)))], 30)


def quote_usable(feed, day):
    return bool(day and not feed["stale"] and date.fromisoformat(day) >= datetime.now(IST).date() - timedelta(days=4))
