import httpx
from geocoding.base import Geocoder

USER_AGENT = "LeeCountyIncidentMap/1.0 (senior-design; real@contact.com)"
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

def _expand_street(name: str) -> str:
    out = []
    for token in name.strip().split():
        u = token.upper()
        out.append(_STREET_TYPES.get(u) or _DIRECTIONS.get(u) or token.title())
    return " ".join(out)

class OverpassIntersectionGeocoder(Geocoder):
    URL = "https://overpass-api.de/api/interpreter"
    #URL = "https://overpass.private.coffee/api/interpreter"
    BBOX = LEE_COUNTY_BBOX

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

        with httpx.Client(timeout=40.0) as client:
            resp = client.post(
                self.URL,
                content=query.encode("utf-8"),
                headers={
                    "Content-Type": "text/plain",
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                }
            )
            resp.raise_for_status()
            elements = resp.json().get("elements", [])

        if not elements:
            return None
        node = elements[0]
        return float(node["lat"]), float(node["lon"]), "overpass:intersection"