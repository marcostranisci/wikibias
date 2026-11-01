"""Sample event sentences for manual checking (from "15. estrai campione frasi.py")."""

import random
from collections import Counter
from typing import Callable, Iterable

from .build import mention_ids


def sample_event_sentences(
    records: Iterable[dict],
    event_counts: Counter,
    labels: dict[str, str],
    n_events: int = 100,
    per_event: int = 10,
    get_sentence: Callable[[dict], str | None] | None = None,
    seed: int | None = None,
) -> list[dict]:
    """For the ``n_events`` most frequent events, sample up to ``per_event``
    pipeline records that contain the event.

    :param records: pipeline results (see ``build.load_records``).
    :param event_counts: event frequencies (e.g. ``analysis.edge_event_counts``).
    :param labels: Wikidata ID -> label, used for authors and mentions.
    :param get_sentence: returns the sentence text of a record; by default the
        record's ``sentence`` field. Pass a function to rebuild it from the
        page for older results that only store the sentence index.
    """
    rng = random.Random(seed)
    get_sentence = get_sentence or (lambda record: record.get("sentence"))
    records = list(records)

    rows = []
    for event, _ in event_counts.most_common(n_events):
        matching = [r for r in records if event in r.get("events", [])]
        for record in rng.sample(matching, min(per_event, len(matching))):
            sentence = get_sentence(record)
            if not sentence:
                continue
            rows.append({
                "event": event,
                "author id": record["author"],
                "author label": labels.get(record["author"]),
                "sentence": sentence,
                "references": ",".join(f"{m} : {labels.get(m)}" for m in mention_ids(record)),
            })
    return rows
