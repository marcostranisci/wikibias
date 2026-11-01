"""Abstract interface for entity linking."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict


@dataclass
class LinkedEntity:
    """A person mention linked to a Wikidata item."""

    mention: str
    wikidata_id: str
    label: str
    score: float      # gestalt similarity between mention and label
    rule: str         # heuristic that produced the link

    def to_dict(self) -> dict:
        return asdict(self)


class EntityLinker(ABC):
    """Links the people mentioned in a sentence to Wikidata."""

    @abstractmethod
    def link(self, sentence: str) -> list[LinkedEntity]:
        """Return the people in ``sentence`` linked to Wikidata."""
