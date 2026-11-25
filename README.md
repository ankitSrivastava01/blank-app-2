# AI Market Research

A separate US-focused research dashboard. It shows recent Google News search headlines and reported merger and acquisition stories, example market snapshots from Yahoo Finance, and optional Groq-generated educational analysis based on the data returned.

## Run

```sh
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Choose Groq, OpenAI, or Gemini in the AI research tab. Set the corresponding `GROQ_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY` in `.streamlit/secrets.toml` or as an environment variable. Add the corresponding secret to Streamlit Cloud for a deployed app. OpenAI uses `gpt-4.1-mini`; Gemini uses `gemini-3.8-flash`. Provider access, limits, and charges depend on the relevant account. Secrets are ignored by Git.

Prices may be delayed. News search results may include rumors, proposed or completed deals, and unrelated articles; check the linked source. Yahoo may block cloud environments. Market snapshots are examples, not a complete screener, and unavailable data is labeled. AI output is educational, may be inaccurate, and is not personalized financial advice. Mutual fund minimums, fees and fractional-share availability must be checked with a broker.
