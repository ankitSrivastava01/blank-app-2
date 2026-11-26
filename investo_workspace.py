"""Private portfolio, watchlist and investment calculators."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
import streamlit as st

import investo_data as data
import investo_store as store
from investo_analysis import alert_status, position_cost
from investo_ui import news_list, percent, rupees, source, stock_picker, table, when

MAX_CALCULATOR_AMOUNT = 1_000_000_000_000.0
MAX_SHARES = 100_000_000


def workspace(account_page=False):
    owner = st.session_state.get("workspace_owner")
    if owner:
        if st.button("Sign out" if account_page else "Lock workspace", key="workspace_lock", on_click=lock_workspace):
            return None
        return owner
    if account_page:
        st.info("Create an InvestoAI account or sign in with your recovery code.")
    else:
        st.info("Create a private workspace or open an existing one with its recovery code.")
    if st.button("Create account" if account_page else "Create workspace", type="primary"):
        code = store.create_workspace()
        st.session_state.update(workspace_owner=store.private_owner(code), new_workspace_code=code)
        st.rerun()
    with st.form("workspace_open", clear_on_submit=True):
        code = st.text_input("Recovery code", type="password", max_chars=60)
        if st.form_submit_button("Sign in" if account_page else "Open workspace"):
            owner = store.unlock_workspace(code.strip())
            if owner:
                st.session_state.workspace_owner = owner
                st.rerun()
            st.error("Recovery code was not recognized.")
    return None


def lock_workspace():
    st.session_state.pop("workspace_owner", None)
    st.session_state.pop("new_workspace_code", None)
    st.session_state.pop("account_email", None)


def recovery_code():
    code = st.session_state.get("new_workspace_code")
    if code:
        st.warning("Save this recovery code securely. It opens your workspace and is shown only during this session.")
        st.code(code, language=None)
        if st.button("I saved my code"):
            del st.session_state["new_workspace_code"]
            st.rerun()


def account():
    st.header("InvestoAI account")
    st.caption("Your InvestoAI account and your brokerage account have separate sign-ins.")
    if getattr(st.user, "is_logged_in", False):
        st.success("You’re signed in with Google.")
        email = getattr(st.user, "email", None)
        if email:
            st.text(email)
        if st.button("Sign out"):
            lock_workspace()
            st.logout()
        return
    if st.session_state.get("workspace_owner"):
        st.success("You’re signed in to InvestoAI.")
        if st.session_state.get("account_email"):
            st.text(st.session_state.account_email)
        st.button("Sign out", on_click=lock_workspace)
        recovery_code()
        return

    method = st.radio("Sign-in method", ["Google", "Email and password", "Recovery code"], horizontal=True,
                      index=1)
    if method == "Google":
        try:
            google = st.secrets.get("auth", {}).get("google", {})
            configured = bool(google.get("client_id") and google.get("client_secret"))
        except FileNotFoundError:
            configured = False
        if configured:
            st.button("Continue with Google", on_click=st.login, args=("google",), type="primary")
        else:
            st.info("Google sign-in is available once this app has Google OAuth credentials configured.")
    elif method == "Recovery code":
        workspace(account_page=True)
    else:
        email_account_form()


def email_account_form():
    action = st.radio("Email account", ["Sign in", "Create account"], horizontal=True)
    with st.form("email_account", clear_on_submit=True):
        email = st.text_input("Email", max_chars=254)
        password = st.text_input("InvestoAI password", type="password", max_chars=128)
        if not st.form_submit_button(action, type="primary"):
            return
    try:
        owner = (store.create_email_account(email, password) if action == "Create account"
                 else store.sign_in_email(email, password))
    except ValueError as exc:
        st.error(str(exc))
        return
    if owner:
        st.session_state.workspace_owner = owner
        st.session_state.account_email = email.strip().casefold()
        st.rerun()
    st.error("Email or password was not recognized.")


def portfolio():
    st.header("Portfolio")
    owner = workspace()
    if not owner:
        return
    recovery_code()
    with st.expander("Record a purchase"):
        stock = stock_picker("purchase_stock")
        if stock:
            today = datetime.now(data.IST).date()
            with st.form("record_purchase", clear_on_submit=True):
                cols = st.columns(3)
                quantity = cols[0].number_input("Shares", min_value=1, max_value=MAX_SHARES, value=1, step=1)
                price = cols[1].number_input("Cost per share (₹)", min_value=0.01, max_value=10_000_000.0, value=100.0, step=0.01, format="%.2f")
                purchased = cols[2].date_input("Purchase date", value=today, max_value=today)
                if st.form_submit_button("Save purchase", type="primary"):
                    paise = int((Decimal(str(price)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                    store.add_purchase(owner, stock["ticker"], stock["alias"], stock["name"], quantity, paise, purchased.isoformat())
                    st.rerun()
    purchases = store.purchases(owner)
    if not purchases:
        st.caption("Add your first purchase to track average cost, unrealized returns and sector allocation.")
        return
    st.caption("Records represent open purchase lots. Remove a lot when it is no longer held. Returns use daily closes and exclude dividends, fees and taxes.")
    grouped = {}
    for row in purchases:
        grouped.setdefault(row["symbol"], []).append(row)
    instruments = {symbol: rows[-1]["alias"] for symbol, rows in grouped.items()}
    with st.spinner("Valuing holdings"):
        quotes = data.histories(instruments)
        with ThreadPoolExecutor(max_workers=5) as pool:
            finances = dict(zip(instruments, pool.map(data.fundamentals, instruments.keys(), instruments.values())))
    positions = []
    for symbol, rows in grouped.items():
        quantity, cost = position_cost(rows)
        price, _, day = data.latest_quote(quotes[symbol])
        comparable = bool(day and day >= rows[-1]["purchased"] and data.quote_usable(quotes[symbol], day))
        value = price * quantity if comparable else None
        sector = (finances[symbol]["data"] or {}).get("sector", "Unclassified")
        positions.append({"Company": rows[-1]["name"], "Listing": rows[-1]["alias"] or symbol, "Shares": quantity, "Cost (₹)": cost,
                          "Average cost (₹)": cost / quantity, "Close (₹)": price, "Value (₹)": value,
                          "Unrealized P&L (₹)": value - cost if comparable else None,
                          "Return (%)": 100 * (value / cost - 1) if comparable else None,
                          "Sector": sector, "Session": when(day), "Price source": source(quotes[symbol]),
                          "Sector source": source(finances[symbol])})
    valued = [row for row in positions if row["Value (₹)"] is not None]
    cost = sum(row["Cost (₹)"] for row in positions)
    value = sum(row["Value (₹)"] for row in valued)
    matched_cost = sum(row["Cost (₹)"] for row in valued)
    cols = st.columns(3)
    cols[0].metric("Total purchase cost", rupees(cost), border=True)
    cols[1].metric("Value of priced holdings", rupees(value) if valued else "Unavailable", border=True)
    cols[2].metric("Unrealized return", percent(100 * (value / matched_cost - 1)) if matched_cost else "Unavailable", border=True)
    st.caption(f"Valuation and aggregate return cover {len(valued)} of {len(positions)} holdings. Cached fallback and older closes are shown for reference.")
    table(positions)
    if valued:
        sectors = pd.DataFrame(valued).groupby("Sector")["Value (₹)"].sum().sort_values(ascending=False)
        st.subheader("Sector allocation by market value")
        table([{"Sector": sector, "Value": rupees(amount), "Allocation": f"{amount / value:.1%}"}
               for sector, amount in sectors.items()])
    with st.expander("Purchase history"):
        options = {row["id"]: f"{row['name']} · {row['symbol']} · {row['purchased']} · {row['quantity']} shares at {rupees(row['price_paise'] / 100)}"
                   for row in purchases}
        table([{"Date": row["purchased"], "Company": row["name"], "Listing": row["alias"] or row["symbol"],
                "Shares": row["quantity"], "Cost/share (₹)": row["price_paise"] / 100} for row in purchases])
        selection = st.selectbox("Purchase to remove", list(options), index=None, format_func=options.get)
        if st.button("Remove purchase", disabled=selection is None):
            store.remove_purchase(owner, selection)
            st.rerun()


def watchlist():
    st.header("Watchlist & alerts")
    owner = workspace()
    if not owner:
        return
    recovery_code()
    st.caption("Price targets check the latest recent daily close when this page runs. Company headlines load on selection. Alerts appear on this page.")
    with st.expander("Add a stock or update its alert"):
        stock = stock_picker("watch_stock")
        if stock:
            with st.form("save_watch"):
                direction = st.selectbox("Price alert", ["Off", "At or above", "At or below"])
                target = st.number_input("Target price (₹)", min_value=0.01, max_value=10_000_000.0, value=100.0, step=0.01)
                if st.form_submit_button("Save watch", type="primary"):
                    active = direction != "Off"
                    store.save_watch(owner, stock["ticker"], stock["alias"], stock["name"],
                                     direction if active else None, target if active else None)
                    st.rerun()
    watches = store.watchlist(owner)
    if not watches:
        st.caption("Save a listed company to follow its prices and headlines.")
        return
    quotes = data.histories({row["symbol"]: row["alias"] for row in watches})
    table_rows = []
    for row in watches:
        feed = quotes[row["symbol"]]
        price, change, day = data.latest_quote(feed)
        status = alert_status(row["direction"], row["target"], price, data.quote_usable(feed, day))
        if status == "Target met":
            st.success(f"{row['name']} · {row['direction'].lower()} {rupees(row['target'])} · {rupees(price)} on {when(day)}")
        table_rows.append({"Company": row["name"], "Listing": row["alias"] or row["symbol"], "Close": rupees(price), "Change": percent(change),
                           "Target": f"{row['direction']} {rupees(row['target'])}" if row["direction"] else "—",
                           "Alert": status, "Session": when(day), "Source": source(feed)})
    table(table_rows)
    items = {row["symbol"]: row for row in watches}
    selected = st.selectbox("Company headlines", list(items), index=None,
                            format_func=lambda symbol: f"{items[symbol]['name']} · {symbol}")
    if selected:
        news_list(data.headlines(items[selected]["name"]), show_sentiment=True)
        if st.button("Remove selected stock"):
            store.remove_watch(owner, selected)
            st.rerun()


def calculator():
    st.header("Investment calculators")
    kind = st.selectbox("Calculator", ["CAGR", "Stock returns", "Dividends", "Brokerage"])
    result = {}
    if kind == "CAGR":
        columns = st.columns(3)
        start = columns[0].number_input("Starting value (₹)", min_value=0.01, max_value=MAX_CALCULATOR_AMOUNT, value=10_000.0)
        end = columns[1].number_input("Ending value (₹)", min_value=0.0, max_value=MAX_CALCULATOR_AMOUNT, value=15_000.0)
        years = columns[2].number_input("Years", min_value=0.1, max_value=100.0, value=3.0, step=0.1)
        result["Annualized growth"] = percent(100 * ((end / start) ** (1 / years) - 1))
    elif kind == "Stock returns":
        columns = st.columns(3)
        buy = columns[0].number_input("Purchase price (₹)", min_value=0.01, max_value=MAX_CALCULATOR_AMOUNT, value=100.0)
        sell = columns[1].number_input("Sale price (₹)", min_value=0.0, max_value=MAX_CALCULATOR_AMOUNT, value=120.0)
        shares = columns[2].number_input("Shares", min_value=1, max_value=MAX_SHARES, value=10)
        dividends = st.number_input("Total dividends received (₹)", min_value=0.0, max_value=MAX_CALCULATOR_AMOUNT, value=0.0)
        fees = st.number_input("Total fees and charges (₹)", min_value=0.0, max_value=MAX_CALCULATOR_AMOUNT, value=0.0)
        gain = (sell - buy) * shares + dividends - fees
        result = {"Net gain": rupees(gain), "Return on purchase cost": percent(100 * gain / (buy * shares))}
    elif kind == "Dividends":
        columns = st.columns(3)
        shares = columns[0].number_input("Shares", min_value=1, max_value=MAX_SHARES, value=100)
        dividend = columns[1].number_input("Annual dividend per share (₹)", min_value=0.0, max_value=MAX_CALCULATOR_AMOUNT, value=5.0)
        price = columns[2].number_input("Share price (₹)", min_value=0.01, max_value=MAX_CALCULATOR_AMOUNT, value=100.0)
        result = {"Annual gross dividend": rupees(dividend * shares), "Dividend yield": percent(100 * dividend / price)}
    else:
        columns = st.columns(3)
        shares = columns[0].number_input("Shares", min_value=1, max_value=MAX_SHARES, value=10)
        buy = columns[1].number_input("Buy price (₹)", min_value=0.01, max_value=MAX_CALCULATOR_AMOUNT, value=100.0)
        sell = columns[2].number_input("Sell price (₹)", min_value=0.01, max_value=MAX_CALCULATOR_AMOUNT, value=120.0)
        rate = st.number_input("Brokerage rate per order (%)", min_value=0.0, max_value=100.0, value=0.0, format="%.3f")
        cap = st.number_input("Per-order cap (₹, 0 for uncapped)", min_value=0.0, max_value=MAX_CALCULATOR_AMOUNT, value=0.0)
        extra = st.number_input("Other charges for both orders (₹)", min_value=0.0, max_value=MAX_CALCULATOR_AMOUNT, value=0.0,
                                help="Enter the combined taxes and fees from your broker’s fee schedule.")
        buy_fee, sell_fee = buy * shares * rate / 100, sell * shares * rate / 100
        if cap:
            buy_fee, sell_fee = min(cap, buy_fee), min(cap, sell_fee)
        total = buy_fee + sell_fee + extra
        result = {"Total brokerage": rupees(buy_fee + sell_fee), "Total charges": rupees(total),
                  "Net trading gain": rupees((sell - buy) * shares - total)}
        st.caption("This estimate assumes one buy order and one sell order. Rates and additional charges come from your inputs.")
    for col, (label, value) in zip(st.columns(len(result)), result.items()):
        col.metric(label, value, border=True)
