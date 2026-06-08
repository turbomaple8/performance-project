"""Data loading and metric computation for the performance dashboard.

Reads Lobby Board building tabs from each city's Google Sheet and turns every
room row into a normalized record. Columns are mapped BY HEADER NAME (row 3), not
by fixed position, because some cities add columns (e.g. London has an extra
"Building" column). All weekly / four-weekly figures are converted to monthly.

Conventions (confirmed with the user):
  - Market Rent is a WEEKLY price -> monthly = weekly * WEEKS_PER_MONTH.
  - A room is OCCUPIED when its Amount is > 0; otherwise it is vacant.
  - Amount on a "Four-Weekly" plan is a weekly figure -> * WEEKS_PER_MONTH;
    "Monthly" (or blank) amounts are already monthly.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

from config import (
    WEEKS_PER_MONTH, cities, display_name, removed_buildings, sheet_id,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
SA_PATH = Path(__file__).resolve().parent.parent / "config" / "service-account.json"

HEADER_ROW = 3  # Lobby Board header lives on row 3 in every sheet

# Four-Weekly amount convention is inconsistent across cities: some teams enter a
# WEEKLY rate (Boston), others enter the MONTHLY amount (Vancouver, Montreal).
# Auto-detect per row: if the amount exceeds this multiple of the weekly market
# rent, it was clearly entered as a monthly figure (×4.345 would blow past market),
# so use it as-is; otherwise treat it as weekly and convert. Limitation: a genuine
# deep-discount monthly rent below ~1.5× the weekly market rate is read as weekly.
FOUR_WEEKLY_MONTHLY_RATIO = 1.5
# A tab is a building lobbyboard if its header row contains these labels.
LOBBY_TOKENS = {"MARKET RENT", "ROOM TYPE"}
OLD_RE = re.compile(r"\bOLD\b", re.IGNORECASE)  # skip stale "- OLD" tabs

# header label (lower-case) -> normalized field name
HEADER_FIELDS = {
    "no.": "no",
    "apartment": "apartment",
    "building": "building",
    "room type": "room_type",
    "market rent": "market_rent_weekly",
    "amount": "amount_raw",
    "plan": "plan",
    "current resident name": "resident",
    "room availability": "availability",
}

COLUMNS = [
    "city", "building", "no", "apartment", "room_type",
    "market_rent_weekly", "market_rent_monthly",
    "amount_raw", "amount_monthly", "plan", "resident",
    "availability", "occupied",
]


def _credentials() -> Credentials:
    """Prefer Streamlit secrets (cloud); fall back to the local key file (dev)."""
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


def _q(tab: str) -> str:
    """Quote a tab name for an A1 range."""
    return "'" + tab.replace("'", "''") + "'"


def _colmap(header: list) -> dict:
    out: dict = {}
    for i, cell in enumerate(header):
        key = str(cell).strip().lower()
        if key in HEADER_FIELDS:
            out.setdefault(HEADER_FIELDS[key], i)
    return out


def _records(rows: list, header: list, tab: str, city: str) -> list[dict]:
    cm = _colmap(header)
    mr_i = cm.get("market_rent_weekly")
    amt_i = cm.get("amount_raw")
    plan_i = cm.get("plan")
    avail_i = cm.get("availability")
    type_i = cm.get("room_type")
    apt_i = cm.get("apartment")
    no_i = cm.get("no")
    res_i = cm.get("resident")
    bld_i = cm.get("building")
    if mr_i is None or no_i is None:
        return []

    tab_label = display_name(tab)
    recs: list[dict] = []
    for row in rows:
        def g(i):
            return row[i] if (i is not None and i < len(row)) else ""

        no = str(g(no_i)).strip()
        if not no.isdigit():
            continue

        mr = _num(g(mr_i))
        amt = _num(g(amt_i))
        plan = str(g(plan_i)).strip()
        is_four_weekly = plan.lower().startswith("four")

        mr_monthly = mr * WEEKS_PER_MONTH if mr is not None else 0.0
        occupied = amt is not None and amt > 0
        if not occupied:
            amount_monthly = 0.0
        elif not is_four_weekly:
            amount_monthly = amt  # monthly plan: already monthly
        elif mr is None or amt > FOUR_WEEKLY_MONTHLY_RATIO * mr:
            amount_monthly = amt  # four-weekly cell entered as a monthly amount
        else:
            amount_monthly = amt * WEEKS_PER_MONTH  # four-weekly cell is a weekly rate

        # London-style tabs carry a per-row Building column; otherwise the tab is
        # the building.
        building = str(g(bld_i)).strip() if bld_i is not None else ""
        if not building:
            building = tab_label

        recs.append({
            "city": city,
            "building": building,
            "no": int(no),
            "apartment": str(g(apt_i)).strip(),
            "room_type": str(g(type_i)).strip() or "Unspecified",
            "market_rent_weekly": mr,
            "market_rent_monthly": mr_monthly,
            "amount_raw": amt,
            "amount_monthly": amount_monthly,
            "plan": plan or "—",
            "resident": str(g(res_i)).strip(),
            "availability": str(g(avail_i)).strip(),
            "occupied": occupied,
        })
    return recs


def _retry(fn, tries: int = 4):
    """Call fn(), retrying transient Sheets API errors (429/5xx) with backoff."""
    delay = 1.0
    for attempt in range(tries):
        try:
            return fn()
        except APIError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (429, 500, 502, 503) and attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise


@st.cache_data(ttl=600, show_spinner=False)
def load_city(country: str, city: str) -> pd.DataFrame:
    """Load every building tab in a city into one room-level DataFrame.

    One open + two batched reads per city (with retry), to stay well under the
    Sheets API rate limits when a whole country is loaded at once.
    """
    sid = sheet_id(country, city)
    if not sid:
        return pd.DataFrame(columns=COLUMNS)

    sh = _retry(lambda: _client().open_by_key(sid))
    titles = [ws.title for ws in sh.worksheets() if not OLD_RE.search(ws.title)]
    if not titles:
        return pd.DataFrame(columns=COLUMNS)

    # Detect building tabs from the header row, then fetch only those.
    head = _retry(lambda: sh.values_batch_get(
        [f"{_q(t)}!A{HEADER_ROW}:N{HEADER_ROW}" for t in titles]))["valueRanges"]
    tabs = []
    for title, vr in zip(titles, head):
        header = (vr.get("values") or [[]])
        labels = {str(c).strip().upper() for c in (header[0] if header else [])}
        if LOBBY_TOKENS <= labels:
            tabs.append(title)
    if not tabs:
        return pd.DataFrame(columns=COLUMNS)

    res = _retry(lambda: sh.values_batch_get(
        [f"{_q(t)}!A{HEADER_ROW}:N2000" for t in tabs]))["valueRanges"]
    recs: list[dict] = []
    for tab, vr in zip(tabs, res):
        values = vr.get("values") or []
        if not values:
            continue
        recs.extend(_records(values[1:], values[0], tab, city))
    df = pd.DataFrame(recs, columns=COLUMNS)
    dropped = removed_buildings(city)
    if dropped:
        df = df[~df["building"].isin(dropped)].reset_index(drop=True)
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_country(country: str) -> pd.DataFrame:
    """Concatenate every city in a country into one room-level DataFrame."""
    frames = [load_city(country, c) for c in cities(country)]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat(frames, ignore_index=True)


def active_buildings(df: pd.DataFrame) -> set:
    """Buildings with at least one occupied room (i.e. not closed/empty)."""
    if df is None or df.empty:
        return set()
    return set(df.loc[df["occupied"], "building"].unique())


# Non-occupied rooms whose availability label means "committed, revenue pending"
# (vs truly empty). Matches the original perf sheet's "Vacant room loss (booked)"
# vs "(vacant)" split. "PIpeline" is the sheet's typo for Pipeline.
BOOKED_LABELS = {"booked", "pre-booked", "prebooked", "pipeline"}


def metrics(df: pd.DataFrame) -> dict:
    """Headline KPIs for any room-level DataFrame (building/city/country).

    Loss decomposition mirrors the original performance sheet:
        market_rent = collected + price_loss + vacancy_loss
        vacancy_loss = booked_loss + vacant_loss
    """
    if df is None or df.empty:
        return {
            "rooms": 0, "occupied": 0, "vacant": 0, "booked": 0,
            "market_rent": 0.0, "collected": 0.0, "occupied_market": 0.0,
            "price_loss": 0.0, "vacancy_loss": 0.0,
            "vacant_loss": 0.0, "booked_loss": 0.0,
            "occupancy": 0.0, "capture": 0.0,
        }
    occ = df[df["occupied"]]
    non = df[~df["occupied"]]
    booked_mask = non["availability"].str.strip().str.lower().isin(BOOKED_LABELS)
    booked = non[booked_mask]
    vacant = non[~booked_mask]

    rooms = len(df)
    market = float(df["market_rent_monthly"].sum())
    collected = float(occ["amount_monthly"].sum())
    occupied_market = float(occ["market_rent_monthly"].sum())
    booked_loss = float(booked["market_rent_monthly"].sum())
    vacant_loss = float(vacant["market_rent_monthly"].sum())
    return {
        "rooms": rooms,
        "occupied": int(len(occ)),
        "vacant": int(len(vacant)),
        "booked": int(len(booked)),
        "market_rent": market,
        "collected": collected,
        "occupied_market": occupied_market,
        "price_loss": occupied_market - collected,
        "vacancy_loss": booked_loss + vacant_loss,
        "vacant_loss": vacant_loss,
        "booked_loss": booked_loss,
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
