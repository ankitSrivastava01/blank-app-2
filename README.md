# India & US Stock Explorer

A Streamlit dashboard using Yahoo Finance through `yfinance`, without a market-data API key. The app uses provider data instead of hardcoded sample stocks or generated prices.

## Run locally

```sh
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

## For first-time users

Open **New to stocks? Start here** in the sidebar for the three-step guide. Start with a price range and country, leave optional filters on All, and select a company. Read Company Profile to understand the business, Overview for the screening score, Price & Performance for the chart, and the topic tabs for company figures with plain-language explanations.

Filter help, a glossary, chart examples, and explanations of reporting periods are built into the app. The single health score is a screening summary, not a probability of profit. AI briefings are prompted to expand acronyms and explain figures for beginners. Missing data is labelled explicitly, and news remains disabled.

## Browse stocks

- India and USA appear by default. Select either country to switch price labels to INR or USD.
- Price ranges include below 10, 10-100, 100-500, and higher ranges. Prices use local currency, without currency conversion.
- Country, price, sector, market-cap type, and valuation filters search Yahoo's supported universe. Previous/Next page shows up to 100 stocks per country per page. Counts show provider-reported matches.
- Matching stocks appear only in the stock dropdown, with their quoted prices. Page controls are in the sidebar.
- Filters update only the stock list. Select a stock to load its single Stock Health Score, performance chart, and AI briefing controls. Changing filters or page clears the selection. Missing values remain unavailable.
- Data is cached for five minutes. **Refresh market data** clears the caches and retries Yahoo.

Market-cap thresholds: India large cap >= INR 200 billion, mid cap INR 50-200 billion; US large cap >= USD 10 billion, mid cap USD 2-10 billion. Small caps fall below each mid-cap threshold. Value uses positive trailing P/E <=20; Growth uses annual EPS growth >=15%; Defensive uses beta <=1.

The Stock Health Score is one overall screening score out of 100. Fundamentals, valuation, momentum, and risk each carry 25% weight. The underlying checks cover ROE, revenue growth, earnings growth, margin, P/E, P/B, close versus SMA50/SMA200, MACD versus its signal, debt/equity, current ratio, and absolute beta. The methodology is available in a collapsed explanation; individual indicator cards are hidden.

Checks within each group have equal weight. A score requires data in all four groups and at least two-thirds of applicable checks. Missing checks are excluded; insufficient coverage shows "Insufficient data". Debt/equity and current ratio are excluded for financial companies. Higher scores mean more app screening conditions are met, not higher expected returns. Thresholds are fixed app heuristics, not sector benchmarks or SEBI ratings. ROCE, promoter pledging, institutional flows, macroeconomic conditions, and news are not included.

The **Company Profile** tab includes the business description, sector and industry, headquarters, employee count, exchange, currencies, website and contact details, leadership, and reporting dates when available from Yahoo Finance. Missing fields are marked unavailable.

## Optional AI briefings

Set `GROQ_API_KEY` in the environment or `.streamlit/secrets.toml`:

```toml
GROQ_API_KEY = "your-groq-api-key"
```

Groq runs only when **Generate AI briefing** is clicked, using the selected company's returned fundamentals. Stock data and indicators work without this key. News is currently disabled.

## Data limitations

Yahoo Finance is a free upstream service accessed through an unofficial client, not a guaranteed real-time exchange feed. Coverage may omit listings, prices may be delayed, and requests may be rate limited. Counts reflect Yahoo's screener, not every exchange listing. Failed markets are identified; the app does not substitute sample prices. Use is subject to the provider's terms.

Returns use adjusted closes over 1, 5, and 21 trading sessions. The available-year figure uses the first and last valid closes within the fetched one-year history. The app does not generate synthetic forecasts or trading signals.

## Validation

```sh
python -m unittest discover -s tests -v
```

## Deployment

```sh
streamlit run streamlit_app.py --server.port $PORT --server.headless true
```

Educational research only; not personalized investment advice.

## Company detail tabs

After selecting a stock, 12 main tabs organize its details: Overview, Company Profile, Earnings & Growth, Profitability, Valuation, Debt & Liquidity, Cash Flow, Ownership, Technical Trends, Market Context, Price & Performance, and AI Briefing. Each topic explains its figures for beginners. News stays disabled; unavailable external market data is identified explicitly.

The **11. Company Size & Workforce** tab shows market value, the app size group, employee count, and quick company facts. Attrition and employee history can be supplemented by the connected sources below; unsupported figures remain explicitly unavailable. The separate Return Guide tab has been removed; the return figures retain their help tooltips.

## Additional free company sources

- **SEC EDGAR:** US stocks with matching tickers can show annual revenue and net-profit growth in Earnings & Growth. Values use consecutive annual filing periods, the same currency, and the same accounting concept. Later comparative restatements replace older values. Growth is not calculated from a zero or negative prior amount. No API key is needed. Deployments can set `SEC_USER_AGENT` to their application name and real operator contact, following SEC developer guidance.
- **Official company reports:** TCS revenue growth and Infosys revenue/profit growth come from their period-ended 30 September 2026 disclosures. Infosys growth is calculated from published rounded USD amounts and can differ from its reported rate. These are quarterly figures, distinct from SEC annual growth and Yahoo measures.
- **Official workforce disclosures:** TCS and Infosys workforce/attrition reports are parsed with period and table checks. Sources and dates are shown in Company Size & Workforce. Coverage is currently these companies and reports; the reports are not guaranteed to be the newest release.
- **Wikidata:** Founding details and dated employee history are accepted only after the ticker and company website identify one entity. Community-maintained historical counts are kept separate from Yahoo's snapshot.

Additional sources are cached for 24 hours. Refresh market data retries them. A failed source does not replace missing values with zero or discard data from other sources. External growth data is displayed separately and does not change the existing health-score inputs. News remains disabled.

## Official announcements

**12. Announcements** provides an optional loader for official company updates. NSE-listed Indian stocks use the announcement RSS URL verified against [NSE's official RSS directory](https://www.nseindia.com/static/rss-feed). US stocks use SEC EDGAR submissions, matched by exact ticker and CIK.

Only titles/subjects, dates, sources, and links are displayed; article and document bodies are not fetched. NSE matching uses full company names with common legal suffixes normalized, not ticker substring guesses. The rolling feed is not a full archive. BSE-only listings are explicitly unsupported. SEC entries are regulatory filings, not a general news feed. Duplicate links/filing identifiers are removed and invalid links are excluded.

Switch on **Load recent company announcements** after selecting a stock. Sources are cached for ten minutes and Refresh market data clears those caches. No AI sentiment processing is performed; general financial-news feeds remain off. Public feed access does not by itself establish redistribution or commercial-use rights; applicable source terms still apply.

The former Overview, Company Profile, and Earnings & Growth tabs are combined in **1. Company Overview**, with separate sections for each. There are now 12 main tabs; the other sections remain available and have been renumbered.

## Price chart controls

The Price & Performance tab supports 1W, 1M, 3M, 6M, and available 1Y chart windows, line/candlestick styles when OHLC data exists, optional 50/200-session averages, and volume when available. Averages use history before the display window. Window statistics show period change, highest/lowest adjusted close, and session count. The fixed 1D/1W/1M/1Y return figures retain their help tooltips and trading-session definitions. Charts remain daily, not intraday.
