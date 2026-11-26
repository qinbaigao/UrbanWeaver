"""Allocate floor-level furniture deficits without duplicating each room's target.

Only same-function rooms can share a requirement. Tables and their seating stay
in one functional bundle; final acceptance still checks the original floor.
"""
from collections import Counter
from cityg.interior_requirements import inventory_for

_BUNDLES=(frozenset({'desk','office_chair'}),
          frozenset({'dining_table','dining_chair'}),
          frozenset({'meeting_table','meeting_chair'}),
          frozenset({'sofa','coffee_table'}),
          frozenset({'bed','wardrobe'}),
          frozenset({'kitchen_counter','cabinet'}))


def allocate_remaining_inventory(building, floor, function, *, excluded=()):
    """Split semantic bundles, never dimensions or an explicitly requested seat count."""
    rooms=[r for r in floor.rooms if r.function==function and r.id not in excluded]
    if not rooms:return {}
    all_ids={r.id for r in floor.rooms if r.function==function}
    counts=Counter(o.category for o in floor.objects if o.room_id in all_ids)
    pending=[{**i,'min_count':i['min_count']-counts[i['category']]}
             for i in inventory_for(building,floor.level,function) if i['min_count']>counts[i['category']]]
    bundles=[];seen=set()
    for item in pending:
        category=item['category']
        if category in seen:continue
        group=next((g for g in _BUNDLES if category in g),frozenset({category}))
        items=[i for i in pending if i['category'] in group];seen.update(i['category'] for i in items)
        bundles.append(items)
    # Existing furniture remains protected by the transaction gate. Prefer an
    # existing compatible anchor for a missing member, otherwise spread bundles
    # over available rooms before asking one compact room to serve every role.
    allocation={r.id:[] for r in rooms};load=Counter()
    for bundle in sorted(bundles,key=lambda b:-sum(i['min_count'] for i in b)):
        cats={i['category'] for i in bundle}
        family=next((g for g in _BUNDLES if cats <= g),cats)
        def score(room):
            existing={o.category for o in floor.objects if o.room_id==room.id}
            return (bool(existing & (family-cats)),not allocation[room.id],
                    -load[room.id]/max(room.bounds.area,1),room.bounds.area,room.id)
        room=max(rooms,key=score)
        own=Counter(o.category for o in floor.objects if o.room_id==room.id)
        allocation[room.id].extend({**i,'min_count':i['min_count']+own[i['category']]} for i in bundle)
        load[room.id]+=sum(i['min_count'] for i in bundle)
    return {rid:items for rid,items in allocation.items() if items}
