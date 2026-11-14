# Build the base writer network from author and entity data.

import csv
import os
import json
import pandas as pd
import networkx as nx
from utils import write_network_graphml


# Initialize the graph.

# File paths.
csv_file_path = "data/authors_links.csv"  # CSV file.
# Load the CSV that maps authors to display names.
authors_df = pd.read_csv(csv_file_path, dtype=str)
writers = authors_df['entity'].tolist()
author_code_to_transnational = dict(zip(authors_df['entity'], (authors_df['transnational'])))

# File paths.
csv_file_path = "data/writers_gender.csv"  # CSV file.
# Load the CSV that maps authors to display names.
authors_df = pd.read_csv(csv_file_path, dtype=str)
author_code_to_gender = dict(zip(authors_df['s'], (authors_df['P21'])))

csv_file_path ="data/writers_postcolonial.csv"  # CSV file.
# Load the CSV that maps authors to display names.

authors_df = pd.read_csv(csv_file_path, dtype=str)
author_code_to_country = dict(zip(authors_df['s'], (authors_df['CountryIsoCode'])))
#print(authorcode_to_country)
author_code_to_former_colony = dict(zip(authors_df['s'], (authors_df['FormerColony'])))
author_code_to_continent = dict(zip(authors_df['s'], (authors_df['Continent'])))
author_code_to_minority = dict(zip(authors_df['s'], (authors_df['minority'])))
author_code_to_postcolonial = dict(zip(authors_df['s'], (authors_df['postcolonial'])))
author_code_to_birth = dict(zip(authors_df['s'], (authors_df['P569'])))

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


# Load the CSV file.
csv_path = "data/existing_kb.csv"
df = pd.read_csv(csv_path)

# Create a directed graph.
graph = nx.DiGraph()  # Directed graph.

# Add graph edges with the 'event' attribute.
for _, row in df.iterrows():
    source_author_code = row['s']
    properties = row['p']
    target_author_code = row['o']

    if source_author_code in to_be_remove or target_author_code in to_be_remove:
        continue

    if source_author_code not in graph:

        # Add the source node to the graph.
        graph.add_node(source_author_code,
                       code=source_author_code,
                       writer = "1" if source_author_code in writers else "0",
                       display_name=author_code_to_display_name.get(source_author_code,source_author_code),
                       transnational=author_code_to_transnational.get(source_author_code, "N/D"),
                       gender=author_code_to_gender.get(source_author_code, "N/D"),
                       country=author_code_to_country.get(source_author_code, "N/D"),
                       former_colony=author_code_to_former_colony.get(source_author_code, "N/D"),
                       continent=author_code_to_continent.get(source_author_code, "N/D"),
                       minority=author_code_to_minority.get(source_author_code, "N/D"),
                       postcolonial=author_code_to_postcolonial.get(source_author_code, "N/D"),
                       birth=author_code_to_birth.get(source_author_code, "N/D"),
                       passport_mobility_score=entity_to_passport_mobility_score.get(source_author_code, "N/D"),
                       HDI_value=entity_to_hdi_value.get(source_author_code, "N/D"))

    if target_author_code not in graph:
        graph.add_node(target_author_code,
                       code=target_author_code,
                       writer="1" if target_author_code in writers else "0",
                       display_name=author_code_to_display_name.get(target_author_code, target_author_code),
                       transnational=author_code_to_transnational.get(target_author_code, "N/D"),
                       gender=author_code_to_gender.get(target_author_code, "N/D"),
                       country=author_code_to_country.get(target_author_code, "N/D"),
                       former_colony=author_code_to_former_colony.get(target_author_code, "N/D"),
                       continent=author_code_to_continent.get(target_author_code, "N/D"),
                       minority=author_code_to_minority.get(target_author_code, "N/D"),
                       postcolonial=author_code_to_postcolonial.get(target_author_code, "N/D"),
                       birth=author_code_to_birth.get(target_author_code, "N/D"),
                       passport_mobility_score=entity_to_passport_mobility_score.get(target_author_code, "N/D"),
                       HDI_value=entity_to_hdi_value.get(target_author_code, "N/D"))

    if graph.add_edge(source_author_code, target_author_code):
        properties+=","+graph.get_edge_data(source_author_code, target_author_code)["event"]
        print(properties)
        graph.remove_edge(source_author_code, target_author_code)
    # Add an edge with the 'event' attribute.
    graph.add_edge(source_author_code, target_author_code, event=properties)

# Save the graph in GraphML format for later inspection.
write_network_graphml(graph, "data/networks/base_network_graph.graphml.gz")
