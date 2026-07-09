from leecad.geocoding.base import Geocoder

class CompositeGeocoder(Geocoder):
    def __init__(self, geocoders: list[Geocoder]):
        self.geocoders = geocoders

    def geocode(self, address: str, city: str, state: str = "FL") -> tuple[float, float, str] | None:
        for geocoder in self.geocoders:
            name = type(geocoder).__name__
            try:
                if result := geocoder.geocode(address, city, state):
                    return result
            except Exception as e:
                print(f"    {name} errored on {address!r}: {e}")
                continue
        return None