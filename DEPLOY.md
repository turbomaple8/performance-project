# Deploying the dashboard to Streamlit Community Cloud

Gives you a public/private URL like `https://<app-name>.streamlit.app`.

## 1. Push the code to GitHub

The repo is already initialized locally and the first commit is in place. Create
an **empty** GitHub repo (private is fine), then:

```bash
git remote add origin git@github.com:<you>/performance-pipeline.git
git branch -M main
git push -u origin main
```

The service-account key (`config/service-account.json`) and
`.streamlit/secrets.toml` are gitignored, so they are **not** pushed.

## 2. Create the app on Streamlit Cloud

1. Go to https://share.streamlit.io → **New app**.
2. Pick the repo, branch `main`, and main file **`app/streamlit_app.py`**.
3. Under **Advanced settings → Python version**, choose 3.11+.
4. Deploy. Streamlit installs from `requirements.txt` automatically.

## 3. Add the service-account secret

The app reads Google credentials from `st.secrets["gcp_service_account"]` when
present (otherwise it falls back to the local file).

1. In the app: **Settings → Secrets**.
2. Paste the block from `.streamlit/secrets.toml.example`, filling the real
   values from `config/service-account.json`. Keep the `\n` sequences inside the
   `private_key` quotes.
3. Save. The app restarts and connects to Google Sheets.

## 4. Sheet access

Every sheet the dashboard reads must be shared (Viewer) with the service account:

```
perf-pipeline-reader@performance-pipeline-495618.iam.gserviceaccount.com
```

Vancouver is already shared. Share new city/country sheets the same way as you
add them to `app/config.py`.

## 5. Restrict access (optional)

In **Settings → Sharing** set the app to private and add your team's emails so
only they can open the URL.

---

### Quick temporary share (no GitHub)

To show it instantly from your machine while it runs locally:

```bash
.venv/bin/streamlit run app/streamlit_app.py    # terminal 1
cloudflared tunnel --url http://localhost:8501   # terminal 2 -> prints a URL
```

This only works while your machine and the tunnel are running. Use Community
Cloud for a durable link.
