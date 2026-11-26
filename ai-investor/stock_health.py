"""Transparent screening heuristics, separate from any price forecast."""

import math

import pandas as pd

from market_data import number


def technical_indicators(history):
    result = {key: None for key in ["close", "sma50", "sma200", "rsi14", "macd", "signal", "histogram"]}
    if history.empty or "Close" not in history:
        return result
    close = pd.to_numeric(history.sort_index()["Close"], errors="coerce").astype(float)
    close = close[close.gt(0) & close.map(lambda x: number(x) is not None)]
    if close.empty:
        return result
    result["close"] = float(close.iloc[-1])
    for period in [50, 200]:
        if len(close) >= period:
            result[f"sma{period}"] = float(close.iloc[-period:].mean())
    if len(close) >= 15:
        changes = close.diff().iloc[1:]
        gains, losses = changes.clip(lower=0), -changes.clip(upper=0)
        gain, loss = float(gains.iloc[:14].mean()), float(losses.iloc[:14].mean())
        for i in range(14, len(changes)):
            gain = (gain * 13 + float(gains.iloc[i])) / 14
            loss = (loss * 13 + float(losses.iloc[i])) / 14
        result["rsi14"] = 50.0 if gain == loss == 0 else 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)

    def ema(series, period):
        valid = series.dropna()
        out = pd.Series(float("nan"), index=series.index)
        if len(valid) >= period:
            seeded = valid.iloc[period - 1:].copy()
            seeded.iloc[0] = valid.iloc[:period].mean()
            out.loc[seeded.index] = seeded.ewm(span=period, adjust=False).mean()
        return out

    macd = ema(close, 12) - ema(close, 26)
    signal = ema(macd, 9)
    result["macd"] = number(macd.iloc[-1])
    result["signal"] = number(signal.iloc[-1])
    if result["macd"] is not None and result["signal"] is not None:
        result["histogram"] = result["macd"] - result["signal"]
    return result


def stock_health(info, history):
    technical = technical_indicators(history)
    checks = []

    def add(factor, label, value, rule, score, applicable=True):
        checks.append({"Factor": factor, "Indicator": label, "Value": value,
                       "Rule": rule, "Points": None if value is None or not applicable else score(value),
                       "Status": "Not applicable" if not applicable else "Missing" if value is None else "Included"})

    def val(key, scale=1):
        value = number(info.get(key))
        return None if value is None else value * scale

    def higher(target):
        return lambda x: 100 if x >= target else 50 if x > 0 else 0

    def lower(good, middle):
        return lambda x: 0 if x < 0 else 100 if x <= good else 50 if x <= middle else 0

    add("Fundamentals", "ROE (%)", val("returnOnEquity", 100), "≥15: 100; >0 to <15: 50; ≤0: 0", higher(15))
    add("Fundamentals", "Revenue growth YoY (%)", val("revenueGrowth", 100), "≥10: 100; >0 to <10: 50; ≤0: 0", higher(10))
    add("Fundamentals", "Earnings growth YoY (%)", val("earningsGrowth", 100), "≥15: 100; >0 to <15: 50; ≤0: 0", higher(15))
    add("Fundamentals", "Net margin (%)", val("profitMargins", 100), "≥10: 100; >0 to <10: 50; ≤0: 0", higher(10))
    add("Valuation", "Trailing P/E (x)", val("trailingPE"), "0<P/E≤20: 100; 20<P/E≤35: 50; otherwise: 0", lambda x: 0 if x <= 0 else lower(20, 35)(x))
    add("Valuation", "Price/book (x)", val("priceToBook"), "0<P/B≤3: 100; 3<P/B≤6: 50; otherwise: 0", lambda x: 0 if x <= 0 else lower(3, 6)(x))
    for period in [50, 200]:
        average = technical[f"sma{period}"]
        difference = None if average is None else (technical["close"] / average - 1) * 100
        add("Momentum", f"Close vs SMA{period} (%)", difference, "Above average: 100; equal: 50; below: 0", lambda x: 100 if x > 0 else 50 if x == 0 else 0)
    add("Momentum", "MACD minus signal", technical["histogram"], "Above signal: 100; equal: 50; below: 0", lambda x: 100 if x > 0 else 50 if x == 0 else 0)
    financial = info.get("sector") in {"Financial Services", "Financials"}
    add("Risk", "Debt/equity (x)", val("debtToEquity", 0.01), "0–0.5: 100; >0.5–1: 50; >1 or negative equity: 0", lower(0.5, 1), not financial)
    add("Risk", "Current ratio (x)", val("currentRatio"), "≥1.5: 100; ≥1 to <1.5: 50; <1: 0", lambda x: 100 if x >= 1.5 else 50 if x >= 1 else 0, not financial)
    add("Risk", "Absolute beta", None if val("beta") is None else abs(val("beta")), "≤1: 100; >1–1.5: 50; >1.5: 0", lower(1, 1.5))
    factors = {}
    for factor in ["Fundamentals", "Valuation", "Momentum", "Risk"]:
        values = [c["Points"] for c in checks if c["Factor"] == factor and c["Points"] is not None]
        factors[factor] = None if not values else sum(values) / len(values)
    applicable = sum(c["Status"] != "Not applicable" for c in checks)
    available = sum(c["Points"] is not None for c in checks)
    enough = all(v is not None for v in factors.values()) and available >= math.ceil(applicable * 2 / 3)
    overall = sum(factors.values()) / 4 if enough else None
    return {"overall": overall, "factors": factors, "checks": checks,
            "available": available, "applicable": applicable, "technical": technical}
