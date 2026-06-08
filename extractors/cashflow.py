"""CashFlow sheet extractor: bank-transaction level inflows/expenses per city.

Source of actual cash received (incl. partner payouts like Ohana that never
reach the dashboard). Transaction-level; bookingId is embedded in Description.
Amounts are in local currency (the `Amount` column); a converted `CAD` column
also exists but we use local for a single-currency city.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import CityConfig
from .sheets import num, parse_ym, worksheet_by_gid

# Booking codes seen: FL... (US/fllat), HH... (Harrington), FLB2B... (partner).
_BOOKING_RE = re.compile(r"\b((?:FL|HH)[A-Za-z0-9]{6,})\b")
_PARTNER_RE = re.compile(r"ohana|airbnb", re.I)


def _clean_type(s: str) -> str:
    """Strip emoji/non-ascii prefix from the Type column."""
    return re.sub(r"[^\x00-\x7F]", "", s or "").strip()


@dataclass(frozen=True)
class CashTxn:
    year: int
    month: int
    type: str            # Operating Inflows | Expense | Security Deposit Cash | Non Operating | Loans ...
    category: str        # Rental Revenue | Security Deposit Collected | ...
    description: str
    amount: float        # local currency
    building: str
    account: str
    booking_id: str | None
    is_partner: bool


def extract_transactions(cfg: CityConfig) -> list[CashTxn]:
    if not cfg.cashflow_sheet or cfg.cashflow_gid is None:
        return []
    ws = worksheet_by_gid(cfg.cashflow_sheet, cfg.cashflow_gid)
    rows = ws.get_all_values()
    if not rows:
        return []
    H = {n: i for i, n in enumerate(rows[0])}
    cD, cT, cC, cDesc, cAmt = H["Date"], H["Type"], H["Category"], H["Description"], H["Amount"]
    cBld = H.get("Building")
    cAcc = H.get("Account")
    cCity = H.get("City")
    out: list[CashTxn] = []
    for r in rows[1:]:
        if len(r) <= cAmt:
            continue
        # Guard: this tab carries stray rows from other cities; keep only ours.
        if cfg.cashflow_city and cCity is not None:
            if (r[cCity].strip() if len(r) > cCity else "") != cfg.cashflow_city:
                continue
        ym = parse_ym(r[cD])
        if ym is None:
            continue
        desc = r[cDesc] if len(r) > cDesc else ""
        bid = _BOOKING_RE.search(desc)
        out.append(
            CashTxn(
                year=ym[0],
                month=ym[1],
                type=_clean_type(r[cT]) if len(r) > cT else "",
                category=(r[cC].strip() if len(r) > cC else ""),
                description=desc,
                amount=num(r[cAmt]),
                building=(r[cBld].strip() if cBld is not None and len(r) > cBld else ""),
                account=(r[cAcc].strip() if cAcc is not None and len(r) > cAcc else ""),
                booking_id=bid.group(1) if bid else None,
                is_partner=bool(_PARTNER_RE.search(desc)),
            )
        )
    return out


def total_cash_received(txns: list[CashTxn], year: int, month: int) -> dict[str, float]:
    """Perf-sheet r19 basis (per user): Operating Inflows + Security Deposit Cash,
    excluding Loans and Non-Operating. Partner (Ohana) payouts sit inside
    Operating Inflows / Rental Revenue already."""
    m = [t for t in txns if t.year == year and t.month == month]
    operating = sum(t.amount for t in m if t.type == "Operating Inflows")
    deposits = sum(t.amount for t in m if t.type == "Security Deposit Cash")
    rental_revenue = sum(t.amount for t in m if "Rental Revenue" in t.category)
    partner = sum(t.amount for t in m if t.is_partner and "Rental Revenue" in t.category)
    return {
        "total_cash_received": operating + deposits,
        "operating_inflows": operating,
        "security_deposit_cash": deposits,
        "rental_revenue": rental_revenue,
        "partner_rental_revenue": partner,
    }
