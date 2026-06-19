"""Live data from the team's edge app (hh-fllat-edge.web.app).

This is the authoritative operational source behind the team's own Lobbyboard
app. We use it for the parts our Sheets pipeline does NOT have:

  * Rent arrears  -> GET /api/arrears        (booking rent schedule vs payments,
                                              aged into 0-30 / 31-60 / 60+ buckets)
  * Manual arrears-> GET /api/arrears-manual (hand-maintained sheet + reconciliation)
  * Lobbyboard    -> GET /api/grid           (authoritative per-room availability:
                                              Occupied / Booked / Pre-Booked /
                                              Pipeline / Vacant / B2B / Legacy /
                                              Facilities, with server-side losses)

Auth mirrors the edge app itself: a Firebase ID token sent as
`Authorization: Bearer <token>`. The app signs in with Google (domain-locked to
@harringtonhousing.com) and email/password is disabled on the project, so we
cannot mint a token from a password. Instead we store a long-lived Firebase
**refresh token** once (obtained from a real logged-in session) and exchange it
for short-lived ID tokens via Google's securetoken endpoint - no browser, fully
headless, repeatable.

Refresh token resolution order:
  1. st.secrets["edge_refresh_token"]   (Streamlit Cloud)
  2. env EDGE_REFRESH_TOKEN
  3. runs/hh-edge/refresh_token.txt      (local dev; gitignored)
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
import streamlit as st

API_KEY = "AIzaSyB7Pj777hozIp80XC-yk9Srf9N78Mj5LvA"
HOST = "https://hh-fllat-edge.web.app"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_LOCAL_RT = Path(__file__).resolve().parent.parent / "runs" / "hh-edge" / "refresh_token.txt"

# availability labels that mean "committed, revenue pending" (vs truly Vacant).
BOOKED_LABELS = {"booked", "pre-booked", "prebooked", "pipeline"}


class EdgeAuthError(RuntimeError):
    """No usable refresh token / token exchange failed."""


def _refresh_token() -> str | None:
    try:
        v = st.secrets.get("edge_refresh_token")
        if v:
            return str(v).strip()
    except Exception:
        pass
    v = os.environ.get("EDGE_REFRESH_TOKEN")
    if v:
        return v.strip()
    if _LOCAL_RT.exists():
        return _LOCAL_RT.read_text().strip()
    return None


def configured() -> bool:
    """True if a refresh token is available (so the UI can degrade gracefully)."""
    return _refresh_token() is not None


@st.cache_data(ttl=3000, show_spinner=False)  # ID tokens live ~1h; refresh at 50m
def _id_token() -> str:
    rt = _refresh_token()
    if not rt:
        raise EdgeAuthError(
            "No edge refresh token configured (set edge_refresh_token in secrets, "
            "EDGE_REFRESH_TOKEN env, or runs/hh-edge/refresh_token.txt).")
    body = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": rt}).encode()
    req = urllib.request.Request(
        f"https://securetoken.googleapis.com/v1/token?key={API_KEY}",
        data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)["id_token"]
    except urllib.error.HTTPError as e:
        raise EdgeAuthError(f"Token refresh failed ({e.code}): "
                            f"{e.read().decode('utf-8', 'replace')[:200]}") from e


def _get(path: str):
    tok = _id_token()
    req = urllib.request.Request(
        f"{HOST}/api{path}",
        headers={"Authorization": f"Bearer {tok}", "User-Agent": UA,
                 "Origin": HOST, "Referer": HOST + "/", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _scope_qs(cities=None, buildings=None, **extra) -> str:
    params = {}
    params.update({k: v for k, v in extra.items() if v})
    if buildings:
        params["buildings"] = ",".join(buildings)
    if cities:
        params["cities"] = ",".join(cities)
    return urllib.parse.urlencode(params)


# --------------------------------------------------------------------- arrears

@st.cache_data(ttl=600, show_spinner=False)
def arrears(cities=None, buildings=None, status: str | None = None) -> dict:
    """Rent arrears for a scope. Returns a summary dict + a tenant DataFrame.

    Criteria (server-side, mirrored here for transparency): a booking schedule
    line is in arrears when due_date is past and remaining_amount > 0; lines are
    aged by days overdue into 0-30 / 31-60 / 60+ buckets; per-tenant totals are
    normalized to CAD.
    """
    qs = _scope_qs(cities=cities, buildings=buildings, status=status)
    raw = _get("/arrears?" + qs)
    tenants = raw.get("tenants") or []
    df = pd.DataFrame(tenants)
    # Aging totals straight from the per-tenant aggregates the API already aged.
    def col_sum(c):
        return float(df[c].fillna(0).sum()) if (not df.empty and c in df) else 0.0
    total = float(raw.get("total_owed_cad") or col_sum("total_owed_cad"))
    chronic = int((df["max_overdue_days"] >= 60).sum()) if "max_overdue_days" in df else 0
    return {
        "status": raw.get("status"),
        "tenant_count": int(raw.get("tenant_count") or len(df)),
        "total_owed_cad": total,
        "owed_0_30": col_sum("owed_0_30"),
        "owed_31_60": col_sum("owed_31_60"),
        "owed_60_plus": col_sum("owed_60_plus"),
        "chronic_60plus": chronic,
        "tenants": df,
    }


@st.cache_data(ttl=600, show_spinner=False)
def arrears_manual() -> dict:
    """Hand-maintained arrears sheet + reconciliation flags (global, not scoped)."""
    raw = _get("/arrears-manual")
    raw = dict(raw)
    raw["rows_df"] = pd.DataFrame(raw.get("rows") or [])
    return raw


# ------------------------------------------------------------------ lobbyboard

@st.cache_data(ttl=600, show_spinner=False)
def grid(cities=None, building_id: str = "all") -> pd.DataFrame:
    """Authoritative per-room lobbyboard grid (availability + server-side losses)."""
    qs = _scope_qs(cities=cities, building_id=building_id)
    rows = _get("/grid?" + qs)
    return pd.DataFrame(rows if isinstance(rows, list) else [])


def availability_split(df: pd.DataFrame) -> dict:
    """Counts + monthly market by authoritative availability label."""
    if df is None or df.empty:
        return {"counts": {}, "booked": 0, "vacant": 0, "occupied": 0}
    av = df["availability"].fillna("Unknown")
    low = av.str.strip().str.lower()
    booked = int(low.isin(BOOKED_LABELS).sum())
    vacant = int((low == "vacant").sum())
    occupied = int((low == "occupied").sum())
    counts = av.value_counts().to_dict()
    return {"counts": counts, "booked": booked, "vacant": vacant,
            "occupied": occupied}


# --------------------------------------------------- building name <-> slug map

@st.cache_data(ttl=3600, show_spinner=False)
def buildings() -> pd.DataFrame:
    return pd.DataFrame(_get("/buildings"))


def _norm(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", str(s).lower()) if t]


def building_id_for(city: str, name: str) -> str | None:
    """Best-effort map of our Sheets building display name -> edge building_id.

    Matches within the city by token-prefix (handles abbreviations like
    'int-plaza' <-> 'International Plaza'). Returns a slug only on a single
    confident match, else None (caller falls back to city scope + a note).
    """
    try:
        bdf = buildings()
    except Exception:
        return None
    cand = bdf[bdf["city"].str.lower() == str(city).lower()] if "city" in bdf else bdf
    name_tok = _norm(name)
    if not name_tok:
        return None
    hits = []
    for bid in cand["building_id"]:
        slug_tok = _norm(str(bid).replace("-", " "))
        # every slug token must prefix-match some name token (or vice-versa)
        ok = all(any(nt.startswith(stk) or stk.startswith(nt) for nt in name_tok)
                 for stk in slug_tok)
        if ok and slug_tok:
            hits.append(bid)
    return hits[0] if len(hits) == 1 else None
