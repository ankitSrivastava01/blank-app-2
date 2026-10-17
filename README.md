# Market Brief

A Streamlit company research dashboard with a company selector, recent adjusted-price history, return snapshots, headlines, and an optional Groq-generated educational briefing.

## Run locally

```sh
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Enable AI briefings

Set `GROQ_API_KEY` in the environment, or add it to `.streamlit/secrets.toml`:

```toml
GROQ_API_KEY = "your-groq-api-key"
```

Without the key, price history and news remain available; only AI briefings are disabled. Groq is called only when the user selects **Generate AI briefing**.

## Deployment

Use this start command on Streamlit-compatible hosts:

```sh
streamlit run streamlit_app.py --server.port $PORT --server.enableCORS false --server.headless true
```

Configure `GROQ_API_KEY` as a host secret to enable AI briefings.

## Data and use

Market history and headlines are retrieved through Yahoo Finance via `yfinance`. Availability, delays, and coverage depend on that upstream service. The dashboard is for educational research only and does not provide personalized investment advice or buy, sell, or hold recommendations. AI summaries use the currently displayed performance and returned headline titles; verify information with primary sources before making financial decisions.
