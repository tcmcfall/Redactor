# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
"""Conservative offline candidate detection and exact, simultaneous substitution."""
from __future__ import annotations

import ipaddress
import re
import secrets
import uuid
import unicodedata
from difflib import SequenceMatcher
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from .vault import now

KINDS = ["Business", "IP address", "Hostname", "Personal name", "Social security number", "Credit card", "Email", "Custom"]
PEOPLE = ["Hermione Granger", "Leia Organa", "Samwise Gamgee", "Chani Kynes", "Luna Lovegood", "Bilbo Baggins", "Lando Calrissian"]
BUSINESSES = ["Stark Industries", "Ollivanders", "CHOAM", "Wonka Industries", "Acme Corporation", "Wayne Enterprises"]
HOSTS = ["hogwarts", "tatooine", "bag-end", "arrakis", "rivendell", "millennium-falcon"]


@dataclass
class Candidate:
    original: str
    kind: str
    replacement: str
    reason: str
    selected: bool = True
    included_starts: set[int] | None = None


@dataclass
class SimilarValue:
    imported: str
    original: str
    replacement: str
    reason: str
    score: float


def _normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _one_typo(left, right):
    if abs(len(left) - len(right)) > 1: return False
    if len(left) == len(right):
        positions = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        return len(positions) == 1 or (len(positions) == 2 and positions[1] == positions[0] + 1
                                      and left[positions[0]] == right[positions[1]] and left[positions[1]] == right[positions[0]])
    shorter, longer = sorted([left, right], key=len)
    index = next((i for i, (a, b) in enumerate(zip(shorter, longer)) if a != b), len(shorter))
    return shorter[index:] == longer[index+1:]


