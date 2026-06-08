"""Schema discovery for Google Sheets used by the performance pipeline.

Phase 1 only: inspect a sheet's tabs, sample raw cells, and write structural
artifacts to docs/schema_discovery/<label>/. No extraction, no normalization.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

import click
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICE_ACCOUNT_PATH = REPO_ROOT / "config" / "service-account.json"
OUTPUT_ROOT = REPO_ROOT / "docs" / "schema_discovery"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

SAMPLE_ROWS = 40
SAMPLE_COLS = 30
HEADER_MAX_CELL_LEN = 40
HEADER_MIN_STRING_RATIO = 0.6
NON_EMPTY_PROBE_COLS = 5

FLAGGED_TABS = {"OneLob", "Summary", "New York"}

console = Console()


def safe_name(name: str) -> str:
    """Make a tab title safe for use as a filename."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "untitled"


def extract_sheet_id(url_or_id: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        return match.group(1)
    return url_or_id.strip()


def looks_like_header_row(row: list[str]) -> bool:
    """Heuristic: ≥60% of non-empty cells are short strings, no leading number/date."""
    non_empty = [c.strip() for c in row if c is not None and str(c).strip() != ""]
    if not non_empty:
        return False
    string_like = 0
    for cell in non_empty:
        if len(cell) > HEADER_MAX_CELL_LEN:
            continue
        if re.match(r"^\s*[-+]?\d", cell):
            continue
        if re.match(r"^\s*\d{1,4}[-/]\d", cell):
            continue
        string_like += 1
    return (string_like / len(non_empty)) >= HEADER_MIN_STRING_RATIO


def detect_header_row(grid: list[list[str]]) -> int | None:
    """Return the 0-based index of the first row that looks like a header, or None."""
    for idx, row in enumerate(grid[:SAMPLE_ROWS]):
        if looks_like_header_row(row):
            return idx
    return None


def count_non_empty_data_rows(grid: list[list[str]], header_idx: int) -> int:
    """Count rows below header where any of the first N columns is non-empty."""
    count = 0
    for row in grid[header_idx + 1 :]:
        probe = row[:NON_EMPTY_PROBE_COLS]
        if any((c is not None and str(c).strip() != "") for c in probe):
            count += 1
    return count


def build_inferred_schema(
    grid: list[list[str]], header_idx: int | None
) -> dict[str, Any]:
    if header_idx is None:
        return {"header_row_index": None, "columns": []}

    header = grid[header_idx]
    columns: list[dict[str, Any]] = []
    data_rows = grid[header_idx + 1 :]
    for col_idx, col_name in enumerate(header):
        samples: list[str] = []
        for row in data_rows:
            if col_idx >= len(row):
                continue
            val = row[col_idx]
            if val is None:
                continue
            sval = str(val).strip()
            if sval == "":
                continue
            samples.append(sval)
            if len(samples) >= 5:
                break
        columns.append(
            {
                "index": col_idx,
                "name": str(col_name).strip() if col_name is not None else "",
                "sample_values": samples,
            }
        )
    return {"header_row_index": header_idx, "columns": columns}


def write_csv_sample(path: Path, grid: list[list[str]]) -> None:
    rows = grid[:SAMPLE_ROWS]
    width = SAMPLE_COLS
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        for row in rows:
            padded = list(row[:width]) + [""] * max(0, width - len(row))
            writer.writerow(padded)


def fetch_grid(ws: gspread.Worksheet) -> list[list[str]]:
    """Fetch first SAMPLE_ROWS x SAMPLE_COLS as raw values."""
    try:
        end_col_letter = gspread.utils.rowcol_to_a1(1, SAMPLE_COLS).rstrip("1")
        end_row = SAMPLE_ROWS
        rng = f"A1:{end_col_letter}{end_row}"
        values = ws.get(rng)
    except APIError as e:
        console.print(f"  [yellow]API error fetching {ws.title!r}: {e}[/yellow]")
        return []
    return [list(row) for row in values] if values else []


def authenticate() -> gspread.Client:
    if not SERVICE_ACCOUNT_PATH.exists():
        console.print(
            f"[red]ERROR:[/red] missing service account key at {SERVICE_ACCOUNT_PATH}.\n"
            "Follow steps in config/README.md before running this script."
        )
        sys.exit(2)
    creds = Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_PATH), scopes=SCOPES
    )
    return gspread.authorize(creds)


