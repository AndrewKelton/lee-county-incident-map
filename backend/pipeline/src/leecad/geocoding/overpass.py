import random

import httpx
from leecad.geocoding.base import Geocoder
import time
import threading

from leecad.config import USER_AGENT

LEE_COUNTY_BBOX = (26.32, -82.30, 26.85, -81.55)  # (south, west, north, east)

_STREET_TYPES = {
    "AVE": "Avenue", "BLVD": "Boulevard", "ST": "Street", "RD": "Road",
    "DR": "Drive", "PKWY": "Parkway", "LN": "Lane", "CT": "Court",
    "TRL": "Trail", "CIR": "Circle", "TER": "Terrace", "WAY": "Way",
    "PL": "Place", "HWY": "Highway", "SQ": "Square", "LOOP": "Loop",
    "BCH": "Beach",
}
_DIRECTIONS = {
    "N": "North", "S": "South", "E": "East", "W": "West",
    "NE": "Northeast", "NW": "Northwest", "SE": "Southeast", "SW": "Southwest",
}

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    #"https://maps.mail.ru/osm/tools/overpass/api/interpreter",     Seems to be down, consistent 403 response on all requests
    "https://overpass.private.coffee/api/interpreter",
]

def _expand_street(name: str) -> str:
    out = []
    for token in name.strip().split():
        u = token.upper()
        out.append(_STREET_TYPES.get(u) or _DIRECTIONS.get(u) or token.title())
    return " ".join(out)

class _Endpoint:
    __slots__ = ("url", "ready_at")
    def __init__(self, url: str) -> None:
        self.url = url
        self.ready_at = 0.0

class OverpassIntersectionGeocoder(Geocoder):
    BBOX = LEE_COUNTY_BBOX
    MIN_INTERVAL = 1.0
    BUSY_COOLDOWN = 30.0
    MAX_COOLDOWN = 120.0
    REQUEST_TIMEOUT = 90.0

    _lock = threading.Lock()
    _endpoints = [_Endpoint(u) for u in ENDPOINTS]

    def _claim_endpoint(self) -> tuple[_Endpoint, float]:
        with OverpassIntersectionGeocoder._lock:
            ep = min(self._endpoints, key=lambda e: e.ready_at)
            now = time.monotonic()
            wait = max(0.0, ep.ready_at - now)
            ep.ready_at = max(now, ep.ready_at) + self.MIN_INTERVAL
        return ep, wait

    def _cooldown(self, ep: _Endpoint, seconds: float) -> None:
        with OverpassIntersectionGeocoder._lock:
            ep.ready_at = time.monotonic() + min(seconds, self.MAX_COOLDOWN)

    def geocode(self, address: str, city: str, state: str = "FL") -> tuple[float, float, str] | None:
        if " / " not in address:
            return None

        a_raw, b_raw = address.split(" / ", 1)
        a, b = _expand_street(a_raw), _expand_street(b_raw)
        s, w, n, e = self.BBOX
        query = (
            "[out:json][timeout:25];"
            f'way[name="{a}"][highway]({s},{w},{n},{e})->.a;'
            f'way[name="{b}"][highway]({s},{w},{n},{e})->.b;'
            "node(w.a)(w.b);"
            "out 1;"
        )

        for _ in range(len(self._endpoints) * 2):
            ep, wait = self._claim_endpoint()
            if wait > 0:
                time.sleep(min(wait, self.MAX_COOLDOWN))
            try:
                with httpx.Client(timeout=self.REQUEST_TIMEOUT) as client:
                    resp = client.post(
                        ep.url, content=query.encode("utf-8"),
                        headers={"Content-Type": "text/plain",
                                 "Accept": "application/json",
                                 "User-Agent": USER_AGENT},
                    )
            except (httpx.TransportError, httpx.TimeoutException):
                self._cooldown(ep, 10.0)
                continue
            if resp.status_code in (429, 504): # rate limited / too busy
                self._cooldown(ep, self.BUSY_COOLDOWN + random.uniform(0, 15))
                continue
            if resp.status_code >= 400:
                return None
            elements = resp.json().get("elements", [])
            if not elements:
                return None
            node = elements[0]
            return float(node["lat"]), float(node["lon"]), "overpass:intersection"
        return None
