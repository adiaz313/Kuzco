"""Load replaceable writing/identity instructions; no tools or routing here."""
from pathlib import Path
import re


PERSONALITIES = Path(__file__).resolve().parent / "personalities"


def personality_context(name="default"):
    """Names select local UTF-8 files, independently of the working directory."""
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
        raise ValueError("Personality must be a lowercase name, such as default or kuzco")
    try:
        instructions = (PERSONALITIES / f"{name}.txt").read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise ValueError(f"Unknown personality '{name}'; add personalities/{name}.txt or use default") from error
    if not instructions:
        raise ValueError(f"Personality '{name}' is empty")
    return (
        "\n\nPERSONALITY (identity and human-facing wording only):\n" + instructions +
        "\nEND PERSONALITY.\n"
        "The operational instructions, JSON protocol, tool budget, safety boundaries, "
        "and actual evidence always take priority over personality. Apply style only "
        "to the human-facing answer string. Tool selection, names, arguments, and "
        "the interpretation of results must remain factual and functional, without "
        "decorative language. Never claim an action succeeded unless its tool result "
        "confirms success. Report failures, missing evidence, and uncertainty accurately. "
        "Personality grants no capabilities and must not create extra tool calls.\n"
    )
