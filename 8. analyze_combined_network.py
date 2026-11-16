# Analyze the combined base and expanded networks.

from utils import (
    network_graph_path,
    print_low_hdi_low_passport_percentages,
    read_network_graphml,
    read_network_graphml_with_igraph,
)

import csv

import networkx as nx
from collections import Counter
from networkx.algorithms.community import modularity
import igraph as ig
import pandas as pd
import time

file = open("base+expanded.csv","w")
csv_writer = csv.writer(file, delimiter=",",quotechar="\"")
csv_writer.writerow(["node","node name","filterd_by","type","value","global rank","filtered rank"])

graphml_path = network_graph_path("base_network_graph.graphml.gz")
# Load the graph.
base_graph = read_network_graphml(graphml_path)

graphml_path = network_graph_path("extended_network_graph.graphml.gz")
# Load the graph.
extended_graph = read_network_graphml(graphml_path)

graph=nx.compose(base_graph,extended_graph)
print_low_hdi_low_passport_percentages(graph)

# 1. Percentage of nodes for each attribute.
def calculate_attribute_distribution(graph, attribute):
    attr_values = [data.get(attribute, 'N/D') for node, data in graph.nodes(data=True) if graph.nodes[node].get('writer') == '1']
    total = len(attr_values)
    counter = Counter(attr_values)
    percentages = {key: round((count / total) * 100, 2) for key, count in counter.items()}
    return percentages


def print_top_10(measure, graph, filtered_sorted_measure, global_ranking_measure):
    top_10_transnational = filtered_sorted_measure[:10]
    print(f"\nPrimi 10 nodi per {measure}:")
    for node, degree in top_10_transnational:
        global_position = global_ranking_measure[node]
        print(
            f"\tPosizione Globale: {global_position}, Nodo: {graph.nodes[node]}, {measure}: {degree}")  # , Attributi: {graph.nodes[node]}")

    ##########
    #
    # transnational + female
    #
    ##########

    # Filter nodes where gender=female.
    degree_filtered_by_minority = [
        (node, degree) for node, degree in filtered_sorted_measure if
        graph.nodes[node].get('gender') == 'female' and graph.nodes[node].get('transnational') == '1' and graph.nodes[
            node].get('writer') == '1'
    ]

    # Top 10 transnational=1 nodes by in-degree.
    top_10_transnational = degree_filtered_by_minority[:10]
    print(f"\nPrimi 10 nodi per {measure} transnational female:")
    for node, degree in top_10_transnational:
        global_position = global_ranking_measure[node]
        print(
            f"\tPosizione Globale: {global_position}, Nodo: {graph.nodes[node]['display_name']}, {measure}: {degree}")  # , Attributi: {graph.nodes[node]}")
    for index, author in enumerate(degree_filtered_by_minority):
        node, degree = author
        global_position = global_ranking_measure[node]
        csv_writer.writerow(
            [node, graph.nodes[node]['display_name'], "writer=1 and gender=female and transnational=1", measure, degree,
             global_position, index])


    ##########
    #
    # western + female
    #
    ##########

    # Filter nodes where gender=female.
    degree_filtered_by_minority = [
        (node, degree) for node, degree in filtered_sorted_measure if
        graph.nodes[node].get('gender') == 'female' and graph.nodes[node].get('transnational') == '0' and graph.nodes[
            node].get('writer') == '1'
    ]

    # Top 10 transnational=1 nodes by in-degree.
    top_10_transnational = degree_filtered_by_minority[:10]
    print(f"\nPrimi 10 nodi per {measure} western women")
    for node, degree in top_10_transnational:
        global_position = global_ranking_measure[node]
        print(
            f"\tPosizione Globale: {global_position}, Nodo: {graph.nodes[node]['display_name']}, {measure}: {degree}")  # , Attributi: {graph.nodes[node]}")

    for index, author in enumerate(degree_filtered_by_minority):
        node, degree = author
        global_position = global_ranking_measure[node]
        csv_writer.writerow(
            [node, graph.nodes[node]['display_name'], "writer=1 and transnational=0 gender=female", measure, degree, global_position,
             index])


    ##########
    #
    # transnational men
    #
    ##########

    # Filter nodes where transnational=1.
    degree_filtered_by_minority = [
        (node, degree) for node, degree in filtered_sorted_measure if graph.nodes[node].get('transnational') == '1' and graph.nodes[node].get('writer') == '1' and graph.nodes[node].get('gender') == 'male'
    ]

    # Top 10 transnational=1 nodes by in-degree.
    top_10_transnational = degree_filtered_by_minority[:10]
    print(f"\nPrimi 10 nodi writer per {measure} transnational men:")
    for node, degree in top_10_transnational:
        global_position = global_ranking_measure[node]
        print(f"\tPosizione Globale: {global_position}, Nodo: {graph.nodes[node]['display_name']}, {measure}: {degree}")#, Attributi: {graph.nodes[node]}")

    for index,author in enumerate(degree_filtered_by_minority):
        node, degree = author
        global_position = global_ranking_measure[node]
        csv_writer.writerow([node,graph.nodes[node]['display_name'],"writer=1 and transnational=1 gender=male", measure, degree, global_position, index])


    ##########
    #
    # western men
    #
    ##########

    # Filter nodes where transnational=1.
    degree_filtered_by_minority = [
        (node, degree) for node, degree in filtered_sorted_measure if graph.nodes[node].get('transnational') == '0' and graph.nodes[node].get('writer') == '1' and graph.nodes[node].get('gender') == 'male'
    ]

    # Top 10 transnational=1 nodes by in-degree.
    top_10_transnational = degree_filtered_by_minority[:10]
    print(f"\nPrimi 10 nodi writer per {measure} western men:")
    for node, degree in top_10_transnational:
        global_position = global_ranking_measure[node]
        print(f"\tPosizione Globale: {global_position}, Nodo: {graph.nodes[node]['display_name']}, {measure}: {degree}")#, Attributi: {graph.nodes[node]}")

    for index,author in enumerate(degree_filtered_by_minority):
        node, degree = author
        global_position = global_ranking_measure[node]
        csv_writer.writerow([node,graph.nodes[node]['display_name'],"writer=1 and transnational=0 gender male", measure, degree, global_position, index])


