# Analyze event attributes on paths in the base network.

from utils import network_graph_path, read_network_graphml

import networkx as nx
from collections import Counter
from networkx.algorithms.community import modularity
import igraph as ig
import pandas as pd
import time


# Assume G is the loaded graph with attributes.
graphml_path = network_graph_path("extended_network_graph.graphml.gz")
# Load the graph.
graph = read_network_graphml(graphml_path)
# Filter nodes where writer='1'.
writer_nodes_1 = [n for n, d in graph.nodes(data=True) if d.get('writer') == '1' and d.get('transnational') == '1']
writer_nodes_2 = [n for n, d in graph.nodes(data=True) if d.get('writer') == '1' and d.get('transnational') == '0']

# Collect `event` attributes along shortest paths.
event_counts = Counter()

# Iterate over all pairs of writer nodes.
for i, source in enumerate(writer_nodes_1):
    print(i)
    for target in writer_nodes_2:
        try:
            # Find the shortest path.
            shortest_path = nx.shortest_path(graph, source=source, target=target)

            # Retrieve `event` attributes from the path edges.
            for u, v in zip(shortest_path[:-1], shortest_path[1:]):
                edge_data = graph.get_edge_data(u, v)
                if edge_data and 'event' in edge_data:
                    event_counts[edge_data['event']] += 1
        except nx.NetworkXNoPath:
            # No path exists between the nodes.
            continue

# Sort events by frequency.
most_common_events = event_counts.most_common()

# Print the results.
print("Eventi più comuni negli shortest path tra autori:")
for event, count in most_common_events[0:10]:
    print(f"Evento: {event}, Occorrenze: {count}")
