# Analyze event counts between writer groups.

from utils import network_graph_path, read_network_graphml

import networkx as nx
from collections import defaultdict
from itertools import combinations
import numpy as np

graphml_path = network_graph_path("base_network_graph.graphml.gz")
# Load the graph.
G_writer = read_network_graphml(graphml_path)



#graphml_path = network_graph_path("extended_network_graph.graphml.gz")
#G_writer = read_network_graphml(graphml_path)


#graphml_path = network_graph_path("base_network_graph.graphml.gz")
# Load the graph.
#base_graph = read_network_graphml(graphml_path)

#graphml_path = network_graph_path("extended_network_graph.graphml.gz")
# Load the graph.
#extended_graph = read_network_graphml(graphml_path)

#G_writer=nx.compose(base_graph,extended_graph)



writer_nodes = [n for n, d in G_writer.nodes(data=True) if d.get('writer') == '1' and
                (d.get('transnational') == '1' or d.get('transnational') == '0') and
                (d.get('gender') == 'male' or d.get('gender') == 'female')]

# Create a subgraph containing only these nodes.
G_writer = G_writer.subgraph(writer_nodes)

# Define writer groups.
group_transnational_1 = {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1'}
group_transnational_0 = {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '0'}

group_gender_female = {n for n, d in G_writer.nodes(data=True) if d.get('gender') == 'female'}
group_gender_male = {n for n, d in G_writer.nodes(data=True) if d.get('gender') == 'male'}

group_trans_male = {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1' and d.get('gender') == 'male'}
group_trans_female = {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1' and d.get('gender') == 'female'}

# Create group combinations.
groups = {
    "Transnational Women": group_trans_female,
    "Transnational Men": group_trans_male,
    "Western Women": group_gender_female - group_trans_female,
    "Western Men": group_gender_male - group_trans_male,
}

# Count events between pairs of groups.
def count_events_between_groups(G, group1, group2):
    event_counts = defaultdict(int)

    for u, v in G.edges():
        if (u in group1 and v in group2) or (v in group1 and u in group2):
            edge_data = G.get_edge_data(u, v)
            if edge_data and 'event' in edge_data:
                for event in edge_data['event'].split(","):
                        event_counts[event] += 1
                print(edge_data["event"])

    # Return the five most frequent events.
    return sorted(event_counts.items(), key=lambda x: x[1], reverse=True)[:5]

# Count events for each pair of groups.
results = {}

for (group1_name, group1), (group2_name, group2) in combinations(groups.items(), 2):
    pair_name = f"{group1_name} - {group2_name}"
    results[pair_name] = count_events_between_groups(G_writer, group1, group2)

# Print the results.
for pair, events in results.items():
    print(f"Top 5 eventi per {pair}:")
    for event, count in events:
        print(f"  {event}: {count} {count/np.sum([np.sum(values) for event,values in results[pair]])*100}")
    print()
