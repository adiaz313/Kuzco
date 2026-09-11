"""Declarative local skill contract. These are trusted project modules, not web plugins."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    instructions: str
    tools: tuple[str, ...] | None
    llm_required: str
    execution: str
    context: str
    output: str
    matches: Callable
    plan: Callable = lambda prompt: None
