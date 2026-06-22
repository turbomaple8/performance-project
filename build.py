"""Build the static dashboard data file.

Reuses the existing Sheets pipeline (app/data.py) and the edge arrears source
(app/edge_api.py) to precompute every selectable scope (country / city /
building) into a single web/public/data.json. A scheduled GitHub Action runs
this and publishes the static site, so there is no live backend, no Streamlit,
and no secrets panel - auth tokens live once in CI and are refreshed inside the
job.

Run locally:  .venv/bin/python build.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd  # noqa: E402

import config as cfg  # noqa: E402
import data  # noqa: E402
import edge_api  # noqa: E402

OUT = ROOT / "web" / "public" / "data.json"

INCLUDE_CLOSED = False  # mirror the dashboard default: hide 0-occupied buildings
# Mask tenant/resident names so the output is safe on an un-gated (public) host.
# Set ANONYMIZE=1 for public deploys; leave unset behind access-controlled hosting.
ANONYMIZE = os.environ.get("ANONYMIZE") == "1"


def _active(df: pd.DataFrame) -> pd.DataFrame:
    if INCLUDE_CLOSED or df is None or df.empty:
        return df
    return df[df["building"].isin(data.active_buildings(df))].reset_index(drop=True)


def _round(obj):
    """Recursively round floats so the JSON stays small and stable."""
    if isinstance(obj, float):
        return round(obj, 2)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


# --------------------------------------------------------------------- arrears

def _visible_slugs(df: pd.DataFrame):
    slugs, unmatched = set(), []
    for _, r in df[["city", "building"]].drop_duplicates().iterrows():
        bid = edge_api.building_id_for(r["city"], r["building"])
        (slugs.add(bid) if bid else unmatched.append(r["building"]))
    return slugs, unmatched, sorted(df["city"].unique())


def _arrears(df: pd.DataFrame) -> dict | None:
    if df is None or df.empty or not edge_api.configured():
        return None
    try:
        slugs, unmatched, cities = _visible_slugs(df)
        a = edge_api.arrears(cities=cities)
    except Exception as exc:  # never fail the whole build on arrears
        return {"error": str(exc)[:200]}
    t = a["tenants"]
    if slugs and not t.empty and "building_id" in t:
        t = t[t["building_id"].isin(slugs)].reset_index(drop=True)
    s = lambda c: float(t[c].fillna(0).sum()) if (not t.empty and c in t) else 0.0
    cols = [c for c in ["tenant_name", "building_id", "total_owed_cad",
                        "max_overdue_days", "overdue_lines", "oldest_due",
                        "collection_status"] if (not t.empty and c in t)]
    top = (t.sort_values("total_owed_cad", ascending=False)[cols].head(20)
           .to_dict(orient="records") if not t.empty else [])
    if ANONYMIZE:
        for i, r in enumerate(top, 1):
            if "tenant_name" in r:
                r["tenant_name"] = f"Tenant {i}"
    return {
        "total": s("total_owed_cad"),
        "count": int(len(t)),
        "b030": s("owed_0_30"), "b3160": s("owed_31_60"), "b60": s("owed_60_plus"),
        "chronic": int((t["max_overdue_days"] >= 60).sum()) if (not t.empty and "max_overdue_days" in t) else 0,
        "unmatched": unmatched,
        "top": top,
    }


# ---------------------------------------------------------------- scope payload

ROOM_COLS = ["no", "apartment", "room_type", "plan", "resident",
             "market_rent_monthly", "amount_monthly", "status", "occupied"]


def scope_payload(df: pd.DataFrame, scope: str, currency: str) -> dict:
    p = {"scope": scope, "currency": currency, "metrics": data.metrics(df)}
    if scope in ("country", "city"):
        group_col = "city" if scope == "country" else "building"
        g = data.group_kpis(df, group_col).sort_values("collected", ascending=False)
        p["groupCol"] = group_col
        p["groups"] = g.to_dict(orient="records")
    p["roomTypes"] = data.by_room_type(df).to_dict(orient="records")
    p["arrears"] = _arrears(df)
    if scope == "building":
        cols = [c for c in ROOM_COLS if c in df]
        rooms = df[cols].to_dict(orient="records")
        if ANONYMIZE:
            for r in rooms:
                if r.get("resident"):
                    r["resident"] = "—"
        p["rooms"] = rooms
    return p


def main() -> None:
    nav = []
    scopes: dict[str, dict] = {}

    for country in cfg.countries():
        currency = cfg.currency(country)
        cdf = _active(data.load_country(country))
        if cdf is None or cdf.empty:
            continue
        scopes[country] = scope_payload(cdf, "country", currency)

        cities_out = []
        for city in cfg.cities(country):
            citydf = _active(data.load_city(country, city))
            if citydf is None or citydf.empty:
                continue
            scopes[f"{country}|{city}"] = scope_payload(citydf, "city", currency)

            buildings_out = []
            for bname in sorted(citydf["building"].unique()):
                bdf = citydf[citydf["building"] == bname].reset_index(drop=True)
                scopes[f"{country}|{city}|{bname}"] = scope_payload(bdf, "building", currency)
                buildings_out.append(bname)
            cities_out.append({"name": city, "buildings": buildings_out})

        nav.append({"name": country, "flag": cfg.flag(country),
                    "currency": currency, "cities": cities_out})

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "weeks_per_month": cfg.WEEKS_PER_MONTH,
        "nav": nav,
        "scopes": scopes,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(_round(payload), ensure_ascii=False, separators=(",", ":")))
    n_b = sum(len(c["buildings"]) for ctry in nav for c in ctry["cities"])
    size_kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  ({size_kb:.0f} KB)  "
          f"{len(nav)} countries, {len(scopes)} scopes, {n_b} buildings")


if __name__ == "__main__":
    main()
