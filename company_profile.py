"""Company profile using already loaded provider data."""

from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from market_data import number


def profile_date(value, milliseconds=False):
    timestamp = number(value)
    if timestamp is None:
        return "Unavailable"
    try:
        return datetime.fromtimestamp(timestamp / 1000 if milliseconds else timestamp, timezone.utc).strftime("%d %b %Y")
    except (OverflowError, OSError, ValueError):
        return "Unavailable"


def company_size_group(market_cap, country, currency):
    market_cap = number(market_cap)
    if market_cap is None or market_cap <= 0:
        return "Unavailable"
    if country == "India" and currency == "INR":
        mid, large = 50e9, 200e9
    elif country == "USA" and currency == "USD":
        mid, large = 2e9, 10e9
    else:
        return "Unavailable"
    return "Large Cap" if market_cap >= large else "Mid Cap" if market_cap >= mid else "Small Cap"


def render_sourced_details(enrichment, workforce=False):
    records = enrichment.get("records", [])
    records = [row for row in records if (row["Detail"] != "Inception / founding date") == workforce]
    if records:
        st.markdown("### Details from additional free sources")
        st.dataframe(pd.DataFrame(records), hide_index=True, width="stretch",
                     column_config={"Source URL": st.column_config.LinkColumn("Source link", display_text="Open source")})
        st.caption("Each row has its own source and reporting period. These are dated disclosures, not live workforce readings. Wikidata is community maintained and can be incomplete or outdated. Sources may use different employee definitions.")
    elif workforce:
        st.info("No additional workforce figures could be verified for this company. Source coverage varies; a missing figure is not zero.")
    if workforce:
        for notice in enrichment.get("notices", []):
            st.warning(notice)
        st.caption("Free source coverage: Wikidata for matched companies; official workforce reports currently supported for TCS and Infosys, period ended 30 September 2026. Results are cached for 24 hours; Refresh market data retries all sources. These reports are not guaranteed to be the newest disclosures.")


def render_company_workforce(info, fallback, enrichment=None):
    enrichment = enrichment or {"records": [], "notices": []}
    name = info.get("longName") or fallback.get("Name") or fallback["Symbol"]
    currency = info.get("currency") or fallback.get("Currency", "")
    cap = number(info.get("marketCap"))
    if cap is None:
        cap = number(fallback.get("Market cap"))
    st.subheader(f"Company Size & Workforce: {name}")
    st.markdown("### Company size")
    st.write("Market value measures company size on the stock market. Employee count measures the size of its workforce; these are different ways to describe a business.")
    st.write(f"**Market value:** {f'{cap:,.0f} {currency}' if cap is not None else 'Unavailable'}")
    st.write(f"**Size group:** {company_size_group(cap, fallback.get('Country'), currency)}")
    st.caption("App groupings: India large cap ≥INR 200 billion, mid cap ≥INR 50 billion; USA large cap ≥USD 10 billion, mid cap ≥USD 2 billion. Smaller positive market values fall in small cap. These are app thresholds, not official exchange or SEBI classifications.")

    st.markdown("### Employees & attrition")
    employees = number(info.get("fullTimeEmployees"))
    st.write(f"**Full-time employees (Yahoo Finance snapshot):** {f'{employees:,.0f}' if employees is not None else 'Unavailable'}")
    has_attrition = any("attrition" in row["Detail"].lower() for row in enrichment["records"])
    if has_attrition:
        st.write("**Employee attrition:** See the sourced report and period below.")
    else:
        st.write("**Employee attrition rate:** No verified figure found in the connected sources for this company.")
    st.caption("Attrition describes employees leaving over a stated period, often as a percentage of average headcount. It cannot be calculated from one employee-count snapshot. Check the company's annual report for its definition and reporting period.")
    render_sourced_details(enrichment, workforce=True)
    st.caption("Historical employee counts describe headcount changes, not employee departures or gross hiring. They cannot by themselves establish an attrition rate.")

    st.markdown("### Quick facts")
    facts = [
        ("Business sector", info.get("sector") or fallback.get("Sector")),
        ("Industry", info.get("industry")),
        ("Headquarters", ", ".join(str(info[k]) for k in ["city", "country"] if info.get(k))),
        ("Listed market", fallback.get("Country")),
        ("Stock exchange", info.get("fullExchangeName") or info.get("exchange")),
        ("Shares outstanding", number(info.get("sharesOutstanding"))),
        ("Shares available for public trading (float)", number(info.get("floatShares"))),
        ("Reporting currency", info.get("financialCurrency")),
    ]
    for label, value in facts:
        if isinstance(value, (float, int)):
            value = f"{value:,.0f}"
        st.write(f"**{label}:** {value or 'Unavailable'}")
    st.caption("Float is the provider's estimate of shares available for public trading. It can differ from shares outstanding. Profile figures may be reported on different dates.")


