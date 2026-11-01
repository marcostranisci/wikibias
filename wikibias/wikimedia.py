"""Small client for the Wikipedia and Wikidata APIs.

Wikimedia rejects requests without a descriptive User-Agent that includes
contact information (https://meta.wikimedia.org/wiki/User-Agent_policy).
Set your contact (email or URL) with ``WikimediaClient(contact=...)`` or the
``WIKIMEDIA_CONTACT`` environment variable.
"""

import os
import time
from typing import Iterable

import requests

WIKIPEDIA_API = "https://{lang}.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
PROJECT_URL = "https://github.com/marcostranisci/wikibias"

# Wikidata allows at most 50 IDs/titles per request.
MAX_BATCH = 50


def _chunks(items: list, size: int = MAX_BATCH):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def build_user_agent(contact: str | None = None) -> str:
    """``wikibias/0.1 (<project url>; <contact>) requests/<version>``."""
    contact = contact or os.environ.get("WIKIMEDIA_CONTACT")
    info = f"{PROJECT_URL}; {contact}" if contact else PROJECT_URL
    return f"wikibias/0.1 ({info}) requests/{requests.__version__}"


class WikimediaClient:
    """
    :param contact: email or URL put in the User-Agent (see module docstring).
    :param max_retries: retries on HTTP 429/5xx and on ``maxlag`` errors.
    :param maxlag: Wikimedia asks automated clients to send ``maxlag`` so they
        back off when the servers are under load.
    """

    def __init__(
        self,
        language: str = "en",
        contact: str | None = None,
        user_agent: str | None = None,
        timeout: int = 30,
        max_retries: int = 5,
        maxlag: int = 5,
    ):
        self.language = language
        self.timeout = timeout
        self.max_retries = max_retries
        self.maxlag = maxlag
        self.session = requests.Session()
        user_agent = user_agent or build_user_agent(contact)
        self.session.headers.update({
            "User-Agent": user_agent,
            "Api-User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        })

    @property
    def wikipedia_api(self) -> str:
        return WIKIPEDIA_API.format(lang=self.language)

    def _get(self, url: str, params: dict) -> dict:
        params = {**params, "format": "json", "formatversion": 1, "maxlag": self.maxlag}
        for attempt in range(self.max_retries + 1):
            response = self.session.get(url, params=params, timeout=self.timeout)
            retry = response.status_code == 429 or response.status_code >= 500
            data = None
            if not retry:
                response.raise_for_status()
                data = response.json()
                retry = data.get("error", {}).get("code") == "maxlag"
            if not retry:
                if "error" in data:
                    raise RuntimeError(f"Wikimedia API error: {data['error']}")
                return data
            if attempt == self.max_retries:
                response.raise_for_status()
                raise RuntimeError(f"Wikimedia API still busy after {self.max_retries} retries")
            time.sleep(self._wait_seconds(response, attempt))
        raise AssertionError("unreachable")

    @staticmethod
    def _wait_seconds(response: requests.Response, attempt: int) -> float:
        try:
            return float(response.headers.get("Retry-After", ""))
        except ValueError:
            return float(2 ** attempt)

    # ---------------- Wikipedia ----------------

    def search_wikipedia(self, query: str, limit: int) -> list[str]:
        """Return the titles of the top ``limit`` Wikipedia search results."""
        data = self._get(self.wikipedia_api, {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srnamespace": 0,
        })
        return [hit["title"] for hit in data.get("query", {}).get("search", [])]

    def wikidata_ids_for_titles(self, titles: Iterable[str]) -> dict[str, str]:
        """Map Wikipedia page titles to Wikidata IDs (redirects are followed)."""
        titles = list(titles)
        result: dict[str, str] = {}
        for batch in _chunks(titles):
            data = self._get(self.wikipedia_api, {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "pageprops",
                "ppprop": "wikibase_item",
                "redirects": 1,
            })
            query = data.get("query", {})
            # Map every requested title to its final (normalized/redirected) title.
            final = {t: t for t in batch}
            for step in ("normalized", "redirects"):
                for item in query.get(step, []):
                    for original, current in final.items():
                        if current == item["from"]:
                            final[original] = item["to"]
            by_title = {
                page["title"]: page["pageprops"]["wikibase_item"]
                for page in query.get("pages", {}).values()
                if "wikibase_item" in page.get("pageprops", {})
            }
            for original, current in final.items():
                if current in by_title:
                    result[original] = by_title[current]
        return result

    # ---------------- Wikidata ----------------

    def get_entities(self, ids: Iterable[str], props: str = "labels|claims") -> dict[str, dict]:
        """Fetch Wikidata entities, batching the IDs."""
        ids = list(dict.fromkeys(ids))
        entities: dict[str, dict] = {}
        for batch in _chunks(ids):
            data = self._get(WIKIDATA_API, {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": props,
                "languages": self.language,
            })
            entities.update(data.get("entities", {}))
        return entities

    def search_wikidata(self, query: str, limit: int = 10) -> list[dict]:
        data = self._get(WIKIDATA_API, {
            "action": "wbsearchentities",
            "search": query,
            "language": self.language,
            "type": "item",
            "limit": limit,
        })
        return data.get("search", [])


def claim_item_ids(entity: dict, prop: str) -> list[str]:
    """Return the item IDs that are values of ``prop`` in a Wikidata entity."""
    ids = []
    for claim in entity.get("claims", {}).get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and "id" in value:
            ids.append(value["id"])
    return ids


def entity_label(entity: dict, language: str = "en") -> str | None:
    return entity.get("labels", {}).get(language, {}).get("value")
