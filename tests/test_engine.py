# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
import copy
import pytest
from redactor.engine import Candidate, detect, prepare_mappings, replace_exact, restore, validate_mappings, suggest


def test_all_requested_types_roundtrip():
    text = "Tavi Quill works at Zephyr Quill Company (ZQC) with MossQuill / QZRA. Host prod-server.example.com: 10.2.3.4. SSN 123-45-6789. Card 4111 1111 1111 1111."
    candidates = detect(text, [])
    by_value = {c.original: c.kind for c in candidates}
    for value in ["Tavi Quill", "Zephyr Quill Company", "ZQC", "MossQuill", "QZRA", "prod-server.example.com", "10.2.3.4", "123-45-6789", "4111 1111 1111 1111"]:
        assert value in by_value
    mappings, conversions = prepare_mappings(candidates, [], text)
    output, counts = replace_exact(text, conversions)
    assert counts
    for value in conversions: assert value not in output
    assert restore(output, mappings)[0] == text


@pytest.mark.parametrize("value", ["10.0.0.1", "192.168.4.20", "::1", "2001:db8::5", "fe80::abcd"])
def test_ips_with_punctuation(value):
    assert any(c.original == value and c.kind == "IP address" for c in detect(f"Address: {value}.", []))


def test_invalid_card_not_selected():
    assert not any(c.kind == "Credit card" for c in detect("4111 1111 1111 1112", []))


def test_simultaneous_longest_and_boundaries():
    output, counts = replace_exact("ZQC ZQCx ZQC Corp ZQC", {"ZQC": "ABC", "ZQC Corp": "XYZ", "ABC": "NO"})
    assert output == "ABC ZQCx XYZ ABC"
    assert counts == {"ZQC": 2, "ZQC Corp": 1}


def test_manual_multiline_unicode_exact():
    text = "😀 Confidential\n東京の研究 — Néro Lúmivex"
    candidates = [Candidate("東京の研究", "Custom", "REDACTED-R1234ABCD", "manual"), Candidate("Néro Lúmivex", "Personal name", "Leia Organa RABC12345", "manual")]
    mappings, conversions = prepare_mappings(candidates, [], text)
    assert restore(replace_exact(text, conversions)[0], mappings)[0] == text


def test_old_alias_retained_after_replacement_edit():
    candidates = [Candidate("Tavi Quill", "Personal name", "Leia Organa R1234ABCD", "manual")]
    mappings, _ = prepare_mappings(candidates, [], "Tavi Quill")
    candidates[0].replacement = "Luna Lovegood R5678ABCD"
    updated, _ = prepare_mappings(candidates, mappings, "Tavi Quill")
    assert restore("Leia Organa R1234ABCD and Luna Lovegood R5678ABCD", updated)[0] == "Tavi Quill and Tavi Quill"
    assert mappings[0]["aliases"] == []


def test_delete_removes_restoration():
    mappings, _ = prepare_mappings([Candidate("Secret", "Custom", "R1234ABCD", "manual")], [], "Secret")
    assert restore("R1234ABCD", [])[0] == "R1234ABCD"
    assert restore("R1234ABCD", mappings)[0] == "Secret"


@pytest.mark.parametrize("replacement", ["", " Tavi ", "Tavi Quill", "Tavi Quill alias", "x\ny"])
def test_unsafe_replacements_rejected(replacement):
    with pytest.raises(ValueError):
        prepare_mappings([Candidate("Tavi Quill", "Personal name", replacement, "manual")], [], "Tavi Quill")


def test_natural_replacement_collision_rejected():
    with pytest.raises(ValueError, match="already appears"):
        prepare_mappings([Candidate("Secret", "Custom", "Public", "manual")], [], "Secret and Public")


def test_duplicate_and_nested_replacements_rejected():
    for second in ["Alias", "Alias Two", "alias"]:
        with pytest.raises(ValueError):
            prepare_mappings([Candidate("One", "Custom", "Alias", "manual"), Candidate("Two", "Custom", second, "manual")], [], "One Two")


def test_existing_replacement_input_rejected():
    mappings, _ = prepare_mappings([Candidate("Secret", "Custom", "R1234ABCD", "manual")], [], "Secret")
    with pytest.raises(ValueError, match="existing replacement"):
        prepare_mappings([], mappings, "Secret and R1234ABCD")


def test_restore_does_not_guess_changed_spelling():
    mappings, _ = prepare_mappings([Candidate("Secret", "Custom", "Leia Organa R1234ABCD", "manual")], [], "Secret")
    result, counts, unknown = restore("leia organa R1234ABCD", mappings)
    assert result == "leia organa R1234ABCD" and not counts and unknown


def test_unselected_not_mapped():
    mappings, conversions = prepare_mappings([Candidate("Secret", "Custom", "R1234ABCD", "manual", False)], [], "Secret")
    assert mappings == [] and conversions == {}


def test_random_ips_are_documentation_only():
    values = [suggest("IP address", []) for _ in range(20)]
    assert all(v.startswith(("192.0.2.", "198.51.100.", "203.0.113.")) for v in values)


def test_occurrence_replacement_rejects_conflicting_overlap():
    from redactor.engine import replace_candidates
    text = "ZQC Corp and ZQC"
    candidates = [Candidate("ZQC Corp", "Business", "Acme R11111111", "test"),
                  Candidate("ZQC", "Business", "Wonka R22222222", "test", True, {13})]
    with pytest.raises(ValueError, match="overlap"):
        replace_candidates(text, candidates, {c.original: c.replacement for c in candidates})
