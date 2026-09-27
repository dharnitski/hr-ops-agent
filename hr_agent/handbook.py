"""Handbook retrieval tool. Keyword scoring over sections; the corpus is small enough that
embeddings would add cost without adding accuracy."""

import re
from pathlib import Path
from typing import Any

HANDBOOK_PATH = Path(__file__).parent / "data" / "handbook.md"
MAX_RESULTS = 3
TITLE_WEIGHT = 3

_STOPWORDS = frozenset(
    {
        *("a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for"),
        *("from", "how", "i", "in", "is", "it", "many", "much", "my", "of", "on", "or"),
        *("the", "to", "what", "when", "where", "which", "who", "will", "with"),
    }
)


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS}


def _load_sections(path: Path) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for block in re.split(r"^## ", path.read_text(), flags=re.MULTILINE)[1:]:
        title, _, body = block.partition("\n")
        sections.append((title.strip(), " ".join(body.split())))
    return sections


_SECTIONS = _load_sections(HANDBOOK_PATH)


def score_section(query_tokens: set[str], title: str, body: str) -> int:
    """Body-token overlap plus TITLE_WEIGHT per title-token overlap."""
    return len(query_tokens & _tokenize(body)) + TITLE_WEIGHT * len(query_tokens & _tokenize(title))


def search_handbook(query: str) -> dict[str, Any]:
    """Search the company employee handbook for policy text.

    Use for questions about company policy: PTO accrual and carryover, approval rules, sick
    leave, parental leave, remote work, expenses, payroll schedule. Not for an individual
    employee's balances or requests.

    Args:
        query: Keywords or a short question, e.g. "PTO carryover".

    Returns:
        On success: {"status": "success", "results": [{"section", "text"}, ...]}, best match
        first. If nothing matches: {"status": "not_found", "message", "available_sections"}.
        On empty query: {"status": "error", "error": <reason>}.
    """
    tokens = _tokenize(query)
    if not tokens:
        return {
            "status": "error",
            "error": "Query is empty. Provide keywords such as 'PTO carryover'.",
        }
    scored = sorted(
        ((score_section(tokens, title, body), i) for i, (title, body) in enumerate(_SECTIONS)),
        key=lambda s: (-s[0], s[1]),
    )
    results = [
        {"section": _SECTIONS[i][0], "text": _SECTIONS[i][1]}
        for score, i in scored[:MAX_RESULTS]
        if score > 0
    ]
    if not results:
        return {
            "status": "not_found",
            "message": f"The handbook has no section matching '{query}'.",
            "available_sections": [title for title, _ in _SECTIONS],
        }
    return {"status": "success", "results": results}
