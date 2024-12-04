import csv
import glob
import gzip
import json
import os.path
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
from utils import string_to_hash


def clean_wikitext(wikitext):
    """
    Pulisce il wikitext dai tag di MediaWiki e restituisce solo il testo leggibile.
    """
    # Converte il wikitext in un oggetto parsabile
    wikicode = mwparserfromhell.parse(wikitext)

    # Rimuove i template (es: {{...}})
    templates = wikicode.filter_templates()
    for template in templates:
        wikicode.remove(template)
    #print(wikicode.filter_wikilinks())
    # Rimuove i link interni ed esterni, mantenendo solo il testo
    for link in wikicode.filter_wikilinks():
        try:
            wikicode.remove(link)
        except:
            continue
    for external_link in wikicode.filter_external_links():
        wikicode.remove(external_link)

    # Rimuove eventuali tag HTML
    cleaned_text = wikicode.strip_code()

    # Restituisce il testo pulito
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
        Divide i dati in batch.
        """
        for i in range(0, len(data), batch_size):
            yield data[i:i + batch_size]


    def process_batch(self, batch):
        """
        Elabora un singolo batch di righe.
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
    def launch_experiment(self, sample, batch_size=500, num_core=3):
        """
        Lancia l'esperimento utilizzando ProcessPoolExecutor e batching.
        """
        log.info("Dividing data into batches.")
        batches = list(self.batch_data(sample, batch_size))
        print("Number of batches",len(batches))

        log.info(f"Processing {len(batches)} batches with {num_core} cores.")

        all_results = []
        with ThreadPoolExecutor(max_workers=num_core) as executor:
            # Invia i batch al pool di processi
            futures = {executor.submit(self.process_batch, batch): batch for batch in batches}

            # Elaborazione con barra di avanzamento
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
            log.info(f"{entity} {link} in processing")

            linked_people = list()
            out_put_filename=f"output_data/{string_to_hash(link)}.json.gz"
            if os.path.isfile(out_put_filename):
                log.info(f"{entity} {link} Already done")

                return

            file_name=f"output/{string_to_hash(link)}.txt.gz"

            if not os.path.isfile(file_name):
                log.error(f"{entity} {link} Not found")
                return
            file = gzip.open(file_name,"rt")

            page=clean_wikitext(file.read())
            if len(page)>100000:
             page=page[0:100000]
            sentences,tokenized = extractor.tokenize_sentences(page)

            for i,sent in enumerate(sentences):

                mentions = list()
                events = extractor.event_detection(sent)
                try:
                    if len(events)>0:
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
            json.dump(data,gzip.open(out_put_filename,"wt"),indent=4)
            # Resto del codice
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
    expanded = exp.launch_experiment(titles,num_core=5)
    print(expanded)




