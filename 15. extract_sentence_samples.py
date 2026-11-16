# Extract a sample of sentences containing events.

from utils import network_graph_path, read_network_graphml
from utils import output_data_path

import networkx as nx
from collections import Counter
from networkx.algorithms.community import modularity
import igraph as ig
import pandas as pd
import time
import glob
import gzip
import json
import random
import os
#import mwparserfromhell
import spacy
import csv

file_path = "data/to_be_removed.csv"  # CSV file.
to_be_remove={}
with open(file_path, mode='r', encoding='utf-8') as csv_file:
    reader = csv.DictReader(csv_file)
    for row in reader:
        #print(row)
        to_be_remove[row["entity"]]=0

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



# Assume G is the loaded graph with attributes.
graphml_path = network_graph_path("extended_network_graph.graphml.gz")
# Load the graph.
graph = read_network_graphml(graphml_path)
# Filter nodes where writer='1'.
writer_nodes = [n for n, d in graph.nodes(data=True) if d.get('writer') == '1']


event_counts = Counter()

for source,target,edge_data in graph.edges(data=True):

    if edge_data and 'event' in edge_data:
        for event in edge_data['event'].split(","):
         event_counts[event] += 1


# Sort events by frequency.
most_common_events = event_counts.most_common()
total_events = sum(event_counts.values())

# Get the 10 most common events
top_10_events = event_counts.most_common(10)

# Calculate the percentage contribution of the top 10 events
top_10_count = sum(count for _, count in top_10_events)
top_10_percentage = (top_10_count / total_events) * 100

# Output the results
print("Top 10 Events and Their Counts:")
for event, count in top_10_events:
    print(f"{event}: {count}")

print(f"\nTotal Events: {total_events}")
print(f"Top 10 Events Contribution: {top_10_percentage:.2f}%")

exit()

spam_writer = csv.DictWriter(open("sentences.csv","w"),fieldnames=["event","author id","author label", "sentence", "references"])
spam_writer.writeheader()


authors_id=json.load(open("data/all_people.json"))
authors_label = {value: key for key, value in authors_id.items()}
csv_reader=csv.DictReader(open("data/authors_links.csv"))
for row in csv_reader:

    authors_label[row["entity"]]=row["label"]
    authors_id[row["label"]]=row["entity"]
csv_reader=csv.DictReader(open("data/entity_labels.csv"))
for row in csv_reader:

    authors_label[row["entity"]]=row["label"]
    authors_id[row["label"]]=row["entity"]

sent_tokenizer = 'en_core_web_sm'
nlp = spacy.load(sent_tokenizer)
file_list = glob.glob("output/*.txt.gz")

#event, author, sentence, other entities.
sentences=[]

for j,(event,count) in enumerate(list(most_common_events)[0:100]):
    num_file = 10
    while num_file>0:
        print(j, event, num_file)
        random_sample = list(range(0,len(file_list)))
        random.shuffle(random_sample)
        random_author=random_sample[0]
        #print("random_author",random_author,)

        json_filename = os.path.basename(file_list[random_author]).replace(".txt.gz", ".json.gz")
        file_expanded = gzip.open(output_data_path(json_filename), "rt")

        json_expanded = json.load(file_expanded)

        is_event = False
        for result in json_expanded["result"]:
            if event in result["events"]:
                is_event=True
        if not is_event:
            continue
        try:
            file_base = gzip.open(file_list[random_author], "rt")

            page_text = clean_wikitext(file_base.read())
            if len(page_text) > 100000:
                page_text = page_text[0:100000]
            tokenized = nlp(page_text)

            text_sentences = [[x.text for x in sent] for sent in tokenized.sents]
            #for i,sentence in enumerate(text_sentences):
            #    print(i, ' '.join(sentence))

            event_sentence_ids = [x["event_sentences"] for x in json_expanded["result"] if event in x["events"]]
            event_sentences = [x for x in json_expanded["result"] if event in x["events"]]
            random_event_sentence = random.sample(range(len(event_sentence_ids)), 1)[0]
            #print(random_event_sentence,len(event_sentence_ids))
            text_sentence = ' '.join(text_sentences[event_sentence_ids[random_event_sentence]])
            event_sentence = event_sentences[random_event_sentence]
        except:
            continue
        #print(text_sentence)
        #print(event_sentence["author"])
        mentions=[]
        for mention in event_sentence["mentions"]:

            if mention in to_be_remove:
                continue

            if mention in authors_label:
                mentions.append(f"{mention} : {authors_label[mention]} ")
            else:
                mentions.append(f"{mention} : {None}")
        if len(mentions)==0:
            continue

        sentences.append([event,event_sentence["author"], authors_label[event_sentence["author"]], text_sentence, ",".join(mentions)])
        num_file-=1
        print(event_sentence_ids[random_event_sentence],file_expanded, text_sentence, mentions)
        spam_writer.writerow({
                    "event":event,
                    "author id":event_sentence["author"],
                    "author label" : authors_label[event_sentence["author"]],
                    "sentence": text_sentence,
                    "references":",".join(mentions)
                    }
        )
    #print(sentences)
    #exit()
