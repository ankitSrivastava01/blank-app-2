# 🎈 Blank app template

A simple Streamlit app template with landing, pricing, and Stripe subscription support.

## Deploy to a host that supports `.com` / `.co`

This repo is configured for services like Render or Fly that allow custom domains.

### Recommended host: Render

1. Push this repository to GitHub.
2. Create a new Web Service on Render and connect the repo.
3. Use the following start command:

   ```sh
   streamlit run streamlit_app.py --server.port $PORT --server.enableCORS false --server.headless true
   ```

4. Add these environment variables in Render:
   - `STRIPE_SECRET_KEY`
   - `STRIPE_PRICE_BASIC`
   - `STRIPE_PRICE_PRO`
   - `STRIPE_SUCCESS_URL`
   - `STRIPE_CANCEL_URL`

5. Add your `.com` or `.co` custom domain in Render's dashboard.
6. Update your domain registrar's DNS records using the values Render provides.

> Custom domains are supported by Render paid plans. If you want a free `.streamlit.app` URL, use Streamlit Community Cloud instead.

### Alternative hosts

- Fly.io
- Railway
- DigitalOcean App Platform
- AWS Elastic Beanstalk / Lightsail

These hosts also support custom domains and environment variables.

## Stripe subscription setup

1. Create a Stripe account at https://dashboard.stripe.com.
2. Add recurring prices in the Products section.
3. Copy the price IDs into `STRIPE_PRICE_BASIC` and `STRIPE_PRICE_PRO`.
4. Set `STRIPE_SUCCESS_URL` and `STRIPE_CANCEL_URL` to your deployed app URLs.

Example:

```sh
STRIPE_SUCCESS_URL=https://your-app.com/success
STRIPE_CANCEL_URL=https://your-app.com/cancel
```

## Run locally

Install dependencies:

```sh
pip install -r requirements.txt
```

Run the app:

```sh
streamlit run streamlit_app.py
```

## App pages

- `Home` — landing page and monetization overview
- `Pricing` — plan comparison
- `Subscribe` — Stripe checkout flow
