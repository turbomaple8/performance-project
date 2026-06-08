"""Registry of countries -> cities -> buildings for the performance dashboard.

Only Canada / Vancouver is wired up for now. US and UK are placeholders so the
navigation shows the full hierarchy the project will grow into.
"""

from __future__ import annotations

VANCOUVER_SHEET_ID = "1qMcSju_Pa6yq_h1yazNXvj_l1WUO9I5qhaWBFNrpn_o"

# Weeks per month used to convert weekly / four-weekly figures to monthly.
# 4.34524 = 365.25 / 7 / 12. (52/12 = 4.33333 is an accepted alternative.)
WEEKS_PER_MONTH = 4.34524

REGISTRY: dict = {
    "Canada": {
        "flag": "🇨🇦",
        "currency": "CA$",
        "cities": {
            "Vancouver": {
                "sheet_id": VANCOUVER_SHEET_ID,
                "buildings": [
                    {"tab": "Int Plaza", "name": "International Plaza"},
                    {
                        "tab": "Richard & Pender",
                        "name": "Richard & Pender",
                        "note": (
                            "Apartments 507, 701 and 901 (11 vacant rooms at the bottom of "
                            "the sheet) appear to be under renovation. Manually-prepared "
                            "figures exclude them, so the team's market rent came out lower "
                            "(~CA$20,075). This dashboard counts all rooms, so its market rent "
                            "and vacancy are higher. To revisit."
                        ),
                    },
                    {"tab": "Hub Place", "name": "Hub Place"},
                    {"tab": "Broughton", "name": "Broughton"},
                    {"tab": "Hillcrest Manor", "name": "Hillcrest Manor"},
                    {"tab": "Lynn Gary Apt", "name": "Lynn Gary Apt"},
                    {"tab": "Pendrell", "name": "Pendrell"},
                    {"tab": "Tantus Tower", "name": "Tantus Tower"},
                ],
            },
        },
    },
    "United States": {
        "flag": "🇺🇸",
        "currency": "US$",
        "cities": {},
    },
    "United Kingdom": {
        "flag": "🇬🇧",
        "currency": "£",
        "cities": {},
    },
}


def countries() -> list[str]:
    return list(REGISTRY.keys())


def cities(country: str) -> list[str]:
    return list(REGISTRY.get(country, {}).get("cities", {}).keys())


def buildings(country: str, city: str) -> list[dict]:
    return REGISTRY.get(country, {}).get("cities", {}).get(city, {}).get("buildings", [])


def building_note(country: str, city: str, name: str) -> str | None:
    for b in buildings(country, city):
        if b["name"] == name:
            return b.get("note")
    return None


def currency(country: str) -> str:
    return REGISTRY.get(country, {}).get("currency", "$")


def flag(country: str) -> str:
    return REGISTRY.get(country, {}).get("flag", "")


def sheet_id(country: str, city: str) -> str | None:
    return REGISTRY.get(country, {}).get("cities", {}).get(city, {}).get("sheet_id")
