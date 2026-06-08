"""Data loading and metric computation for the performance dashboard.

Reads Lobby Board building tabs from Google Sheets and turns each room row into
a normalized record. All weekly / four-weekly figures are converted to monthly.

Conventions (confirmed with the user):
  - Market Rent (column D) is a WEEKLY price -> monthly = weekly * WEEKS_PER_MONTH.
  - A room is OCCUPIED when its Amount (column E) is > 0; otherwise it is vacant.
  - Amount on a "Four-Weekly" plan is a weekly figure -> monthly = amount * WEEKS_PER_MONTH.
    Amount on a "Monthly" (or blank) plan is already monthly.
"""

from __future__ import annotations

from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from config import WEEKS_PER_MONTH, buildings, cities, sheet_id

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
SA_PATH = Path(__file__).resolve().parent.parent / "config" / "service-account.json"

# Column layout shared by every Lobby Board building tab (header lives on row 3).
HEADER_ROW = 3
COLS = [
    "no", "apartment", "room_type", "market_rent_weekly", "amount_raw",
    "plan", "source", "resident", "sex", "availability", "status",
]


def _credentials() -> Credentials:
    """Load service-account credentials.

    Prefers Streamlit secrets ([gcp_service_account] block) so the app works on
    Streamlit Community Cloud without committing the key; falls back to the local
    config/service-account.json for development.
    """
    try:
        sa = st.secrets.get("gcp_service_account")
    except Exception:
        sa = None
    if sa:
        return Credentials.from_service_account_info(dict(sa), scopes=SCOPES)
    return Credentials.from_service_account_file(str(SA_PATH), scopes=SCOPES)


@st.cache_resource(show_spinner=False)
def _client() -> gspread.Client:
    return gspread.authorize(_credentials())


def _num(value) -> float | None:
    """Parse a currency/number cell -> float, or None if not numeric."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    for token in ("CA$", "US$", "£", "$", "CA", ","):
        s = s.replace(token, "")
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        return None


def _is_room_row(no_cell) -> bool:
    return str(no_cell).strip().isdigit()


@st.cache_data(ttl=600, show_spinner=False)
def load_building(sheet_id_: str, tab: str, building_name: str, city: str) -> pd.DataFrame:
    """Load one building tab into a normalized room-level DataFrame."""
    ws = _client().open_by_key(sheet_id_).worksheet(tab)
    values = ws.get(f"A{HEADER_ROW}:K{ws.row_count}")
    data = values[1:] if values else []  # drop header row

    records: list[dict] = []
    for raw in data:
        row = list(raw) + [""] * (len(COLS) - len(raw))
        if not _is_room_row(row[0]):
            continue

        mr_weekly = _num(row[3])
        amount = _num(row[4])
        plan = str(row[5]).strip()
        is_four_weekly = plan.lower().startswith("four")

        mr_monthly = mr_weekly * WEEKS_PER_MONTH if mr_weekly is not None else 0.0
        occupied = amount is not None and amount > 0
        if occupied:
            amount_monthly = amount * WEEKS_PER_MONTH if is_four_weekly else amount
        else:
            amount_monthly = 0.0

        records.append(
            {
                "city": city,
                "building": building_name,
                "no": int(str(row[0]).strip()),
                "apartment": str(row[1]).strip(),
                "room_type": str(row[2]).strip() or "Unspecified",
                "market_rent_weekly": mr_weekly,
                "market_rent_monthly": mr_monthly,
                "amount_raw": amount,
                "amount_monthly": amount_monthly,
                "plan": plan or "—",
                "resident": str(row[7]).strip(),
                "availability": str(row[9]).strip(),
                "occupied": occupied,
            }
        )

    return pd.DataFrame(records, columns=[
        "city", "building", "no", "apartment", "room_type",
        "market_rent_weekly", "market_rent_monthly",
        "amount_raw", "amount_monthly", "plan", "resident",
        "availability", "occupied",
    ])


@st.cache_data(ttl=600, show_spinner=False)
def load_city(country: str, city: str) -> pd.DataFrame:
    """Concatenate every building in a city into one room-level DataFrame."""
    sid = sheet_id(country, city)
    frames = [
        load_building(sid, b["tab"], b["name"], city)
        for b in buildings(country, city)
    ]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_country(country: str) -> pd.DataFrame:
    """Concatenate every city in a country into one room-level DataFrame."""
    frames = [load_city(country, c) for c in cities(country)]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def metrics(df: pd.DataFrame) -> dict:
    """Compute headline KPIs for any room-level DataFrame (building/city/country)."""
    if df is None or df.empty:
        return {
            "rooms": 0, "occupied": 0, "vacant": 0,
            "market_rent": 0.0, "collected": 0.0, "vacancy_loss": 0.0,
            "occupancy": 0.0, "capture": 0.0,
        }
    occ = df[df["occupied"]]
    vac = df[~df["occupied"]]
    rooms = len(df)
    market = float(df["market_rent_monthly"].sum())
    collected = float(occ["amount_monthly"].sum())
    return {
        "rooms": rooms,
        "occupied": int(len(occ)),
        "vacant": int(len(vac)),
        "market_rent": market,
        "collected": collected,
        "vacancy_loss": float(vac["market_rent_monthly"].sum()),
        "occupancy": len(occ) / rooms if rooms else 0.0,
        "capture": collected / market if market else 0.0,
    }


def group_kpis(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Per-entity KPI table grouped by a column (e.g. 'building' or 'city')."""
    rows = []
    for name, g in df.groupby(by, sort=False):
        rows.append({by: name, **metrics(g)})
    return pd.DataFrame(rows)


def by_room_type(df: pd.DataFrame) -> pd.DataFrame:
    """Collected revenue and room counts grouped by room type."""
    rows = []
    for rt, g in df.groupby("room_type", sort=False):
        occ = g[g["occupied"]]
        rows.append({
            "room_type": rt,
            "rooms": len(g),
            "occupied": int(len(occ)),
            "collected": float(occ["amount_monthly"].sum()),
            "market_rent": float(g["market_rent_monthly"].sum()),
        })
    out = pd.DataFrame(rows)
    return out.sort_values("collected", ascending=False) if not out.empty else out