def discover(sheet_url_or_id: str, label: str) -> None:
    sheet_id = extract_sheet_id(sheet_url_or_id)
    out_dir = OUTPUT_ROOT / label
    out_dir.mkdir(parents=True, exist_ok=True)

    client = authenticate()
    try:
        sh = client.open_by_key(sheet_id)
    except SpreadsheetNotFound:
        console.print(
            f"[red]ERROR:[/red] sheet {sheet_id} not found or not shared with the service account."
        )
        sys.exit(3)

    inspected_at = dt.datetime.now(dt.timezone.utc).isoformat()

    try:
        last_modified = sh.lastUpdateTime  # type: ignore[attr-defined]
    except Exception:
        last_modified = None

    overview: list[dict[str, Any]] = []
    flagged_hits: list[str] = []

    for ws in sh.worksheets():
        title = ws.title
        gid = ws.id
        rows = ws.row_count
        cols = ws.col_count

        grid = fetch_grid(ws)
        header_idx = detect_header_row(grid) if grid else None
        if header_idx is not None:
            data_rows = count_non_empty_data_rows(grid, header_idx)
            header_columns = [str(c).strip() for c in grid[header_idx][:SAMPLE_COLS]]
        else:
            data_rows = sum(
                1
                for row in grid
                if any(
                    (c is not None and str(c).strip() != "")
                    for c in row[:NON_EMPTY_PROBE_COLS]
                )
            )
            header_columns = []

        entry = {
            "title": title,
            "gid": gid,
            "rows": rows,
            "cols": cols,
            "header_row_index": header_idx,
            "header_columns": header_columns,
            "non_empty_data_rows": data_rows,
            "last_inspected_at": inspected_at,
        }
        overview.append(entry)

        if title in FLAGGED_TABS:
            flagged_hits.append(title)

        sname = safe_name(title)
        write_csv_sample(out_dir / f"{sname}_sample.csv", grid)
        schema = build_inferred_schema(grid, header_idx)
        (out_dir / f"{sname}_inferred_schema.json").write_text(
            json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    (out_dir / "tabs_overview.json").write_text(
        json.dumps(
            {
                "sheet_title": sh.title,
                "sheet_id": sheet_id,
                "last_modified": last_modified,
                "inspected_at": inspected_at,
                "tabs": overview,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    table = Table(title=f"{label}: {sh.title}")
    table.add_column("Tab", style="cyan", no_wrap=True)
    table.add_column("gid", justify="right")
    table.add_column("Rows", justify="right")
    table.add_column("Cols", justify="right")
    table.add_column("Header row", justify="right")
    table.add_column("Data rows", justify="right")
    table.add_column("Flag", style="magenta")
    for entry in overview:
        flag = "★" if entry["title"] in FLAGGED_TABS else ""
        hdr = "—" if entry["header_row_index"] is None else str(entry["header_row_index"])
        table.add_row(
            entry["title"],
            str(entry["gid"]),
            str(entry["rows"]),
            str(entry["cols"]),
            hdr,
            str(entry["non_empty_data_rows"]),
            flag,
        )
    console.print(table)
    if flagged_hits:
        console.print(
            f"[bold magenta]Flagged tabs found:[/bold magenta] {', '.join(flagged_hits)}"
        )
    else:
        console.print("[yellow]No flagged tabs (OneLob / Summary / New York) found.[/yellow]")
    console.print(f"[green]Wrote artifacts to[/green] {out_dir}")


@click.command()
@click.argument("sheet", required=True)
@click.option("--label", required=True, help="Short name for output directory.")
def main(sheet: str, label: str) -> None:
    """Discover the schema of a Google Sheet (Phase 1)."""
    discover(sheet, label)


if __name__ == "__main__":
    main()
