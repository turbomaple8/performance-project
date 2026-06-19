# Static dashboard — deploy (Vercel)

The dashboard is a **scheduled build + static site**, replacing Streamlit Cloud
(no live backend, no secrets panel, no sleeping app, no manual token re-pasting).

```
build.py            pulls Sheets (+ edge arrears) -> web/public/data.json
web/                Vite + React static site that reads data.json
vercel.json         tells Vercel how to build both (Python + Vite)
.github/workflows/  refresh.yml: 6-hourly ping to a Vercel deploy hook
```

Vercel rebuilds on every push to `main` (native Git integration) and runs
`build.py` during the build, so each deploy already has fresh data. The GitHub
Action only adds a **time-based** refresh between pushes.

## One-time setup (account: turbomaple8@gmail.com)

1. **Import the repo** at vercel.com → Add New → Project → `turbomaple8/performance-project`.
   - Root Directory: **`./`** (repo root — leave default).
   - Framework Preset: **Other** (`vercel.json` already sets the build).
   - `vercel.json` handles install (`pip install` + `npm ci`) and build
     (`python3 build.py` → `npm run build`), output `web/dist`.

2. **Environment Variables** (Project → Settings → Environment Variables,
   Production + Preview) — set **once**:
   - `GCP_SERVICE_ACCOUNT` — full JSON of `config/service-account.json` (one line).
     `build.py`/`data.py` now read it from this env var.
   - `EDGE_REFRESH_TOKEN` — Firebase refresh token for Rent Arrears. The build
     refreshes it into a short-lived ID token every run → no manual re-pasting.

3. **🔒 Access control (REQUIRED — data has tenant PII):** Project → Settings →
   Deployment Protection → enable **Vercel Authentication** (Vercel SSO) or set a
   **Password**. Without this the dashboard would expose arrears debtor names and
   resident names publicly. `data.json` is gitignored so PII never enters the repo.

4. **Scheduled refresh:** Project → Settings → Git → **Deploy Hooks** → create one
   for branch `main`. Copy the URL into the GitHub repo secret
   `VERCEL_DEPLOY_HOOK` (Settings → Secrets and variables → Actions). The
   `refresh-data` workflow pings it every 6 hours.

## Local dev

```
.venv/bin/python build.py        # writes web/public/data.json
cd web && npm install && npm run dev
```

## Notes
- Vercel's build image has `python3` + `pip3`, so `build.py` runs in the build.
- To change cadence, edit the cron in `.github/workflows/refresh.yml`.
- The old Streamlit app (`app/streamlit_app.py`) still runs locally as a dev view.
