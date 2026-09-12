# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
from redactor.engine import find_similar_values

MAPPINGS = [{"original": "Jane Smith", "replacement": "Leia Organa R12345678", "id": "one"}]


def test_similarity_suggests_case_and_typos_without_changing_text():
    text = "jane smith; Jnae Smith; Jane Smyth; Jane Smith."
    matches = find_similar_values(text, MAPPINGS)
    assert {match.imported for match in matches} == {"jane smith", "Jnae Smith", "Jane Smyth"}
    assert all(match.original == "Jane Smith" for match in matches)
    assert text == "jane smith; Jnae Smith; Jane Smyth; Jane Smith."


def test_exact_known_values_and_denied_matches_not_suggested():
    mappings = MAPPINGS + [{"original": "Jane Smyth", "replacement": "Luna R23456789"}]
    assert find_similar_values("Jane Smith; Jane Smyth; jane smith", mappings,
                               {("jane smith", "Jane Smith"), ("jane smith", "Jane Smyth")}) == []


def test_distant_values_not_suggested():
    assert find_similar_values("Mary Jones; Random reports and ordinary text.", MAPPINGS) == []


def test_numeric_near_match_requires_review_too():
    mappings = [{"original": "10.2.3.4", "replacement": "192.0.2.8"}]
    matches = find_similar_values("10.2.3.5", mappings)
    assert matches and matches[0].imported == "10.2.3.5"
