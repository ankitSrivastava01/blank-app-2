"""Interactive daily price charts and plain-language price context."""

import altair as alt
import pandas as pd
import streamlit as st


def prepare_price_history(history, period):
    frame = history.copy().sort_index()
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    frame = frame[frame["Close"].gt(0) & frame["Close"].lt(float("inf"))]
    if frame.empty:
        return frame
    # Calculate averages before trimming the display window.
    frame["50-day average"] = frame["Close"].rolling(50, min_periods=50).mean()
    frame["200-day average"] = frame["Close"].rolling(200, min_periods=200).mean()
    if period == "1W":
        frame = frame.loc[frame.index >= frame.index[-1] - pd.Timedelta(days=7)]
    elif period != "1Y":
        months = {"1M": 1, "3M": 3, "6M": 6}[period]
        frame = frame.loc[frame.index >= frame.index[-1] - pd.DateOffset(months=months)]
    return frame.rename_axis("Date").reset_index()


def render_price_chart(history, currency, symbol):
    period = st.radio("Chart period", ["1W", "1M", "3M", "6M", "1Y"], index=4,
                      horizontal=True, key=f"price_period_{symbol}",
                      help="Show about one week, one month, three months, six months, or the available past year. The window ends at the latest returned trading date.")
    frame = prepare_price_history(history, period)
    if frame.empty:
        st.info("No valid prices are available for this chart.")
        return
    has_ohlc = all(column in frame and pd.to_numeric(frame[column], errors="coerce").notna().any()
                   for column in ["Open", "High", "Low"])
    style = st.selectbox("Chart style", ["Line", "Candlestick"] if has_ohlc else ["Line"],
                         key=f"price_style_{symbol}", help="A line shows daily closing prices. A candlestick shows the open, high, low, and close for each trading day.")
    averages = st.multiselect("Compare with moving averages", ["50-day average", "200-day average"],
                              key=f"price_averages_{symbol}", help="A moving average smooths past closing prices. It needs 50 or 200 daily closes and can lag changes in the market.")
    base = alt.Chart(frame).encode(x=alt.X("Date:T", title="Trading date"))
    y_title = f"Adjusted price ({currency})"
    if style == "Candlestick":
        color = alt.condition("datum.Close >= datum.Open", alt.value("#4fd1c5"), alt.value("#ff8a80"))
        tooltip = [alt.Tooltip("Date:T"), *[alt.Tooltip(f"{c}:Q", format=",.2f") for c in ["Open", "High", "Low", "Close"]]]
        chart = (base.mark_rule().encode(y=alt.Y("Low:Q", title=y_title, scale=alt.Scale(zero=False)), y2="High:Q", color=color, tooltip=tooltip)
                 + base.mark_bar(size=5).encode(y="Open:Q", y2="Close:Q", color=color, tooltip=tooltip))
        st.caption("Mint candles: close at or above the open. Coral candles: close below the open. The thin line shows the day's high and low; all values are adjusted daily prices.")
    else:
        chart = base.mark_line(color="#4fd1c5").encode(
            y=alt.Y("Close:Q", title=y_title, scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("Close:Q", format=",.2f")])
    for average, color in [("50-day average", "#ffd166"), ("200-day average", "#b8a4ff")]:
        if average in averages:
            if frame[average].notna().any():
                chart += base.mark_line(color=color, strokeDash=[6, 3]).encode(
                    y=alt.Y(f"{average}:Q", title=y_title),
                    tooltip=[alt.Tooltip("Date:T"), alt.Tooltip(f"{average}:Q", format=",.2f")])
                st.caption(f"{average}: {'gold' if average.startswith('50') else 'lavender'} dashed line.")
            else:
                st.caption(f"{average}: not enough daily history to calculate it.")
    st.altair_chart(chart.interactive(), width="stretch")
    st.caption(f"Showing {frame['Date'].iloc[0]:%d %b %Y} to {frame['Date'].iloc[-1]:%d %b %Y}. Charts use daily prices, not an intraday feed. Different currencies are not converted.")
    close = frame["Close"]
    cols = st.columns(4)
    cols[0].metric("Period change", "Unavailable" if len(close) < 2 else f"{(close.iloc[-1] / close.iloc[0] - 1) * 100:+.2f}%",
                   help="Change between the first and last closing prices visible in this chart. It can differ from the fixed 1W/1M figures below because those count trading sessions.")
    cols[1].metric("Highest close", f"{close.max():,.2f} {currency}", help="Highest adjusted daily closing price in the selected chart window, not the intraday high.")
    cols[2].metric("Lowest close", f"{close.min():,.2f} {currency}", help="Lowest adjusted daily closing price in the selected chart window, not the intraday low.")
    cols[3].metric("Trading sessions shown", len(frame))
    if "Volume" in frame and pd.to_numeric(frame["Volume"], errors="coerce").gt(0).any():
        if st.checkbox("Show trading volume", key=f"price_volume_{symbol}", help="Volume is the number of shares traded during a session. More activity does not by itself tell you whether the price will rise."):
            volume = base.mark_bar(color="#70b4da").encode(y=alt.Y("Volume:Q", title="Shares traded"),
                         tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("Volume:Q", format=",")]).properties(height=150)
            st.altair_chart(volume, width="stretch")
