"""Step 3: detect biographical events and link the people mentioned in them.

For each author in ``data/authors_links.csv`` the page downloaded by steps 1-2
(``output/<hash>.txt.gz``) is processed as follows:

1. biographical event detection   -> ``wikibias.event_detection``
2. person mentions in event sentences are linked to Wikidata
   (candidate extraction + entity linking) -> ``wikibias.entity_linking``

Results go to ``data/output_data/<hash>.json.gz``. Network analysis on these files
lives in ``wikibias.network``.

Usage:
    python "3. perform_entity_linking.py" [--shard 0 --num-shards 4]
"""

import argparse
import csv
import gzip
import json
import logging as log
import os
import tempfile
import traceback
import zlib
from itertools import groupby

from tqdm import tqdm

from utils import output_data_path, string_to_hash
from wikibias.candidate_extraction import WikipediaSearchCandidateExtractor
from wikibias.entity_linking import HeuristicEntityLinker
from wikibias.event_detection import BertEventDetector

log.basicConfig(
    encoding="utf-8",
    level=log.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)


def read_page(path: str) -> str:
    """Pages from steps 1-2: title on the first line, then the page text."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        f.readline()
        return f.read()


def has_valid_output(path: str) -> bool:
    """True if ``path`` holds a complete result; broken files are regenerated."""
    if not os.path.isfile(path):
        return False
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("result"), list):
            return True
    except (gzip.BadGzipFile, EOFError, OSError, UnicodeDecodeError, json.JSONDecodeError, zlib.error):
        pass
    log.warning("Regenerating invalid entity-linking output: %s", path)
    return False


def write_output(path: str, data: dict) -> None:
    """Write through a temporary file so a crash never leaves a partial file."""
    with tempfile.NamedTemporaryFile(dir=os.path.dirname(path), delete=False) as tmp:
        tmp_path = tmp.name
    try:
        with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def process_author(wikidata_id, page, detector, linker):
    events = detector.detect(wikidata_id, page)
    records = []
    for sentence_index, group in groupby(events, key=lambda e: e.sentence_index):
        group = list(group)
        mentions = [m for m in linker.link(group[0].sentence) if m.wikidata_id != wikidata_id]
        if not mentions:
            continue
        records.append({
            "author": wikidata_id,
            "sentence_index": sentence_index,
            "sentence": group[0].sentence,
            "events": [e.trigger for e in group],
            "mentions": [m.to_dict() for m in mentions],
            "n_mentions": len({m.wikidata_id for m in mentions}),
        })
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--authors", default="data/authors_links.csv")
    parser.add_argument("--id-column", default="entity", help="column with the Wikidata ID")
    parser.add_argument("--title-column", default="sitelink", help="column with the Wikipedia title")
    parser.add_argument("--input-dir", default="output")
    parser.add_argument("--output-dir", default=output_data_path())
    parser.add_argument("--model", default="event_detection_model.pth")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    args = parser.parse_args()

    with open(args.authors, encoding="utf-8") as f:
        authors = [(row[args.id_column], row[args.title_column]) for row in csv.DictReader(f)]
    authors = authors[args.shard::args.num_shards]
    os.makedirs(args.output_dir, exist_ok=True)

    detector = BertEventDetector(model_path=args.model)
    linker = HeuristicEntityLinker(
        WikipediaSearchCandidateExtractor(top_k=args.top_k),
        threshold=args.threshold,
        nlp=detector.nlp,
    )

    for wikidata_id, title in tqdm(authors):
        page_hash = string_to_hash(title)
        out_path = os.path.join(args.output_dir, f"{page_hash}.json.gz")
        in_path = os.path.join(args.input_dir, f"{page_hash}.txt.gz")
        if has_valid_output(out_path):
            continue
        if not os.path.isfile(in_path):
            log.error("%s %s: page not found (%s)", wikidata_id, title, in_path)
            continue
        try:
            records = process_author(wikidata_id, read_page(in_path), detector, linker)
        except Exception:
            log.error("%s %s: failed", wikidata_id, title)
            traceback.print_exc()
            continue
        write_output(out_path, {"result": records})
        log.info("%s %s: %d event sentences with people", wikidata_id, title, len(records))


if __name__ == "__main__":
    main()
