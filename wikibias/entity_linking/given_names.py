"""Check whether a word is a given name, using Wikidata."""

from functools import lru_cache

from ..wikimedia import WikimediaClient, claim_item_ids

# given name, male given name, female given name, unisex given name
GIVEN_NAME_CLASSES = frozenset({"Q202444", "Q12308941", "Q11879590", "Q3409032"})


class WikidataGivenNameChecker:
    """A word is a given name if a Wikidata item with that exact label is an
    instance of one of ``GIVEN_NAME_CLASSES`` (e.g. "Adele" -> Q18157727)."""

    def __init__(self, client: WikimediaClient | None = None, search_limit: int = 10):
        self.client = client or WikimediaClient()
        self.search_limit = search_limit

    @lru_cache(maxsize=100_000)
    def __call__(self, word: str) -> bool:
        word = word.strip()
        if not word:
            return False
        results = self.client.search_wikidata(word, limit=self.search_limit)
        ids = [r["id"] for r in results if r.get("label", "").casefold() == word.casefold()]
        if not ids:
            return False
        entities = self.client.get_entities(ids, props="claims")
        return any(
            GIVEN_NAME_CLASSES.intersection(claim_item_ids(entity, "P31"))
            for entity in entities.values()
        )
