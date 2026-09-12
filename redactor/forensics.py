# SPDX-License-Identifier: GPL-3.0-or-later
"""Length-preserving surrogates with explicit network relationship validation.

IP relations mean equality and common binary prefix length, not routability or
geolocation. No substitute is contacted. Domain relations mean literal DNS suffixes.
"""
import ipaddress
import re
import secrets
import string


def domain(value, kind):
    return value.rsplit('@', 1)[-1] if kind == 'Email' else value if kind == 'Hostname' and '.' in value else None


def prefixes(a, b):
    a, b = ipaddress.ip_address(a), ipaddress.ip_address(b)
    if a.version != b.version: return None
    return a.max_prefixlen - (int(a) ^ int(b)).bit_length()


def suffix_pairs(original, replacement):
    left, right = original.split('.'), replacement.split('.')
    if len(left) != len(right): raise ValueError('R003: Domain label count must stay unchanged.')
    return [('.'.join(left[i:]).casefold(), '.'.join(right[i:])) for i in range(len(left))]


def validate_relationships(mappings, require_length=False):
    suffixes, inverse, ips = {}, {}, []
    for m in mappings:
        original, replacement, kind = m['original'], m['replacement'], m['kind']
        if require_length and len(original) != len(replacement):
            raise ValueError('R003: Replacement character length differs from original. Generate a same-length substitute.')
        left, right = domain(original, kind), domain(replacement, kind)
        if left:
            if not right or ('@' not in replacement and kind == 'Email'):
                raise ValueError('R003: Email must retain its local part and domain structure.')
            for a, b in suffix_pairs(left, right):
                if a in suffixes and suffixes[a].casefold() != b.casefold():
                    raise ValueError('R003: Shared domain suffixes have inconsistent substitutes. Update all related values together.')
                if b.casefold() in inverse and inverse[b.casefold()] != a:
                    raise ValueError('R003: Distinct original domains cannot collapse into the same substitute.')
                suffixes[a], inverse[b.casefold()] = b, a
        if kind == 'IP address':
            try:
                a, b = ipaddress.ip_address(original), ipaddress.ip_address(replacement)
                if a.version != b.version: raise ValueError()
            except ValueError as exc: raise ValueError('R003: Replacement must be a valid IP of the same version.') from exc
            for old, new in ips:
                if prefixes(original, old) != prefixes(replacement, new):
                    raise ValueError('R003: IP common-prefix relationships changed. Regenerate the related group in a fresh vault.')
            ips.append((original, replacement))


def shaped(original):
    return ''.join(secrets.choice(string.ascii_uppercase if c.isupper() else string.ascii_lowercase)
                   if c.isalpha() else secrets.choice(string.digits) if c.isdigit() else c for c in original)


def network_ip(original, mappings):
    address = ipaddress.ip_address(original)
    width = address.max_prefixlen
    mask, forced = 0, 0
    for m in mappings:
        if m['kind'] != 'IP address': continue
        old, new = ipaddress.ip_address(m['original']), ipaddress.ip_address(m['replacement'])
        if old.version != address.version: continue
        common = prefixes(original, str(old))
        bits = min(width, common + 1)
        bitmask = ((1 << bits) - 1) << (width - bits)
        required = int(new) & bitmask
        if common < width: required ^= 1 << (width - common - 1)
        if ((forced ^ required) & mask & bitmask):
            raise ValueError('R003: Existing IP mappings have incompatible prefixes.')
        forced = (forced & ~bitmask) | required
        mask |= bitmask
    if address.version == 4:
        parts = []
        for index, part in enumerate(original.split('.')):
            shift = (3-index)*8
            choices = [n for n in range(256) if len(str(n)) == len(part) and (n & ((mask >> shift)&255)) == ((forced >> shift)&255)]
            if not choices: raise ValueError('R003: No same-length IP fits existing prefix relationships. Start a new related group in a fresh vault.')
            parts.append(str(secrets.choice(choices)))
        return '.'.join(parts)
    # Keep explicit group lengths and compression notation; prune via forced bits.
    groups = original.split(':')
    missing = 8 - sum(bool(g) for g in groups)
    offset, expanded = 0, []
    for group in groups:
        if not group:
            if missing:
                for _ in range(missing):
                    shift = (7-offset)*16
                    if forced & (65535 << shift): raise ValueError('R003: IPv6 compression conflicts with saved prefix relationships.')
                    offset += 1
                missing = 0
            expanded.append(''); continue
        shift = (7-offset)*16
        group_mask, group_forced = (mask>>shift)&65535, (forced>>shift)&65535
        low = 0 if len(group) == 1 or group.startswith('0') else 16**(len(group)-1)
        choices = [n for n in range(low, 16**len(group)) if n & group_mask == group_forced]
        if not choices: raise ValueError('R003: IPv6 length conflicts with saved prefix relationships.')
        text = format(secrets.choice(choices), 'x').zfill(len(group))
        expanded.append(text.upper() if any(c.isupper() for c in group) else text)
        offset += 1
    return ':'.join(expanded)


def generate(original, kind, mappings, forbidden):
    known = {a: b for m in mappings if domain(m['original'], m['kind'])
             for a, b in suffix_pairs(domain(m['original'], m['kind']), domain(m['replacement'], m['kind']))}
    for _ in range(3000):
        if kind == 'IP address':
            value = network_ip(original, mappings)
        elif domain(original, kind):
            source_domain = domain(original, kind)
            labels = source_domain.split('.')
            changed = []
            for i, part in enumerate(labels):
                suffix = '.'.join(labels[i:]).casefold()
                if suffix in known:
                    changed.extend(known[suffix].split('.')); break
                changed.append(shaped(part))
            value = '.'.join(changed)
            if kind == 'Email': value = shaped(original.rsplit('@', 1)[0]) + '@' + value
        else:
            themes = ['Leia Organa', 'Luna Lovegood', 'Bilbo Baggins', 'Samwise Gamgee', 'Chani Kynes', 'CHOAM', 'Acme', 'Hogwarts', 'Arrakis', 'Tatooine']
            choices = [v for v in themes if len(v) == len(original)]
            value = secrets.choice(choices) if choices and secrets.randbelow(3) == 0 else shaped(original)
            if kind == 'Social security number':
                chars=list(value); digits=[i for i,c in enumerate(chars) if c.isdigit()]
                for index in digits[:3]:chars[index]='0'
                value=''.join(chars)  # invalid SSN area, still the same character count
            if kind == 'Credit card':
                from .engine import luhn
                if luhn(value):continue
        if value.casefold() == original.casefold(): continue
        # Exact collisions are never allowed; nested domain values are checked jointly.
        if any(value.casefold() == v.casefold() for v in forbidden if v): continue
        if forbidden and value.casefold() in forbidden[0].casefold(): continue
        proposal = {'original': original, 'replacement': value, 'kind': kind}
        try: validate_relationships([*mappings, proposal], require_length=False)
        except ValueError: continue
        from .engine import validate_mappings
        prospective=[{**m,'id':m.get('id',str(i))} for i,m in enumerate(mappings)]
        prospective.append({**proposal,'id':'proposed'})
        try: validate_mappings(prospective,source=forbidden[0] if forbidden else '',changed={'proposed'})
        except ValueError: continue
        return value
    raise ValueError('R003: No distinct same-length substitute fits the reviewed group. Correct the selection or start a fresh project vault.')
