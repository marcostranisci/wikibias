from .base import BiographicalEvent, BiographicalEventDetector


def __getattr__(name):
    # Lazy import so the abstract interface works without torch installed.
    if name == "BertEventDetector":
        from .bert_detector import BertEventDetector
        return BertEventDetector
    raise AttributeError(name)


__all__ = ["BiographicalEvent", "BiographicalEventDetector", "BertEventDetector"]
