# Export event attributes on paths in the base network.

from utils import network_graph_path, read_network_graphml

import csv

import networkx as nx
from collections import Counter
from networkx.algorithms.community import modularity
import igraph as ig
import pandas as pd
import time



# Assume G is the loaded graph with attributes.
graphml_path = network_graph_path("base_network_graph.graphml.gz")
# Load the graph.
graph = read_network_graphml(graphml_path)
# Filter nodes where writer='1'.
writer_nodes = [n for n, d in graph.nodes(data=True) if d.get('writer') == '1']

# Collect `event` attributes along shortest paths.
event_counts = Counter()
filename="archi_base.csv"
fileoutput=csv.DictWriter(open(filename,"w"),fieldnames=["source","event","target"])
# Iterate over all pairs of writer nodes.
for i, source in enumerate(writer_nodes):
    print(i)
    for target in writer_nodes[i + 1:]:
        try:
            # Find the shortest path.
            shortest_path = nx.shortest_path(graph, source=source, target=target)

            # Retrieve `event` attributes from the path edges.
            for u, v in zip(shortest_path[:-1], shortest_path[1:]):
                edge_data = graph.get_edge_data(u, v)
                if edge_data and 'event' in edge_data:
                    event_counts[edge_data['event']] += 1
                    fileoutput.writerow({'source': u,
                                         'event': edge_data['event'],
                                         'target': v})
        except nx.NetworkXNoPath:
            # No path exists between the nodes.
            continue

# Sort events by frequency.
most_common_events = event_counts.most_common()

# Print the results.
print("Eventi più comuni negli shortest path tra autori:")
for event, count in most_common_events:
    print(f"Evento: {event}, Occorrenze: {count}")
