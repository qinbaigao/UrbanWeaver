"""Single-table seating explicitly requested in a meeting or dining space."""
import re

from cityg.inventory_provenance import _NUMBER_WORDS
from cityg.planning.room_constraints import circulation_check, ROOM_WALL_INSET_M
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.room_metric_frame import restore_metric_object


def seating_contracts(requirement):
    """Floor-wide furniture quantities alone do not specify one table's capacity."""
    inventory = requirement['inventory']
    for item in inventory:
        recipe = {'meeting_chair': ('meeting_table', 'meeting', '会议'),
                  'dining_chair': ('dining_table', 'dining', '餐')}.get(item['category'])
        if not recipe or item.get('count_basis') != 'explicit_number' or item['min_count'] < 2:
            continue
        anchor, word, chinese = recipe
        if not any(i['room_function'] == item['room_function'] and i['category'] == anchor for i in inventory):
            continue
        n = item['min_count']
        numbers = '|'.join([str(n), *(re.escape(k) for k,v in _NUMBER_WORDS.items() if v == n)])
        term = rf'(?:{numbers})'
        text = item.get('source_quote') or requirement['source_quote']
        # Match the specific group inside one clause of a possibly floor-wide quotation.
        group = rf'(?:{word} (?:area|room|table)|{"conference table" if word=="meeting" else "dining space"})'
        seats = rf'(?:seating for\s+{term}\b|(?:seats|for)\s+{term}\b|{term}\s+(?:seats|chairs|people)\b)'
        pattern = (rf'\b(?:a|an|one) {group}\b[^,.;。；，]{{0,65}}?{seats}|'
                   rf'\b{term}[- ](?:seat|person) {group}\b|'
                   rf'(?<![0-9零一二三四五六七八九十百]){term}\s*人(?:的)?{chinese}(?:室|桌|区)')
        if re.search(pattern, text, re.I):
            yield {'room_function':item['room_function'], 'anchor':anchor,
                   'seat':item['category'], 'required':n}


def check_seating(building, floor, contract):
    """Measure one complete group in one room, in the same metric frame as the compiler."""
    from cityg.planning.functional_configuration import paired_counts
    rows = []
    for room in floor.rooms:
        if room.function != contract['room_function']:
            continue
        objects = [o for o in floor.objects if o.room_id == room.id]
        if not any(o.category == contract['anchor'] for o in objects):
            continue
        env = metric_envelope(building, floor, room)
        if env['status'] != 'supported':
            continue
        try:
            physical = [restore_metric_object(o, building, floor, room, env) for o in objects]
        except ValueError:
            continue
        groups = paired_counts(physical, contract['anchor'], contract['seat'], facing=True)
        paired = max(groups, default=0)
        access = (circulation_check(physical, env['room'], env['floor'], env['bounds'].inset(ROOM_WALL_INSET_M))
                  if paired >= contract['required'] else {})
        rows.append({'room_id':room.id,'paired_at_one_table':paired,
                     'access_verified':bool(access.get('ok') and access.get('entrance_verified')),
                     'access_reason':access.get('reason')})
    return {**contract,'rooms':rows,'ok':any(q['paired_at_one_table'] >= contract['required']
                                               and q['access_verified'] for q in rows)}
