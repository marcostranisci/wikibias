"""Event detection with a fine-tuned BERT token classifier."""

import logging

from ..text import clean_wikitext
from .base import BiographicalEvent, BiographicalEventDetector

log = logging.getLogger(__name__)

EVENT_LABEL = 1


class BertEventDetector(BiographicalEventDetector):
    """Splits a page into sentences with spaCy and tags event triggers with
    ``Bert4EventExtraction`` loaded from a ``.pt``/``.pth`` state dict.

    :param model_path: path to the trained weights (download link in the README).
    :param base_model: Hugging Face model the classifier was trained on.
    :param spacy_model: spaCy pipeline used for sentence splitting.
    :param clean_markup: strip MediaWiki markup before processing.
    :param max_page_length: pages are truncated to this many characters.
    """

    def __init__(
        self,
        model_path: str = "event_detection_model.pth",
        base_model: str = "distilbert-base-uncased",
        spacy_model: str = "en_core_web_sm",
        device: str = "cpu",
        clean_markup: bool = True,
        max_page_length: int = 100_000,
    ):
        import spacy
        import torch
        from transformers import AutoTokenizer

        from .model import Bert4EventExtraction

        self._torch = torch
        self.device = torch.device(device)
        self.clean_markup = clean_markup
        self.max_page_length = max_page_length

        self.nlp = spacy.load(spacy_model)
        self.nlp.max_length = max(self.nlp.max_length, max_page_length + 1)

        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        self.model = Bert4EventExtraction(base_model, 2)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()

    # ------------------------------------------------------------------

    def detect(self, wikidata_id: str, wikipedia_page: str) -> list[BiographicalEvent]:
        text = clean_wikitext(wikipedia_page) if self.clean_markup else wikipedia_page
        text = text[: self.max_page_length]
        if not text.strip():
            return []

        events = []
        for i, sent in enumerate(self.split_sentences(text)):
            tokens = [token.text for token in sent]
            for token_index, trigger in self.detect_in_tokens(tokens):
                events.append(BiographicalEvent(
                    subject=wikidata_id,
                    sentence_index=i,
                    sentence=sent.text,
                    trigger=trigger,
                    token_index=token_index,
                ))
        return events

    def split_sentences(self, text: str):
        """Return the spaCy sentence spans of ``text``."""
        return list(self.nlp(text).sents)

    def detect_in_tokens(self, tokens: list[str]) -> list[tuple[int, str]]:
        """Tag a tokenized sentence; return ``(token_index, token)`` triggers.

        Word pieces are mapped back to the original tokens: a token is a
        trigger when its first word piece is labelled as an event.
        """
        if not tokens:
            return []
        encoded = self.tokenizer(
            tokens, is_split_into_words=True, return_tensors="pt", truncation=True
        )
        with self._torch.no_grad():
            logits = self.model(
                encoded["input_ids"].to(self.device),
                encoded["attention_mask"].to(self.device),
            )
        labels = logits[0].argmax(dim=-1).tolist()

        triggers, seen = [], set()
        for piece_index, word_index in enumerate(encoded.word_ids(0)):
            if word_index is None or word_index in seen:
                continue
            seen.add(word_index)
            if labels[piece_index] == EVENT_LABEL:
                triggers.append((word_index, tokens[word_index]))
        return triggers
