# wikibias

People networks extracted from Wikipedia biographies (augmented KG), the
evaluation of mention extraction, and Jensen-Shannon divergence of biographical
events between author groups.

## Prepare the repo

* Copy the file [authors_links.csv](https://drive.google.com/file/d/1EsZmlv4yTUll5E7E-EJpKJzYKCKUNQ99/view?usp=drive_link) in the folder data/
* Copy the [biographical event detection model](https://drive.google.com/file/d/1zrOCqFg_EhsHWkzRsxNZYKntEAMJLEuK/view?usp=sharing) in the root directory as `event_detection_model.pth`

## Augment the KG and analyse the network

`augment_kg.py` runs everything in one go: event detection, entity linking,
Wikidata relations, augmented KG and network analysis.

```bash
export WIKIMEDIA_CONTACT="your.email@example.org"
python augment_kg.py --authors data/authors.csv --biographies output/ \
    --model event_detection_model.pth --output-dir results/
```

* `--authors`: CSV with the author's Wikidata ID, origin and gender (columns
  `entity`, `origin`, `gender` by default; change them with `--id-column`,
  `--origin-column`, `--gender-column`). An optional `label` column gives names.
* `--biographies`: a folder with `<QID>.txt` / `<QID>.txt.gz` files (or the
  `output/` folder of steps 1-2 if the authors CSV has a `sitelink` column),
  or a `.jsonl`/`.json`/`.csv` file with `entity` and `text` fields.
* `--existing-kb`: optional `s,p,o` CSV of Wikidata relations; otherwise they
  are fetched from Wikidata.

Outputs in `--output-dir`:

* `kg/`: `base_triples.csv` (Wikidata), `extracted_triples.csv` (from text,
  with sentence and linking details), `augmented_triples.csv` (both, with a
  `source` column), and the three networks as GraphML.
* `analysis/authors.csv`: per author, people linked on Wikidata, in the text,
  in the augmented KG, and how many the text adds.
* `analysis/<base|extended|augmented>/`: `summary.json` (size, giant
  component, attribute distributions), `rankings.csv` (top nodes by in-degree,
  PageRank, closeness, betweenness, overall and per origin/gender group),
  `densities.csv` (intra/inter-group density among writers), `edge_events.csv`,
  and `path_events.csv` with `--path-events`.
* `extraction/`: per-author extraction, reused when the script is run again.

Run `python augment_kg.py --help` for all options.

## Code structure

The `wikibias` package has one module per step. Modules do not import each
other (they only share `wikibias/wikimedia.py`, a small Wikipedia/Wikidata API
client, and `wikibias/text.py`), so each step can be used, tested or replaced
on its own. The first three modules have an abstract class (the interface) and
one implementation.

| Module | Abstract class | Implementation |
| --- | --- | --- |
| `wikibias.event_detection` | `BiographicalEventDetector.detect(wikidata_id, wikipedia_page) -> list[BiographicalEvent]` | `BertEventDetector`: spaCy sentence splitting + fine-tuned BERT token classifier (`.pt` weights) |
| `wikibias.candidate_extraction` | `CandidateExtractor.extract(mention) -> list[Candidate]` | `WikipediaSearchCandidateExtractor`: top-3 Wikipedia search results, linked to Wikidata, only humans (Q5) |
| `wikibias.entity_linking` | `EntityLinker.link(sentence) -> list[LinkedEntity]` | `HeuristicEntityLinker`: spaCy PERSON entities linked with the heuristics below |
| `wikibias.network` | - | functions to build the base/extended/joint networks and analyse them |

Entity linking heuristics (`HeuristicEntityLinker`):

1. a one-word mention that is also a given name on Wikidata (e.g. *Adele*) is dropped;
2. the candidate whose Wikidata label has gestalt similarity >= 0.8 with the mention is linked;
3. a surname-only mention (e.g. *Orwell* in the page of Orwell's wife) is linked to the best-ranked candidate with that surname (*George Orwell*).

Network module (`wikibias.network`):

* `wikidata_relations.WikidataRelations` - person-to-person relations on Wikidata (`existing_kb.csv`)
* `build` - `NodeAttributes`, `build_base_network`, `build_extended_network`, `compose_networks`, `load_records`
* `analysis` - `attribute_distribution`, `giant_component`, `ranking` (in-degree, PageRank, closeness, betweenness), `top_nodes`, `intra_group_density`, `inter_group_density`, `group_densities`, `shortest_path_edges`, `edge_event_counts`
* `sampling` - `sample_event_sentences`

Example:

```python
from wikibias.event_detection import BertEventDetector
from wikibias.candidate_extraction import WikipediaSearchCandidateExtractor
from wikibias.entity_linking import HeuristicEntityLinker

detector = BertEventDetector(model_path="event_detection_model.pth")
linker = HeuristicEntityLinker(WikipediaSearchCandidateExtractor(top_k=3))

events = detector.detect("Q271625", page_text)
for event in events:
    print(event.trigger, linker.link(event.sentence))
```

Wikipedia/Wikidata calls go through `wikibias/wikimedia.py`, which sends the User-Agent headers Wikimedia requires and retries when rate-limited. Put your contact in it:

```bash
export WIKIMEDIA_CONTACT="your.email@example.org"
```

Tests (no model or network access needed): `python -m unittest discover -s tests -t .`

## Evaluation of mention extraction

Manual annotations, in `data/evaluation/`. The systems compared are
S1 = names in the `MENTIONS:`/`MENTION:` field, S2 = ReLiK entity linking,
S3 = DBpedia Spotlight (its predictions are in
`data/output_data_dbpedia/task_1_evaluation.json`).

`annotations.csv`: one row per annotation, from two annotation rounds
(`dataset`): `mirko_marco` (400 texts) and `rossana` (334 texts, the same
texts as `data/annotated_entity_linking_sample.json`).

* `annotator`: Marco, Mirko or Rossana; `task_id`, `text_id`.
* `text` and, parsed from it, `author`, `event`, `sentence`,
  `extracted_mentions` (S1 output, separated by ` | `).
* `annotation_type`:
  * `correct`: `value` is `yes`/`no` (is the extracted knowledge correct?);
  * `mention` / `event`: a highlighted span (`span_text`, `span_start`,
    `span_end`; offsets refer to the annotation tool's text);
  * `comment`: a comment (`value`, e.g. `manca` = missing) on a span;
  * empty: the line has no annotation by that annotator.

Marco's `mention` spans in `mirko_marco` are the gold mentions. In `rossana`,
Mirko annotated nothing and Marco only 61 lines.

`disagreement_sample_majority.csv`: 200 sentences where S1, S2 and S3
disagree, judged by Marco, Rossana and Mirko. `best_<annotator>` is the
system(s) whose output is best (`1`, `2`, `3`, combinations such as `2,3`, or
`none`); `best_majority` is the majority vote. `system_2` holds the linked
Wikipedia titles, not the text spans.

## Jensen-Shannon divergence of events between author groups

`python jsd_groups.py` compares the event distributions of transnational/Western
women/men (all six pairs, plus women vs men and transnational vs Western), with
author-level permutation tests and per-event contributions (BH-corrected).

* Input: `data/expanded_events.parquet` (columns `s` author, `p` event,
  `o` object, `post_colonial`, `P21` gender), converted from
  `expanded_events.csv`. Events such as `NA` or `null` are strings, not missing.
* Output: `data/jsd_significance/overall.csv` and `events_<A>_<B>.csv`.
  `top10_per_group.csv` and `table_jsd.tex` were derived from these for the paper.

10,000 permutations per comparison: this takes a while.

## References

tbd
