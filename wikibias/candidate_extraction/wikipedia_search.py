"""Candidates from the Wikipedia search API, filtered to humans on Wikidata."""

from functools import lru_cache

from ..wikimedia import WikimediaClient, claim_item_ids, entity_label
from .base import Candidate, CandidateExtractor

INSTANCE_OF = "P31"
HUMAN = "Q5"


class WikipediaSearchCandidateExtractor(CandidateExtractor):
    """Query Wikipedia search with the mention, keep the top-k pages, link them
    to Wikidata, and keep only items that are instances of human (Q5).

    Results are cached per mention.
    """

    def __init__(self, top_k: int = 3, client: WikimediaClient | None = None, cache_size: int = 100_000):
        self.top_k = top_k
        self.client = client or WikimediaClient()
        self._extract_cached = lru_cache(maxsize=cache_size)(self._extract)

    def extract(self, mention: str) -> list[Candidate]:
        mention = " ".join(mention.split())
        if not mention:
            return []
        return list(self._extract_cached(mention))

    def _extract(self, mention: str) -> tuple[Candidate, ...]:
        titles = self.client.search_wikipedia(mention, limit=self.top_k)[: self.top_k]
        if not titles:
            return ()

        title_to_id = self.client.wikidata_ids_for_titles(titles)
        entities = self.client.get_entities(title_to_id.values(), props="labels|aliases|claims")

        candidates = []
        for rank, title in enumerate(titles):
            qid = title_to_id.get(title)
            entity = entities.get(qid or "", {})
            if not qid or HUMAN not in claim_item_ids(entity, INSTANCE_OF):
                continue
            language = self.client.language
            candidates.append(Candidate(
                wikidata_id=qid,
                label=entity_label(entity, language) or title,
                wikipedia_title=title,
                rank=rank,
                aliases=[a["value"] for a in entity.get("aliases", {}).get(language, [])],
            ))
        return tuple(candidates)
