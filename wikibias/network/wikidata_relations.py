"""Person-to-person relations stored on Wikidata (replaces ``src/wd_knowledge.py``)."""

from dataclasses import dataclass

import pandas as pd

from ..wikimedia import WikimediaClient

DEFAULT_RELATIONS_CSV = "data/people-and-media_cleaned.csv"


@dataclass(frozen=True)
class Relation:
    source: str      # Wikidata ID of the subject
    prop: str        # Wikidata property (e.g. "P26")
    target: str      # Wikidata ID of the object (or raw value)


class WikidataRelations:
    """Reads the Wikidata relations listed in ``relations_csv`` (columns
    ``prop`` and ``o``) for a set of people."""

    def __init__(self, relations_csv: str = DEFAULT_RELATIONS_CSV, client: WikimediaClient | None = None):
        df = pd.read_csv(relations_csv)
        self.properties = dict(zip(df["prop"], df["o"]))
        self.client = client or WikimediaClient()

    def relations(self, people: list[str]) -> tuple[list[Relation], dict[str, int]]:
        """Return the relations of ``people`` and the number of relations per person."""
        entities = self.client.get_entities(people, props="claims")
        all_relations: list[Relation] = []
        counts: dict[str, int] = {}
        for person in people:
            claims = entities.get(person, {}).get("claims", {})
            n = 0
            for prop in self.properties:
                for claim in claims.get(prop, []):
                    value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                    if value is None:
                        continue
                    n += 1
                    if isinstance(value, dict) and "id" in value:
                        all_relations.append(Relation(person, prop, value["id"]))
                    elif isinstance(value, dict) and "time" in value:
                        all_relations.append(Relation(person, prop, value["time"]))
            counts[person] = n
        return all_relations, counts

    def existing_kb(self, people: list[str]) -> pd.DataFrame:
        """Person-to-person relations as a ``s, p, o`` table (``data/existing_kb.csv``)."""
        relations, _ = self.relations(people)
        rows = [(r.source, r.prop, r.target) for r in relations if r.target.startswith("Q")]
        return pd.DataFrame(rows, columns=["s", "p", "o"]).drop_duplicates()

    def claim(self, people: list[str], prop: str, dtype: str = "wikibase-item") -> list[dict]:
        """Return the first value of ``prop`` for each person.

        ``dtype`` is one of ``"wikibase-item"``, ``"external-id"``, ``"time"``.
        """
        entities = self.client.get_entities(people, props="claims")
        out = []
        for entity_id, entity in entities.items():
            try:
                value = entity["claims"][prop][0]["mainsnak"]["datavalue"]["value"]
            except (KeyError, IndexError):
                continue
            if dtype == "wikibase-item":
                value = value["id"]
            elif dtype == "time":
                value = value["time"]
            out.append({"entity": entity_id, prop: value})
        return out

    def sitelinks(self, people: list[str], site: str = "enwiki") -> list[dict]:
        """Return the Wikipedia page title of each person on ``site``."""
        entities = self.client.get_entities(people, props="sitelinks")
        return [
            {"entity": entity_id, "sitelink": entity["sitelinks"][site]["title"]}
            for entity_id, entity in entities.items()
            if site in entity.get("sitelinks", {})
        ]
