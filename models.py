from datetime import datetime
from pydantic import BaseModel

class NormalizedIncident(BaseModel):
    source: str
    source_incident_id: str
    occurred_at: datetime
    fetched_at: datetime
    lat: float | None = None
    lon: float | None = None
    nature: str | None = None
    disposition: str | None
    address: str | None = None
    city: str | None = None
    status: str | None = None
    geocoded_at: datetime | None = None
    geocode_quality: str | None = None
    raw: dict