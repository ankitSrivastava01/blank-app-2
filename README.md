# AI Market Research

A separate US-focused research dashboard. It shows recent Google News search headlines and reported merger and acquisition stories, example market snapshots from Yahoo Finance, and optional Groq-generated educational analysis based on the data returned.

## Run

```sh
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Choose Groq or OpenAI in the AI research tab. Set `GROQ_API_KEY` or `OPENAI_API_KEY` in `.streamlit/secrets.toml` or as an environment variable. Add the corresponding secret to Streamlit Cloud for a deployed app. The OpenAI option uses `gpt-4.1-mini` and requires API access and billing. Secrets are ignored by Git.

Prices may be delayed. News search results may include rumors, proposed or completed deals, and unrelated articles; check the linked source. Yahoo may block cloud environments. Market snapshots are examples, not a complete screener, and unavailable data is labeled. AI output is educational, may be inaccurate, and is not personalized financial advice. Mutual fund minimums, fees and fractional-share availability must be checked with a broker.
