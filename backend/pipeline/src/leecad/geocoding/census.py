import httpx
from .base import Geocoder

class CensusGeocoder(Geocoder):
    URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

    def geocode(self, address: str, city: str, state: str = "FL") -> tuple[float, float, str] | None:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(self.URL, params={
                "address": f"{address}, {city}, {state}",
                "benchmark": "Public_AR_Current",
                "format": "json"
            })
            response.raise_for_status()
            data = response.json()

        matches = data["result"]["addressMatches"]
        if not matches:
            return None

        coords = matches[0]["coordinates"]
        quality = "EXACT" if len(matches) == 1 else "AMBIGUOUS"
        return coords["y"], coords["x"], quality
