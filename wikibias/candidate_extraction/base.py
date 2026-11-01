"""Abstract interface for candidate extraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field


@dataclass
class Candidate:
    """A Wikidata person that a mention may refer to."""

    wikidata_id: str
    label: str                  # English Wikidata label
    wikipedia_title: str
    rank: int                   # position in the search results (0 = best)
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class CandidateExtractor(ABC):
    """Finds the candidate entities a person mention may refer to."""

    @abstractmethod
    def extract(self, mention: str) -> list[Candidate]:
        """Return candidates for ``mention``, best first."""
