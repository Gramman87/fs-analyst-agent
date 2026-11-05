"""The eval's scoring rules, kept apart from the API calls so they can be tested offline."""

from __future__ import annotations

import json
import re
from typing import Any

JUDGE_DIMENSIONS = ("accuracy", "specificity", "decisiveness")
MIN_JUDGE_SCORE = 3

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        **{dimension: {"type": "integer"} for dimension in JUDGE_DIMENSIONS},
        "critique": {"type": "string"},
    },
    "required": [*JUDGE_DIMENSIONS, "critique"],
    "additionalProperties": False,
}

FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def check_routing(called: set[str], expected: set[str]) -> bool:
    return expected.issubset(called)


def check_coverage(memo: str, terms: list[str]) -> list[str]:
    """Return the required terms the memo misses. Matching is on whole words, plural allowed, so
    'rate' isn't satisfied by 'corporate'. A term can list alternatives as 'a|b'."""
    missing = []
    for term in terms:
        options = "|".join(re.escape(option) for option in term.split("|"))
        if not re.search(rf"\b(?:{options})s?\b", memo, re.IGNORECASE):
            missing.append(term)
    return missing


def parse_judge(text: str) -> dict[str, Any]:
    """Parse the judge's reply. A reply that can't be read is an error, never a low score."""
    try:
        judge = json.loads(text)
    except json.JSONDecodeError:
        return {"judge_error": "judge returned non-JSON"}
    if not isinstance(judge, dict):
        return {"judge_error": "judge returned non-object JSON"}
    for dimension in JUDGE_DIMENSIONS:
        score = judge.get(dimension)
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
            return {"judge_error": f"judge gave an invalid {dimension} score: {score!r}"}
    return judge


def case_passed(result: dict[str, Any]) -> bool:
    if "error" in result or not result.get("routing_pass") or not result.get("coverage_pass"):
        return False
    judge = result.get("judge", {})
    if "judge_error" in judge:
        return False
    return all(judge[dimension] >= MIN_JUDGE_SCORE for dimension in JUDGE_DIMENSIONS)


def _normalize(figure: str) -> str:
    plain = figure.replace(",", "")
    return plain.rstrip("0").rstrip(".") if "." in plain else plain


def unsupported_figures(memo: str, briefings: list[str], holdings: dict[str, float]) -> list[str]:
    """Figures in the memo with no source in the briefings or the portfolio.

    Weights are matched as percentages too, since 0.3 usually appears as 30%. Integers under 10 are
    skipped because they're mostly ordinary prose ("3 risks", "Q2").
    """
    known = {_normalize(f) for text in briefings for f in FIGURE.findall(text)}
    for weight in holdings.values():
        known.update({_normalize(str(weight)), _normalize(f"{weight * 100:.2f}")})

    unsupported = []
    for figure in FIGURE.findall(memo):
        normalized = _normalize(figure)
        if normalized in known or ("." not in normalized and int(normalized) < 10):
            continue
        if figure not in unsupported:
            unsupported.append(figure)
    return unsupported
