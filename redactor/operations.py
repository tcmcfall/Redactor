# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared, transactional operations used by GUI and CLI."""
import copy
import hashlib
from difflib import SequenceMatcher
from .engine import validate_mappings


def text_changes(before, after):
    if max(len(before),len(after)) > 20000:
        # Bound diff cost for large evidence; a complete before/after span is exact.
        return [] if before == after else [{'input_start':0,'input_end':len(before),
                'output_start':0,'output_end':len(after),'before':before,'after':after}]
    return [{'input_start': a, 'input_end': b, 'output_start': c, 'output_end': d,
             'before': before[a:b], 'after': after[c:d]}
            for op, a, b, c, d in SequenceMatcher(None, before, after, autojunk=False).get_opcodes() if op != 'equal']


def audit_text(vault, action, before, after, **details):
    # Full touched text is encrypted with the vault; exact offsets are Unicode code points.
    vault.commit(action, input_text=before, output_text=after,
                 input_sha256=hashlib.sha256(before.encode()).hexdigest(),
                 output_sha256=hashlib.sha256(after.encode()).hexdigest(),
                 text_changes=text_changes(before, after), **details)


def bulk_proposal(mappings, ids, field, find, replacement):
    if field not in ('original', 'replacement', 'kind'): raise ValueError('R010: Invalid field.')
    if not find: raise ValueError('R010: Enter nonempty text to find.')
    proposed = copy.deepcopy(mappings)
    for m in proposed:
        if m['id'] not in ids: continue
        old = m[field]
        m[field] = old.replace(find, replacement)
        if field == 'replacement' and m[field] != old:
            m['aliases'] = list(dict.fromkeys([*m.get('aliases', []), old]))
            m['aliases'] = [v for v in m['aliases'] if v != m[field]]
    validate_mappings(proposed, strict=True)
    return proposed


def save_mappings(vault, proposed, action, ids):
    old = copy.deepcopy(vault.data)
    try:
        vault.data['mappings'] = proposed
        vault.commit(action, mapping_ids=sorted(ids))
    except Exception:
        vault.data = old
        raise
