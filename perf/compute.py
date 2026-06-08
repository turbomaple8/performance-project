"""Assemble a Performance-Sheet column for one (city, month) from all sources.

Each output line carries: value, source, and `reproducible` — whether it can be
rebuilt for a CLOSED past month from live data, or is point-in-time (only correct
when the pipeline runs at month-close). This honesty is deliberate: occupancy and
arrears are snapshots that the live systems overwrite.

Period keying = rule A (a payment belongs to a month by its dueDate calendar month).
"""

from __future__ import annotations

from dataclasses import dataclass

from extractors.cashflow import extract_transactions, total_cash_received
from extractors.config import CITIES
from extractors.dashboard import COUNTRY_SITE, DashboardClient
from extractors.lobbyboard import extract_rooms, onelob_top_section


@dataclass
class Line:
    value: float
    source: str
    reproducible: bool
    note: str = ""


def _ym(s) -> str:
    return (s or "")[:7]


def _window(year: int, month: int) -> tuple[str, str]:
    # 6 months before .. 2 months after, to catch LMR/early and late collections.
    start_m = month - 6
    sy, sm = (year, start_m) if start_m >= 1 else (year - 1, start_m + 12)
    end_m = month + 2
    ey, em = (year, end_m) if end_m <= 12 else (year + 1, end_m - 12)
    return f"{sy}-{sm:02d}-01", f"{ey}-{em:02d}-28"


def bucket_payments(payments: list[dict], year: int, month: int) -> dict[str, float]:
    p = f"{year}-{month:02d}"
    b = {"in_period_for_period_rent": 0.0, "for_period_rent_other_months": 0.0,
         "other_in_period_for_period": 0.0, "in_period_for_other_months": 0.0,
         "total_collected_in_period": 0.0}
    for r in payments:
        dm, ddm = _ym(r.get("date")), _ym(r.get("dueDate"))
        t = (r.get("type") or "").strip()
        amt = float(r.get("amount") or 0)
        is_rent = t == "Rent"
        if dm == p:
            b["total_collected_in_period"] += amt
        if dm == p and ddm == p and is_rent:
            b["in_period_for_period_rent"] += amt
        if ddm == p and dm != p and is_rent:
            b["for_period_rent_other_months"] += amt
        if dm == p and ddm == p and not is_rent:
            b["other_in_period_for_period"] += amt
        if dm == p and ddm != p:
            b["in_period_for_other_months"] += amt
    return b


def compute_city_month(city_key: str, year: int, month: int) -> dict[str, Line]:
    cfg = CITIES[city_key]
    rooms = extract_rooms(cfg)
    top = onelob_top_section(rooms)

    client = DashboardClient(COUNTRY_SITE[cfg.country]).login()
    start, end = _window(year, month)
    cp = client.collected_payments(cfg.dashboard_city, start, end)
    buckets = bucket_payments(cp, year, month)

    txns = extract_transactions(cfg)
    cash = total_cash_received(txns, year, month) if txns else {}
    arrears_rows = client.new_arrears(cfg.dashboard_city)
    arrears_total = sum(float(a.get("remainingAmount") or 0) for a in arrears_rows)

    L: dict[str, Line] = {}
    # TOP
    L["potential_revenue"] = Line(top["potential_revenue"], "OneLob Σ market rent (excl new buildings)", True)
    L["price_optimization_loss"] = Line(top["price_optimization_loss"], "OneLob market-current (occupied)", False,
                                        "occupancy is point-in-time")
    L["vacant_room_loss_vacant"] = Line(top["vacant_room_loss_vacant"], "OneLob vacant rooms", False,
                                        "needs dashboard move-in/out timeline for the month")
    L["vacant_room_loss_booked"] = Line(top["vacant_room_loss_booked"], "OneLob booked rooms", False,
                                        "needs vacancy-gap (move-out -> booked move-in) from dashboard")
    L["billable_revenue"] = Line(top["billable_revenue"], "OneLob Σ current rent (occupied)", False,
                                 "occupancy is point-in-time")
    # ARREARS (point-in-time; chronic/temp split needs a rule)
    L["rent_arrears_total"] = Line(arrears_total, "dashboard newarrears Σ remaining", False,
                                   "current snapshot; bad-debt vs temp split rule TBD")
    # PAYMENT FLOWS (rule A, reproducible by collection/due date)
    L["payments_in_period_for_period"] = Line(buckets["in_period_for_period_rent"], "dashboard collectedPayments A", True,
                                              "excludes partner (Ohana) -> see cashflow")
    L["payments_for_period_other_months"] = Line(buckets["for_period_rent_other_months"], "dashboard collectedPayments A", True)
    L["other_payments_in_period_for_period"] = Line(buckets["other_in_period_for_period"], "dashboard collectedPayments A (non-rent)", True)
    L["payments_in_period_for_other_months"] = Line(buckets["in_period_for_other_months"], "dashboard collectedPayments A", True)
    # CASH (cashflow sheet)
    if cash:
        L["total_cash_received"] = Line(cash["total_cash_received"], "cashflow Operating+Deposit", True,
                                        "secondary reconciliation line; GT may include manual adjustments")
        L["partner_rental_revenue"] = Line(cash["partner_rental_revenue"], "cashflow Ohana/Airbnb inflows", True)
    return L
