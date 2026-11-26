"""Independent growth sources: SEC annual filings and official Indian reports."""

import io
import os
import re
from datetime import date

import streamlit as st

from company_sources import INFOSYS_REPORT, TCS_REPORT, get, host
from market_data import number, yahoo_session


def growth_percent(current, previous):
    if previous <= 0:
        return "Not meaningful (prior value ≤0)"
    return f"{(current / previous - 1) * 100:+.2f}%"


def annual_observations(facts):
    by_end = {}
    for fact in facts:
        value = number(fact.get("val"))
        try:
            start, end = date.fromisoformat(fact["start"]), date.fromisoformat(fact["end"])
        except (KeyError, ValueError, TypeError):
            continue
        if value is None or fact.get("form") not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"} or not 330 <= (end - start).days <= 400:
            continue
        existing = by_end.get(end)
        if existing is None or fact.get("filed", "") > existing.get("filed", ""):
            by_end[end] = dict(fact, val=value)
    return sorted(by_end.values(), key=lambda f: f["end"], reverse=True)


def sec_growth_rows(data, cik):
    concepts = {
        "Revenue": [("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"), ("us-gaap", "Revenues"), ("us-gaap", "SalesRevenueNet"), ("ifrs-full", "Revenue")],
        "Net profit": [("us-gaap", "NetIncomeLoss"), ("us-gaap", "ProfitLoss"), ("ifrs-full", "ProfitLoss")],
    }
    rows = []
    for metric, candidates in concepts.items():
        options = []
        for taxonomy, concept in candidates:
            units = data.get("facts", {}).get(taxonomy, {}).get(concept, {}).get("units", {})
            for currency, facts in units.items():
                if not re.fullmatch(r"[A-Z]{3}", currency):
                    continue
                annual = annual_observations(facts)
                if len(annual) < 2:
                    continue
                current, previous = annual[:2]
                gap = (date.fromisoformat(current["end"]) - date.fromisoformat(previous["end"])).days
                if not 330 <= gap <= 400:
                    continue
                options.append((current["end"], current, previous, currency, f"{taxonomy}:{concept}"))
        if not options:
            continue
        # Preserve concept priority for equally recent periods; never combine tags or currencies.
        _, current, previous, currency, concept = max(options, key=lambda x: x[0])
        rows.append({"Metric": metric, "Current": f"{current['val']:,.0f} {currency}",
                     "Previous": f"{previous['val']:,.0f} {currency}",
                     "YoY growth": growth_percent(current["val"], previous["val"]),
                     "Period": f"FY ended {current['end']} vs {previous['end']}",
                     "Source": "SEC EDGAR annual filings", "Basis": f"Calculated from comparable annual facts ({concept}); filed {current.get('filed', 'date unavailable')}",
                     "Source URL": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"})
    return rows


def sec_get(url):
    # Deployments can supply their operator's identifying contact without an API key.
    agent = os.getenv("SEC_USER_AGENT", "InvestoAI/1.0 (public-company financial research)")
    response = yahoo_session().get(url, timeout=15, headers={"User-Agent": agent})
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=86400, show_spinner=False)
def sec_ticker_directory():
    return sec_get("https://www.sec.gov/files/company_tickers.json")


def sec_company_growth(symbol):
    entries = sec_ticker_directory()
    matches = [row for row in entries.values() if row.get("ticker", "").upper() == symbol.upper().replace(".", "-")]
    if len(matches) != 1:
        return []
    cik = matches[0]["cik_str"]
    data = sec_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json")
    if int(data.get("cik", -1)) != int(cik):
        raise ValueError("SEC company identity did not match.")
    return sec_growth_rows(data, cik)


def parse_infosys_growth(text):
    if "In US $ million, except per equity share data" not in text or "Sep 30, 2026 Sep 30, 2025" not in text:
        raise ValueError("Unsupported report period or currency.")
    block = text.split("Consolidated Statement of Comprehensive Income for six months")[0]
    if "Net profit (after non-controlling interests)" not in block:
        raise ValueError("Net profit label was not found.")
    pattern = r"^\s*([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s+[-\d.]+%\s+[\d,.]+\s+[-\d.]+%\s*$"
    values = re.findall(pattern, block, re.M)
    if len(values) != 14:
        raise ValueError("The financial table layout has changed.")
    values = [(float(a.replace(",", "")), float(b.replace(",", ""))) for a, b in values]
    if any(abs(values[0][i] - values[1][i] - values[2][i]) > 1 for i in [0, 1]):
        raise ValueError("Revenue and cost subtotals do not match.")
    return [{"Metric": label, "Current": f"{values[index][0]:,.0f} USD million",
             "Previous": f"{values[index][1]:,.0f} USD million",
             "YoY growth": growth_percent(*values[index]),
             "Period": "Quarter ended 2026-09-30 vs 2025-09-30",
             "Source": "Infosys company factsheet", "Basis": "Calculated from published rounded amounts; may differ from reported growth",
             "Source URL": INFOSYS_REPORT} for label, index in [("Revenue", 0), ("Net profit after non-controlling interests", 11)]]


def indian_company_growth(symbol, website):
    if symbol in {"INFY.NS", "500209.BO"} and (not website or host(website) == "infosys.com"):
        from pypdf import PdfReader
        response = get(INFOSYS_REPORT)
        if len(response.content) > 5_000_000 or not response.content.startswith(b"%PDF"):
            raise ValueError("Unexpected factsheet response.")
        reader = PdfReader(io.BytesIO(response.content))
        return parse_infosys_growth(reader.pages[2].extract_text() or "")
    if symbol in {"TCS.NS", "532540.BO"} and (not website or host(website) == "tcs.com"):
        from bs4 import BeautifulSoup
        text = BeautifulSoup(get(TCS_REPORT).text, "html.parser").get_text(" ", strip=True)
        if not re.search(r"quarter\s+ending\s+September\s+30,?\s+2026", text, re.I):
            raise ValueError("Report period mismatch.")
        match = re.search(r"Q2\s+Revenue\s+at\s+\$([\d,]+)\s+Mn\s*;\s*Growth\s+[+\-\d.]+%\s+QoQ\s*,\s*([+\-\d.]+)%\s+YoY\s+in\s+USD", text, re.I)
        if not match:
            raise ValueError("The revenue growth disclosure layout has changed.")
        return [{"Metric": "Revenue", "Current": f"{int(match[1].replace(',', '')):,} USD million", "Previous": "Not extracted",
                 "YoY growth": f"{float(match[2]):+.2f}%", "Period": "Quarter ended 2026-09-30 vs 2025-09-30",
                 "Source": "TCS company disclosure", "Basis": "Company-reported growth in USD, not constant currency",
                 "Source URL": TCS_REPORT}]
    return []


@st.cache_data(ttl=86400, show_spinner=False)
def load_company_growth(symbol, website, country):
    try:
        rows = sec_company_growth(symbol) if country == "USA" and website else indian_company_growth(symbol, website) if country == "India" else []
        return {"records": rows, "error": None}
    except Exception:
        return {"records": [], "error": "The additional growth source could not be loaded or verified. Yahoo figures remain available."}
