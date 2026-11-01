# reducing-underrepresentation
experiments related to the reduction of underrepresentation

## Prepare the repo

* Copy the file [authors_links.csv](https://drive.google.com/file/d/1EsZmlv4yTUll5E7E-EJpKJzYKCKUNQ99/view?usp=drive_link) in the folder data/
* Copy the file [all_people.parquet](https://drive.google.com/file/d/1JDN7ygIEju50ozvFTC7c52Gh27NDrOg4/view?usp=drive_link) in the folder data/
* Copy the [biographical event detection model](https://drive.google.com/file/d/1KWGphIp7HV39RWmGxp7_KuMxNhX-TSTi/view?usp=drive_link) in the root directory as `event_detection_model.pth`

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

## References

tbd
