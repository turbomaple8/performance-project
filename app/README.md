# Performance Dashboard (Streamlit)

Country → City → Building navigation with monthly performance KPIs.
Currently live: **Canada › Vancouver** (8 buildings, read from the Vancouver Lobby Board sheet). US and UK appear in the nav as placeholders.

## Run

```bash
uv pip install -e .            # or: uv pip install streamlit plotly
.venv/bin/streamlit run app/streamlit_app.py
```

Then open http://localhost:8501.

## Files

- `config.py`   — registry of countries / cities / buildings + the Vancouver sheet id and conversion constant.
- `data.py`     — Google Sheets loading + normalization + KPI math (cached).
- `streamlit_app.py` — the UI (sidebar nav, KPI cards, charts, tables).
- `style.css`   — dashboard theme.

## Metric rules (confirmed with the user)

- **Market Rent** (col D) is a *weekly* price → monthly = `weekly × 4.34524`.
- A room is **occupied** when its **Amount (col E) > 0**; otherwise it is vacant.
- **Collected rent**: amount on a `Four-Weekly` plan is treated as a weekly figure → `× 4.34524`; `Monthly` (or blank) amounts are used as-is.
- **Vacancy loss** = monthly market rent of the vacant rooms.
- **Revenue capture** = collected ÷ market rent.

Three report scopes, driven by the sidebar:
- **Building** — pick a specific building (room-level table, occupancy donut, capture gauge).
- **City** — "All buildings" (per-building comparison).
- **Country** — "All cities" (per-city comparison).
