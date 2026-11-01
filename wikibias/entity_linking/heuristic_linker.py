"""Person linking with spaCy NER, candidate extraction and string heuristics."""

import re
from difflib import SequenceMatcher
from typing import Callable, Protocol, Sequence

from .base import EntityLinker, LinkedEntity

POSSESSIVE = re.compile(r"(?:'s|’s|'|’)$")
PARENTHESIS = re.compile(r"\s*\(.*?\)\s*")
NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}


class Candidate(Protocol):
    """What the linker needs from a candidate (matches
    ``wikibias.candidate_extraction.Candidate``)."""

    wikidata_id: str
    label: str
    rank: int


class CandidateSource(Protocol):
    """Anything with ``extract(mention) -> candidates``, e.g. a
    ``wikibias.candidate_extraction.CandidateExtractor``."""

    def extract(self, mention: str) -> Sequence[Candidate]: ...


def gestalt_similarity(a: str, b: str) -> float:
    """Ratcliff/Obershelp ("gestalt pattern matching") similarity, case-insensitive."""
    return SequenceMatcher(None, a.casefold(), b.casefold()).ratio()


def normalize_mention(text: str) -> str:
    text = " ".join(text.split())
    return POSSESSIVE.sub("", text).strip()


class HeuristicEntityLinker(EntityLinker):
    """Links PERSON entities found by spaCy to Wikidata.

    For each mention, candidates come from a ``CandidateExtractor`` and are
    scored against their Wikidata label:

    1. single-word mentions that are also given names (e.g. "Adele") are dropped;
    2. the candidate with the highest gestalt similarity is linked if the
       score is >= ``threshold`` (0.8);
    3. otherwise, if the mention is a surname only (e.g. "Orwell"), it is
       linked to the best-ranked candidate whose label ends with that surname
       (e.g. "George Orwell"): search ranking favours the more famous person.

    :param is_given_name: callable returning True for given names;
        defaults to ``WikidataGivenNameChecker``.
    """

    def __init__(
        self,
        candidate_extractor: CandidateSource,
        spacy_model: str = "en_core_web_sm",
        threshold: float = 0.8,
        is_given_name: Callable[[str], bool] | None = None,
        nlp=None,
    ):
        if nlp is None:
            import spacy
            nlp = spacy.load(spacy_model)
        if is_given_name is None:
            from .given_names import WikidataGivenNameChecker
            is_given_name = WikidataGivenNameChecker()

        self.nlp = nlp
        self.candidate_extractor = candidate_extractor
        self.threshold = threshold
        self.is_given_name = is_given_name

    # ------------------------------------------------------------------

    def link(self, sentence: str) -> list[LinkedEntity]:
        linked = []
        for mention in self.person_mentions(sentence):
            entity = self.link_mention(mention)
            if entity is not None:
                linked.append(entity)
        return linked

    def person_mentions(self, sentence: str) -> list[str]:
        """Return the PERSON mentions in ``sentence`` (normalized, de-duplicated)."""
        mentions = (normalize_mention(ent.text) for ent in self.nlp(sentence).ents if ent.label_ == "PERSON")
        return list(dict.fromkeys(m for m in mentions if m))

    def link_mention(self, mention: str) -> LinkedEntity | None:
        mention = normalize_mention(mention)
        single_word = len(mention.split()) == 1

        # Rule 1: a mention that is also a given name is too ambiguous.
        if single_word and self.is_given_name(mention):
            return None

        candidates = self.candidate_extractor.extract(mention)
        if not candidates:
            return None

        # Rule 2: gestalt similarity with the Wikidata label.
        scored = [(gestalt_similarity(mention, c.label), c) for c in candidates]
        best_score, best = max(scored, key=lambda pair: (pair[0], -pair[1].rank))
        if best_score >= self.threshold:
            return self._linked(mention, best, best_score, "gestalt")

        # Rule 3: surname only -> best-ranked (most famous) person with that surname.
        if single_word:
            for score, candidate in sorted(scored, key=lambda pair: pair[1].rank):
                if self._surname(candidate) == mention.casefold():
                    return self._linked(mention, candidate, score, "surname")

        return None

    # ------------------------------------------------------------------

    @staticmethod
    def _surname(candidate: Candidate) -> str:
        words = [w.casefold().rstrip(",") for w in PARENTHESIS.sub(" ", candidate.label).split()]
        while words and words[-1] in NAME_SUFFIXES:
            words.pop()
        return words[-1] if words else ""

    @staticmethod
    def _linked(mention: str, candidate: Candidate, score: float, rule: str) -> LinkedEntity:
        return LinkedEntity(
            mention=mention,
            wikidata_id=candidate.wikidata_id,
            label=candidate.label,
            score=round(score, 4),
            rule=rule,
        )
