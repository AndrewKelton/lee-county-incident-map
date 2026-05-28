from .base import Geocoder, GeocodeCache

class GeocodingService:
    def __init__(self, geocoder: Geocoder, cache: GeocodeCache):
        self.geocoder = geocoder
        self.cache = cache

    def geocode(self, address: str, city: str):
        key = self._key(address, city)

        if cached := self.cache.get(key):
            return cached

        result = self.geocoder.geocode(address, city)
        if result:
            lat, lon, quality = result
            self.cache.set(key, lat, lon, quality)
        return result

    @staticmethod
    def _key(address: str, city: str) -> str:
        # Normalize so "2217 Twin Brooks Rd" and "2217 TWIN BROOKS RD" share a cache entry.
        return f"{address.upper().strip()}|{city.upper().strip()}"