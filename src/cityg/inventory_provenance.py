"""Numeric provenance for model-extracted furniture minima, not a text planner."""
import re
from copy import deepcopy
import json


def ground_extraction_schema(schema, instruction):
    """Constrain quoted evidence to literal input spans, without interpreting it.

    Agents still choose meanings, ownership and categories. Source strings no
    longer need to be retyped from memory or paraphrased during JSON decoding.
    """
    schema=deepcopy(schema)
    item=schema['properties']['interior_requirements']['items']
    item['properties']['building_id']['enum']=[None,*dict.fromkeys(
        re.findall(r'\bbuilding_[A-Za-z0-9_]+\b',instruction))]
    starts=[m.start() for m in re.finditer(r'\b[Bb]uilding\s+[A-Z0-9]+\b|(?:建筑|楼栋)\s*[A-Z0-9]+',instruction)]
    spans=[instruction.strip()]
    spans.extend(instruction[a:b].strip() for a,b in zip(starts,starts[1:]+[len(instruction)]))
    item['properties']['source_quote']['enum']=list(dict.fromkeys(s for s in spans if s))
    # Distinguish presence minima from explicit quantities during decoding.
    inventory=item['properties']['inventory']; template=inventory['items']
    presence=deepcopy(template);explicit=deepcopy(template)
    presence['properties']['count_basis']['enum']=['presence']
    presence['properties']['min_count']={'type':'integer','const':1}
    explicit['properties']['count_basis']['enum']=['explicit_number']
    inventory['items']={'anyOf':[presence,explicit]}
    return schema


def deduplicate_identical_inventory(data):
    """Repeated identical predicates do not multiply a minimum requirement."""
    data=deepcopy(data)
    for row in data.get('interior_requirements',[]):
        if not isinstance(row,dict) or not isinstance(row.get('inventory'),list):continue
        seen=set();items=[]
        for item in row['inventory']:
            key=json.dumps(item,sort_keys=True,ensure_ascii=False)
            if key not in seen:items.append(item);seen.add(key)
        row['inventory']=items
    return data


def _number_words():
    small='zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
    tens='zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()
    chinese='零一二三四五六七八九'
    result={}
    for n in range(1,201):
        remainder=n%100
        tail=(small[remainder] if remainder<20 else tens[remainder//10]+(' '+small[remainder%10] if remainder%10 else ''))
        english=(small[n//100]+' hundred'+(' '+tail if remainder else '')) if n>=100 else tail
        result[english]=n
        if n>=100 and remainder:result[english.replace('hundred ','hundred and ')]=n
        if n<10:cn=chinese[n]
        elif n<100:cn=(chinese[n//10] if n>=20 else '')+'十'+(chinese[n%10] if n%10 else '')
        elif n==100:cn='一百'
        elif n==200:cn='二百'
        else:cn='一百'+(('零'+chinese[remainder]) if remainder<10 else (chinese[remainder//10]+'十'+(chinese[remainder%10] if remainder%10 else '')))
        result[cn]=n
    result['两']=2
    return result


_NUMBER_WORDS=_number_words()
_ENGLISH=re.compile(r'\b(?:'+ '|'.join(re.escape(w) for w in sorted(_NUMBER_WORDS,key=len,reverse=True) if w[0].isascii()) +r')\b')
_CHINESE=re.compile(r'[零一二三四五六七八九十百两]+')


def validate_inventory_source(item, requirement_quote):
    """Read legacy rows; new proposals carry a basis and inherit the source quote."""
    if 'count_basis' not in item and 'source_quote' not in item:
        return
    if item.get('count_basis') not in ('presence','explicit_number'):
        raise ValueError('Inventory count_basis must be presence or explicit_number')
    quote=item.get('source_quote',requirement_quote)
    if not isinstance(quote,str) or not quote.strip() or quote not in requirement_quote:
        raise ValueError(f"Inventory {item.get('category')} quote {quote!r} is not inside enclosing "
                         f"source_quote {requirement_quote!r}. Quote the FULL building-specific passage in "
                         'the enclosing requirement, including its functions and furniture, not just the area sentence.')
    if item['count_basis']=='presence':
        if item['min_count']!=1:
            raise ValueError('Unnumbered furniture has presence minimum 1, not an invented hard capacity; choose extra furniture downstream')
        return
    numbers={int(x) for x in re.findall(r'(?<![\d.])\d+(?![\d.])',quote)}
    numbers.update(_NUMBER_WORDS[w] for w in _ENGLISH.findall(quote.lower().replace('-',' ')))
    numbers.update(_NUMBER_WORDS[w] for w in _CHINESE.findall(quote) if w in _NUMBER_WORDS)
    if item['min_count'] not in numbers:
        raise ValueError(f"Inventory minimum {item['min_count']} has no matching number in source_quote; "
                         'retain the explicitly quoted count, or use presence minimum 1 for an unnumbered item')
