"""Build the people networks (from "4. crea rete base.py" / "5. crea rete espansa.py").

* **base** network: relations already on Wikidata (``data/existing_kb.csv``,
  columns ``s, p, o``); the edge ``event`` is the Wikidata property.
* **extended** network: people linked in event sentences by the pipeline
  (``output_data/*.json.gz``); the edge ``event`` lists the event triggers.
* **joint** network: both merged.

Edge ``event`` attributes are comma-separated strings so graphs can be saved
as GraphML.
"""

import csv
import glob
import gzip
import json
import os
from dataclasses import dataclass, field
from typing import Iterable

import networkx as nx
import pandas as pd

MISSING = "N/D"


def split_events(value: str | None) -> set[str]:
    return {e for e in (value or "").split(",") if e}


def join_events(events: Iterable[str]) -> str:
    return ",".join(sorted(set(events)))


# ----------------------------------------------------------------------
# Node attributes
# ----------------------------------------------------------------------

@dataclass
class NodeAttributes:
    """Attributes attached to every node (writer, gender, transnational, ...)."""

    writers: set[str] = field(default_factory=set)
    labels: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, dict[str, str]] = field(default_factory=dict)  # attribute -> {qid: value}
    removed: set[str] = field(default_factory=set)

    @classmethod
    def from_files(
        cls,
        authors_csv: str = "data/authors_links.csv",
        gender_csv: str | None = "data/writers_gender.csv",
        postcolonial_csv: str | None = "data/writers_postcolonial.csv",
        labels_csv: str | None = "data/entity_labels.csv",
        to_be_removed_csv: str | None = "data/to_be_removed.csv",
    ) -> "NodeAttributes":
        """Load the attribute files; optional files that do not exist are skipped."""
        def exists(path):
            return path is not None and os.path.isfile(path)

        authors = pd.read_csv(authors_csv, dtype=str)
        attrs = cls(writers=set(authors["entity"]))
        attrs.attributes["transnational"] = dict(zip(authors["entity"], authors["transnational"]))

        if exists(gender_csv):
            df = pd.read_csv(gender_csv, dtype=str)
            attrs.attributes["gender"] = dict(zip(df["s"], df["P21"]))

        if exists(postcolonial_csv):
            df = pd.read_csv(postcolonial_csv, dtype=str)
            for name, column in [
                ("country", "CountryIsoCode"),
                ("former_colony", "FormerColony"),
                ("continent", "Continent"),
                ("minority", "minority"),
                ("postcolonial", "postcolonial"),
                ("birth", "P569"),
            ]:
                attrs.attributes[name] = dict(zip(df["s"], df[column]))

        for path in (labels_csv, authors_csv):
            if exists(path):
                with open(path, encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        attrs.labels[row["entity"]] = row["label"]

        if exists(to_be_removed_csv):
            with open(to_be_removed_csv, encoding="utf-8") as f:
                attrs.removed = {row["entity"] for row in csv.DictReader(f)}

        return attrs

    def for_node(self, qid: str) -> dict[str, str]:
        data = {
            "code": qid,
            "writer": "1" if qid in self.writers else "0",
            "display_name": self.labels.get(qid, qid),
        }
        for name, values in self.attributes.items():
            value = values.get(qid)
            data[name] = MISSING if value is None or pd.isna(value) else value
        return data


def _add_edge(graph: nx.DiGraph, source: str, target: str, events: Iterable[str], attrs: NodeAttributes):
    if source in attrs.removed or target in attrs.removed or source == target:
        return
    for node in (source, target):
        if node not in graph:
            graph.add_node(node, **attrs.for_node(node))
    old = split_events(graph.edges[source, target]["event"]) if graph.has_edge(source, target) else set()
    graph.add_edge(source, target, event=join_events(old | set(events)))


# ----------------------------------------------------------------------
# Networks
# ----------------------------------------------------------------------

def build_base_network(existing_kb: pd.DataFrame | str, attrs: NodeAttributes) -> nx.DiGraph:
    """Network of Wikidata relations (columns ``s``, ``p``, ``o``)."""
    if isinstance(existing_kb, str):
        existing_kb = pd.read_csv(existing_kb, dtype=str)
    graph = nx.DiGraph()
    for s, p, o in existing_kb[["s", "p", "o"]].itertuples(index=False):
        _add_edge(graph, s, o, [p], attrs)
    return graph


def load_records(results_dir: str) -> list[dict]:
    """Read the pipeline results (``output_data/*.json.gz``)."""
    records = []
    for path in sorted(glob.glob(os.path.join(results_dir, "*.json.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            records.extend(json.load(f)["result"])
    return records


def mention_ids(record: dict) -> list[str]:
    """Mentions are Wikidata IDs (old output) or dicts with ``wikidata_id``."""
    return [m["wikidata_id"] if isinstance(m, dict) else m for m in record.get("mentions", [])]


def build_extended_network(records: Iterable[dict], attrs: NodeAttributes) -> nx.DiGraph:
    """Network of people mentioned in the event sentences of each page."""
    graph = nx.DiGraph()
    for record in records:
        author = record["author"]
        if author not in attrs.removed and author not in graph:
            graph.add_node(author, **attrs.for_node(author))
        events = set(record.get("events", []))
        if not events:
            continue
        for mention in set(mention_ids(record)):
            _add_edge(graph, author, mention, events, attrs)
    return graph


def compose_networks(base: nx.DiGraph, extended: nx.DiGraph) -> nx.DiGraph:
    """Merge two networks; edges present in both keep the events of both."""
    graph = nx.compose(base, extended)
    for u, v in set(base.edges) & set(extended.edges):
        graph.edges[u, v]["event"] = join_events(
            split_events(base.edges[u, v].get("event")) | split_events(extended.edges[u, v].get("event"))
        )
    return graph