if False:
    #################################################
    ##
    #Attribute distribution analysis.
    ##
    #################################################
    print("\nRete Totale:")
    # Total nodes and edges in the original graph.
    total_nodes = graph.number_of_nodes()
    total_edges = graph.number_of_edges()
    print(f" - Numero totale di nodi: {total_nodes}")
    print(f" - Numero totale di archi: {total_edges}")

    # Attributes to analyze.
    attributes = [ 'former_colony', 'continent', 'minority', 'postcolonial', 'transnational','gender',"writer" ]#'birth','country',]

    print("\nDistribuzione degli attributi nella rete totale:")
    for attr in attributes:
        distribution = calculate_attribute_distribution(graph, attr)
        print(f" - {attr}: {distribution}%")

    # 2. Extract the giant component.
    largest_cc = max(nx.weakly_connected_components(graph), key=len)  # Find the largest connected component.
    GC = graph.subgraph(largest_cc).copy()  # Extract the giant component.

    # Percentage of nodes and edges in the giant component.
    gc_nodes = GC.number_of_nodes()
    gc_edges = GC.number_of_edges()

    node_percentage = (gc_nodes / total_nodes) * 100
    edge_percentage = (gc_edges / total_edges) * 100

    print("\nGiant Component:")
    print(f" - Nodi nella GC: {gc_nodes} ({node_percentage:.2f}%)")
    print(f" - Archi nella GC: {gc_edges} ({edge_percentage:.2f}%)")

    # 3. Attribute distribution in the giant component.
    print("\nDistribuzione degli attributi nella Giant Component:")
    for attr in attributes:
        gc_distribution = calculate_attribute_distribution(GC, attr)
        print(f" - {attr}: {gc_distribution}")
    # Print summary information about the graph.
    print(f"Numero di nodi: {graph.number_of_nodes()}")
    print(f"Numero di archi: {graph.number_of_edges()}")

    #################################################
    ##
    #Degree analysis.
    ##
    #################################################
    # Calculate the in-degree of every node.
    in_degrees = dict(graph.in_degree())
    # Sort nodes by in-degree in descending order.
    in_degrees = {
        node: rank for node, rank in in_degrees.items()
        if graph.nodes[node].get('writer') == '1'
    }
    sorted_in_degrees = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)

    # Create a mapping for global rank positions.
    degree_global_ranking = {node: rank for rank, (node, _) in enumerate(sorted_in_degrees, start=1)}
    print_top_10("degree",graph,sorted_in_degrees,degree_global_ranking)

    #################################################
    ##
    #Centrality analysis.
    ##
    #################################################
    #################################################
    ##
    ##  Page rank
    ##
    #################################################
    # Calculate PageRank.
    pagerank = nx.pagerank(graph)
    pagerank = {
        node: rank for node, rank in pagerank.items()
        if graph.nodes[node].get('writer') == '1'
    }
    # Sort nodes by PageRank in descending order.
    sorted_pagerank = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)

    # Map each node to its global rank.
    pagerank_global_ranking = {node: rank for rank, (node, _) in enumerate(sorted_pagerank, start=1)}

    print_top_10("PageRank",graph,sorted_pagerank,pagerank_global_ranking)


    #################################################
    ##
    #Closeness and betweenness centrality analysis.
    ##
    #################################################

    # Calculate closeness centrality.
    closeness = nx.closeness_centrality(graph)
    closeness = {
        node: rank for node, rank in closeness.items()
        if graph.nodes[node].get('writer') == '1'
    }
    # Sort nodes by closeness centrality in descending order.
    sorted_closeness = sorted(closeness.items(), key=lambda x: x[1], reverse=True)

    # Map each node to its global rank.
    closeness_global_ranking = {node: rank for rank, (node, _) in enumerate(sorted_closeness, start=1)}

    print_top_10("closeness",graph,sorted_closeness,closeness_global_ranking)



    #################################################
    # Calculate betweenness centrality.


    # Load the graph from a file.
    # Replace this with the path to your GraphML file or another supported format.

    g = read_network_graphml_with_igraph(graphml_path)

    # Calcolo della Betweenness Centrality
    print("Calcolo della betweenness centrality...")

    # Calculate betweenness centrality for all nodes.
    betweenness = g.betweenness(vertices=None, directed=True, cutoff=None, weights=None)

    # Add betweenness values as node attributes.
    g.vs['betweenness'] = betweenness

    # Sort nodes by centrality in descending order.
    sorted_betweenness = sorted(zip(g.vs, betweenness), key=lambda x: x[1], reverse=True)

    sorted_betweenness = [(x["code"],y) for x,y in sorted_betweenness]

    sorted_betweenness = [(x,y) for x,y in sorted_betweenness if
     graph.nodes[x].get('writer') == '1']
    # Map each node to its global rank.
    betweenness_global_ranking = {node: rank for rank, (node, _) in enumerate(sorted_betweenness, start=1)}


    print_top_10("betweenness",graph,sorted_betweenness,betweenness_global_ranking)





