# AI Market Research

A separate US-focused research dashboard. It shows recent Google News search headlines and reported merger and acquisition stories, example market snapshots from Yahoo Finance, and optional Groq-generated educational analysis based on the data returned.

## Run

```sh
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Add `GROQ_API_KEY = "your-key"` to `.streamlit/secrets.toml` or set the environment variable. Secrets are not copied from the original app and are ignored by Git.

Prices may be delayed. News search results may include rumors, proposed or completed deals, and unrelated articles; check the linked source. Yahoo may block cloud environments. Market snapshots are examples, not a complete screener, and unavailable data is labeled. AI output is educational, may be inaccurate, and is not personalized financial advice. Mutual fund minimums, fees and fractional-share availability must be checked with a broker.

## India stock suggestions

Select **India stock dashboard** in the sidebar to filter the NSE sector lists by sector, share price, P/E, annual revenue and profit growth, and ROE. The app shows up to 12 qualifying companies ranked by annual profit growth, with lower P/E breaking ties. Select a stock to see its growth table, company details, chart, and company news. Chart ranges run from 1D to 1Y. Set `OPENAI_API_KEY` in the environment or private Streamlit secrets for optional AI guidance.
