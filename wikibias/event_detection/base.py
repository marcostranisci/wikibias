"""Abstract interface for biographical event detection."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict


@dataclass
class BiographicalEvent:
    """An event trigger found in a sentence of a person's Wikipedia page."""

    subject: str          # Wikidata ID of the person the page is about
    sentence_index: int   # position of the sentence in the page
    sentence: str         # sentence text
    trigger: str          # word that triggers the event (e.g. "married")
    token_index: int      # position of the trigger in the sentence tokens

    def to_dict(self) -> dict:
        return asdict(self)


class BiographicalEventDetector(ABC):
    """Detects biographical events in a Wikipedia page."""

    @abstractmethod
    def detect(self, wikidata_id: str, wikipedia_page: str) -> list[BiographicalEvent]:
        """Return the events found in ``wikipedia_page``.

        :param wikidata_id: Wikidata ID of the person (e.g. "Q3335").
        :param wikipedia_page: text of the person's Wikipedia page
            (wikitext or plain text).
        """
