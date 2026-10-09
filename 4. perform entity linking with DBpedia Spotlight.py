import csv
import gzip
import json
import logging as log
import os
import random
import re
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import mwparserfromhell
import pandas as pd
import spacy
import spacy_dbpedia_spotlight  # noqa: F401
import torch
from tqdm import tqdm

from src.model import Bert4EventExtraction
from src.retrieve_knowledge import OpenInformationExtraction
from utils import string_to_hash


# ============================================================
# CONFIGURATION
# ============================================================

SPACY_MODEL = "en_core_web_sm"
EVENT_MODEL = "distilbert-base-uncased"

# DBpedia Spotlight runs locally in Docker:
# http://localhost:2222/rest/
DBPEDIA_ENDPOINT = "http://localhost:2222/rest"

DBPEDIA_CONFIDENCE = 0.35

EVENT_MODEL_PATH = "event_detection_model.pth"

PEOPLE_PARQUET = "data/all_people.parquet"
PEOPLE_JSON = "data/all_people.json"

AUTHORS_CSV = "data/authors_links.csv"

INPUT_DIR = "output"
OUTPUT_DIR = "data/output_data_dbpedia"

MAX_PAGE_LENGTH = 100000

BATCH_SIZE = 100
NUM_CORES = 2

ANNOTATED_SAMPLE_PATH = "data/annotated_entity_linking_sample.json"
ANNOTATED_TASK_INDEX = 0
ANNOTATED_RESULTS_PATH = "data/output_data_dbpedia/task_1_evaluation.json"


# ============================================================
# LOGGING
# ============================================================

log.basicConfig(
    encoding="utf-8",
    level=log.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)

random.seed(30081993)


# ============================================================
# DBPEDIA/WIKIDATA/SCHEMA TYPES THAT IDENTIFY A PERSON
# ============================================================

# Accept person types returned by DBpedia, Schema.org, or Wikidata.
PERSON_TYPES = (
    "DBpedia:Person",
    "Schema:Person",
    "Wikidata:Q5",
)


# ============================================================
# DBPEDIA SPOTLIGHT + OPEN INFORMATION EXTRACTION
# ============================================================

class OpenInformationExtractionDBpedia(OpenInformationExtraction):
    """
    OpenInformationExtraction variant that uses DBpedia Spotlight
    instead of spaCy NER to detect and link person mentions.
    """

    def __init__(
        self,
        sent_tokenizer=SPACY_MODEL,
        ev_model=EVENT_MODEL,
        confidence=DBPEDIA_CONFIDENCE,
        dbpedia_endpoint=DBPEDIA_ENDPOINT,
    ):
        log.info("Loading spaCy model: %s", sent_tokenizer)

        # Skip the parent initializer to avoid loading spaCy twice.
        self.nlp = spacy.load(sent_tokenizer)

        log.info(
            "Adding DBpedia Spotlight component. Endpoint: %s",
            dbpedia_endpoint,
        )

        self.nlp.add_pipe(
            "dbpedia_spotlight",
            config={
                "confidence": confidence,
                "dbpedia_rest_endpoint": dbpedia_endpoint,
            },
        )

        log.info("Loading event extraction model: %s", ev_model)

        self.ev_model = Bert4EventExtraction(ev_model, 2)

        self.ev_model.load_state_dict(
            torch.load(
                EVENT_MODEL_PATH,
                map_location=torch.device("cpu"),
            )
        )

        self.ev_model.eval()

        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(ev_model)

        # --------------------------------------------------------
        # Load the people lookup table
        # --------------------------------------------------------

        if not os.path.isfile(PEOPLE_JSON):
            log.info(
                "%s not found. Creating it from %s",
                PEOPLE_JSON,
                PEOPLE_PARQUET,
            )

            people = pd.read_parquet(PEOPLE_PARQUET)

            # Map each person's name to its Wikidata ID for fast lookups.
            self.people_name_to_id = {
                row["o"]: row["s"]
                for _, row in people.iterrows()
            }

            os.makedirs(
                os.path.dirname(PEOPLE_JSON),
                exist_ok=True,
            )

            with open(
                PEOPLE_JSON,
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    self.people_name_to_id,
                    f,
                    ensure_ascii=False,
                )

        else:
            log.info("Loading people mapping from %s", PEOPLE_JSON)

            with open(
                PEOPLE_JSON,
                "r",
                encoding="utf-8",
            ) as f:
                self.people_name_to_id = json.load(f)

        log.info(
            "Loaded %d people mappings",
            len(self.people_name_to_id),
        )

    # ------------------------------------------------------------
    # Entity linking
    # ------------------------------------------------------------

    def entity_linking(self, sentence):
        """
        Extract person mentions recognized by DBpedia Spotlight
        from a sentence.

        Return:

            [
                {
                    "text": "...",
                    "uri": "http://dbpedia.org/resource/..."
                }
            ]
        """

        mentions = []

        for ent in sentence.ents:
            raw = ent._.dbpedia_raw_result or {}

            types = raw.get("@types", "")

            if any(
                person_type in types
                for person_type in PERSON_TYPES
            ):
                mentions.append(
                    {
                        "text": ent.text,
                        "uri": ent.kb_id_,
                    }
                )

        return mentions

    # ------------------------------------------------------------
    # Mapping DBpedia -> Wikidata
    # ------------------------------------------------------------

    def find_candidates_wiki(
        self,
        mention,
        limit=1,
        language="en",
    ):
        """
        Resolve a DBpedia mention to a Wikidata ID using the
        pipeline's existing name-to-ID lookup table.

        First, try the mention text.

        If that fails, try the DBpedia resource name.
        """

        text = mention["text"].strip()

        # First, look up the mention text as written.
        wd = self.people_name_to_id.get(text)

        if wd is not None:
            return wd

        # If needed, look up the DBpedia resource name.
        if mention.get("uri"):
            resource_name = (
                mention["uri"]
                .rsplit("/", 1)[-1]
                .replace("_", " ")
                .strip()
            )

            wd = self.people_name_to_id.get(resource_name)

            if wd is not None:
                return wd

        return None