def render_company_profile(info, fallback, enrichment=None):
    name = info.get("longName") or fallback.get("Name") or fallback["Symbol"]
    st.subheader(f"About {name}")
    st.caption("Start by understanding what the company does, where it operates, and who runs it. Company size and a familiar brand do not guarantee investment returns.")
    st.write(info.get("longBusinessSummary") or "A business description is unavailable for this company.")
    render_sourced_details(enrichment or {"records": []})

    st.subheader("Company Information")
    st.caption("Ticker = the company's trading code. Exchange = the marketplace where shares trade. Sector and industry describe its type of business. Trading currency is used for share prices; reporting currency is used in its accounts.")
    employees = number(info.get("fullTimeEmployees"))
    fields = [
        ("Legal / reported name", name),
        ("Ticker", fallback["Symbol"]),
        ("Sector", info.get("sector") or fallback.get("Sector")),
        ("Industry", info.get("industry")),
        ("Exchange", info.get("fullExchangeName") or info.get("exchange")),
        ("Security type", info.get("quoteType")),
        ("Headquarters country", info.get("country")),
        ("City / state", ", ".join(str(info[k]) for k in ["city", "state"] if info.get(k))),
        ("Full-time employees", f"{employees:,.0f}" if employees is not None else None),
        ("Trading currency", info.get("currency") or fallback.get("Currency")),
        ("Financial reporting currency", info.get("financialCurrency")),
        ("Exchange timezone", info.get("exchangeTimezoneName")),
    ]
    left, right = st.columns(2)
    for i, (label, value) in enumerate(fields):
        [left, right][i % 2].write(f"**{label}:** {value if value is not None and value != '' else 'Unavailable'}")

    st.subheader("Website & Contact")
    website = info.get("website")
    if isinstance(website, str) and urlparse(website).scheme in {"http", "https"} and urlparse(website).netloc:
        st.link_button("Company website", website)
    else:
        st.write("**Website:** Unavailable")
    address = ", ".join(str(info[k]) for k in ["address1", "address2", "city", "state", "zip", "country"] if info.get(k))
    st.write(f"**Registered / business address:** {address or 'Unavailable'}")
    st.write(f"**Phone:** {info.get('phone') or 'Unavailable'}")

    st.subheader("Leadership")
    st.caption("The executives reported by the data source. CEO means chief executive officer; CFO means chief financial officer. This list may not include the full board.")
    officers = info.get("companyOfficers") or []
    leadership = [{"Name": officer.get("name") or "Unavailable",
                   "Role": officer.get("title") or "Unavailable"}
                  for officer in officers if isinstance(officer, dict) and officer.get("name")]
    if leadership:
        st.dataframe(pd.DataFrame(leadership), hide_index=True, width="stretch")
    else:
        st.info("Leadership information is unavailable from the provider.")

    st.subheader("Reporting Dates")
    st.caption("A quarter is a three-month accounting period. A fiscal year is the company's accounting year, which may differ from January–December. These dates mark period ends, not necessarily results announcement dates.")
    dates = [("Most recent quarter end", profile_date(info.get("mostRecentQuarter"))),
             ("Last fiscal year end", profile_date(info.get("lastFiscalYearEnd"))),
             ("Next fiscal year end (provider estimate)", profile_date(info.get("nextFiscalYearEnd"))),
             ("First trading date in provider records", profile_date(info.get("firstTradeDateEpochUtc"), milliseconds=True))]
    for label, value in dates:
        st.write(f"**{label}:** {value}")
    st.caption("Source: Yahoo Finance. Profile and officer data may lag company disclosures. First trading date reflects provider records and may differ from the IPO date. Headquarters country can differ from the listing market.")
