import unittest

import pandas as pd

from wikibias.network.analysis import (
    edge_event_counts, giant_component, group_densities, intra_group_density, ranking, shortest_path_edges, top_nodes,
)
from wikibias.network.build import NodeAttributes, build_base_network, build_extended_network, compose_networks
from wikibias.network.sampling import sample_event_sentences


def attrs():
    return NodeAttributes(
        writers={"A", "B", "C"},
        labels={"A": "Author A", "B": "Author B", "C": "Author C", "P": "Person P"},
        attributes={"transnational": {"A": "1", "B": "0", "C": "1"}, "gender": {"A": "female", "B": "male", "C": "male"}},
        removed={"X"},
    )


RECORDS = [
    {"author": "A", "events": ["married"], "mentions": ["P", "X"], "sentence": "A married P."},
    {"author": "A", "events": ["met"], "mentions": [{"wikidata_id": "P"}], "sentence": "A met P."},
    {"author": "B", "events": ["met"], "mentions": ["P"], "sentence": "B met P."},
    {"author": "C", "events": [], "mentions": ["A"]},
]


class NetworkTest(unittest.TestCase):
    def test_extended(self):
        g = build_extended_network(RECORDS, attrs())
        self.assertEqual(g.edges["A", "P"]["event"], "married,met")
        self.assertNotIn("X", g)
        self.assertIn("C", g)                 # author kept as a node
        self.assertFalse(g.has_edge("C", "A"))  # no events, no edge
        self.assertEqual(g.nodes["A"]["display_name"], "Author A")
        self.assertEqual(g.nodes["P"]["writer"], "0")

    def test_base_and_joint(self):
        base = build_base_network(pd.DataFrame({"s": ["A", "C"], "p": ["P26", "P737"], "o": ["P", "A"]}), attrs())
        joint = compose_networks(base, build_extended_network(RECORDS, attrs()))
        self.assertEqual(joint.edges["A", "P"]["event"], "P26,married,met")
        self.assertTrue(joint.has_edge("C", "A"))

    def test_analysis(self):
        g = compose_networks(
            build_base_network(pd.DataFrame({"s": ["C"], "p": ["P737"], "o": ["A"]}), attrs()),
            build_extended_network(RECORDS, attrs()),
        )
        self.assertEqual(ranking(g, "in_degree")[0], ("P", 2))
        self.assertEqual(top_nodes(g, ranking(g, "in_degree"), lambda d: d["writer"] == "1", n=1)[0]["node"], "A")
        self.assertEqual(giant_component(g).number_of_nodes(), 4)
        self.assertEqual(intra_group_density(g, {"A", "C"}), 1.0)
        self.assertEqual(group_densities(g)["intra transnational=1"], 1.0)
        self.assertEqual(edge_event_counts(g)["met"], 2)
        edges = list(shortest_path_edges(g, ["C", "A"]))
        self.assertEqual(edges, [("C", "P737", "A")])
        for measure in ("pagerank", "closeness", "betweenness"):
            self.assertEqual(len(ranking(g, measure)), 4)

    def test_sampling(self):
        g = build_extended_network(RECORDS, attrs())
        rows = sample_event_sentences(RECORDS, edge_event_counts(g), attrs().labels, per_event=5, seed=0)
        self.assertEqual({r["event"] for r in rows}, {"married", "met"})
        self.assertEqual(len([r for r in rows if r["event"] == "met"]), 2)


if __name__ == "__main__":
    unittest.main()
