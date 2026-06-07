from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import Geocoder, GeocodeCache

class GeocodingService:
    def __init__(self, geocoder: Geocoder, cache: GeocodeCache):
        self.geocoder = geocoder
        self.cache = cache

    def geocode(self, address: str, city: str):
        key = self._key(address, city)

        if cached := self.cache.get(key):
            return cached, True

        result = self.geocoder.geocode(address, city)
        if result:
            lat, lon, quality = result
            self.cache.set(key, lat, lon, quality)
        return result, False

    def geocode_batch(self, items: list[tuple[str, str]], max_workers: int = 10):
        """Batch counterpart of geocode(). Returns [(result, from_cache), ...] aligned to
        `items`. Cache reads/writes are single round trips; external geocoder calls keep the
        same per-geocoder throttle as geocode(). Misses are deduped by cache key, so the same
        address appearing twice in a batch is geocoded once."""
        keys = [self._key(addr, city) for addr, city in items]
        cached = self.cache.get_many(list(set(keys)))

        # Unique cache misses -> one external geocode each.
        misses: dict[str, tuple[str, str]] = {}
        for key, (addr, city) in zip(keys, items):
            if key not in cached:
                misses.setdefault(key, (addr, city))

        fresh: dict[str, tuple[float, float, str]] = {}
        if misses:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(self.geocoder.geocode, addr, city): key
                           for key, (addr, city) in misses.items()}
                for fut in as_completed(futures):
                    key = futures[fut]
                    try:
                        result = fut.result()
                    except Exception as e:
                        print(f"    geocode failed for {misses[key][0]!r}: {e}")
                        result = None
                    if result:
                        fresh[key] = result
            if fresh:
                self.cache.set_many(fresh)

        out = []
        for key in keys:
            if key in cached:
                out.append((cached[key], True))
            elif key in fresh:
                out.append((fresh[key], False))
            else:
                out.append((None, False))
        return out

    @staticmethod
    def _key(address: str, city: str) -> str:
        # Normalize so "2217 Twin Brooks Rd" and "2217 TWIN BROOKS RD" share a cache entry.
        return f"{address.upper().strip()}|{city.upper().strip()}"