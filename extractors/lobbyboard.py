"""Lobbyboard (OneLob) extractor: per-room market rent + occupancy snapshot.

OneLob is a current, hand-maintained snapshot. We trust it primarily for
*market rent*; occupancy / current rent are cross-checked against the dashboard.
OneLob has no bookingId, so resident-level joins happen by name/room downstream.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import CityConfig
from .sheets import num, open_sheet

# OneLob canonical columns (header row 0).
_COLS = {
    "building": "Building",
    "apt": "APT",
    "room_type": "Room Type",
    "market_rent_weekly": "Market Rent",
    "availability": "Room Availability",
    "market_rent_monthly": "Market Rent - Monthly",
    "current_rent_monthly": "Current Rent (Monthly)",
    "resident": "Current Resident Name",
}

# Availability buckets.
OCCUPIED = "Occupied"
VACANT = "Vacant"
BOOKED = {"Booked", "Pre-Booked"}


@dataclass(frozen=True)
class Room:
    building: str
    apt: str
    room_type: str
    availability: str
    market_rent_monthly: float
    current_rent_monthly: float
    resident: str


def extract_rooms(cfg: CityConfig) -> list[Room]:
    ws = open_sheet(cfg.lobbyboard_sheet).worksheet("OneLob")
    rows = ws.get_all_values()
    if not rows:
        return []
    idx = {k: rows[0].index(v) for k, v in _COLS.items()}
    out: list[Room] = []
    for r in rows[1:]:
        if len(r) <= idx["building"]:
            continue
        building = r[idx["building"]].strip()
        if building == "" or building in cfg.excluded_buildings:
            continue
        out.append(
            Room(
                building=building,
                apt=r[idx["apt"]].strip() if len(r) > idx["apt"] else "",
                room_type=r[idx["room_type"]].strip() if len(r) > idx["room_type"] else "",
                availability=r[idx["availability"]].strip() if len(r) > idx["availability"] else "",
                market_rent_monthly=num(r[idx["market_rent_monthly"]]) if len(r) > idx["market_rent_monthly"] else 0.0,
                current_rent_monthly=num(r[idx["current_rent_monthly"]]) if len(r) > idx["current_rent_monthly"] else 0.0,
                resident=r[idx["resident"]].strip() if len(r) > idx["resident"] else "",
            )
        )
    return out


def onelob_top_section(rooms: list[Room]) -> dict[str, float]:
    """OneLob-only view of the TOP section, for cross-checking against the
    dashboard-derived occupancy. Note: occupancy here is OneLob's *current*
    state, so vacancy-dependent lines reflect 'now', not the reporting month."""
    occ = [r for r in rooms if r.availability == OCCUPIED]
    vac = [r for r in rooms if r.availability == VACANT]
    bkd = [r for r in rooms if r.availability in BOOKED]
    potential = sum(r.market_rent_monthly for r in rooms)
    price_opt_loss = sum(r.market_rent_monthly - r.current_rent_monthly for r in occ)
    vacant_loss = sum(r.market_rent_monthly for r in vac)
    booked_loss = sum(r.market_rent_monthly for r in bkd)
    billable = sum(r.current_rent_monthly for r in occ)
    return {
        "potential_revenue": potential,
        "price_optimization_loss": price_opt_loss,
        "vacant_room_loss_vacant": vacant_loss,
        "vacant_room_loss_booked": booked_loss,
        "total_loss": price_opt_loss + vacant_loss + booked_loss,
        "billable_revenue": billable,
        "rooms": len(rooms),
        "occupied": len(occ),
        "vacant": len(vac),
        "booked": len(bkd),
    }
