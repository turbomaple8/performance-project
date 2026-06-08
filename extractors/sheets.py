"""Shared Google Sheets access + value parsing for the pipeline."""

from __future__ import annotations

import re
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

_REPO = Path(__file__).resolve().parent.parent
_SA = _REPO / "config" / "service-account.json"
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_client = None


def client() -> gspread.Client:
    global _client
    if _client is None:
        _client = gspread.authorize(
            Credentials.from_service_account_file(str(_SA), scopes=_SCOPES)
        )
    return _client


def open_sheet(sheet_id: str):
    return client().open_by_key(sheet_id)


def worksheet_by_gid(sheet_id: str, gid: int):
    return next(w for w in open_sheet(sheet_id).worksheets() if w.id == gid)


_NUM_JUNK = {"", "-", "#REF!", "#DIV/0!", "#N/A", "#VALUE!"}


def num(s) -> float:
    """Parse a currency/number string. Handles $, CA$, £, commas, leading-,
    parens-negative, em-dash-as-zero. Returns 0.0 for blanks/errors."""
    s = str(s if s is not None else "").strip()
    if s in _NUM_JUNK:
        return 0.0
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    cleaned = re.sub(r"[^0-9.]", "", s)
    if cleaned == "" or cleaned == ".":
        return 0.0
    return -float(cleaned) if neg else float(cleaned)


def parse_ym(s) -> tuple[int, int] | None:
    """Parse a sheet date in any of the observed formats to (year, month).
    Accepts MM/DD/YYYY, MM/DD/YY, M.DD.YYYY, MM.DD.YYYY. Month is the first token."""
    s = str(s if s is not None else "").strip()
    if not s:
        return None
    m = re.match(r"^\s*(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", s)
    if not m:
        return None
    month = int(m.group(1))
    year = int(m.group(3))
    if year < 100:
        year += 2000
    if not (1 <= month <= 12):
        return None
    return year, month
