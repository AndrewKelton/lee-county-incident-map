import time
import threading
import httpx
from leecad.geocoding.base import Geocoder
from leecad.config import USER_AGENT

class NominatimGeocoder(Geocoder):
    URL = "https://nominatim.openstreetmap.org/search"

    _lock = threading.Lock()
    _last_call = 0.0
    MIN_INTERVAL = 1.1

    def geocode(self, address: str, city: str, state: str = "FL") -> tuple[float, float, str] | None:
        with NominatimGeocoder._lock:
            wait = self.MIN_INTERVAL - (time.monotonic() - NominatimGeocoder._last_call)
            if wait > 0:
                time.sleep(wait)
            NominatimGeocoder._last_call = time.monotonic()

        query = address.replace(" / ", " and ")
        with httpx.Client(timeout=10.0, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(self.URL, params={
                "q": f"{query}, {city}, {state}",
                "format": "json",
                "limit": 1,
            })
            resp.raise_for_status()
            results = resp.json()

        if not results:
            return None
        best = results[0]
        return float(best["lat"]), float(best["lon"]), f"nominatim:{best.get('type', 'match')}"