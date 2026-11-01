"""Network analysis (from scripts 6-14: "analisi rete", "analisi attributi archi",
"esporta archi")."""

from collections import Counter
from typing import Callable, Iterable, Iterator

import networkx as nx

from .build import split_events

NodeFilter = Callable[[dict], bool]

ATTRIBUTES = ["former_colony", "continent", "minority", "postcolonial", "transnational", "gender", "writer"]


def is_writer(d: dict) -> bool:
    return d.get("writer") == "1"


# Groups of writers compared in the analyses.
WRITER_GROUPS: dict[str, NodeFilter] = {
    "writers": is_writer,
    "transnational writers": lambda d: is_writer(d) and d.get("transnational") == "1",
    "female writers": lambda d: is_writer(d) and d.get("gender") == "female",
    "female transnational writers": lambda d: is_writer(d) and d.get("gender") == "female" and d.get("transnational") == "1",
}


# ----------------------------------------------------------------------
# Structure
# ----------------------------------------------------------------------

def attribute_distribution(graph: nx.Graph, attribute: str) -> dict[str, float]:
    """Percentage of nodes for each value of ``attribute``."""
    values = Counter(d.get(attribute, "N/D") for _, d in graph.nodes(data=True))
    total = sum(values.values()) or 1
    return {k: round(100 * v / total, 2) for k, v in values.items()}


def giant_component(graph: nx.DiGraph) -> nx.DiGraph:
    """Largest weakly connected component."""
    if graph.number_of_nodes() == 0:
        return graph.copy()
    return graph.subgraph(max(nx.weakly_connected_components(graph), key=len)).copy()


# ----------------------------------------------------------------------
# Centrality
# ----------------------------------------------------------------------

def _betweenness(graph: nx.DiGraph) -> dict[str, float]:
    """Unnormalised directed betweenness; uses igraph when installed (much faster)."""
    try:
        import igraph as ig
    except ImportError:
        return nx.betweenness_centrality(graph, normalized=False)
    nodes = list(graph.nodes)
    index = {n: i for i, n in enumerate(nodes)}
    g = ig.Graph(n=len(nodes), edges=[(index[u], index[v]) for u, v in graph.edges], directed=True)
    return dict(zip(nodes, g.betweenness(directed=True)))


CENTRALITY: dict[str, Callable[[nx.DiGraph], dict]] = {
    "in_degree": lambda g: dict(g.in_degree()),
    "pagerank": nx.pagerank,
    "closeness": nx.closeness_centrality,
    "betweenness": _betweenness,
}


def ranking(graph: nx.DiGraph, measure: str) -> list[tuple[str, float]]:
    """Nodes sorted by ``measure`` (one of ``CENTRALITY``), highest first."""
    scores = CENTRALITY[measure](graph)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def top_nodes(graph: nx.DiGraph, ranked: list[tuple[str, float]], node_filter: NodeFilter | None = None, n: int = 20) -> list[dict]:
    """Top ``n`` nodes passing ``node_filter``, with their global position."""
    out = []
    for position, (node, score) in enumerate(ranked, start=1):
        data = graph.nodes[node]
        if node_filter is None or node_filter(data):
            out.append({"global_position": position, "node": node,
                        "display_name": data.get("display_name", node), "score": score})
            if len(out) == n:
                break
    return out


# ----------------------------------------------------------------------
# Segregation between groups of writers
# ----------------------------------------------------------------------

def nodes_where(graph: nx.Graph, node_filter: NodeFilter) -> set[str]:
    return {n for n, d in graph.nodes(data=True) if node_filter(d)}


def intra_group_density(graph: nx.Graph, group: set[str]) -> float:
    """Edges inside ``group`` over possible pairs, ``2E / (n(n-1))``.

    Note: on a directed graph this counts both directions, so it can exceed 0.5
    when ties are reciprocal (formula kept from the original analysis).
    """
    n = len(group)
    if n < 2:
        return 0.0
    return 2 * graph.subgraph(group).number_of_edges() / (n * (n - 1))


def inter_group_density(graph: nx.Graph, group1: set[str], group2: set[str]) -> float:
    """Edges from ``group1`` to ``group2`` over ``|group1| * |group2|``."""
    if not group1 or not group2:
        return 0.0
    edges = sum(1 for u in group1 for v in graph.successors(u) if v in group2) if graph.is_directed() else \
        sum(1 for u in group1 for v in graph.neighbors(u) if v in group2)
    return edges / (len(group1) * len(group2))


def group_densities(graph: nx.DiGraph) -> dict[str, float]:
    """Intra/inter densities among writers by transnational status and gender."""
    writers = graph.subgraph(nodes_where(graph, is_writer))
    attr = lambda key, value: nodes_where(writers, lambda d: d.get(key) == value)

    trans1, trans0 = attr("transnational", "1"), attr("transnational", "0")
    female, male = attr("gender", "female"), attr("gender", "male")
    trans_male, trans_female = trans1 & male, trans1 & female
    everyone = set(writers.nodes)

    return {
        "intra transnational=1": intra_group_density(writers, trans1),
        "intra transnational=0": intra_group_density(writers, trans0),
        "inter transnational=1 vs 0": inter_group_density(writers, trans1, trans0),
        "intra gender=female": intra_group_density(writers, female),
        "intra gender=male": intra_group_density(writers, male),
        "inter gender=female vs male": inter_group_density(writers, female, male),
        "intra transnational male": intra_group_density(writers, trans_male),
        "intra transnational female": intra_group_density(writers, trans_female),
        "inter transnational male vs all": inter_group_density(writers, trans_male, everyone - trans_male),
        "inter transnational female vs all": inter_group_density(writers, trans_female, everyone - trans_female),
    }


# ----------------------------------------------------------------------
# Events on the edges
# ----------------------------------------------------------------------

def shortest_path_edges(graph: nx.DiGraph, nodes: Iterable[str]) -> Iterator[tuple[str, str, str]]:
    """Yield ``(source, event, target)`` for every edge on the shortest path
    between each pair of ``nodes`` (pairs taken in list order, as before)."""
    nodes = list(nodes)
    for i, source in enumerate(nodes):
        # One BFS per source instead of one search per pair.
        paths = nx.single_source_shortest_path(graph, source)
        for target in nodes[i + 1:]:
            path = paths.get(target)
            if not path:
                continue
            for u, v in zip(path[:-1], path[1:]):
                for event in split_events(graph.edges[u, v].get("event")):
                    yield u, event, v


def edge_event_counts(graph: nx.DiGraph) -> Counter:
    """How often each event appears on the edges."""
    counts = Counter()
    for _, _, data in graph.edges(data=True):
        counts.update(split_events(data.get("event")))
    return counts
