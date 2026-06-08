# config/

## `service-account.json`

This file is **not** in git (see `.gitignore`). Place it here manually:

1. In [Google Cloud Console](https://console.cloud.google.com/), pick or create a project named `performance-pipeline`.
2. Enable **Google Sheets API** and **Google Drive API** for that project.
3. **IAM & Admin → Service Accounts → Create**. Name: `perf-pipeline-reader`. No project-level role required.
4. Open the new service account → **Keys** → **Add key → Create new key → JSON**. Download.
5. Save the downloaded file at `config/service-account.json` (this exact path).
6. Copy the service account email (e.g. `perf-pipeline-reader@<project>.iam.gserviceaccount.com`).
7. For every Google Sheet the pipeline must read:
   - Open the sheet, click **Share**.
   - Paste the service account email.
   - Grant **Viewer** access. Uncheck "Notify people".

Without step 7 the pipeline gets `gspread.exceptions.SpreadsheetNotFound` even though the sheet exists — the service account simply has no read grant on it.

## `cities.yaml`

Reserved for later phases — will map per-city Lobby Board sheets to country/region groupings. Currently empty.
