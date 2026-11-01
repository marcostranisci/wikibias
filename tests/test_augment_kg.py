import gzip
import json
import os
import tempfile
import unittest

import pandas as pd

import augment_kg
from wikibias.entity_linking import LinkedEntity
from wikibias.event_detection import BiographicalEvent


class FakeDetector:
    def detect(self, qid, page):
        return [
            BiographicalEvent(qid, i, sentence, sentence.split()[1], 1)
            for i, sentence in enumerate(s.strip() + "." for s in page.split(".") if s.strip())
        ]


class FakeLinker:
    PEOPLE = {"Orwell": ("Q3335", "George Orwell"), "Woolf": ("Q40909", "Virginia Woolf"), "Rushdie": ("Q44306", "Salman Rushdie")}

    def link(self, sentence):
        return [LinkedEntity(w, *self.PEOPLE[w], 1.0, "gestalt") for w in self.PEOPLE if w in sentence]


class AugmentKGTest(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            pd.DataFrame({
                "entity": ["Q1", "Q2", "Q44306"],
                "label": ["Author One", "Author Two", "Salman Rushdie"],
                "origin": ["transnational", "western", "transnational"],
                "gender": ["female", "male", "male"],
            }).to_csv(os.path.join(tmp, "authors.csv"), index=False)
            bios = os.path.join(tmp, "bios")
            os.makedirs(bios)
            with open(os.path.join(bios, "Q1.txt"), "w") as f:
                f.write("She married Orwell. She met Rushdie. She was born.")
            with gzip.open(os.path.join(bios, "Q2.txt.gz"), "wt") as f:
                f.write("He met Woolf and Rushdie.")

            out = os.path.join(tmp, "out")
            args = augment_kg.parse_args([
                "--authors", os.path.join(tmp, "authors.csv"), "--biographies", bios,
                "--output-dir", out, "--path-events",
            ])
            base = pd.DataFrame({"s": ["Q2"], "p": ["P737"], "o": ["Q1"]})
            summaries = augment_kg.run(
                args,
                make_components=lambda: (FakeDetector(), FakeLinker()),
                fetch_base_kg=lambda ids: base,
                fetch_labels=lambda ids: {"Q40909": "Virginia Woolf"},
            )

            self.assertEqual(summaries["base"]["edges"], 1)
            self.assertEqual(summaries["extended"]["edges"], 4)
            self.assertEqual(summaries["augmented"]["edges"], 5)

            aug = pd.read_csv(os.path.join(out, "kg", "augmented_triples.csv"))
            self.assertEqual(sorted(aug["source"].value_counts().items()), [("text", 4), ("wikidata", 1)])

            authors = pd.read_csv(os.path.join(out, "analysis", "authors.csv")).set_index("author")
            self.assertEqual(authors.at["Q2", "base_out_degree"], 1)
            self.assertEqual(authors.at["Q2", "augmented_out_degree"], 3)
            self.assertEqual(authors.at["Q2", "new_from_text"], 2)

            dens = pd.read_csv(os.path.join(out, "analysis", "augmented", "densities.csv"))
            self.assertIn("origin=transnational|gender=female", set(dens["group"]))
            ranks = pd.read_csv(os.path.join(out, "analysis", "augmented", "rankings.csv"))
            top = ranks[(ranks.measure == "in_degree") & (ranks.group == "all")].iloc[0]
            self.assertEqual(top["display_name"], "Salman Rushdie")
            for name in ("summary.json", "edge_events.csv", "path_events.csv"):
                self.assertTrue(os.path.isfile(os.path.join(out, "analysis", "augmented", name)))
            self.assertTrue(os.path.isfile(os.path.join(out, "kg", "augmented.graphml")))

            # Second run reuses the cached extraction (models are not loaded).
            def fail():
                raise AssertionError("models should not be loaded")
            augment_kg.run(args, make_components=fail, fetch_base_kg=lambda ids: base, fetch_labels=None)


if __name__ == "__main__":
    unittest.main()
