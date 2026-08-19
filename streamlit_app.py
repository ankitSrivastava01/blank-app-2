import os

import streamlit as st

try:
    import stripe
except ImportError:
    stripe = None

st.set_page_config(page_title="My App", layout="wide")

stripe_secret_key = st.secrets.get("STRIPE_SECRET_KEY") or os.getenv("STRIPE_SECRET_KEY", "")
stripe.api_key = stripe_secret_key if stripe else None

PRICE_IDS = {
    "basic": os.getenv("STRIPE_PRICE_BASIC", ""),
    "pro": os.getenv("STRIPE_PRICE_PRO", ""),
}

DEFAULT_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://your-domain.com/success")
DEFAULT_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://your-domain.com/cancel")

MENU_OPTIONS = ["Home", "Pricing", "Subscribe"]
page = st.sidebar.selectbox("Navigate", MENU_OPTIONS)

st.title("🎈 My new app")
st.write("A simple landing page, pricing display, and Stripe subscription checkout flow built with Streamlit.")


def create_checkout_session(price_id: str, customer_email: str):
    if not stripe or not stripe_secret_key:
        raise RuntimeError("Stripe is not configured. Set STRIPE_SECRET_KEY and install stripe.")
    if not price_id:
        raise RuntimeError("Stripe price ID is missing. Configure STRIPE_PRICE_BASIC and STRIPE_PRICE_PRO.")

    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=customer_email if customer_email else None,
        success_url=f"{DEFAULT_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=DEFAULT_CANCEL_URL,
    )
    return session.url


def show_home():
    st.header("Welcome to your custom `.com` or `.co` app")
    st.markdown(
        "Streamlit makes it easy to build and deploy interactive applications. This repo is configured for custom domains on hosts like Render or Fly."
    )

    st.subheader("Why this app?")
    st.write(
        "- Fast Streamlit landing experience\n"
        "- Built-in pricing and subscription page\n"
        "- Stripe checkout integration for recurring billing"
    )

    st.subheader("How to monetize")
    st.write(
        "Offer a free tier for casual users, then charge for premium capabilities like advanced analytics, downloads, or team access. "
        "Your app can run on a `.com`/`.co` domain after you deploy to a service that supports custom domains."
    )

    st.info("Deploy to Render, Fly, or another host and point your purchased domain to the service DNS records.")


def show_pricing():
    st.header("Pricing")
    st.write("Choose a plan and subscribe through Stripe checkout.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Basic")
        st.write("$10 / month")
        st.write("- Landing page access\n- Basic usage\n- Email support")
    with col2:
        st.subheader("Pro")
        st.write("$25 / month")
        st.write("- Everything in Basic\n- Premium features\n- Priority support")

    st.markdown("---")
    st.write("To enable checkout, set the Stripe price IDs in environment variables:")
    st.code("STRIPE_PRICE_BASIC, STRIPE_PRICE_PRO")


def show_subscribe():
    st.header("Subscribe")
    if not stripe or not stripe_secret_key:
        st.warning(
            "Stripe is not configured. Add STRIPE_SECRET_KEY as an environment variable or in Streamlit secrets."
        )
        st.write(
            "On Render, add the key under Environment > Environment Variables. "
            "On Streamlit Cloud, add it to `.streamlit/secrets.toml`."
        )
        return

    plan = st.selectbox("Select a plan", ["basic", "pro"])
    email = st.text_input("Email address", type="default")
    if st.button("Start subscription"):
        try:
            checkout_url = create_checkout_session(PRICE_IDS[plan], email)
            st.success("Subscription session created successfully.")
            st.write("Click the button below to go to Stripe checkout.")
            st.markdown(f"[Continue to payment]({checkout_url})")
            st.markdown(
                "<meta http-equiv=\"refresh\" content=\"0; url={checkout_url}\">",
                unsafe_allow_html=True,
            )
        except Exception as exc:
            st.error(f"Unable to create checkout session: {exc}")
            st.write("Check your Stripe keys and price IDs.")


if page == "Home":
    show_home()
elif page == "Pricing":
    show_pricing()
else:
    show_subscribe()
