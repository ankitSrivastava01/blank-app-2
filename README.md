# InvestoAI

Indian equity market research in Streamlit. The app covers NSE and BSE company equities and the NIFTY 50 and SENSEX benchmarks. No API key is required for the default data sources.

## Run locally

```sh
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

The previous US research app is preserved as `legacy_research.py` and can be launched separately with `python -m streamlit run legacy_research.py`. It retains its optional `GROQ_API_KEY`, `OPENAI_API_KEY` and `GEMINI_API_KEY` settings.

## MVP priorities

| Priority | Scope |
| --- | --- |
| P0 | Price-filtered NSE stocks ranked by daily change, delayed benchmark tables, NSE/BSE listing search, price growth tables, and company details with data sources and dates. |
| P1 | Screening the NIFTY 50 or up to 20 selected listings, comparison of up to five listings, market and company headlines, exchange announcements and results, headline sentiment, and calculators. |

The MVP uses daily prices. The Stocks page ranks NSE listings from the highest to the lowest daily price change after applying the price range. Select a listing to see its growth table and company news.

## Providers and fallback behavior

| Data | Source order and behavior |
| --- | --- |
| Company search | Active equity listings from [NSE mainboard and SME](https://www.nseindia.com/market-data/securities-available-for-trading) and [BSE](https://www.bseindia.com/corporates/List_Scrips.html). [Upstox instrument masters](https://upstox.com/developer/api-documentation/instruments/) can supplement an unavailable exchange directory. Eligible saved directory data is marked as cached. A small labeled starter list is used when there is no usable directory for an exchange. Search by name, trading symbol, ISIN or BSE scrip code. Coverage depends on listing files and is separate from price/fundamental availability. |
| Market dashboard | The [NSE daily reports](https://www.nseindia.in/all-reports) supply NIFTY 50 closing levels and movers when available. The [index provider](https://www.niftyindices.com/indices/equity/broad-based-indices/NIFTY-50) supplies constituents. Yahoo Finance supplies SENSEX, trend charts, and a fallback for NIFTY 50 levels and mover prices. Movers use constituents with comparable prices for a single session and show coverage. |
| Stock prices and financials | Yahoo Finance via yfinance provides delayed daily OHLC and company fundamentals. Prices stay specific to the selected exchange. BSE lookup tries the trading symbol and then the scrip code. A missing field stays unavailable. Annual figures retain their fiscal date and reporting currency. |
| News and filings | Google News RSS supplies headlines. [NSE RSS](https://www.nseindia.in/static/rss-feed) and [BSE filings](https://www.bseindia.com/corporates/ann.html) supply recent disclosures. Direct exchange links are available for older or missing filings. Sentiment uses headline keywords and labels mixed or unrecognized wording as neutral. |

Streamlit caches provider calls for 10–60 minutes, depending on the feed. When a provider fails, the app can reuse the last successful SQLite snapshot for up to 3 days for news, 7 days for NSE reports and movers, 14 days for price history, or 30 days for directories and fundamentals. Snapshots retain the source, fetch timestamp in IST, and session or fiscal date where available. Expired or missing values are shown as unavailable. Portfolio valuations and watchlist triggers require a non-fallback close no more than four calendar days old. Portfolio valuations also require the close to be on or after the holding’s latest purchase date.

## Render deployment

### Optional OpenAI suggestions

Set `OPENAI_API_KEY` in the server environment or in the private `.streamlit/secrets.toml` to enable **AI guidance** for a selected stock. On Render, add it as a secret environment variable. The default model is `gpt-4.1-mini`; set the `OPENAI_MODEL` environment variable to use another accessible model. API usage can incur charges. The quick research summary, public prices, and news work without a key. For a public deployment, consider who can trigger requests against the server-funded API key.

### Web service

`render.yaml` configures the Python web service, `/_stcore/health`, custom domain `investoai.in`, and a persistent SQLite disk. It binds Streamlit to Render’s `$PORT`. For an existing Render service, apply the same build/start commands, health check and database path in its settings. Use one instance with the SQLite disk.

Locally the database defaults to `.cache/investo.sqlite3`; override its path with `INVESTO_DB_PATH`. Render’s persistent disk requires a paid service plan. Its ephemeral filesystem can be used for a demo, where workspaces and cached data may disappear on restart or redeploy. See [Render persistent disks](https://render.com/docs/disks) and [custom domain setup](https://render.com/docs/custom-domains) for the account and DNS settings.

Before serving exchange or vendor data publicly, confirm the applicable display and redistribution terms for the planned use of each feed. Public accessibility and API pricing are separate from redistribution permission. [NSE data usage policy](https://betanseapi.nseindia.com/static/market-data/nse-data-policy) · [BSE market data](https://marketdata.bseindia.com/).

## Investment disclaimer

InvestoAI is for information and education only. Nothing here constitutes investment advice, a recommendation, or an offer to buy or sell securities. Market data may be delayed or incomplete. Investing involves risk, including loss of principal. Verify figures with the exchange or issuer and consult a SEBI-registered investment adviser for personalized advice.
