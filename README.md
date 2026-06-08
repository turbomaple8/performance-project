# performance-pipeline

Multi-month performance reporting pipeline for a co-living business across US/CA/UK.

**Phase 1 (current):** Schema discovery only. Inspect Lobby Board "OneLob" tabs from per-city Google Sheets and CashFlow summary sheets without committing to a parser.

## Project Layout

```
performance-pipeline/
├── config/
│   ├── service-account.json   # NOT in git — see auth setup below
│   ├── cities.yaml            # placeholder
│   └── README.md
├── extractors/                # to be built in later phases
├── scripts/
│   └── discover_schema.py     # phase 1 CLI
├── docs/schema_discovery/     # output from discover_schema.py
└── runs/                      # ad-hoc run outputs (gitignored)
```

## Setup

### 1. Python environment

Requires Python 3.11+ and [`uv`](https://github.com/astral-sh/uv).

```bash
uv venv
uv pip install -e .
source .venv/bin/activate
```

### 2. Google service-account auth (manual, do once)

These steps must be done by the project owner in the Google Cloud Console. The pipeline never creates credentials itself.

1. Go to [Google Cloud Console](https://console.cloud.google.com/), create a new project (or reuse one) named `performance-pipeline`.
2. Enable two APIs on that project:
   - **Google Sheets API**
   - **Google Drive API**
3. Create a **Service Account** named `perf-pipeline-reader`. No project-level role is needed (it gets per-sheet access via Share, not IAM).
4. On the service account, create a **JSON key** and download it. Save it locally as:
   ```
   config/service-account.json
   ```
   This file is gitignored. Never commit it.
5. Note the service account email (looks like `perf-pipeline-reader@<project>.iam.gserviceaccount.com`). For each Google Sheet you want the pipeline to read (Lobby Board sheets, CashFlow sheets), open the sheet in your browser, click **Share**, paste that email, and grant **Viewer** access.

See `config/README.md` for a checklist version.

## Phase 1: Schema Discovery

Run against any sheet you have shared with the service account:

```bash
python scripts/discover_schema.py "<SHEET_URL_OR_ID>" --label <name>
```

Outputs land in `docs/schema_discovery/<label>/`:

- `tabs_overview.json` — every worksheet with row/col counts, detected header row, non-empty data row count.
- `<tab>_sample.csv` — first 40×30 raw cells, no header assumption.
- `<tab>_inferred_schema.json` — header row index, columns with first 5 non-empty sample values.

Example for the New York Lobby Board:

```bash
python scripts/discover_schema.py \
  "https://docs.google.com/spreadsheets/d/1cUTL-wNsVN5jnhJ_F5M0NY57rD1seDqfvRWvJ7x_xgc/edit" \
  --label ny_lobbyboard
```
