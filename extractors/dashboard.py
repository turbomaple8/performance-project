"""Browser-free client for the Harrington / fllat admin data API.

The two dashboards are structurally identical; only the hosts differ
(fllat = US side, harrington = CA/other). Auth is NextAuth credentials login
on the admin host (csrf -> callback/credentials -> session), which yields a
JWT we then send as `Authorization: Bearer` to the separate data API host.

The data API sits behind a WAF that 403s non-browser requests, so every API
call carries a browser-like User-Agent + Origin/Referer.

Credentials are read from env (never hardcoded): <PREFIX>_USER / <PREFIX>_PASS,
e.g. FLLAT_USER / FLLAT_PASS, HARRINGTON_USER / HARRINGTON_PASS.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class Site:
    name: str
    admin: str  # admin (NextAuth) host
    api: str    # data API host


SITES = {
    "fllat": Site("fllat", "https://admin.fllat.com", "https://api.fllat.com"),
    "harrington": Site(
        "harrington",
        "https://admin.harringtonhousing.com",
        "https://api.harringtonhousing.com",
    ),
}

# Which dashboard a country/market lives on.
COUNTRY_SITE = {"US": "fllat", "CA": "harrington", "UK": "harrington"}


class DashboardError(RuntimeError):
    pass


class DashboardClient:
    """One authenticated session against a single dashboard site."""

    def __init__(self, site: str, email: str | None = None, password: str | None = None):
        if site not in SITES:
            raise DashboardError(f"unknown site {site!r}; known: {list(SITES)}")
        self.site = SITES[site]
        prefix = site.upper()
        self.email = email or os.environ.get(f"{prefix}_USER")
        self.password = password or os.environ.get(f"{prefix}_PASS")
        if not self.email or not self.password:
            raise DashboardError(
                f"missing creds: set {prefix}_USER / {prefix}_PASS or pass them in"
            )
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cj)
        )
        self._token: str | None = None

    # -- low level ---------------------------------------------------------
    def _admin(self, path: str, data: dict | None = None, headers: dict | None = None):
        url = self.site.admin + path
        hdr = {"User-Agent": _UA, **(headers or {})}
        if data is not None:
            body = urllib.parse.urlencode(data).encode()
            hdr["Content-Type"] = "application/x-www-form-urlencoded"
            req = urllib.request.Request(url, data=body, headers=hdr)
        else:
            req = urllib.request.Request(url, headers=hdr)
        with self._opener.open(req, timeout=45) as r:
            return r.read().decode()

    def login(self) -> "DashboardClient":
        csrf = json.loads(self._admin("/api/auth/csrf"))["csrfToken"]
        self._admin(
            "/api/auth/callback/credentials",
            data={
                "email": self.email,
                "password": self.password,
                "csrfToken": csrf,
                "callbackUrl": self.site.admin,
                "json": "true",
            },
            headers={"Origin": self.site.admin, "Referer": self.site.admin + "/"},
        )
        sess = json.loads(self._admin("/api/auth/session", headers={"Referer": self.site.admin + "/"}))
        token = (sess.get("user") or {}).get("token")
        if not token:
            raise DashboardError(f"login failed for {self.email} on {self.site.name}")
        self._token = token
        return self

    def _api_get(self, path: str, params: dict | None = None, _tries: int = 4) -> dict:
        if self._token is None:
            self.login()
        qs = ("?" + urllib.parse.urlencode(params)) if params else ""
        last = None
        for attempt in range(_tries):
            req = urllib.request.Request(
                self.site.api + path + qs,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "User-Agent": _UA,
                    "Origin": self.site.admin,
                    "Referer": self.site.admin + "/",
                    "Accept": "application/json",
                },
            )
            try:
                with self._opener.open(req, timeout=90) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                # 4xx (except 429) is a real error; 5xx / 429 are transient WAF/origin hiccups.
                if e.code < 500 and e.code != 429:
                    raise DashboardError(f"{e.code} on {path}: {e.read().decode()[:200]}") from e
                last = e
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                # URLError (conn reset), socket timeout, or JSON decode of a truncated body.
                last = e
            time.sleep(2 * (attempt + 1))
        raise DashboardError(f"transient failures on {path}: {last}")

    def paginate(self, path: str, params: dict, list_key: str | None = None, limit: int = 200):
        """Yield every row across pages. Detects the list field if not given."""
        page = 1
        while True:
            data = self._api_get(path, {**params, "page": page, "limit": limit})
            if list_key is None:
                list_key = next(
                    (k for k, v in data.items() if isinstance(v, list)), None
                )
                if list_key is None:
                    return
            rows = data.get(list_key) or []
            for row in rows:
                yield row
            pages = data.get("pages") or 1
            if page >= pages or not rows:
                return
            page += 1

    # -- typed endpoints ---------------------------------------------------
    def unique_cities(self):
        return self._api_get("/admin/booking/uniqueCities")

    def collected_payments(self, city: str, start: str, end: str):
        """Payments collected with collection-date in [start,end] (YYYY-MM-DD)."""
        return list(self.paginate(
            "/admin/booking/payments/collectedPayments",
            {"city": city, "locality": "all", "paymentType": "all",
             "paymentMode": "all", "startDate": start, "endDate": end},
            list_key="payments",
        ))

    def new_arrears(self, city: str):
        return list(self.paginate(
            "/admin/booking/payments/newarrears",
            {"city": city, "status": "all", "paymentType": "all", "paymentMode": "all"},
            list_key="payments",
        ))

    def bookings(self, city: str):
        return list(self.paginate(
            "/admin/booking/custom", {"city": city}, list_key="bookings"
        ))

    def b2b_bookings(self):
        return list(self.paginate("/admin/b2b/bookings", {}, list_key="bookings"))


if __name__ == "__main__":  # smoke test
    import sys
    c = DashboardClient(sys.argv[1] if len(sys.argv) > 1 else "fllat").login()
    print("cities:", json.dumps(c.unique_cities())[:200])
