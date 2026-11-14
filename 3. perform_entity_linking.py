# Run entity linking over the selected author sample.

import csv
import glob
import gzip
import json
import os
import tempfile
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed, ThreadPoolExecutor
import traceback
from src import retrieve_knowledge,wd_knowledge
import pandas as pd
import random, requests
import numpy as np
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from tqdm import tqdm
import logging as log
import mwparserfromhell
import wikipediaapi
from src.retrieve_knowledge import RetrieveSources, OpenInformationExtraction
from src.wd_knowledge import Knowledge
from utils import output_data_path, string_to_hash


def clean_wikitext(wikitext):
    """
    Remove MediaWiki markup from wikitext and return readable text.
    """
    # Parse the wikitext into a structure that can be edited.
    wikicode = mwparserfromhell.parse(wikitext)

    # Remove templates (for example, {{...}}).
    templates = wikicode.filter_templates()
    for template in templates:
        wikicode.remove(template)
    #print(wikicode.filter_wikilinks())
    # Remove internal and external links.
    for link in wikicode.filter_wikilinks():
        try:
            wikicode.remove(link)
        except:
            continue
    for external_link in wikicode.filter_external_links():
        wikicode.remove(external_link)

    # Remove any remaining markup, including HTML tags.
    cleaned_text = wikicode.strip_code()

    # Return the cleaned text.
    return str(cleaned_text).strip()

log.basicConfig(
    encoding='utf-8',
    level=log.INFO,
    format='%(asctime)s %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p'
)

random.seed(30081993)

class Experiment:
    def __init__(self) -> None:
        self.authors = pd.read_csv('./data/authors_links.csv')

    def batch_data(self, data, batch_size):
        """
        Split the input data into batches of the requested size.
        """
        for i in range(0, len(data), batch_size):
            yield data[i:i + batch_size]


    def process_batch(self, batch):
        """
        Process a single batch of rows.
        """

        log.error(f"Pre OpenInformationExtraction")
        batch_extractor = OpenInformationExtraction()
        log.error(f"Post OpenInformationExtraction")

        processed = []
        for row in batch:
            try:
                result = self._expand_kb(row,batch_extractor)
                if result:
                    processed.append(result)
            except Exception as e:
                log.error(f"Error processing row 1 {row}: {e}")
        return processed
    def launch_experiment(self, sample, batch_size=100, num_core=3):
        """
        Run the experiment on batches using a thread pool.
        """
        log.info("Dividing data into batches.")
        batches = list(self.batch_data(sample, batch_size))
        print("Number of batches",len(batches))

        log.info(f"Processing {len(batches)} batches with {num_core} cores.")

        all_results = []
        with ThreadPoolExecutor(max_workers=num_core) as executor:
            # Submit each batch to the thread pool.
            futures = {executor.submit(self.process_batch, batch): batch for batch in batches}

            # Collect completed batches while displaying progress.
            for future in tqdm(as_completed(futures), total=len(futures)):
                try:
                    batch_result = future.result()
                    #all_results.extend(batch_result)
                except Exception as e:
                    log.error(f"Error processing batch: {e}")

        return all_results




    def _expand_kb(self,row,extractor):
        try:
            entity,link=row

            linked_people = list()
            out_put_filename = output_data_path(f"{string_to_hash(link)}.json.gz")
            os.makedirs(os.path.dirname(out_put_filename), exist_ok=True)
            if os.path.isfile(out_put_filename):
                try:
                    with gzip.open(out_put_filename, "rt", encoding="utf-8") as existing_file:
                        existing_data = json.load(existing_file)
                    if isinstance(existing_data, dict) and isinstance(existing_data.get("result"), list):
                        return
                except (gzip.BadGzipFile, EOFError, OSError, UnicodeDecodeError, json.JSONDecodeError, zlib.error):
                    pass
                log.warning("Regenerating invalid entity-linking output: %s", out_put_filename)
            log.info(f"{entity} {link} in processing")

            file_name=f"output/{string_to_hash(link)}.txt.gz"

            if not os.path.isfile(file_name):
                log.error(f"{entity} {link} Not found")
                return
            file = gzip.open(file_name,"rt")

            page=clean_wikitext(file.read())
            # Limit the input size to keep sentence processing manageable.
            if len(page)>100000:
             page=page[0:100000]
            sentences,tokenized = extractor.tokenize_sentences(page)

            for i,sent in enumerate(sentences):

                mentions = list()
                events = extractor.event_detection(sent)
                try:
                    if len(events)>0:
                        # Link entities only in sentences where an event was detected.
                        people = extractor.entity_linking(tokenized)
                        for person in people:
                            wd = extractor.find_candidates_wiki(person)
                            if wd is not None and wd !=entity:
                                mentions.append(wd)
                    if len(mentions)>0:
                        output = {'author':entity,'sentence':i,'events':events,'mentions':mentions,'n_mentions':len(set(mentions))}

                        linked_people.append(output)

                except:
                    traceback.print_exc()
                    continue
            #print(linked_people)
            data={ "result" : linked_people}
            # Save the extracted event and entity-linking results as compressed JSON.
            with tempfile.NamedTemporaryFile(dir=os.path.dirname(out_put_filename), delete=False) as temporary_file:
                temporary_path = temporary_file.name
            try:
                with gzip.open(temporary_path, "wt", encoding="utf-8") as output_file:
                    json.dump(data, output_file, indent=4)
                os.replace(temporary_path, out_put_filename)
            finally:
                if os.path.exists(temporary_path):
                    os.unlink(temporary_path)
            # Continue with any additional processing here.
        except Exception as e:
            log.error(f"Error processing row 2 {row}: {e}")
            traceback.print_exc()

        return




if __name__ == "__main__":

    exp = Experiment()

    l = list()
    titles = []
    file=open("data/authors_links.csv")
    log.info("Reading authors")
    reader= csv.DictReader(file, delimiter=",", quotechar="\"")
    for row in reader:
        titles.append([row["label"],row["sitelink"]])
    log.info("Start experiment")
    expanded = exp.launch_experiment(titles, batch_size=100, num_core=1)
    print(expanded)

