from abc import ABC, abstractmethod
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from config import USER_AGENT

DEFAULT_TIMEOUT = 30.0

class IncidentSource(ABC):
    name: str

    def _client(self) -> httpx.Client:
        return httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True
    )
    def fetch_json(self, url: str, params: dict | None = None) -> dict | list:
        """Common case: GET, parse JSON, raise on error"""
        with self._client() as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def fetch_text(self, url: str, params: dict | None = None) -> str:
        """For HTML scraping or XML feeds"""
        with self._client() as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.text

    @abstractmethod
    def fetch_raw(self) -> list[dict]:
        """Hit the API/scrape the page. Return raw records as-is"""

    @abstractmethod
    def normalize(self, raw: dict, fetched_at: datetime) -> "NormalizedIncident":
        """Map one raw record to the canonical schema"""