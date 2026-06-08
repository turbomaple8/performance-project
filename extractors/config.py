"""Per-city configuration for the performance pipeline.

One entry per city we report on. `dashboard_city` must match exactly the name
returned by the dashboard's uniqueCities. `excluded_buildings` are buildings
that did NOT exist in the reporting period (new since), excluded so OneLob's
current snapshot approximates the period's inventory.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CityConfig:
    key: str                 # internal key
    perf_label: str          # column header in the Performance Sheet
    country: str             # US | CA | UK  -> picks dashboard site
    dashboard_city: str      # exact uniqueCities name
    lobbyboard_sheet: str    # Google Sheet id (has OneLob tab)
    cashflow_sheet: str | None = None
    cashflow_gid: int | None = None       # transaction tab gid for this city
    cashflow_city: str | None = None      # exact City value inside the cashflow tab
    excluded_buildings: frozenset[str] = field(default_factory=frozenset)


CITIES: dict[str, CityConfig] = {
    "NY": CityConfig(
        key="NY",
        perf_label="NY",
        country="US",
        dashboard_city="New York City",
        lobbyboard_sheet="1cUTL-wNsVN5jnhJ_F5M0NY57rD1seDqfvRWvJ7x_xgc",
        cashflow_sheet="1AxmsoL-99F2snTxnmTJvhnchJ7_AX3FxDsyrfhNVPkQ",
        cashflow_gid=1627004006,
        cashflow_city="New York",   # tab also contains stray Seattle/Boston rows
        # Buildings that arrived after March 2026 (confirmed by user):
        excluded_buildings=frozenset({"Amsterdam Residences", "Stratford"}),
    ),
    "Ottawa": CityConfig(
        key="Ottawa",
        perf_label="Ottawa",
        country="CA",
        dashboard_city="Ottawa",
        lobbyboard_sheet="1VwnmC_I44dNPDkmgzwWbDAQk7QBuflIWgO5e0l0VGao",
        cashflow_sheet=None,     # CA cashflow not yet provided
        cashflow_gid=None,
        excluded_buildings=frozenset(),
    ),
}
