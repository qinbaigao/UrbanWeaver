"""Preserve explicit executable input, not keyword guesses about free-form prose.

Supports an embedded CitySpec JSON and qualified zones[i].architecture={...}
or numbered-zone architecture={...} assignments. Unqualified architecture is
city-wide. Natural language intent still belongs to the Requirement Agent.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy


def explicit_contract(text):
    contract = {}
    decoder = json.JSONDecoder()
    # A full embedded spec (the existing smoke/CLI workflow) is authoritative.
    for match in re.finditer(r'\{', text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        if isinstance(value, dict) and 'building_count' in value and 'zones' in value:
            for key, val in value.items():
                if key in contract and contract[key] != val:
                    raise ValueError(f'Conflicting explicit {key} constraints')
                contract[key] = val
    # Qualified assignments are recorded separately, so zone list containment
    # never gets mistaken for a city-wide architecture.
    assignments = []
    for match in re.finditer(r'\b(building_count|width_m|depth_m|min_floors|max_floors|seed|'
                             r'road_pattern|branch_road_ratio|river_mode|parcel_layout|morphology)\s*=\s*', text):
        tail = text[match.end():]
        try:
            value, _ = decoder.raw_decode(tail)
        except ValueError:
            word = re.match(r'[a-z][a-z_]*', tail)
            if not word:
                continue
            value = word[0]
        key = match[1]
        if key in contract and contract[key] != value:
            raise ValueError(f'Conflicting explicit {key} constraints')
        contract[key] = value
    pattern = r'(?:(zones\[(\d+)\])\.)?(architecture(?:\.envelope(?:_palette)?)?)\s*=\s*'
    for match in re.finditer(pattern, text):
        try:
            value, _ = decoder.raw_decode(text[match.end():])
        except ValueError:
            continue
        zone = int(match[2]) if match[2] is not None else None
        if zone is None:
            prefix = text[text.rfind('\n', 0, match.start())+1:match.start()]
            numbered = re.match(r'\s*(\d+)[.、．]\s*', prefix)
            if numbered:
                zone = int(numbered[1])-1
        path = (['zones', zone] if zone is not None else []) + match[3].split('.')
        assignments.append({'path': path, 'value': value})
    if assignments:
        contract['_assignments'] = assignments
    return contract


def constrained_response_schema(base_schema, contract):
    """Guide decoding with explicit fields, rather than retrying optional omissions.

    Array alternatives are keyed by explicit values; ordered subset validation
    remains authoritative after decoding. No model response is silently patched.
    """
    expected = deepcopy({k: v for k, v in contract.items() if k != '_assignments'})
    def combine(existing, new):
        if isinstance(existing, dict) and isinstance(new, dict):
            result = deepcopy(existing)
            for key, value in new.items():
                result[key] = combine(result[key], value) if key in result else deepcopy(value)
            return result
        if existing != new:
            raise ValueError('Conflicting explicit architecture constraints')
        return deepcopy(existing)
    for assignment in contract.get('_assignments', []):
        path = assignment['path']
        target = expected
        for index, key in enumerate(path):
            if isinstance(target, list):
                if key < 0 or key > 5:
                    raise ValueError('explicit zone index outside 0..5')
                while len(target) <= key:
                    target.append({})
            if index == len(path)-1:
                if isinstance(target, dict) and key in target:
                    target[key] = combine(target[key], assignment['value'])
                else:
                    target[key] = deepcopy(assignment['value'])
            else:
                if isinstance(target, dict) and key not in target:
                    target[key] = [] if isinstance(path[index+1], int) else {}
                target = target[key]

    def specialize(schema, value, *, exact_length=True):
        result = deepcopy(schema)
        if isinstance(value, dict):
            properties = result.get('properties', {})
            for key, val in value.items():
                if key not in properties:
                    raise ValueError(f'unsupported explicit requirement field: {key}')
                properties[key] = specialize(properties[key], val,
                    exact_length=not (key == 'zones' and 'zones' not in contract))
            result['required'] = sorted(set(result.get('required', [])) | set(value))
        elif isinstance(value, list):
            variants = [specialize(result.get('items', {}), v) for v in value]
            # A partial indexed assignment cannot constrain unrelated zones.
            if not exact_length:
                variants.append(deepcopy(result.get('items', {})))
            result['items'] = {'anyOf': variants} if variants else result.get('items', {})
            result['minItems'] = len(value)
            if exact_length:
                result['maxItems'] = len(value)
        else:
            result['const'] = value
        return result
    return specialize(base_schema, expected)


def check_explicit_contract(actual, expected):
    """Subset matching permits extra defaults, but never omitted explicit values."""
    def compare(a, e, path):
        if isinstance(e, dict):
            if not isinstance(a, dict):
                raise ValueError(f'explicit requirement missing: {path}')
            for key, value in e.items():
                if key not in a:
                    raise ValueError(f'explicit requirement missing: {path}.{key}')
                compare(a[key], value, f'{path}.{key}')
        elif isinstance(e, list):
            if not isinstance(a, list) or len(a) != len(e):
                raise ValueError(f'explicit list changed: {path}')
            for index, value in enumerate(e):
                compare(a[index], value, f'{path}[{index}]')
        elif a != e:
            raise ValueError(f'explicit requirement changed: {path}: expected {e!r}, got {a!r}')
    compare(actual, {k: v for k, v in expected.items() if k != '_assignments'}, 'spec')
    for assignment in expected.get('_assignments', []):
        a = actual
        try:
            for key in assignment['path']:
                a = a[key]
        except (KeyError, IndexError, TypeError):
            raise ValueError(f"explicit requirement missing: {assignment['path']}") from None
        compare(a, assignment['value'], str(assignment['path']))
