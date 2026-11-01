import unittest
from types import SimpleNamespace

from wikibias.candidate_extraction import Candidate
from wikibias.entity_linking import HeuristicEntityLinker, gestalt_similarity


class FakeNLP:
    """Returns the PERSON entities given at construction time."""

    def __init__(self, people):
        self.people = people

    def __call__(self, text):
        return SimpleNamespace(ents=[SimpleNamespace(text=p, label_="PERSON") for p in self.people if p in text])


class FakeExtractor:
    def __init__(self, table):
        self.table = table

    def extract(self, mention):
        return self.table.get(mention, [])


def cand(qid, label, rank):
    return Candidate(wikidata_id=qid, label=label, wikipedia_title=label, rank=rank)


class HeuristicEntityLinkerTest(unittest.TestCase):
    def make(self, people, table, given_names=()):
        return HeuristicEntityLinker(
            FakeExtractor(table), nlp=FakeNLP(people), is_given_name=lambda w: w in given_names
        )

    def test_gestalt_match(self):
        linker = self.make(["Eileen O'Shaughnessy"], {"Eileen O'Shaughnessy": [cand("Q1", "Eileen O'Shaughnessy", 0)]})
        [entity] = linker.link("She was Eileen O'Shaughnessy.")
        self.assertEqual((entity.wikidata_id, entity.rule), ("Q1", "gestalt"))

    def test_below_threshold_is_dropped(self):
        linker = self.make(["John Smith"], {"John Smith": [cand("Q2", "Joan Smithson-Taylor", 0)]})
        self.assertEqual(linker.link("John Smith came."), [])

    def test_surname_links_most_famous(self):
        table = {"Orwell": [cand("Q3", "Sonia Orwell", 1), cand("Q4", "George Orwell", 0)]}
        linker = self.make(["Orwell"], table)
        [entity] = linker.link("She married Orwell in 1936.")
        self.assertEqual((entity.wikidata_id, entity.rule), ("Q4", "surname"))

    def test_possessive_is_stripped(self):
        linker = self.make(["Orwell's"], {"Orwell": [cand("Q4", "George Orwell", 0)]})
        [entity] = linker.link("Orwell's wife")
        self.assertEqual(entity.mention, "Orwell")

    def test_given_name_is_dropped(self):
        linker = self.make(["Adele"], {"Adele": [cand("Q5", "Adele", 0)]}, given_names={"Adele"})
        self.assertEqual(linker.link("Adele sang."), [])

    def test_similarity(self):
        self.assertEqual(gestalt_similarity("ORWELL", "orwell"), 1.0)


if __name__ == "__main__":
    unittest.main()