# Filter nodes where writer='1'.
writer_nodes = [n for n, d in graph.nodes(data=True) if d.get('writer') == '1' and
                (d.get('transnational') == '1' or d.get('transnational') == '0') and
                (d.get('gender') == 'male' or d.get('gender') == 'female')]

# Create a subgraph containing only these nodes.
G_writer = graph.subgraph(writer_nodes)
print(G_writer.number_of_nodes(),G_writer.number_of_edges())

# Define groups.
group_transnational_1 = {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1'}
group_transnational_0 = {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '0'}

group_gender_female = {n for n, d in G_writer.nodes(data=True) if d.get('gender') == 'female'}
group_gender_male = {n for n, d in G_writer.nodes(data=True) if d.get('gender') == 'male'}

group_trans_male = {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1' and d.get('gender') == 'male'}
group_trans_female = {n for n, d in G_writer.nodes(data=True) if d.get('transnational') == '1' and d.get('gender') == 'female'}

all_other_than_trans_male = set(G_writer.nodes) - group_trans_male
all_other_than_trans_female = set(G_writer.nodes) - group_trans_female

"""# Function to calculate modularity
def calculate_modularity(G, group1, group2):
    communities = [group1, group2]
    return nx.algorithms.community.quality.modularity(G, communities)

# Calculate segregation metrics
mod_transnational = calculate_modularity(G_writer, group_1, group_0)
mod_gender = calculate_modularity(G_writer, group_gender_female, group_gender_male)
mod_trans_male_vs_all = calculate_modularity(G_writer, group_trans_male, all_other_than_trans_male)
mod_trans_female_vs_all = calculate_modularity(G_writer, group_trans_female, all_other_than_trans_female)

# Print the results.
print("Modularità transnational='1' vs transnational='0':", mod_transnational)
print("Modularità gender='female' vs gender='male':", mod_gender)
print("Modularità transnational='1' and gender='male' vs all others:", mod_trans_male_vs_all)
print("Modularità transnational='1' and gender='female' vs all others:", mod_trans_female_vs_all)"""





def intra_group_density(G, group):
    """
    Calculate within-group density.
    """
    subgraph = G.subgraph(group)  # Create a subgraph containing the group's nodes.
    n_nodes = len(group)
    if n_nodes < 2:  # Avoid division by zero.
        return 0
    n_edges = subgraph.number_of_edges()
    density = (2 * n_edges) / (n_nodes * (n_nodes - 1))
    return density

def inter_group_density(G, group1, group2):
    """
    Calculate between-group density.
    """
    edges_between = 0
    for u in group1:
        for v in group2:
            if G.has_edge(u, v):
                edges_between += 1
    n1, n2 = len(group1), len(group2)
    if n1 == 0 or n2 == 0:  # Avoid division by zero.
        return 0
    density = edges_between / (n1 * n2)
    return density

# Calculate within- and between-group densities.
intra_trans_1 = intra_group_density(G_writer, group_transnational_1)
intra_trans_0 = intra_group_density(G_writer, group_transnational_0)
inter_trans_1_0 = inter_group_density(G_writer, group_transnational_1, group_transnational_0)
print("Densità intra transnational='1':", intra_trans_1)
print("Densità intra transnational='0':", intra_trans_0)
print("Densità inter transnational='1' vs transnational='0':", inter_trans_1_0)



intra_gender_female = intra_group_density(G_writer, group_gender_female)
intra_gender_male = intra_group_density(G_writer, group_gender_male)
inter_gender_female_male = inter_group_density(G_writer, group_gender_female, group_gender_male)
print("Densità intra gender='female':", intra_gender_female)
print("Densità intra gender='male':", intra_gender_male)
print("Densità inter gender='female' vs gender='male':", inter_gender_female_male)



intra_trans_male = intra_group_density(G_writer, group_trans_male)
intra_trans_female = intra_group_density(G_writer, group_trans_female)
inter_trans_male_vs_all = inter_group_density(G_writer, group_trans_male, all_other_than_trans_male)
inter_trans_female_vs_all = inter_group_density(G_writer, group_trans_female, all_other_than_trans_female)
print("Densità intra transnational='1' and gender='male':", intra_trans_male)
print("Densità intra transnational='1' and gender='female':", intra_trans_female)
print("Densità inter transnational='1' and gender='male' vs all others:", inter_trans_male_vs_all)
print("Densità inter transnational='1' and gender='female' vs all others:", inter_trans_female_vs_all)

import numpy as np


def permutation_test(G, group1, group2, observed_value, num_permutations=10):
    """
    Esegue un test di permutazione per verificare se la differenza tra le densità è significativa.

    :param G: NetworkX graph
    :param group1: set of nodes in the first group
    :param group2: set of nodes in the second group
    :param observed_value: observed within- or between-group density
    :param num_permutations: number of permutations
    :return: p-value
    """
    combined = list(group1 | group2)  # Combine the nodes from both groups.
    count_extreme = 0
    permuted_values = []
    i=0
    for _ in range(num_permutations):
        print(i)
        i+=1
        np.random.shuffle(combined)  # Shuffle the nodes between groups.
        perm_group1 = set(combined[:len(group1)])
        perm_group2 = set(combined[len(group1):])
        perm_density = inter_group_density(G, perm_group1, perm_group2)
        permuted_values.append(perm_density)

        if abs(perm_density - observed_value) >= abs(observed_value - np.mean(permuted_values)):
            count_extreme += 1

    p_value = count_extreme / num_permutations
    return p_value


# Run a permutation test for selected density differences.
p_transnational = permutation_test(G_writer, group_transnational_1, group_transnational_0, inter_trans_1_0)
p_gender = permutation_test(G_writer, group_gender_female, group_gender_male, inter_gender_female_male)

print("P-value per differenza di densità tra transnational='1' e transnational='0':", p_transnational)
print("P-value per differenza di densità tra gender='female' e gender='male':", p_gender)
