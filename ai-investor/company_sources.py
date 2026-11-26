"""Free company enrichment, with identity checks, dates and per-field attribution."""

import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import streamlit as st
from bs4 import BeautifulSoup

from market_data import number, yahoo_session

TCS_REPORT = "https://www.tcs.com/who-we-are/newsroom/press-release/tcs-financial-results-q2-fy-2027"
INFOSYS_REPORT = "https://www.infosys.com/investors/reports-filings/quarterly-results/2026-2027/q2/documents/fact-sheet.pdf"
REPORT_DATE = "2026-09-30"


def host(url):
    if not isinstance(url, str):
        return ""
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def get(url, **kwargs):
    response = yahoo_session().get(url, timeout=15, headers={"User-Agent": "InvestoAI/1.0 (company research dashboard)"}, **kwargs)
    response.raise_for_status()
    return response


def record(field, value, period, source, url):
    return {"Detail": field, "Value": value, "Period / as of": period,
            "Source": source, "Source URL": url}


def parse_tcs_report(html):
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "nav", "footer"]):
        element.decompose()
    text = soup.get_text(" ", strip=True)
    if not re.search(r"quarter\s+ending\s+September\s+30,?\s+2026", text, re.I):
        raise ValueError("The report period could not be verified.")
    employees = re.search(r"Workforce\s+strength\s*:\s*([\d,]+)", text, re.I)
    attrition = re.search(r"LTM\s+Attrition\s*\(IT\s+Services\)\s*:\s*([\d.]+)\s*%", text, re.I)
    if not employees or not attrition:
        raise ValueError("The workforce report layout has changed.")
    count, rate = int(employees[1].replace(",", "")), float(attrition[1])
    if count <= 0 or not 0 <= rate <= 100:
        raise ValueError("Invalid workforce figures.")
    return [record("Reported workforce", f"{count:,}", REPORT_DATE, "TCS company disclosure", TCS_REPORT),
            record("Attrition (IT services, last 12 months)", f"{rate:g}%", REPORT_DATE, "TCS company disclosure", TCS_REPORT)]


def parse_infosys_report(text):
    # Verify both the period and table structure; do not take numbers from arbitrary prose.
    segment = re.search(r"Employee\s+Metrics(.*?)Cash\s+Metrics", text, re.I | re.S)
    if not segment or "Total employees" not in segment[1] or "Voluntary Attrition" not in segment[1]:
        raise ValueError("The workforce table could not be identified.")
    segment = segment[1]
    if not re.search(r"Sep\s+30,\s+2026\s+Jun\s+30,\s+2026\s+Sep\s+30,\s+2025", segment):
        raise ValueError("The table periods have changed.")
    counts = re.findall(r"^\s*([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$", segment, re.M)
    rates = re.findall(r"^\s*([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s*$", segment, re.M)
    if len(counts) != 3 or len(rates) != 2:
        raise ValueError("The workforce table layout has changed.")
    counts = [[int(n.replace(",", "")) for n in row] for row in counts]
    if any(counts[0][i] != counts[1][i] + counts[2][i] for i in range(3)):
        raise ValueError("Employee subtotals do not match the total.")
    if any(not 0 <= float(n) <= 100 for row in rates for n in row):
        raise ValueError("Invalid percentage in workforce table.")
    rows = [record("Reported employees", f"{counts[0][i]:,}", period, "Infosys company factsheet", INFOSYS_REPORT)
            for i, period in enumerate([REPORT_DATE, "2026-06-30", "2025-09-30"])]
    rows.extend([
        record("Voluntary attrition (IT services, last 12 months)", f"{float(rates[0][0]):g}%", REPORT_DATE, "Infosys company factsheet", INFOSYS_REPORT),
        record("Women employees", f"{float(rates[1][0]):g}%", REPORT_DATE, "Infosys company factsheet", INFOSYS_REPORT),
    ])
    return rows


