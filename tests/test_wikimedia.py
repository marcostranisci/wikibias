import unittest
from unittest import mock

from wikibias.wikimedia import WikimediaClient, build_user_agent


class FakeResponse:
    def __init__(self, status, data=None, headers=None):
        self.status_code = status
        self._data = data or {}
        self.headers = headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class WikimediaClientTest(unittest.TestCase):
    def test_headers(self):
        client = WikimediaClient(contact="someone@example.org")
        ua = client.session.headers["User-Agent"]
        self.assertIn("someone@example.org", ua)
        self.assertIn("github.com/marcostranisci/wikibias", ua)
        self.assertEqual(client.session.headers["Api-User-Agent"], ua)
        self.assertEqual(client.session.headers["Accept"], "application/json")

    def test_contact_from_env(self):
        with mock.patch.dict("os.environ", {"WIKIMEDIA_CONTACT": "env@example.org"}):
            self.assertIn("env@example.org", build_user_agent())

    def test_retries_on_429_and_maxlag(self):
        client = WikimediaClient(max_retries=3)
        responses = [
            FakeResponse(429, headers={"Retry-After": "0"}),
            FakeResponse(200, {"error": {"code": "maxlag"}}, headers={"Retry-After": "0"}),
            FakeResponse(200, {"query": {"search": [{"title": "George Orwell"}]}}),
        ]
        with mock.patch.object(client.session, "get", side_effect=responses) as get:
            self.assertEqual(client.search_wikipedia("Orwell", 3), ["George Orwell"])
        self.assertEqual(get.call_count, 3)
        self.assertEqual(get.call_args.kwargs["params"]["maxlag"], 5)


if __name__ == "__main__":
    unittest.main()
