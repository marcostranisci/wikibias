"""Augment a knowledge graph of authors with relations found in their biographies,
then analyse the resulting networks.

Inputs
------
--authors       CSV with one row per author: Wikidata ID, origin and gender
                (column names set with --id-column, --origin-column,
                --gender-column; an optional --label-column gives names).
--biographies   the biographies, one of:
                * a directory with one file per author, named ``<QID>.txt``
                  or ``<QID>.txt.gz`` (wikitext or plain text). Pages saved by
                  steps 1-2 (``output/<hash of title>.txt.gz``) are also found
                  when the authors CSV has a ``sitelink`` column;
                * a ``.jsonl``/``.json``/``.csv`` file with ``entity`` and
                  ``text`` fields.

Steps
-----
1. biographical event detection on each biography      (wikibias.event_detection)
2. people in event sentences linked to Wikidata         (wikibias.entity_linking,
                                                          wikibias.candidate_extraction)
3. base KG: person-to-person relations on Wikidata       (wikibias.network)
4. augmented KG = base KG + extracted relations
5. network analysis of the base, extended and augmented networks

Outputs (in --output-dir)
-------------------------
extraction/<QID>.json.gz      per-author extraction (reused on later runs)
kg/base_triples.csv           Wikidata relations (s, p, o)
kg/extracted_triples.csv      relations found in text, one row per sentence
kg/augmented_triples.csv      both, with a ``source`` column
kg/{base,extended,augmented}.graphml
analysis/authors.csv          per author: people linked in each network
analysis/<network>/summary.json, rankings.csv, densities.csv, edge_events.csv
                              (+ path_events.csv with --path-events)

Example
-------
    export WIKIMEDIA_CONTACT="you@example.org"
    python augment_kg.py --authors data/authors.csv --biographies output/ \\
        --model event_detection_model.pth --output-dir results/
"""

import argparse
import csv
import glob
import gzip
import json
import logging
import os
from collections import Counter
from itertools import groupby

import networkx as nx
import pandas as pd
from tqdm import tqdm

from utils import string_to_hash
from wikibias.network import analysis
from wikibias.network.build import (
    NodeAttributes,
    build_base_network,
    build_extended_network,
    compose_networks,
)

log = logging.getLogger("augment_kg")

NETWORKS = ("base", "extended", "augmented")


# ======================================================================
# Inputs
# ======================================================================

def load_authors(path, id_column, origin_column, gender_column, label_column=None):
    """Read the authors CSV; returns a DataFrame indexed by Wikidata ID."""
    df = pd.read_csv(path, dtype=str)
    missing = [c for c in (id_column, origin_column, gender_column) if c not in df.columns]
    if missing:
        raise ValueError(f"{path} has no column(s) {missing}; columns are {list(df.columns)}")
    df = df.dropna(subset=[id_column]).drop_duplicates(id_column).set_index(id_column)
    df = df.rename(columns={origin_column: "origin", gender_column: "gender"})
    if label_column and label_column in df.columns:
        df = df.rename(columns={label_column: "label"})
    return df