def official_workforce(symbol, website):
    if symbol in {"TCS.NS", "532540.BO"} and (not website or host(website) == "tcs.com"):
        return parse_tcs_report(get(TCS_REPORT).text)
    if symbol in {"INFY.NS", "500209.BO", "INFY"} and (not website or host(website) == "infosys.com"):
        from pypdf import PdfReader
        response = get(INFOSYS_REPORT)
        if len(response.content) > 5_000_000 or not response.content.startswith(b"%PDF"):
            raise ValueError("Unexpected factsheet response.")
        reader = PdfReader(io.BytesIO(response.content))
        return parse_infosys_report("\n".join(page.extract_text() or "" for page in reader.pages))
    return []


def wikidata_date(value):
    if not isinstance(value, dict):
        return None
    time = value.get("time", "").lstrip("+")
    precision = value.get("precision", 0)
    if not re.match(r"\d{4}-\d{2}-\d{2}T", time) or precision < 9:
        return None
    return time[:4] if precision == 9 else time[:7] if precision == 10 else time[:10]


def claim_value(claim):
    return claim.get("mainsnak", {}).get("datavalue", {}).get("value")


def entity_records(entity, qid):
    source, url = "Wikidata (community maintained)", f"https://www.wikidata.org/wiki/{qid}"
    claims, rows = entity.get("claims", {}), []
    inception = [c for c in claims.get("P571", []) if c.get("rank") != "deprecated"]
    if inception:
        preferred = [c for c in inception if c.get("rank") == "preferred"] or inception
        dates = {wikidata_date(claim_value(c)) for c in preferred}
        dates.discard(None)
        if len(dates) == 1:
            rows.append(record("Inception / founding date", dates.pop(), "Historical", source, url))
    employees = {}
    for claim in claims.get("P1128", []):
        qualifiers = claim.get("qualifiers", {})
        if claim.get("rank") == "deprecated" or any(k in qualifiers for k in ["P518", "P21", "P1540", "P1539"]):
            continue
        value = claim_value(claim)
        if not isinstance(value, dict) or value.get("unit") != "1":
            continue
        count = number(value.get("amount"))
        periods = [wikidata_date(s.get("datavalue", {}).get("value")) for s in qualifiers.get("P585", [])]
        periods = [p for p in periods if p]
        if count is None or count < 0 or not count.is_integer() or len(set(periods)) != 1:
            continue
        employees.setdefault(periods[0], set()).add(int(count))
    for period in sorted(employees, reverse=True)[:10]:
        if len(employees[period]) == 1:
            rows.append(record("Historical employee count", f"{employees[period].pop():,}", period, source, url))
    return rows


def wikidata_company(symbol, website):
    domain = host(website)
    ticker = re.sub(r"\.(NS|BO)$", "", symbol)
    if not domain or not re.fullmatch(r"[\w.^&=-]{1,40}", ticker):
        return []
    query = f'''SELECT DISTINCT ?company ?website WHERE {{
      {{ ?company wdt:P249 {json.dumps(ticker)} }} UNION {{ ?company p:P414/pq:P249 {json.dumps(ticker)} }}
      ?company wdt:P856 ?website.
      FILTER(CONTAINS(LCASE(STR(?website)), {json.dumps(domain)}))
    }} LIMIT 100'''
    bindings = get("https://query.wikidata.org/sparql", params={"query": query, "format": "json"}).json()["results"]["bindings"]
    matches = {r["company"]["value"].rsplit("/", 1)[-1] for r in bindings if host(r["website"]["value"]) == domain}
    if len(matches) != 1:
        return []
    qid = matches.pop()
    if not re.fullmatch(r"Q\d+", qid):
        return []
    entity = get(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json").json()["entities"][qid]
    return entity_records(entity, qid)


@st.cache_data(ttl=86400, show_spinner=False)
def load_company_enrichment(symbol, website=""):
    rows, notices = [], []
    jobs = {"Company report": official_workforce, "Wikidata": wikidata_company}
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = {name: executor.submit(loader, symbol, website) for name, loader in jobs.items()}
        for name, future in pending.items():
            try:
                rows.extend(future.result())
            except Exception:
                notices.append(f"{name} could not be loaded or verified. Other company data remains available.")
    return {"records": rows, "notices": notices, "retrieved": datetime.now(timezone.utc).isoformat()}
