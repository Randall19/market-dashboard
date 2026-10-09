# Detailed deployment guide: Dash_Button.py on GitHub + Streamlit Community Cloud

These steps are written for Linux Mint XFCE and assume the working program is named `Dash_Button.py`.

## Part A — Download and keep a local copy

1. Download the prepared `Dash_Button.py`, `requirements.txt`, `.gitignore`, `README.md`, and this guide.
2. Put them in a new folder, for example `~/Documents/Cryptocurrency/market-dashboard`.
3. Keep your original working dashboard and existing environment variable setup unchanged until the cloud copy is deployed and tested.

## Part B — Understand and create `requirements.txt`

`requirements.txt` is a plain-text list of third-party Python packages the cloud computer must install. It does not contain Python code or API keys. This project imports these third-party packages:

```text
streamlit==1.55.0
yfinance
pandas
requests
numpy
altair
```

The file is already prepared. If you ever need to create it manually in Linux Mint:

1. Open a terminal.
2. Change to your project folder, e.g. `cd ~/Documents/Cryptocurrency/market-dashboard`.
3. Run `nano requirements.txt` (or use your preferred text editor).
4. Type the six package lines shown above, one per line.
5. In nano, press `Ctrl+O`, press `Enter` to save, then `Ctrl+X` to exit.
6. Check the file with `cat requirements.txt`.

Do not list built-in modules such as `datetime`, `json`, `time`, `os`, or `logging`; Python already supplies them. `streamlit==1.55.0` matches the version used by this dashboard. The remaining package versions are left unpinned so pip can resolve compatible releases; if a future update causes a compatibility problem, pin the versions from the working local environment.

## Part C — Test the prepared copy locally

1. Open a terminal and enter the project directory.
2. Activate the same virtual environment you use for your dashboard, or create a fresh one:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Make sure the FRED key is set in your shell. If you already set it in `~/.bashrc`, open a new terminal or run `source ~/.bashrc`. Confirm that it exists without printing the secret itself:

   ```bash
   if [ -n "$FRED_API_KEY" ]; then echo "FRED key is set"; else echo "FRED key is missing"; fi
   ```

4. Run the app:

   ```bash
   streamlit run Dash_Button.py
   ```

5. Check the charts in your browser. Stop the local server with `Ctrl+C` in the terminal when finished.

## Part D — Create a GitHub repository in the browser

1. Sign in at https://github.com/.
2. Open https://github.com/new.
3. Repository name: `market-dashboard` (or choose another name).
4. Add a short description such as `Interactive Streamlit market data dashboard`.
5. Choose **Public** if you want anyone to see the source code, or **Private** if you want to restrict source-code access. The running app's access settings are separate; check them before sharing a public URL.
6. For the easiest first upload, select **Add a README file** only if you intend to replace it with the prepared README. Then click **Create repository**.
7. In the new repository, use **Add file → Upload files**.
8. Upload `Dash_Button.py`, `requirements.txt`, `.gitignore`, and `README.md`. You can also upload `DEPLOYMENT_GUIDE.md`. Do not upload a real `secrets.toml`, `.env` file, or any file containing the API key.
9. If you created the repository with an initial README, confirm/replace the README content as appropriate.
10. Enter a commit message such as `Add Streamlit market dashboard` and click **Commit changes**.

## Part E — Add the FRED key privately to Streamlit Cloud

1. Open https://share.streamlit.io/.
2. Sign in using the GitHub account that owns or can access the repository.
3. Click **Create app**.
4. Select the repository you just created, its branch (usually `main`), and the main file path `Dash_Button.py`.
5. Open **Advanced settings** before deploying.
6. Select Python 3.12 if a Python version selector is shown. This matches the user's local Python 3.12 environment.
7. In the **Secrets** text box, enter this TOML with your actual FRED key substituted for the placeholder:

   ```toml
   FRED_API_KEY = "YOUR_ACTUAL_FRED_API_KEY"
   ```

8. Do not enter the actual key in GitHub. Do not paste it into chat, the README, or the Python source file.
9. Save the settings and click **Deploy**.

## Part F — Test and share

1. Wait for Streamlit Community Cloud to install dependencies and launch the app.
2. Open the app's assigned `https://...streamlit.app` address.
3. Confirm the charts load and no `FRED_API_KEY` error appears.
4. If it fails, open the app's logs in Streamlit Cloud. Typical causes are a missing dependency, a secret typo, or an external API temporarily failing.
5. Copy the actual Streamlit app URL.
6. Edit `README.md` in GitHub and replace `PASTE_YOUR_STREAMLIT_APP_URL_HERE` with that URL. Commit the change.
7. Share the Streamlit app URL directly, or send people to the GitHub repository's README and let them click its dashboard link.

## Security checklist

- [ ] `FRED_API_KEY` is read from `st.secrets` or the local environment.
- [ ] The actual API key is not in `Dash_Button.py`.
- [ ] No real `.streamlit/secrets.toml` or `.env` is uploaded.
- [ ] `.gitignore` is uploaded.
- [ ] The real key is configured in Streamlit Cloud's Secrets settings.
- [ ] The dashboard loads successfully before sharing its link.

If the key was ever committed to a public repository, revoke or regenerate it. Deleting it in a later commit alone does not remove it from earlier Git history.
