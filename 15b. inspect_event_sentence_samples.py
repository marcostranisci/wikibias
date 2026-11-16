# Inspect a random sample of event sentences.

import glob
import gzip
import json
import random
import mwparserfromhell
import spacy
import csv
import os
from utils import output_data_path

authors_label={}
csv_reader=csv.DictReader(open("data/authors_links.csv"))
for row in csv_reader:

    authors_label[row["entity"]]=row["label"]


def clean_wikitext(wikitext):
    """
    Remove MediaWiki markup from wikitext and return only the readable text.
    """
    # Parse wikitext into an editable structure.
    wikicode = mwparserfromhell.parse(wikitext)

    # Remove templates (for example, {{...}}).
    templates = wikicode.filter_templates()
    for template in templates:
        wikicode.remove(template)
    #print(wikicode.filter_wikilinks())
    # Remove internal and external links, keeping only their text.
    #for link in wikicode.filter_wikilinks():

    #    try:
    #        wikicode.remove(link)
    #    except:
    #        continue
    #for external_link in wikicode.filter_external_links():
    #    wikicode.remove(external_link)

    # Remove any remaining HTML tags.
    cleaned_text = wikicode.strip_code()

    # Return the cleaned text.
    return str(cleaned_text).strip()


num_file=250
file_list=glob.glob("output/*.txt.gz")
#print(len(file_list))
random_sample=random.sample(range(len(file_list)), num_file)
sent_tokenizer = 'en_core_web_sm'
nlp = spacy.load(sent_tokenizer)
for random_author in random_sample:


    file = gzip.open(file_list[random_author], "rt")

    page_text = clean_wikitext(file.read())
    print(page_text)
    if len(page_text) > 100000:
        page_text = page_text[0:100000]
    tokenized = nlp(page_text)

    text_sentences = [[x.text for x in sent] for sent in tokenized.sents]

    json_filename = os.path.basename(file_list[random_author]).replace(".txt.gz", ".json.gz")
    file = gzip.open(output_data_path(json_filename), "rt")
    json_text = json.loads(clean_wikitext(file.read()))
    event_sentence_ids=[x["event_sentences"] for x in json_text["result"]]
    event_sentences=[x for x in json_text["result"]]
    random_event_sentence = random.sample(range(len(event_sentence_ids)), 1)[0]

    text_sentence = ' '.join(text_sentences[event_sentence_ids[random_event_sentence]])
    event_sentence = event_sentences[random_event_sentence]
    print(text_sentence)
    print(event_sentence)
    for mention in event_sentence["mentions"]:
        print(mention,authors_label[mention] if mention  in authors_label else None)
    exit()