ANNOTATED_TEXT_PATTERN = re.compile(
    r"^AUTHOR:\s*(.*?)\s+EVENT\s+(.*?)\s+SENTENCE:\s*(.*?)\s+MENTION:\s*(.*)$",
    re.DOTALL,
)


def parse_annotated_text(text):
    match = ANNOTATED_TEXT_PATTERN.match(text)
    if match is None:
        raise ValueError("Text does not match the annotated task format")

    author, event, sentence, mentions = match.groups()
    return {
        "author": author.strip(),
        "sentence": sentence.strip(),
        "expected_events": [event.strip()] if event.strip() else [],
        "expected_mentions": [
            mention.strip()
            for mention in mentions.split(";")
            if mention.strip()
        ],
    }


def compare_labels(expected, predicted):
    expected_counts = Counter(" ".join(value.casefold().split()) for value in expected)
    predicted_counts = Counter(" ".join(value.casefold().split()) for value in predicted)
    matched = expected_counts & predicted_counts

    return {
        "matched": list(matched.elements()),
        "false_positives": list((predicted_counts - expected_counts).elements()),
        "missed": list((expected_counts - predicted_counts).elements()),
    }


def evaluate_annotated_task(task, extractor):
    totals = {
        "events": Counter(),
        "mentions": Counter(),
    }
    results = []
    evaluated_records = 0

    for line in tqdm(task["lines"], desc="Evaluating annotated task"):
        parsed = parse_annotated_text(line["data"]["text"])

        try:
            sentence_tokens, document = extractor.tokenize_sentences(
                parsed["sentence"]
            )
            sentence_spans = list(document.sents)
            if len(sentence_tokens) != len(sentence_spans):
                raise ValueError("Sentence tokenization results are misaligned")

            predicted_events = []
            predicted_mentions = []
            for tokens, span in zip(sentence_tokens, sentence_spans):
                predicted_events.extend(extractor.event_detection(tokens))
                predicted_mentions.extend(
                    mention["text"]
                    for mention in extractor.entity_linking(span)
                )

            expected = {
                "events": parsed["expected_events"],
                "mentions": parsed["expected_mentions"],
            }
            predicted = {
                "events": predicted_events,
                "mentions": predicted_mentions,
            }
            comparisons = {
                label_type: compare_labels(expected[label_type], predicted[label_type])
                for label_type in totals
            }

            for label_type, comparison in comparisons.items():
                totals[label_type]["tp"] += len(comparison["matched"])
                totals[label_type]["fp"] += len(comparison["false_positives"])
                totals[label_type]["fn"] += len(comparison["missed"])

            evaluated_records += 1
            results.append(
                {
                    "text_id": line.get("text_id"),
                    "author": parsed["author"],
                    "sentence": parsed["sentence"],
                    "expected": expected,
                    "predicted": predicted,
                    "comparison": comparisons,
                }
            )
        except Exception as error:
            log.exception("Failed to process annotated text %s", line.get("text_id"))
            results.append(
                {
                    "text_id": line.get("text_id"),
                    "author": parsed["author"],
                    "sentence": parsed["sentence"],
                    "expected": {
                        "events": parsed["expected_events"],
                        "mentions": parsed["expected_mentions"],
                    },
                    "error": str(error),
                }
            )

    summary = {}
    for label_type, counts in totals.items():
        true_positives = counts["tp"]
        false_positives = counts["fp"]
        false_negatives = counts["fn"]
        precision = (
            true_positives / (true_positives + false_positives)
            if true_positives + false_positives
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if true_positives + false_negatives
            else 0.0
        )
        summary[label_type] = {
            "tp": true_positives,
            "fp": false_positives,
            "fn": false_negatives,
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0,
        }

    return {
        "task_id": task.get("id"),
        "total_records": len(task["lines"]),
        "evaluated_records": evaluated_records,
        "summary": summary,
        "results": results,
    }


