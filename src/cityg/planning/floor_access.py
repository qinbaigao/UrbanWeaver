"""Typed access postconditions, checked on the solver's actual rooms and doors.

Interpretation remains model-derived. Only uniform quoted restrictions are
supported; qualified/conflicting interpretations are disclosed, not broadened.
"""
from collections import deque


def forbidden_transit_functions(objective):
    return sorted({r['function'] for r in objective.get('access_constraints',[])
                   if r['applicability']=='uniform'})


def check_floor_access(floor,constraints):
    forbidden=forbidden_transit_functions({'access_constraints':constraints})
    if not forbidden:return
    rooms={r.id:r for r in floor.rooms};graph={rid:set() for rid in rooms}
    roots={r.id for r in floor.rooms if r.function=='corridor'}
    for door in floor.doors:
        if door.room_a_id in rooms and door.room_b_id in rooms:
            graph[door.room_a_id].add(door.room_b_id);graph[door.room_b_id].add(door.room_a_id)
    def reachable(blocked=None):
        seen=roots-{blocked};queue=deque(sorted(seen))
        while queue:
            for nxt in sorted(graph[queue.popleft()]-seen-{blocked}):seen.add(nxt);queue.append(nxt)
        return seen
    reached=reachable()
    if not roots or set(rooms)-reached:raise ValueError('Access postcondition requires a connected realized room graph')
    for rid,room in rooms.items():
        if room.function not in forbidden:continue
        blocked=(set(rooms)-{rid})-reachable(rid)
        if blocked:
            raise ValueError(f'Access requirement violated at level {floor.level}: {room.function} '
                f'{rid} is a required transit room for {sorted(blocked)}. Put this function in a '
                'leaf slot or choose independent access; do not remove required functions.')