def find_similar_values(text: str, mappings: list[dict], denied=None, limit=50) -> list[SimilarValue]:
    """Suggest near originals only; never normalize or link them automatically.

    Uses bounded phrase lengths and length-indexed comparisons. A review batch
    contains at most 50 distinct variants; subsequent scans continue review.
    """
    denied = denied or set()
    token_pattern = re.compile(r"\w+(?:[.'’:@/\-]\w+)*", re.UNICODE)
    exact = {m["original"] for m in mappings}
    aliases = {alias for m in mappings for alias in [m["replacement"], *m.get("aliases", [])]}
    tokens = list(token_pattern.finditer(text))
    groups = {}
    for mapping in mappings:
        normalized = _normalized(mapping["original"])
        size = len(token_pattern.findall(mapping["original"]))
        if 3 <= len(normalized) <= 160 and 1 <= size <= 8:
            groups.setdefault(size, []).append((len(normalized), normalized, mapping))
    found = {}
    for size, entries in groups.items():
        entries.sort(key=lambda entry: entry[0])
        lengths = [entry[0] for entry in entries]
        seen = set()
        for index in range(len(tokens) - size + 1):
            start, end = tokens[index].start(), tokens[index+size-1].end()
            value = text[start:end]
            if value in seen or value in exact or value in aliases or "\n" in value: continue
            seen.add(value)
            normalized = _normalized(value)
            length = len(normalized)
            if length < 3 or length > 160: continue
            tolerance = max(1, min(3, length // 8))
            low, high = bisect_left(lengths, length-tolerance), bisect_right(lengths, length+tolerance)
            for _, canonical, mapping in entries[low:high]:
                if (value, mapping["original"]) in denied: continue
                if normalized == canonical:
                    score, reason = 1.0, "Capitalization, spacing or Unicode form differs"
                elif _one_typo(normalized, canonical):
                    score, reason = .95, "One character differs or adjacent characters are transposed"
                elif min(length, len(canonical)) >= 8:
                    matcher = SequenceMatcher(None, normalized, canonical, autojunk=False)
                    if matcher.quick_ratio() < .88: continue
                    score = matcher.ratio()
                    if score < .88: continue
                    reason = "Similar spelling; verify carefully"
                else:
                    continue
                existing = found.get(value)
                if existing is None or score > existing.score:
                    found[value] = SimilarValue(value, mapping["original"], mapping["replacement"], reason, score)
    # The source is not modified; only the UI can authorize a normalization.
    return sorted(found.values(), key=lambda item: (text.find(item.imported), -len(item.imported)))[:limit]


def candidate_occurrences(text: str, candidate: Candidate):
    return [(m.start(), m.end()) for m in literal_pattern([candidate.original]).finditer(text)]


def occurrence_selected(candidate: Candidate, start: int) -> bool:
    return candidate.selected and (candidate.included_starts is None or start in candidate.included_starts)


def replace_candidates(text: str, candidates: list[Candidate], conversions: dict[str, str]):
    """Apply reviewed positions, preserving intentionally excluded occurrences."""
    selected, excluded = [], []
    for candidate in candidates:
        for start, end in candidate_occurrences(text, candidate):
            if occurrence_selected(candidate, start):
                selected.append((start, end, candidate.original))
            else:
                excluded.append((start, end, candidate.original))
    for start, end, original in selected:
        conflicts = [(left, right, value) for left, right, value in excluded if start < right and left < end]
        if conflicts:
            left, right, value = conflicts[0]
            raise ValueError(f"R002: Selected {original!r} at character {start + 1} overlaps excluded {value!r} at character {left + 1}. In Suggested substitutions, either mark both sensitive (the longest value wins), or mark the larger value insensitive and select only the part you intend to replace. Use All same values only if that scope is intended.")
    edits, cursor = [], 0
    for start, end, original in sorted(selected, key=lambda item: (item[0], -(item[1] - item[0]))):
        if start < cursor: continue
        edits.append((start, end, original))
        cursor = end
    parts, counts, cursor = [], {}, 0
    for start, end, original in edits:
        parts.extend([text[cursor:start], conversions[original]])
        counts[original] = counts.get(original, 0) + 1
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), counts


def literal_pattern(values: list[str]) -> re.Pattern:
    # Each alternative gets its own boundaries, including punctuation-ended selections.
    ordered = sorted(set(values), key=len, reverse=True)
    return re.compile("|".join((r"(?<!\w)" if v[0].isalnum() or v[0] == "_" else "") + re.escape(v) +
                               (r"(?!\w)" if v[-1].isalnum() or v[-1] == "_" else "") for v in ordered))


def replace_exact(text: str, conversions: dict[str, str]) -> tuple[str, dict[str, int]]:
    if not conversions:
        return text, {}
    counts: dict[str, int] = {}
    def swap(match):
        value = match.group()
        counts[value] = counts.get(value, 0) + 1
        return conversions[value]
    return literal_pattern(list(conversions)).sub(swap, text), counts


def luhn(value: str) -> bool:
    digits = [int(c) for c in value if c.isdigit() and c.isascii()]
    if len(digits) < 13 or len(digits) > 19 or len(set(digits)) == 1:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit = digit * 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def suggest(kind: str, forbidden: list[str], original: str = "", mappings=None) -> str:
    if original:
        from .forensics import generate
        return generate(original, kind, mappings or [], forbidden)
    for _ in range(3000):
        token = secrets.token_hex(4).upper()
        if kind == "IP address":
            if ":" in original:
                value = f"2001:db8:{secrets.randbelow(65536):x}:{secrets.randbelow(65536):x}::{secrets.randbelow(65535) + 1:x}"
            else:
                value = f"{secrets.choice(['192.0.2', '198.51.100', '203.0.113'])}.{secrets.randbelow(254) + 1}"
        elif kind == "Hostname":
            value = f"{secrets.choice(HOSTS)}-r{token.lower()}.example.invalid"
        elif kind == "Personal name":
            value = f"{secrets.choice(PEOPLE)} R{token}"
        elif kind == "Business":
            value = f"{secrets.choice(BUSINESSES)} R{token}"
        elif kind == "Social security number":
            value = f"R{token}-000"
        elif kind == "Credit card":
            value = f"R{token}-0000"
        elif kind == "Email":
            value = f"owl-r{token.lower()}@example.invalid"
        else:
            value = f"REDACTED-R{token}"
        if all(value.casefold() not in x.casefold() and x.casefold() not in value.casefold() for x in forbidden if x):
            return value
    raise ValueError("No unambiguous replacement available. Use a custom replacement.")


def detect(text: str, mappings: list[dict]) -> list[Candidate]:
    found: dict[str, tuple[str, str]] = {}
    known = {m["original"]: m for m in mappings}
    for original, mapping in known.items():
        if literal_pattern([original]).search(text):
            found[original] = (mapping["kind"], "Saved mapping")
    def add(pattern, kind, reason, flags=0, validator=None):
        for match in re.finditer(pattern, text, flags):
            value = match.group().strip()
            if not validator or validator(value):
                found.setdefault(value, (kind, reason))
    add(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\w|\.\d)", "IP address", "IPv4 address", validator=valid_ip)
    add(r"(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(?![\w:])", "IP address", "IPv6 address", validator=valid_ip)
    add(r"(?<!\d)\d{3}[- ]\d{2}[- ]\d{4}(?!\d)", "Social security number", "SSN-shaped value; review")
    add(r"(?<!\d)\d{9}(?!\d)", "Social security number", "Nine-digit identifier; review")
    add(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)", "Credit card", "Card number passes Luhn check", validator=luhn)
    add(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "Email", "Email address")
    add(r"(?<![\w@.-])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[A-Za-z]{2,63}\b", "Hostname", "Domain or fully qualified hostname")
    add(r"\b[A-Za-z]+(?:-[A-Za-z0-9]+)+\b", "Hostname", "Possible short hostname; review")
    add(r"\b(?:International Business Machines|IBM|Ginnie\s?Mae|GNMA|Microsoft|Google|Amazon|Apple|OpenAI)\b", "Business", "Business dictionary", re.I)
    add(r"\b(?:[A-Z][\w&'-]*[ \t]+){1,5}(?:Inc\.?|LLC|Ltd\.?|Corporation|Corp\.?|Company|Industries|Bank|Agency)\b", "Business", "Organization suffix; review")
    add(r"\b[A-Z][A-Z0-9&]{1,9}\b", "Business", "Possible business abbreviation; review")
    add(r"\b[A-Z][a-z]+(?:['’-][A-Z]?[a-z]+)?(?:[ \t]+(?:[A-Z]\.\s*)?[A-Z][a-z]+(?:['’-][A-Z]?[a-z]+)?){1,2}\b", "Personal name", "Possible personal name; review")
    forbidden = [text, *found] + [v for m in mappings for v in [m["original"], m["replacement"], *m.get("aliases", [])]]
    candidates = []
    related = list(mappings)
    # Allocate the most textually constrained IPs first (e.g. ::1), so a broad
    # address does not consume a prefix that the short form cannot represent.
    entries = sorted(found.items(), key=lambda item: (0, len(item[0])) if item[1][0] == 'IP address' else (1, text.find(item[0])))
    for original, (kind, reason) in entries:
        replacement = known[original]["replacement"] if original in known else suggest(kind, forbidden, original, related)
        forbidden.append(replacement)
        candidates.append(Candidate(original, kind, replacement, reason))
        if original not in known: related.append({"original": original, "replacement": replacement, "kind": kind})
    return sorted(candidates, key=lambda c: text.find(c.original))


def valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def validate_mappings(mappings: list[dict], source: str = "", changed: set[str] | None = None, strict=False) -> None:
    if strict:
        from .forensics import validate_relationships
        validate_relationships(mappings, require_length=True)
    originals = {m["original"] for m in mappings}
    if len(originals) != len(mappings):
        raise ValueError("Each exact original must have one mapping.")
    tokens: dict[str, str] = {}
    for m in mappings:
        if m["kind"] not in KINDS: raise ValueError("R010: Choose one of the supported sensitive value types.")
        if not m["original"].strip():
            raise ValueError("A sensitive value cannot be empty.")
        for token in [m["replacement"], *m.get("aliases", [])]:
            if not token.strip() or token != token.strip() or "\n" in token or len(token) > 300:
                raise ValueError("Replacements must be nonempty single lines up to 300 characters, without outer spaces.")
            conflict = next((original for original in originals if literal_pattern([token.casefold()]).search(original.casefold()) or literal_pattern([original.casefold()]).search(token.casefold())), None)
            if conflict:
                raise ValueError(f"R002: Replacement {token!r} for {m['original']!r} overlaps sensitive value {conflict!r}. Edit that replacement or generate another suggestion. The conflicting rows may be in the saved vault as well as the current input.")
            for existing, owner in tokens.items():
                if literal_pattern([token.casefold()]).search(existing.casefold()) or literal_pattern([existing.casefold()]).search(token.casefold()):
                    if token == existing and owner == m["id"]:
                        continue
                    other = next(v for v in mappings if v["id"] == owner)
                    from .forensics import domain
                    if token != existing and domain(m["original"], m["kind"]) and domain(other["original"], other["kind"]):
                        left, right = m["original"].casefold(), other["original"].casefold()
                        if (left in right) == (token.casefold() in existing.casefold()) and (right in left) == (existing.casefold() in token.casefold()):
                            continue
                    raise ValueError(f"R002: Replacements overlap or are duplicated: {token!r} for {m['original']!r} conflicts with {existing!r} for {other['original']!r}. Generate another suggestion or edit these two rows.")
            tokens[token] = m["id"]
        if source and (changed is None or m["id"] in changed) and literal_pattern([m["replacement"].casefold()]).search(source.casefold()):
            raise ValueError("A suggested replacement already appears in the input. Generate another replacement.")


def prepare_mappings(candidates: list[Candidate], existing: list[dict], source: str, strict=False) -> tuple[list[dict], dict[str, str]]:
    import copy
    for mapping in existing:
        for alias in [mapping["replacement"], *mapping.get("aliases", [])]:
            if literal_pattern([alias]).search(source):
                raise ValueError("The input contains an existing replacement. Use Restore first to avoid ambiguous or double substitutions.")
    mappings = copy.deepcopy(existing)
    by_original = {m["original"]: m for m in mappings}
    changed, conversions = set(), {}
    for c in candidates:
        if not c.selected:
            continue
        if c.original in by_original:
            mapping = by_original[c.original]
            if mapping["replacement"] != c.replacement:
                mapping["aliases"] = list(dict.fromkeys([*mapping.get("aliases", []), mapping["replacement"]]))
                mapping["aliases"] = [a for a in mapping["aliases"] if a != c.replacement]
                mapping["replacement"] = c.replacement
                changed.add(mapping["id"])
        else:
            mapping = {"id": uuid.uuid4().hex, "original": c.original, "replacement": c.replacement,
                       "kind": c.kind, "aliases": [], "created": now()}
            mappings.append(mapping)
            by_original[c.original] = mapping
            changed.add(mapping["id"])
        conversions[c.original] = c.replacement
    validate_mappings(mappings, source, changed, strict=strict)
    return mappings, conversions


def restore(text: str, mappings: list[dict]) -> tuple[str, dict[str, int], list[str]]:
    conversions = {alias: m["original"] for m in mappings for alias in [m["replacement"], *m.get("aliases", [])]}
    restored, counts = replace_exact(text, conversions)
    unknown = sorted(set(re.findall(r"\b(?:[\w.-]*[Rr][0-9A-Fa-f]{8})\b", restored)))
    return restored, counts, unknown
