# Lobby Metrics — static dashboard

Vite + React site that renders the co-living performance dashboard from a
prebuilt `public/data.json` (produced by `../build.py`). No backend, no live API
calls from the browser.

```
npm install
npm run dev        # local dev (expects ../build.py to have written public/data.json)
npm run build      # -> dist/  (static, deploy anywhere)
```

- `src/App.jsx` — the whole dashboard (nav, KPIs, revenue bridge, rent arrears,
  per-group charts/tables, building room table). Charts via Plotly.
- `src/theme.css` — dark premium theme (ported from the old Streamlit `style.css`).
- Data shape: `{ generated_at, weeks_per_month, nav[], scopes{} }` where each
  scope key is `Country`, `Country|City`, or `Country|City|Building`.

See `../DEPLOY-web.md` for the scheduled build + deploy and the PII/host note.
