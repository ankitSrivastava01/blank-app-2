"""Official company-update metadata: NSE RSS and SEC filing records."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import streamlit as st

from company_growth import sec_get, sec_ticker_directory
from company_sources import get

NSE_FEED = "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"
NSE_DIRECTORY = "https://www.nseindia.com/static/rss-feed"


def company_name_key(name):
    key = re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()
    return re.sub(r"\s+(?:limited|ltd|incorporated|inc|corporation|corp|plc)$", "", key).strip()


def feed_date(value):
    try:
        parsed = parsedate_to_datetime(value)
    except (ValueError, TypeError, IndexError):
        try:
            parsed = datetime.strptime(value, "%d-%b-%Y %H:%M:%S")
        except (ValueError, TypeError):
            return "Date unavailable", 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    local = parsed.astimezone(ZoneInfo("Asia/Kolkata"))
    return local.strftime("%d %b %Y %H:%M IST"), local.timestamp()


def parse_nse_announcements(content, company_name, limit=20):
    if len(content) > 5_000_000 or b"<!ENTITY" in content.upper() or b"<!DOCTYPE" in content.upper():
        raise ValueError("Unexpected feed content.")
    root = ET.fromstring(content)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("The provider did not return an RSS feed.")
    company_key, rows, seen = company_name_key(company_name), [], set()
    if not company_key:
        return []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        if company_name_key(title) != company_key:
            continue
        url = (item.findtext("link") or "").strip()
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or (parts.hostname or "").lower() not in {"nsearchives.nseindia.com", "archives.nseindia.com", "www.nseindia.com", "nseindia.com"}:
            continue
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
        if url in seen:
            continue
        seen.add(url)
        # Use only the feed's short subject metadata, not article or document text.
        description = item.findtext("description") or ""
        match = re.search(r"\bSUBJECT\s*:\s*([^|<]+)", description, re.I)
        subject = " ".join(match[1].strip().split()[:20]) if match else "Company announcement"
        published, sort_key = feed_date(item.findtext("pubDate"))
        rows.append({"Headline": f"{title}: {subject}", "Published": published,
                     "Source": "NSE corporate announcements", "Source URL": url, "sort": sort_key})
    return [{k: v for k, v in row.items() if k != "sort"} for row in sorted(rows, key=lambda r: r["sort"], reverse=True)[:limit]]


@st.cache_data(ttl=600, show_spinner=False)
def nse_feed():
    return get(NSE_FEED).content


def sec_filing_rows(data, cik, limit=20):
    if int(data.get("cik", -1)) != int(cik):
        raise ValueError("Company identity mismatch.")
    recent = data.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict) or "form" not in recent:
        raise ValueError("Incomplete SEC response.")
    types = {"8-K": "Current report", "6-K": "Foreign issuer update", "10-K": "Annual report", "10-Q": "Quarterly report", "20-F": "Foreign issuer annual report", "40-F": "Canadian issuer annual report", "DEF 14A": "Proxy statement"}
    rows, seen = [], set()
    for index, form in enumerate(recent["form"]):
        if form.removesuffix("/A") not in types:
            continue
        def field(key):
            values = recent.get(key, [])
            return values[index] if index < len(values) else ""
        accession, document = field("accessionNumber"), field("primaryDocument")
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or not document or ".." in document or not re.fullmatch(r"[A-Za-z0-9_./-]+", document):
            continue
        if accession in seen:
            continue
        seen.add(accession)
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{quote(document, safe='/')}"
        rows.append({"Headline": f"{form}: {types[form.removesuffix('/A')]}", "Published": field("filingDate") or "Date unavailable",
                     "Source": "SEC EDGAR company filing", "Source URL": url})
        if len(rows) >= limit:
            break
    return rows


@st.cache_data(ttl=600, show_spinner=False)
def load_company_announcements(symbol, company_name, country):
    try:
        if country == "India" and symbol.endswith(".NS"):
            return {"records": parse_nse_announcements(nse_feed(), company_name), "error": None,
                    "note": "Matches are based on the full company name in NSE's recent feed. This feed is a rolling selection, not a complete archive. No matches does not mean the company has made no announcements."}
        if country == "USA":
            matches = [row for row in sec_ticker_directory().values() if row.get("ticker", "").upper() == symbol.upper().replace(".", "-")]
            if len(matches) != 1:
                return {"records": [], "error": None, "note": "No unique SEC filer was found for this ticker."}
            cik = matches[0]["cik_str"]
            data = sec_get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
            return {"records": sec_filing_rows(data, cik), "error": None,
                    "note": "Recent SEC reports and issuer updates. These are regulatory filings, not a general financial news feed. Dates are the filing dates supplied by SEC."}
        return {"records": [], "error": None, "note": "An official announcement feed is not connected for this listing. NSE RSS supports NSE symbols; BSE-only listings are not mapped automatically."}
    except Exception:
        return {"records": [], "error": "The announcement source could not be loaded or verified. Please retry later.", "note": "Company prices and financial information remain available."}
