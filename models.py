"""Explicit local model identities. No automatic routing or fallback."""

FAST_MODEL = "llama-3.2-3b-instruct"
from configuration import load
REASONING_MODEL = load()['model']
MODELS = {"fast": FAST_MODEL, "reasoning": REASONING_MODEL}


def model_id(role="reasoning"):
    try:
        return MODELS[role]
    except (KeyError, TypeError):
        raise ValueError("Choose model 'fast' or 'reasoning'") from None
