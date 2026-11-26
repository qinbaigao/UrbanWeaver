"""Ground explicit, named building uses in the original brief across sentence boundaries."""
import re


_TYPES = {
    'residential': 'residential', 'apartment': 'residential', '住宅': 'residential', '公寓': 'residential',
    'commercial': 'commercial', 'office': 'commercial', 'retail': 'commercial',
    '商业': 'commercial', '办公': 'commercial', '商用': 'commercial',
    'mixed use': 'mixed_use', 'mixed-use': 'mixed_use', '混合用途': 'mixed_use',
    'public': 'public_service', '公共服务': 'public_service',
    'industrial': 'industrial', '工业': 'industrial',
}
_KIND = '|'.join(sorted(_TYPES, key=len, reverse=True))
# A short, case-sensitive identifier avoids reading ordinary following words as names.
_LABEL = r'(?P<label>[A-Z][A-Z0-9]{0,7}|[0-9]{1,4})(?![A-Za-z0-9_])'
_TYPE = '(?P<kind>(?i:' + _KIND + '))'
_PATTERNS = [
    re.compile(r'\b' + _TYPE + r'\s+(?i:building)\s+' + _LABEL),
    re.compile(r'\b(?i:building)\s+' + _LABEL + r'\s+(?i:is|shall be|must be)\s+(?i:an?\s+)?' +
               _TYPE + r'\b(?:\s+(?i:building))?'),
    re.compile(_TYPE + r'(?:建筑|楼栋|楼)\s*' + _LABEL),
    re.compile(r'(?:建筑|楼栋)\s*' + _LABEL + r'\s*(?:是|为|用作)\s*' + _TYPE),
    re.compile(_LABEL + r'\s*(?:号楼|栋|楼)\s*(?:是|为|用作)\s*' + _TYPE),
]


def label_key(label):
    value = re.sub(r'^(?:building\s+|建筑\s*|楼栋\s*)', '', label.strip(), flags=re.I)
    return re.sub(r'(?:号楼|栋|楼)$', '', value).upper()


def named_building_uses(instruction):
    """Only affirmative, explicit labels ground a carrier. Other uses remain agent decisions."""
    claims = {}
    for clause in re.split(r'[.;!?。；！？\n]', instruction or ''):
        if re.search(r'\b(?:if|possibly|either|instead of|not|never|except|may|could|or)\b|如果|或|而非|不是|不要|不得|不应|可能', clause, re.I):
            continue
        for pattern in _PATTERNS:
            for m in pattern.finditer(clause):
                name = m['label']
                value = _TYPES[m['kind'].lower()]
                claims.setdefault(name, {})[value] = m[0]
    return {label: {'function': next(iter(uses)), 'quote': next(iter(uses.values()))}
            for label, uses in claims.items() if len(uses) == 1}


def ground_named_uses(rows, instruction):
    """Set only textually explicit carriers before validating their supported room functions."""
    claims = named_building_uses(instruction)
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get('label'), str):
            claim = claims.get(label_key(row['label']))
            if claim:
                row['building_function'] = claim['function']
