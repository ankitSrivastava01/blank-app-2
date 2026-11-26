"""Time-series calculations, headline classification and portfolio arithmetic."""

import re

import pandas as pd


def ema(series, period):
    values = series.dropna()
    if len(values) < period:
        return pd.Series(float("nan"), index=series.index)
    seeded = values.iloc[period - 1:].copy()
    seeded.iloc[0] = values.iloc[:period].mean()
    return seeded.ewm(span=period, adjust=False).mean().reindex(series.index)


def wilder_average(series, period):
    values = series.dropna()
    if len(values) < period:
        return pd.Series(float("nan"), index=series.index)
    seeded = values.iloc[period - 1:].copy()
    seeded.iloc[0] = values.iloc[:period].mean()
    return seeded.ewm(alpha=1 / period, adjust=False).mean().reindex(series.index)


def technicals(history):
    frame = history.copy()
    close = frame["Close"]
    frame["SMA 50"] = close.rolling(50).mean()
    frame["SMA 200"] = close.rolling(200).mean()
    frame["EMA 20"] = ema(close, 20)
    mean, deviation = close.rolling(20).mean(), close.rolling(20).std(ddof=0)
    frame["Upper band"] = mean + 2 * deviation
    frame["Lower band"] = mean - 2 * deviation
    changes = close.diff()
    gain = wilder_average(changes.clip(lower=0), 14)
    loss = wilder_average(-changes.clip(upper=0), 14)
    frame["RSI 14"] = (100 - 100 / (1 + gain / loss)).mask((gain == 0) & (loss == 0), 50)
    frame["MACD"] = ema(close, 12) - ema(close, 26)
    frame["Signal"] = ema(frame["MACD"], 9)
    frame["Histogram"] = frame["MACD"] - frame["Signal"]
    return frame


POSITIVE = re.compile(r"\b(?:beat(?:s|ing)? (?:estimates|expectations)|profit (?:jump\w*|ris\w*|soar\w*|up)|(?:gains?|rall(?:y|ies)|surges?|soars?|jumps?|upgrades?|record profit|wins? (?:order|contract)))\b", re.I)
NEGATIVE = re.compile(r"\b(?:miss(?:es|ed)? (?:estimates|expectations)|profit (?:fall\w*|drop\w*|slip\w*|down)|(?:falls?|plunges?|slumps?|downgrades?|fraud|losses|sell-off|default(?:s|ed)?))\b", re.I)


def sentiment(title):
    positive = bool(POSITIVE.search(title))
    negative = bool(NEGATIVE.search(title))
    if positive == negative:
        return "Neutral"
    return "Positive" if positive else "Negative"


def position_cost(purchases):
    quantity = sum(row["quantity"] for row in purchases)
    cost = sum(row["quantity"] * row["price_paise"] for row in purchases) / 100
    return quantity, cost


def alert_status(direction, target, price, usable):
    if direction is None:
        return "—"
    if not usable or price is None:
        return "Awaiting recent close"
    reached = price >= target if direction == "At or above" else price <= target
    return "Target met" if reached else "Monitoring"
