# reducing-underrepresentation
experiments related to the reduction of underrepresentation

## Prepare the repo

* Copy the file [authors_links.csv](https://drive.google.com/file/d/1EsZmlv4yTUll5E7E-EJpKJzYKCKUNQ99/view?usp=drive_link) in the folder data/
* Copy the file [all_people.parquet](https://drive.google.com/file/d/1JDN7ygIEju50ozvFTC7c52Gh27NDrOg4/view?usp=drive_link) in the folder data/
* Copy the [biographical event detection model](https://drive.google.com/file/d/1KWGphIp7HV39RWmGxp7_KuMxNhX-TSTi/view?usp=drive_link) in the root directory as `event_detection_model.pth`

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

## Experiment

if you run python main.py, you will start an experiment that works as follows:

1. it takes a sample of 50 Transnational writers and 50 Western writers;
2. it counts how many relations with other people these authors have on Wikidata;
3. it gets the English Wikipedia page of each writer and extracts all the relations with others people from raw text through an Open Information Extraction approach;
4. it counts how many relations with other people these authors have **after the extraction**

## Results

I will put a beautiful table and some images here

## Transnational classification ablation

Run `.venv/bin/python "18. ablation_test.py"` (or use another Python with
the requirements installed). The script joins `data/authors_links.csv` and
`data/entity_cob_new.csv` by `entity`, and evaluates the gold
`authors_links.transnational` against:

```
T = (FormerColony OR minority) AND (HDI OR passport mobility)
```

HDI is true for `HDI_category` Medium or Low; passport mobility is true for
`passport_bin` Q3 or Q4. These are the specified categorical definitions, not
an average recomputed over authors. In this dataset High HDI values can also
be below 0.8, so the category definition is **not** identical to the numerical
test `HDI_value < 0.8`.

The full formula and four leave-one-out ablations use the same author-level
cohort. Each ablation removes one term from its OR group (sets that term to
false), leaving the other terms and AND unchanged. Accuracy, precision,
recall, F1 and Cohen's kappa compare predictions with gold; delta columns
compare each metric with the full formula. `changed_vs_full` counts prediction
changes, not changes relative to gold. This measures association with the
given gold labels, not causal importance.

Duplicate identical records count once per entity. Authors without a match,
with any missing gold or required criterion, or with conflicting gold labels
or differing values of any of the four criteria across their records, are
excluded. Comparisons use the raw HDI and passport categories, not just the
resulting booleans. Exclusion counts can overlap; `excluded_total` counts
distinct excluded authors. Missing or unknown values are never silently
classified as false. Undefined metrics are left blank in the CSV.

The script writes `cohort_counts.csv`, `author_audit.csv`,
`author_classifications.csv`, and `ablation_summary.csv` under
`data/ablation_formula/`, leaving the older `data/ablation/` results untouched.
The audit includes flags for each exclusion reason and allows mismatches to be
examined per author. Use `--authors`, `--entities`, and `--output-dir` to
override the default paths.

### Explain excluded authors

Run `.venv/bin/python "19. explain_ablation_exclusions.py"` to recompute the
same exclusion rules directly from the input CSVs. The default output directory
is `data/ablation_exclusions/`; `--authors`, `--entities`, and `--output-dir`
override the paths.

`excluded_authors.csv` has one row per excluded entity, with all applicable
reasons, per-field missing/conflicting flags, a Wikidata link, and distinct
values as JSON lists. An empty string inside a list is a missing source value.
For an unmatched author, criterion value cells are empty because no source
record exists; the criterion-level missing flags do not count unmatched
authors. A blank and a non-blank value in separate rows count as both missing
and conflicting, consistent with the ablation script. Binary 0.0/1.0 values are
normalized to 0/1 when comparing values.

Each reason also has its own CSV, so the same author can appear in multiple
files. `exclusion_counts.csv` counts authors by reason and by field;
`reason_combinations.csv` counts mutually exclusive combinations of reasons.
`authors_source_rows.csv` and `entities_source_rows.csv` retain the original
values for all excluded authors, without joining the rows together.
`source_record` is the 1-based data record number in the respective input file,
excluding the header; it is not necessarily a physical line number.

## References

tbd
