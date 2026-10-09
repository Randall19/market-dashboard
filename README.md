# Market Data Dashboard

A Streamlit dashboard for viewing market prices, interest rates, credit spreads, stablecoin market capitalization, and Aave USDC supply APY.

## Open the live dashboard

After deploying the app on Streamlit Community Cloud, paste the public app URL here:

**[Open the interactive Market Data Dashboard](PASTE_YOUR_STREAMLIT_APP_URL_HERE)**

## Run locally

Install Python 3.12, create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure your FRED key as an environment variable before starting the app:

```bash
export FRED_API_KEY="YOUR_ACTUAL_FRED_API_KEY"
streamlit run Dash_Button.py
```

## Deploy

Deploy this repository on [Streamlit Community Cloud](https://share.streamlit.io/). Select `Dash_Button.py` as the app's main file. In the deployment's **Advanced settings → Secrets** field, enter:

```toml
FRED_API_KEY = "YOUR_ACTUAL_FRED_API_KEY"
```

Never commit a real API key or `.streamlit/secrets.toml` to GitHub. The `.gitignore` in this repository excludes the local secrets file.

## Dependencies

Python packages are listed in `requirements.txt`. The app uses FRED, Yahoo Finance, DefiLlama's stablecoin API, and Aave's API, so the deployed service needs outbound internet access to those services.
