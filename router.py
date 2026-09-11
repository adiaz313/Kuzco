"""Small, conservative, full-request rules. No tools, personality, or model I/O."""
from dataclasses import dataclass
from enum import Enum
import re


class Destination(str, Enum):
    DIRECT = 'DIRECT'
    FAST = 'FAST_MODEL'
    REASONING = 'REASONING_MODEL'


@dataclass(frozen=True)
class Route:
    destination: Destination
    reason: str
    tool: str | None = None
    application: str | None = None


def route(request):
    if not isinstance(request, str) or not request.strip():
        raise ValueError('Please provide a nonempty request')
    text = ' '.join(request.strip().lower().replace('’', "'").split()).rstrip('.?!')
    # Full matches avoid acting on negations, quotations, compound requests, or references.
    if re.fullmatch(r"(?:please )?(?:what time is it|what's the time|tell me the time|what is the current time)(?: please)?", text):
        return Route(Destination.DIRECT, 'explicit local clock request', 'get_current_time')
    app = re.fullmatch(r'(?:please )?(?:open|launch) (calculator|safari|textedit)(?: please)?', text)
    if app:
        name = {'calculator': 'Calculator', 'safari': 'Safari', 'textedit': 'TextEdit'}[app[1]]
        return Route(Destination.DIRECT, 'explicit launch of a known application', 'open_application', name)
    if re.fullmatch(r'(?:hello|hi|hey)(?: kuzco)?|good (?:morning|afternoon|evening)(?: kuzco)?|how are you(?: doing)?|thank you|thanks', text):
        return Route(Destination.FAST, 'short self-contained social exchange')
    if re.fullmatch(r"(?:what is|what's|explain|briefly explain) (?:an? |the )?(?:embedding|embeddings|rag|photosynthesis|python variable)(?: in simple terms)?", text):
        return Route(Destination.FAST, 'basic explanation of an allowlisted stable concept')
    return Route(Destination.REASONING, 'ambiguous, contextual, current, document, or complex request')
