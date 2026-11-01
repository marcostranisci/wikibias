import unittest

from wikibias.candidate_extraction import WikipediaSearchCandidateExtractor


class FakeClient:
    language = "en"

    def __init__(self):
        self.searches = 0

    def search_wikipedia(self, query, limit):
        self.searches += 1
        return ["George Orwell", "Nineteen Eighty-Four", "Orwell (surname)", "Sonia Orwell"][:limit]

    def wikidata_ids_for_titles(self, titles):
        ids = {"George Orwell": "Q3335", "Nineteen Eighty-Four": "Q208460", "Orwell (surname)": "Q999", "Sonia Orwell": "Q7"}
        return {t: ids[t] for t in titles}

    def get_entities(self, ids, props):
        human = {"claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}]}}
        book = {"claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q7725634"}}}}]}}
        entities = {
            "Q3335": {**human, "labels": {"en": {"value": "George Orwell"}}, "aliases": {"en": [{"value": "Eric Blair"}]}},
            "Q208460": book,
            "Q999": book,
            "Q7": {**human, "labels": {"en": {"value": "Sonia Orwell"}}},
        }
        return {i: entities[i] for i in ids}


class WikipediaSearchCandidateExtractorTest(unittest.TestCase):
    def test_top_k_and_only_humans(self):
        client = FakeClient()
        extractor = WikipediaSearchCandidateExtractor(top_k=3, client=client)
        candidates = extractor.extract("Orwell")
        # Sonia Orwell is the 4th result, outside the top 3.
        self.assertEqual([c.wikidata_id for c in candidates], ["Q3335"])
        self.assertEqual(candidates[0].aliases, ["Eric Blair"])
        extractor.extract("Orwell")
        self.assertEqual(client.searches, 1)  # cached


if __name__ == "__main__":
    unittest.main()