# ============================================================
# EXPERIMENT
# ============================================================

class Experiment:

    def __init__(self) -> None:
        self.authors = pd.read_csv(AUTHORS_CSV)

    # ------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------

    def batch_data(self, data, batch_size):
        for i in range(0, len(data), batch_size):
            yield data[i:i + batch_size]

    # ------------------------------------------------------------
    # Process batch
    # ------------------------------------------------------------

    def process_batch(self, batch):
        log.info(
            "Starting batch with %d rows",
            len(batch),
        )

        log.info(
            "Creating OpenInformationExtractionDBpedia"
        )

        batch_extractor = OpenInformationExtractionDBpedia()

        log.info(
            "OpenInformationExtractionDBpedia ready"
        )

        processed = []

        for row in batch:
            try:
                result = self._expand_kb(
                    row,
                    batch_extractor,
                )

                if result:
                    processed.append(result)

            except Exception as e:
                log.error(
                    "Error processing row %s: %s",
                    row,
                    e,
                )

                traceback.print_exc()

        log.info(
            "Batch completed. Results: %d",
            len(processed),
        )

        return processed

    # ------------------------------------------------------------
    # Launch experiment
    # ------------------------------------------------------------

    def launch_experiment(
        self,
        sample,
        batch_size=BATCH_SIZE,
        num_core=NUM_CORES,
    ):
        """
        Run the experiment using ThreadPoolExecutor and batching.

        DBpedia Spotlight runs locally in Docker, so multiple threads
        can be used. Keeping num_core relatively low is still recommended.
        """

        log.info("Dividing data into batches.")

        batches = list(
            self.batch_data(
                sample,
                batch_size,
            )
        )

        print(
            "Number of batches:",
            len(batches),
        )

        log.info(
            "Processing %d batches with %d workers.",
            len(batches),
            num_core,
        )

        all_results = []

        with ThreadPoolExecutor(
            max_workers=num_core
        ) as executor:

            futures = {
                executor.submit(
                    self.process_batch,
                    batch,
                ): batch
                for batch in batches
            }

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
            ):

                batch = futures[future]

                try:
                    result = future.result()

                    if result:
                        all_results.extend(result)

                except Exception as e:
                    log.error(
                        "Error processing batch %s: %s",
                        batch,
                        e,
                    )

        log.info(
            "Experiment completed. Total in-memory results: %d",
            len(all_results),
        )

        return all_results

    # ------------------------------------------------------------
    # Expand KB
    # ------------------------------------------------------------

    def _expand_kb(
        self,
        row,
        extractor,
    ):

        try:

            entity, link = row

            linked_people = []

            # ----------------------------------------------------
            # Output filename
            # ----------------------------------------------------

            output_filename = os.path.join(
                OUTPUT_DIR,
                f"{string_to_hash(link)}.json.gz",
            )

            # Skip rows whose output file already exists.
            if os.path.isfile(output_filename):
                log.info(
                    "%s already processed. Skipping.",
                    link,
                )
                return None

            log.info(
                "%s %s in processing",
                entity,
                link,
            )

            # ----------------------------------------------------
            # Input filename
            # ----------------------------------------------------

            file_name = os.path.join(
                INPUT_DIR,
                f"{string_to_hash(link)}.txt.gz",
            )

            if not os.path.isfile(file_name):
                log.error(
                    "%s %s Not found: %s",
                    entity,
                    link,
                    file_name,
                )
                return None

            # ----------------------------------------------------
            # Read gzip input
            # ----------------------------------------------------

            with gzip.open(
                file_name,
                "rt",
                encoding="utf-8",
            ) as file:

                page = clean_wikitext(
                    file.read()
                )

            # Limit the page length to keep processing manageable.
            if len(page) > MAX_PAGE_LENGTH:
                page = page[:MAX_PAGE_LENGTH]

            if not page.strip():
                log.warning(
                    "%s %s contains no text after cleaning",
                    entity,
                    link,
                )
                return None

            # ----------------------------------------------------
            # Sentence tokenization
            # ----------------------------------------------------

            sentences, tokenized = (
                extractor.tokenize_sentences(page)
            )

            log.info(
                "%s: %d sentences",
                entity,
                len(sentences),
            )

            # ----------------------------------------------------
            # Process sentences
            # ----------------------------------------------------

            for i, sent in enumerate(sentences):

                try:

                    mentions = []

                    # Event detection
                    events = extractor.event_detection(sent)

                    # Skip sentences that contain no detected events.
                    if len(events) == 0:
                        continue

                    # ------------------------------------------------
                    # DBpedia Spotlight
                    # ------------------------------------------------

                    people = extractor.entity_linking(
                        tokenized[i]
                    )

                    for person in people:

                        wd = extractor.find_candidates_wiki(
                            person
                        )

                        if wd is not None and wd != entity:
                            mentions.append(wd)

                    # ------------------------------------------------
                    # Save sentence result
                    # ------------------------------------------------

                    if len(mentions) > 0:

                        output = {
                            "author": entity,
                            "event_sentences": i,
                            "events": events,
                            "mentions": mentions,
                            "n_mentions": len(
                                set(mentions)
                            ),
                        }

                        linked_people.append(output)

                except Exception as e:

                    log.error(
                        "Error processing sentence %d of %s: %s",
                        i,
                        link,
                        e,
                    )

                    traceback.print_exc()

                    continue

            # ----------------------------------------------------
            # Save result
            # ----------------------------------------------------

            os.makedirs(
                OUTPUT_DIR,
                exist_ok=True,
            )

            data = {
                "result": linked_people
            }

            with gzip.open(
                output_filename,
                "wt",
                encoding="utf-8",
            ) as output_file:

                json.dump(
                    data,
                    output_file,
                    indent=4,
                    ensure_ascii=False,
                )

            log.info(
                "%s completed. Found %d event sentences with people.",
                link,
                len(linked_people),
            )

            return data

        except Exception as e:

            log.error(
                "Error processing row %s: %s",
                row,
                e,
            )

            traceback.print_exc()

            return None


