import math


def estimate_tokens(text: str) -> int:
    """About 4 characters per token. Sizes only shape chunks, so an estimate is enough."""
    return math.ceil(len(text) / 4)
