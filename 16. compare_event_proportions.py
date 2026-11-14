# Compare event and link counts across network groups.

import networkx as nx
import numpy
from utils import network_graph_path, read_network_graphml

for graphml_path in [
    network_graph_path("base_network_graph.graphml.gz"),
    network_graph_path("extended_network_graph.graphml.gz"),
]:
    print("\n")
    print(graphml_path)
    # Load the graph.
    graph = read_network_graphml(graphml_path)
    # Filter nodes where writer='1'.
    writer_nodes = [n for n, d in graph.nodes(data=True) if d.get('writer') == '1']

    # Create a subgraph containing only these nodes.
    G_writer = graph.subgraph(writer_nodes)

    for label, group_1, group_0 in [
            ("Trasnational=1 Not-Trasnational=0",
             {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1'},
             {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '0'}
             ),
            ("Female=1 Male=0",
              {n for n, d in G_writer.nodes(data=True) if d.get('gender') == 'female'},
              {n for n, d in G_writer.nodes(data=True) if d.get('gender') == 'male'},
            ),
            ("transnational female=1 transnational male=0",
             {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1' and d.get('gender') == 'female'},
             {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1' and d.get('gender') == 'male'},
            ),
           ("transnational female=1 not-transnational female=0",
            {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1' and d.get('gender') == 'female'},
            {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '0' and d.get('gender') == 'female'},
           )
        ]:
        print(label)
        G_1 = graph.subgraph(group_1)
        G_0 = graph.subgraph(group_0)
        #print("Number edges subgraphs")
        print("edges_1","\t", G_1.number_of_edges())
        print("edges_0","\t", G_0.number_of_edges())
        print("edges_1/edges_0","\t", G_1.number_of_edges() / G_0.number_of_edges())

        count_links_1=[]
        count_links_0=[]
        count_event_1=[]
        count_event_0=[]

        for node in group_0:
            count_links_0.append(len(list(G_writer[node].keys())))
            count_event_0.append(numpy.average([len(value["event"].split(',')) for value in G_writer[node].values()]) if len(list(G_writer[node].keys()))>0 else 0)

        for node in group_1:
            count_links_1.append(len(list(G_writer[node].keys())))
            count_event_1.append(numpy.average([len(value["event"].split(',')) for value in G_writer[node].values()]) if len(list(G_writer[node].keys()))>0 else 0)

        #print("Average number of edges for authors 1 or 0")
        print("avg_links_1","\t",numpy.average(count_links_1))
        print("avg_links_0","\t",numpy.average(count_links_0))
        print('avg_links_1/avg_links_0',"\t",numpy.average(count_links_1)/numpy.average(count_links_0))

        #print("Median number of edges for authors 1 or 0")
        print("median_links_1","\t",numpy.median(count_links_1))
        print("median_links_0","\t",numpy.median(count_links_0))
        print('median_links_1/median_links_0',"\t",numpy.median(count_links_1)/numpy.median(count_links_0))

        #print("Std number of edges for authors 1 or 0")
        print("std_links_1","\t",numpy.std(count_links_1))
        print("std_links_0","\t",numpy.std(count_links_0))
        print('std_links_1/std_links_0',"\t",numpy.std(count_links_1)/numpy.std(count_links_0))

        #print("Average number of events for authors 1 or 0")
        print("avg_events_1","\t",numpy.average(count_event_1))
        print("avg_events_0","\t",numpy.average(count_event_0))
        print('avg_events_1/avg_events_0',"\t",numpy.average(count_event_1)/numpy.average(count_event_0))

        #print("Median number of events for authors 1 or 0")
        print("median_events_1","\t",numpy.median(count_event_1))
        print("median_events_0","\t",numpy.median(count_event_0))
        print('median_events_1/median_events_0',"\t",numpy.median(count_event_1)/numpy.median(count_event_0))

        #print("Std number of events for authors 1 or 0")
        print("std_events_1","\t",numpy.std(count_event_1))
        print("std_events_0","\t",numpy.std(count_event_0))
        print('std_events_1/std_events_0',"\t",numpy.std(count_event_1)/numpy.std(count_event_0))