# ============================================================
# WIKITEXT CLEANING
# ============================================================

def clean_wikitext(wikitext):
    """
    Remove MediaWiki templates from wikitext
    and return readable text.
    """

    wikicode = mwparserfromhell.parse(
        wikitext
    )

    # Remove templates.
    templates = wikicode.filter_templates()

    for template in templates:
        wikicode.remove(template)

    # Remove the remaining markup.
    cleaned_text = wikicode.strip_code()

    return str(cleaned_text).strip()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    with open(ANNOTATED_SAMPLE_PATH, "r", encoding="utf-8") as file:
        annotated_data = json.load(file)

    annotated_task = annotated_data["tasks"][ANNOTATED_TASK_INDEX]["task"]
    log.info(
        "Evaluating task %s with %d annotated texts",
        annotated_task.get("id"),
        len(annotated_task["lines"]),
    )

    extractor = OpenInformationExtractionDBpedia()
    evaluation = evaluate_annotated_task(annotated_task, extractor)

    os.makedirs(os.path.dirname(ANNOTATED_RESULTS_PATH), exist_ok=True)
    with open(ANNOTATED_RESULTS_PATH, "w", encoding="utf-8") as file:
        json.dump(evaluation, file, indent=2, ensure_ascii=False)

    print(json.dumps(evaluation["summary"], indent=2))
    log.info("Detailed results saved to %s", ANNOTATED_RESULTS_PATH)
