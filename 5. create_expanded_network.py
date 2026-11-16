# Build the expanded network from extracted entity links.


import pandas as pd
import networkx as nx
import gzip
import os
import json
import csv
import zlib
from utils import output_data_path, write_network_graphml

# File paths.
csv_file_path = "data/authors_links.csv"  # CSV file.
# Load the CSV that maps authors to display names.
authors_df = pd.read_csv(csv_file_path, dtype=str)
writers = authors_df['entity'].tolist()
author_code_to_transnational = dict(zip(authors_df['entity'], authors_df['transnational']))

# File paths.
csv_file_path = "data/writers_gender.csv"  # CSV file.
# Load the CSV that maps authors to display names.
authors_df = pd.read_csv(csv_file_path, dtype=str)
author_code_to_gender = dict(zip(authors_df['s'], authors_df['P21']))

csv_file_path ="data/writers_postcolonial.csv"  # CSV file.
# Load the CSV that maps authors to display names.

authors_df = pd.read_csv(csv_file_path, dtype=str)
author_code_to_country = dict(zip(authors_df['s'], authors_df['CountryIsoCode']))
#print(authorcode_to_country)
author_code_to_former_colony = dict(zip(authors_df['s'], authors_df['FormerColony']))
author_code_to_continent = dict(zip(authors_df['s'], authors_df['Continent']))
author_code_to_minority = dict(zip(authors_df['s'], authors_df['minority']))
author_code_to_postcolonial = dict(zip(authors_df['s'], authors_df['postcolonial']))
author_code_to_birth = dict(zip(authors_df['s'], authors_df['P569']))

entity_data_df = pd.read_csv("data/entity_cob_new.csv", dtype=str)
entity_data_df[["passport_mobility_score", "HDI_value"]] = entity_data_df[
    ["passport_mobility_score", "HDI_value"]
].fillna("N/D")
entity_to_passport_mobility_score = dict(
    zip(entity_data_df['entity'], entity_data_df['passport_mobility_score'])
)
entity_to_hdi_value = dict(zip(entity_data_df['entity'], entity_data_df['HDI_value']))

file_path = "data/entity_labels.csv"
author_code_to_display_name = {}
display_name_to_author_code = {}
with open(file_path, mode='r', encoding='utf-8') as csv_file:
    reader = csv.DictReader(csv_file)
    for row in reader:
        #{'entity': 'Q50364891', 'label': 'Oliver Evans'}
        author_code_to_display_name[row['entity']] = row['label']
        display_name_to_author_code[row['label']] = row['entity']

file_path = "data/authors_links.csv"  # CSV file.
with open(file_path, mode='r', encoding='utf-8') as csv_file:
    reader = csv.DictReader(csv_file)
    for row in reader:
        #print(row)
        author_code_to_display_name[row['entity']] = row['label']
        display_name_to_author_code[row['label']] = row['entity']

file_path = "data/to_be_removed.csv"  # CSV file.
to_be_remove={}
with open(file_path, mode='r', encoding='utf-8') as csv_file:
    reader = csv.DictReader(csv_file)
    for row in reader:
        #print(row)
        to_be_remove[row["entity"]]=0



# Create a directed graph.
graph = nx.DiGraph()


#############################################################
json_folder_path = output_data_path()
# List for storing edges.
edges = []

# Process the JSON files.
i=0
invalid_json_files = []
empty_result_count = 0
for filename in os.listdir(json_folder_path):
    #print(filename)
    i+=1
    if i%100==0:
        print(i)
    if filename.endswith(".json.gz"):
        file_path = os.path.join(json_folder_path, filename)
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        except (gzip.BadGzipFile, EOFError, OSError, UnicodeDecodeError, json.JSONDecodeError, zlib.error) as error:
            invalid_json_files.append((filename, str(error)))
            continue

        if not isinstance(data, dict) or not isinstance(data.get('result'), list):
            invalid_json_files.append((filename, "missing a list-valued 'result' field"))
            continue

        if not data['result']:
            empty_result_count += 1
            continue
        # Use the filename without its extension as the source.
        #print(data['result'])
        author_code = data['result'][0]['author'] if data['result'] else None
        #print(source,author)
        # Look up the author display name.
        author=author_code_to_display_name[author_code]

        if author_code in writers:
            ...
            # Add the source node to the graph.
        if author_code not in graph:
            if author_code in to_be_remove:
                continue



            graph.add_node(author_code,
                           code=author_code,
                           writer="1" if author_code in writers else "0",
                           display_name = author,
                           transnational=author_code_to_transnational.get(author_code, "N/D"),
                           gender=author_code_to_gender.get(author_code,"N/D"),
                           country=author_code_to_country.get(author_code,"N/D"),
                           former_colony = author_code_to_former_colony.get(author_code,"N/D"),
                           continent = author_code_to_continent.get(author_code,"N/D"),
                           minority = author_code_to_minority.get(author_code,"N/D"),
                           postcolonial = author_code_to_postcolonial.get(author_code,"N/D"),
                           birth = author_code_to_birth.get(author_code, "N/D"),
                           passport_mobility_score=entity_to_passport_mobility_score.get(author_code, "N/D"),
                           HDI_value=entity_to_hdi_value.get(author_code, "N/D"))
            #print("new displayname_author",displayname_author)
        # Create the edges.
        for record in data['result']:
            mentions={}

            for event in set(record['events']):  # Unique events.
                for mention in record['mentions']:
                    if mention not in mentions:
                        mentions[mention] = set()


                    mentions[mention].add(event)

                    # Add mention nodes if they do not already exist.
                    if mention not in graph:
                        if mention in to_be_remove:
                            continue
                        graph.add_node(mention,
                           code=mention,
                           writer="1" if mention in writers else "0",
                           display_name = author_code_to_display_name.get(mention, "?"),
                           transnational=author_code_to_transnational.get(mention, "N/D"),
                           gender=author_code_to_gender.get(mention, "N/D"),
                           country=author_code_to_country.get(mention,"N/D"),
                           former_colony = author_code_to_former_colony.get(mention,"N/D"),
                           continent = author_code_to_continent.get(mention,"N/D"),
                           minority = author_code_to_minority.get(mention,"N/D"),
                           postcolonial = author_code_to_postcolonial.get(mention,"N/D"),
                           birth = author_code_to_birth.get(mention, "N/D"),
                           passport_mobility_score=entity_to_passport_mobility_score.get(mention, "N/D"),
                           HDI_value=entity_to_hdi_value.get(mention, "N/D"))
            for mention,events in mentions.items():
                # Add the edge.
                if author_code in to_be_remove or mention in to_be_remove:
                    continue
                graph.add_edge(author_code, mention, event=','.join(events))

if invalid_json_files:
    print(f"Skipped {len(invalid_json_files)} empty, corrupt, or invalid JSON files.")
    for filename, error in invalid_json_files[:10]:
        print(f"  {filename}: {error}")
    if len(invalid_json_files) > 10:
        print(f"  ... and {len(invalid_json_files) - 10} more.")
if empty_result_count:
    print(f"Skipped {empty_result_count} valid JSON files with no extracted results.")

# Save the graph in GraphML format for later inspection.
write_network_graphml(graph, "data/networks/extended_network_graph.graphml.gz")