def _read_text(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return f.read()


def load_biographies(source, authors):
    """Return ``{QID: page text}`` for the authors that have a biography."""
    ids = set(authors.index)
    pages = {}

    if os.path.isdir(source):
        for qid in ids:
            for name in (f"{qid}.txt", f"{qid}.txt.gz"):
                path = os.path.join(source, name)
                if os.path.isfile(path):
                    pages[qid] = _read_text(path)
                    break
        # Pages saved by steps 1-2: hashed title, title on the first line.
        if "sitelink" in authors.columns:
            for qid, title in authors["sitelink"].dropna().items():
                path = os.path.join(source, f"{string_to_hash(title)}.txt.gz")
                if qid not in pages and os.path.isfile(path):
                    pages[qid] = _read_text(path).split("\n", 1)[-1]

    elif source.endswith((".jsonl", ".json")):
        with open(source, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()] if source.endswith(".jsonl") else json.load(f)
        pages = {r["entity"]: r["text"] for r in rows if r.get("entity") in ids}

    elif source.endswith(".csv"):
        df = pd.read_csv(source, dtype=str)
        pages = {e: t for e, t in zip(df["entity"], df["text"]) if e in ids and isinstance(t, str)}

    else:
        raise ValueError(f"Unsupported biographies source: {source}")

    log.info("Biographies found for %d of %d authors", len(pages), len(ids))
    return pages


# ======================================================================
# Extraction (event detection + entity linking)
# ======================================================================

def extract_author(wikidata_id, page, detector, linker):
    """One record per event sentence that mentions other people."""
    records = []
    events = detector.detect(wikidata_id, page)
    for sentence_index, group in groupby(events, key=lambda e: e.sentence_index):
        group = list(group)
        mentions = [m for m in linker.link(group[0].sentence) if m.wikidata_id != wikidata_id]
        if mentions:
            records.append({
                "author": wikidata_id,
                "sentence_index": sentence_index,
                "sentence": group[0].sentence,
                "events": sorted({e.trigger.lower() for e in group}),
                "mentions": [m.to_dict() for m in mentions],
            })
    return records


def run_extraction(pages, cache_dir, make_components):
    """Extract every author, reusing results cached in ``cache_dir``.

    ``make_components()`` returns ``(detector, linker)``; it is only called if
    some author still needs processing (loading the models is slow).
    """
    os.makedirs(cache_dir, exist_ok=True)
    components = None
    records = []
    for qid, page in tqdm(sorted(pages.items()), desc="Extracting"):
        path = os.path.join(cache_dir, f"{qid}.json.gz")
        if os.path.isfile(path):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                records.extend(json.load(f)["result"])
            continue
        if components is None:
            components = make_components()
        try:
            result = extract_author(qid, page, *components)
        except Exception:
            log.exception("Extraction failed for %s", qid)
            continue
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump({"result": result}, f, ensure_ascii=False)
        records.extend(result)
    return records


def default_components(model_path, top_k, threshold):
    from wikibias.candidate_extraction import WikipediaSearchCandidateExtractor
    from wikibias.entity_linking import HeuristicEntityLinker
    from wikibias.event_detection import BertEventDetector

    detector = BertEventDetector(model_path=model_path)
    linker = HeuristicEntityLinker(
        WikipediaSearchCandidateExtractor(top_k=top_k),
        threshold=threshold,
        nlp=detector.nlp,
    )
    return detector, linker


# ======================================================================
# Knowledge graph
# ======================================================================

def extracted_triples(records):
    rows = []
    for r in records:
        for m in r["mentions"]:
            rows.append({
                "s": r["author"],
                "p": ",".join(r["events"]),
                "o": m["wikidata_id"],
                "o_label": m.get("label"),
                "mention": m.get("mention"),
                "linking_rule": m.get("rule"),
                "linking_score": m.get("score"),
                "sentence_index": r["sentence_index"],
                "sentence": r["sentence"],
            })
    return pd.DataFrame(rows, columns=[
        "s", "p", "o", "o_label", "mention", "linking_rule", "linking_score", "sentence_index", "sentence",
    ])


def augmented_triples(base, extracted):
    base = base[["s", "p", "o"]].assign(source="wikidata")
    text = extracted[["s", "p", "o", "sentence"]].assign(source="text")
    return pd.concat([base, text], ignore_index=True)


def collect_labels(authors, records, fetch_labels=None, node_ids=()):
    """Wikidata ID -> label, from the authors CSV, the linker, then the API."""
    labels = {}
    if "label" in authors.columns:
        labels.update(authors["label"].dropna().to_dict())
    for r in records:
        for m in r["mentions"]:
            if m.get("label"):
                labels.setdefault(m["wikidata_id"], m["label"])
    missing = [n for n in node_ids if n not in labels and str(n).startswith("Q")]
    if fetch_labels and missing:
        try:
            labels.update(fetch_labels(missing))
        except Exception:
            log.exception("Could not fetch labels from Wikidata")
    return labels


def wikidata_labels(ids):
    from wikibias.wikimedia import WikimediaClient, entity_label

    entities = WikimediaClient().get_entities(ids, props="labels")
    return {qid: entity_label(e) for qid, e in entities.items() if entity_label(e)}


def build_networks(authors, base_kg, records, labels):
    attrs = NodeAttributes(
        writers=set(authors.index),
        labels=labels,
        attributes={
            "origin": authors["origin"].dropna().to_dict(),
            "gender": authors["gender"].dropna().to_dict(),
        },
    )
    base = build_base_network(base_kg, attrs)
    extended = build_extended_network(records, attrs)
    return {"base": base, "extended": extended, "augmented": compose_networks(base, extended)}


# ======================================================================
# Analysis
# ======================================================================

def author_table(networks, authors):
    """Per author: how many people are linked in each network, and how many
    the text adds to Wikidata."""
    rows = []
    for qid in authors.index:
        linked = {
            name: set(g.successors(qid)) if qid in g else set()
            for name, g in networks.items()
        }
        rows.append({
            "author": qid,
            "label": authors.at[qid, "label"] if "label" in authors.columns else None,
            "origin": authors.at[qid, "origin"],
            "gender": authors.at[qid, "gender"],
            **{f"{name}_out_degree": len(people) for name, people in linked.items()},
            "new_from_text": len(linked["extended"] - linked["base"]),
            "in_degree_augmented": networks["augmented"].in_degree(qid) if qid in networks["augmented"] else 0,
        })
    return pd.DataFrame(rows)


def analyse_network(graph, out_dir, measures, top_n, path_events):
    os.makedirs(out_dir, exist_ok=True)
    attributes = ["writer", "origin", "gender"]
    gc = analysis.giant_component(graph)
    n_nodes, n_edges = graph.number_of_nodes(), graph.number_of_edges()

    summary = {
        "nodes": n_nodes,
        "edges": n_edges,
        "writers": sum(1 for _, d in graph.nodes(data=True) if analysis.is_writer(d)),
        "giant_component": {
            "nodes": gc.number_of_nodes(),
            "edges": gc.number_of_edges(),
            "nodes_pct": round(100 * gc.number_of_nodes() / n_nodes, 2) if n_nodes else 0.0,
            "edges_pct": round(100 * gc.number_of_edges() / n_edges, 2) if n_edges else 0.0,
        },
        "attribute_distribution": {a: analysis.attribute_distribution(graph, a) for a in attributes},
        "attribute_distribution_giant_component": {a: analysis.attribute_distribution(gc, a) for a in attributes},
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    groups = analysis.groups_by_attributes(graph, ["origin", "gender"])
    filters = {"all": None, "writers": analysis.is_writer}
    for name, members in groups.items():
        filters[name] = lambda d, m=members: d.get("code") in m

    rows = []
    for measure in measures:
        if n_nodes == 0:
            break
        ranked = analysis.ranking(graph, measure)
        for name, node_filter in filters.items():
            for i, row in enumerate(analysis.top_nodes(graph, ranked, node_filter, n=top_n), start=1):
                rows.append({"measure": measure, "group": name, "group_position": i, **row})
    pd.DataFrame(rows).to_csv(os.path.join(out_dir, "rankings.csv"), index=False)

    writers = graph.subgraph(n for n, d in graph.nodes(data=True) if analysis.is_writer(d))
    pd.DataFrame(analysis.density_table(writers, groups)).to_csv(os.path.join(out_dir, "densities.csv"), index=False)

    pd.DataFrame(analysis.edge_event_counts(graph).most_common(), columns=["event", "edges"]).to_csv(
        os.path.join(out_dir, "edge_events.csv"), index=False)

    if path_events:
        counts = Counter(event for _, event, _ in analysis.shortest_path_edges(graph, list(writers.nodes)))
        pd.DataFrame(counts.most_common(), columns=["event", "count"]).to_csv(
            os.path.join(out_dir, "path_events.csv"), index=False)

    return summary


# ======================================================================
# Main
# ======================================================================

def run(args, make_components=None, fetch_base_kg=None, fetch_labels=wikidata_labels):
    out = args.output_dir
    os.makedirs(os.path.join(out, "kg"), exist_ok=True)

    authors = load_authors(args.authors, args.id_column, args.origin_column, args.gender_column, args.label_column)
    pages = load_biographies(args.biographies, authors)

    make_components = make_components or (lambda: default_components(args.model, args.top_k, args.threshold))
    records = run_extraction(pages, os.path.join(out, "extraction"), make_components)

    if args.existing_kb:
        base_kg = pd.read_csv(args.existing_kb, dtype=str)
    else:
        if fetch_base_kg is None:
            from wikibias.network import WikidataRelations
            fetch_base_kg = WikidataRelations(args.relations).existing_kb
        base_kg = fetch_base_kg(list(authors.index))
    base_kg = base_kg[["s", "p", "o"]]

    extracted = extracted_triples(records)
    base_kg.to_csv(os.path.join(out, "kg", "base_triples.csv"), index=False)
    extracted.to_csv(os.path.join(out, "kg", "extracted_triples.csv"), index=False)
    augmented_triples(base_kg, extracted).to_csv(os.path.join(out, "kg", "augmented_triples.csv"), index=False)

    node_ids = set(base_kg["s"]) | set(base_kg["o"]) | set(extracted["o"])
    labels = collect_labels(authors, records, fetch_labels if args.fetch_labels else None, node_ids)
    networks = build_networks(authors, base_kg, records, labels)
    for name, graph in networks.items():
        nx.write_graphml(graph, os.path.join(out, "kg", f"{name}.graphml"))

    os.makedirs(os.path.join(out, "analysis"), exist_ok=True)
    author_table(networks, authors).to_csv(os.path.join(out, "analysis", "authors.csv"), index=False)
    summaries = {
        name: analyse_network(graph, os.path.join(out, "analysis", name), args.measures, args.top_n, args.path_events)
        for name, graph in networks.items()
    }
    log.info("Done. Results in %s", out)
    return summaries


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--authors", required=True, help="CSV with author IDs, origin and gender")
    p.add_argument("--biographies", required=True, help="directory or .jsonl/.json/.csv file")
    p.add_argument("--output-dir", default="results")
    p.add_argument("--id-column", default="entity")
    p.add_argument("--origin-column", default="origin")
    p.add_argument("--gender-column", default="gender")
    p.add_argument("--label-column", default="label")
    p.add_argument("--model", default="event_detection_model.pth", help="event detection weights (.pt/.pth)")
    p.add_argument("--top-k", type=int, default=3, help="Wikipedia search results kept per mention")
    p.add_argument("--threshold", type=float, default=0.8, help="gestalt similarity threshold")
    p.add_argument("--existing-kb", help="CSV (s,p,o) of Wikidata relations; fetched from Wikidata if omitted")
    p.add_argument("--relations", default="data/people-and-media_cleaned.csv",
                   help="Wikidata properties used for the base KG")
    p.add_argument("--no-fetch-labels", dest="fetch_labels", action="store_false",
                   help="do not fetch missing node labels from Wikidata")
    p.add_argument("--measures", nargs="+", default=list(analysis.CENTRALITY), choices=list(analysis.CENTRALITY))
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--path-events", action="store_true",
                   help="count events on shortest paths between writers (slow on large networks)")
    return p.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(parse_args())
