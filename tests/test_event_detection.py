import contextlib
import unittest
from types import SimpleNamespace

from wikibias.event_detection.base import BiographicalEvent, BiographicalEventDetector
from wikibias.event_detection.bert_detector import BertEventDetector


class FakeTensor(list):
    def to(self, device):
        return self


class FakeLogits:
    """Supports ``logits[0].argmax(dim=-1).tolist()`` for a fixed label list."""

    def __init__(self, labels):
        self.labels = labels

    def __getitem__(self, i):
        return SimpleNamespace(argmax=lambda dim: SimpleNamespace(tolist=lambda: self.labels))


class FakeEncoding(dict):
    def __init__(self, word_ids):
        super().__init__(input_ids=FakeTensor(), attention_mask=FakeTensor())
        self._word_ids = word_ids

    def word_ids(self, i):
        return self._word_ids


class FakeSpan:
    def __init__(self, text):
        self.text = text
        self.tokens = [SimpleNamespace(text=t) for t in text.replace(".", " .").split()]

    def __iter__(self):
        return iter(self.tokens)


def fake_detector(word_ids, labels, sentences=None):
    """A BertEventDetector with fake tokenizer/model (no torch needed)."""
    detector = BertEventDetector.__new__(BertEventDetector)
    detector._torch = SimpleNamespace(no_grad=contextlib.nullcontext)
    detector.device = "cpu"
    detector.clean_markup = False
    detector.max_page_length = 1000
    detector.tokenizer = lambda tokens, **kw: FakeEncoding(word_ids)
    detector.model = lambda ids, mask: FakeLogits(labels)
    if sentences is not None:
        detector.split_sentences = lambda text: sentences
    return detector


class BertEventDetectorTest(unittest.TestCase):
    def test_word_pieces_map_to_tokens(self):
        # [CLS] she re ##married him [SEP]: the first piece's label decides.
        detector = fake_detector([None, 0, 1, 1, 2, None], [0, 0, 1, 0, 0, 0])
        self.assertEqual(detector.detect_in_tokens(["She", "remarried", "him"]), [(1, "remarried")])

    def test_detect_returns_events(self):
        span = FakeSpan("She married him.")
        detector = fake_detector([None, 0, 1, 2, 3, None], [0, 0, 1, 0, 0, 0], sentences=[span])
        events = detector.detect("Q1", "She married him.")
        self.assertEqual(events, [BiographicalEvent("Q1", 0, "She married him.", "married", 1)])
        self.assertIsInstance(detector, BiographicalEventDetector)

    def test_empty_page(self):
        self.assertEqual(fake_detector([], []).detect("Q1", "   "), [])


if __name__ == "__main__":
    unittest.main()
