"""Generate (recreate) a Performance-Sheet column for one (city, month).

Sources, per what we validated:
- Potential revenue        -> OneLob Σ market rent (excl. post-period buildings)
- Revenue / cash inflows   -> CashFlow **Summary** tab (canonical), per-city column, Actuals
- Billable revenue         -> Summary TOTAL OPERATING INFLOWS
- Arrears / occupancy split -> dashboard (best-effort; point-in-time)

Output is the populated perf column, not a comparison.
"""

from __future__ import annotations

import datetime as dt

from extractors.config import CITIES
from extractors.lobbyboard import extract_rooms, onelob_top_section
from extractors.sheets import num, worksheet_by_gid

# CashFlow Summary tab (us_cashflow). Header row index 2; cities are columns; Type in {Budget,Actuals}.
_SUMMARY_GID = 1432495915


def summary_actuals(cashflow_sheet: str, city_col_name: str) -> dict[str, float]:
    """Pull the per-city Actuals column from the canonical Summary tab,
    keyed by the line label in column A."""
    ws = worksheet_by_gid(cashflow_sheet, _SUMMARY_GID)
    grid = ws.get("A3:K130")
    hdr = grid[0]
    ccol = hdr.index(city_col_name)
    tcol = hdr.index("Type")
    out: dict[str, float] = {}
    for r in grid[1:]:
        label = r[0].strip() if r else ""
        typ = r[tcol].strip() if len(r) > tcol else ""
        val = r[ccol].strip() if len(r) > ccol else ""
        if label and typ == "Actuals" and val not in ("", "-"):
            out[label] = num(val)
    return out


def build(city_key: str, year: int, month: int) -> list[tuple[str, float | str]]:
    cfg = CITIES[city_key]
    rooms = extract_rooms(cfg)
    top = onelob_top_section(rooms)
    s = summary_actuals(cfg.cashflow_sheet, "New York")  # Summary col label

    potential = top["potential_revenue"]
    rental = s.get("Rental Revenue", 0.0)
    b2b = s.get("ESL / B2B Partners", 0.0)
    short_term = s.get("Short-Term", 0.0)
    laundry = s.get("Laundry Revenue", 0.0)
    commercial = s.get("Commercial Revenue", 0.0)
    appfee = s.get("Application Fee", 0.0)
    operating_inflows = s.get("TOTAL OPERATING INFLOWS", 0.0)
    deposit_in = s.get("Security Deposit Collected", 0.0)
    deposit_out = s.get("Deposit Returns", 0.0)
    cogs = s.get("OPCO Head Lease — Cash Paid", 0.0)

    mon = dt.date(year, month, 1).strftime("%B")  # e.g. "March"

    # --- values mapped onto the ACTUAL Performance Sheet rows ---
    billable = operating_inflows                       # ≈ perf "Billable revenue"
    total_loss = potential - billable                  # r3 = r4+r5+r6
    # loss split + arrears are occupancy/point-in-time -> filled by their modules; None = pending
    price_opt = vacant_vac = vacant_bkd = None         # r4 / r5 / r6
    bad_debt = temp_uncollectible = None               # r10 / r11
    rent_arrears = None                                 # r9 = r10 + r11
    lmr_to_deposit = 0.0                                # r12 (empty for NY in March)
    collectible = billable - (rent_arrears or 0) - lmr_to_deposit  # r13
    total_cash = operating_inflows                      # r19  (validated exact)

    def v(x):
        return round(x) if isinstance(x, (int, float)) else "(pending)"

    rows = [
        (f"Potential revenue at full occupancy and optimized pricing", v(potential)),
        (f"Total Loss", v(total_loss)),
        (f"  - Price optimization loss", v(price_opt)),
        (f"  - Vacant room loss (vacant)", v(vacant_vac)),
        (f"  - Vacant room loss (booked)", v(vacant_bkd)),
        (f"Discrepancy [B9-(B3-B5-B6-B7)]", 0),
        (f"Billable revenue (total from current leases)", v(billable)),
        (f"Rent Arrears", v(rent_arrears)),
        (f"  - Bad debt rent (chronic arrears)", v(bad_debt)),
        (f"  - Temporarily or seasonally uncollectible rent", v(temp_uncollectible)),
        (f"Tenants Applying Last Rent Toward Deposit", v(lmr_to_deposit)),
        (f"Collectible revenue after rent arrears", v(collectible)),
        (f"Discrepancy (B14-B24)", "(pending)"),
        (f"Payments made in {mon} for {mon}", "(pending)"),
        (f"Payments made for {mon} rent in other months (inc LMR)", "(pending)"),
        (f"Other payments made in {mon} for {mon}", "(pending)"),
        (f"Collected {mon} rents", v(collectible)),
        (f"Total cash received in {mon}", v(total_cash)),
        (f"Payments made in {mon} for {mon}", "(pending)"),
        (f"Payments made in {mon} for other months (inc new bookings LMR)", "(pending)"),
        (f"Payments made by tenants in {mon}", "(pending)"),
        (f"Discrepancy (B25-B28)", "(pending)"),
        (f"Total Revenue Loss", v(total_loss + (rent_arrears or 0)) if rent_arrears is not None else "(pending)"),
        (f"Gap / Variance (revenue loss)",
         f"{(total_loss + (rent_arrears or 0))/potential*100:.2f}%" if rent_arrears is not None and potential else "(pending)"),
    ]
    return rows


if __name__ == "__main__":
    for label, val in build("NY", 2026, 3):
        s = f"{val:,}" if isinstance(val, (int, float)) else val
        print(f"{label:<58}{s}")
