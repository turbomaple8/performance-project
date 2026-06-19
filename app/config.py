"""Registry of countries -> cities -> Lobby Board sheet ids for the dashboard.

City -> sheet links come from the "Sales - 2.0" tab (column B) of the Harrington
Housing Business Report index sheet. Building tabs inside each sheet are
auto-detected in data.py (no need to list them here).

Not wired up yet (need action):
  - Toronto  : index link is a Drive *folder*, not a single sheet.
  - DC       : sheet (1Zow3myXuo4z-qyxzYq7A11PpsZB942W_otbm9z9MRHQ) not shared
               with the service account (PermissionError) -> needs sharing.
  - Seattle  : the index link points at the combined multi-city "SPV Lobbyboard"
               (1sbPDNgluJ1...; Regina/Riverflow/etc.) -> would double-count;
               needs a clean Seattle-only sheet.
  - Regina   : same combined "SPV Lobbyboard" -> would double-count.

Added 2026-06-19: Austin, Miami, Chicago (US) once confirmed shared + valid
building tabs. "Copy of ..." backup tabs are skipped in data.py.
"""

from __future__ import annotations

# Weeks per month for weekly/four-weekly -> monthly. 4.34524 = 365.25/7/12.
WEEKS_PER_MONTH = 4.34524

# Source index sheet (column B holds the per-city lobbyboard links).
SALES_INDEX_SHEET = "12mvdf-KgHK38mfek4OCOLIdzLMQ2mtosEKO9je23ALo"

REGISTRY: dict = {
    "Canada": {
        "flag": "🇨🇦",
        "currency": "CA$",
        "cities": {
            "Vancouver": "1qMcSju_Pa6yq_h1yazNXvj_l1WUO9I5qhaWBFNrpn_o",
            "Calgary": "1_JY5hGmWedviemVWMF3rg8ifplUarEP34p7o8xPpPy4",
            "Edmonton": "1-EKowAXNbTzC-iut3zehvXQfItM_ZRQxWp8KQe7Dt_E",
            "Montreal": "18Trtl7TcTdPV9XLkeuYR4O9oAUGvJZE4vX6ZZ3daMo0",
            "Ottawa": "1VwnmC_I44dNPDkmgzwWbDAQk7QBuflIWgO5e0l0VGao",
            "Halifax": "1gBiBiL71bjx9ZU-dCjZ76PEKxqL73iVrOdlueA9b5sg",
            "Victoria": "1ZFaPVYx-VotaQoz3O0BlAnrls6egsZPWnfEppKYTyIM",
        },
    },
    "United States": {
        "flag": "🇺🇸",
        "currency": "US$",
        "cities": {
            "New York": "1cUTL-wNsVN5jnhJ_F5M0NY57rD1seDqfvRWvJ7x_xgc",
            "Boston": "1jYgzWC5Stg5qj49METhJWeE-bqujcJ0_dBpT8z8r_vg",
            "Austin": "1wRnp5cTQiu8DzOw2SB2J5UVsO9PWtPRPWSUBjjVIsBo",
            "Miami": "1vdIU8AkKOaQlqcCktnCiWCw6P9G6h49FofUG0LcRnck",
            "Chicago": "1UUwSuLvuB1urZPnOkAhdl9YYl04NUmqd_BL_opHVCCU",
        },
    },
    "United Kingdom": {
        "flag": "🇬🇧",
        "currency": "£",
        "cities": {
            "London": "1_sbrWBNC6ykg7IsHLVEovdB5sB5Snkv1xjSYwxupOsM",
        },
    },
}

# Prettier display names for a few building tab titles.
DISPLAY_OVERRIDES = {"Int Plaza": "International Plaza"}

# Buildings that have been handed back / are no longer operated. Their lobbyboard
# tabs still hold stale data, so we drop them at load time (per city, by building
# display name). In Vancouver only International Plaza is still active.
CITY_REMOVED_BUILDINGS = {
    "Vancouver": {
        "Richard & Pender", "Hub Place", "Broughton", "Hillcrest Manor",
        "Lynn Gary Apt", "Pendrell", "Tantus Tower",
    },
}

# Per-(city, building) notes rendered as a callout in the building view.
CITY_BUILDING_NOTES: dict = {}


def countries() -> list[str]:
    return list(REGISTRY.keys())


def cities(country: str) -> list[str]:
    return list(REGISTRY.get(country, {}).get("cities", {}).keys())


def sheet_id(country: str, city: str) -> str | None:
    return REGISTRY.get(country, {}).get("cities", {}).get(city)


def currency(country: str) -> str:
    return REGISTRY.get(country, {}).get("currency", "$")


def flag(country: str) -> str:
    return REGISTRY.get(country, {}).get("flag", "")


def display_name(tab: str) -> str:
    return DISPLAY_OVERRIDES.get(tab, tab)


def building_note(city: str, name: str) -> str | None:
    return CITY_BUILDING_NOTES.get((city, name))


def removed_buildings(city: str) -> set:
    """Buildings to drop from the dashboard (handed back); read-only, sheets untouched."""
    return CITY_REMOVED_BUILDINGS.get(city, set())
