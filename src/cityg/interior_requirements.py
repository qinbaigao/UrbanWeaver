"""Entity-bound interior requirements, shared across planning and acceptance.

Models interpret quoted requirements; geometry owns realization. Area values
are never inferred from prototype dimensions or silently treated as density.
"""
from collections import Counter
from copy import deepcopy
import math


class InteriorRequirementConflict(ValueError):
    """A user requirement needs upstream replanning, not a backend failure."""


def response_schema():
    from cityg.planning.baseline import ROOM_FUNCTIONS
    from cityg.planning.interiors import ASSET_CATALOG
    def obj(properties):
        return {'type':'object','additionalProperties':False,'properties':properties,'required':list(properties)}
    functions=sorted({f for fs in ROOM_FUNCTIONS.values() for f in fs if f!='corridor'})
    return {'type':'array','maxItems':20,'items':obj({
        'label':{'type':'string'},'source_quote':{'type':'string'},
        'building_id':{'type':['string','null']},
        'building_function':{'type':'string','enum':list(ROOM_FUNCTIONS)},
        'levels':{'type':'array','minItems':1,'items':{'type':'integer','minimum':0}},
        'area_m2':{'type':['number','null'],'minimum':20},
        'area_basis':{'type':'string','enum':['floor_gross','rooms_net','building_gross'],
            'description':'Use floor_gross for an approximately N m2 ground floor, including circulation. rooms_net ONLY when the user explicitly says net room area excluding circulation; building_gross ONLY for whole-building total area.'},
        'required_functions':{'type':'array','items':{'type':'string','enum':functions}},
        'inventory':{'type':'array','maxItems':40,'items':obj({
            'room_function':{'type':'string','enum':functions},
            'category':{'type':'string','enum':sorted(ASSET_CATALOG)},
            'min_count':{'type':'integer','minimum':1,'maximum':200},
            'count_basis':{'type':'string','enum':['presence','explicit_number'],
                'description':'presence requires min_count=1 for any unnumbered request; explicit_number requires a numeric count in this building source_quote.'}})},
    })}


def validate_requirements(rows, *, instruction=None):
    from cityg.planning.baseline import ROOM_FUNCTIONS
    from cityg.planning.interiors import ASSET_CATALOG
    if not isinstance(rows,(tuple,list)) or len(rows)>20: raise ValueError('Invalid interior requirements')
    seen=set()
    fields={'label','source_quote','building_id','building_function','levels','area_m2','area_basis','required_functions','inventory'}
    for r in rows:
        if not isinstance(r,dict) or set(r)!=fields: raise ValueError('Invalid interior requirement fields')
        if not isinstance(r['label'],str) or not r['label'].strip(): raise ValueError('Interior requirement needs a label')
        q=r['source_quote']
        if not isinstance(q,str) or not q.strip() or (instruction is not None and q not in instruction):
            raise ValueError('Interior requirement must quote the original instruction exactly')
        if r['building_function'] not in ROOM_FUNCTIONS: raise ValueError('Unknown building function')
        if r['building_id'] is not None and (not isinstance(r['building_id'],str) or not r['building_id'].startswith('building_')):
            raise ValueError(f"Interior requirement label={r['label']!r} has invalid building_id={r['building_id']!r}. "
                             'A/B and other names belong in label, not building_id. For a named NEW building set '
                             'building_id to JSON null; only use a building_ prefixed ID actually supplied by the user.')
        levels=r['levels']
        if not isinstance(levels,list) or not levels or any(type(x) is not int or x<0 for x in levels) or len(set(levels))!=len(levels):
            raise ValueError('Interior levels must be unique zero-based integers')
        area=r['area_m2']
        if area is not None and (type(area) not in (int,float) or not math.isfinite(area) or area<20):
            raise ValueError('Interior area must be finite and at least 20 square metres')
        if r['area_basis'] not in ('floor_gross','rooms_net','building_gross'): raise ValueError('Unknown area basis')
        allowed=set(ROOM_FUNCTIONS[r['building_function']])
        if not isinstance(r['required_functions'],list) or any(f not in allowed or f=='corridor' for f in r['required_functions']):
            raise ValueError(f"Interior requirement {r['label']}: functions {r['required_functions']} incompatible with "
                             f"{r['building_function']}; allowed room functions: {sorted(allowed-{'corridor'})}. "
                             'Use supported semantic equivalents, including break_room for cafe seating/service and reception for waiting.')
        if not isinstance(r['inventory'],list) or len(r['inventory'])>40: raise ValueError('Invalid required inventory')
        keys=set()
        for i in r['inventory']:
            if (not isinstance(i,dict) or not {'room_function','category','min_count'}<=set(i) or
                set(i)-{'room_function','category','min_count','source_quote','count_basis'} or
                i['room_function'] not in r['required_functions'] or i['category'] not in ASSET_CATALOG or
                type(i['min_count']) is not int or not 1<=i['min_count']<=200):
                raise ValueError('Required inventory needs a supported function/category and positive count')
            from cityg.inventory_provenance import validate_inventory_source
            validate_inventory_source(i,q)
            key=(i['room_function'],i['category'])
            if key in keys: raise ValueError('Duplicate inventory target')
            keys.add(key)
        for level in levels:
            key=(r['label'],level)
            if key in seen: raise ValueError('Overlapping interior requirements for the same label/level')
            seen.add(key)


def bind_requirements(city, rows, *, eligible_ids=None):
    """Bind new-building labels once; explicit IDs never silently change owner."""
    validate_requirements(rows)
    buildings=list(city.iter_buildings()); by_id={b.id:b for b in buildings}
    bindings={}; labels={}; occupied=set()
    for r in rows:
        bid=r['building_id'] or labels.get(r['label'])
        if bid is None:
            bid=next((b.id for b in buildings if b.function==r['building_function'] and b.id not in occupied
                      and (eligible_ids is None or b.id in eligible_ids)
                      and set(r['levels'])<={f.level for f in b.floors}
                      and (r['area_m2'] is None or r['area_basis']!='floor_gross' or b.footprint.area>=r['area_m2'])),None)
        if bid not in by_id or by_id[bid].function!=r['building_function']:
            raise InteriorRequirementConflict(f"No compatible building for interior requirement {r['label']}")
        if r['label'] in labels and labels[r['label']]!=bid: raise InteriorRequirementConflict('Interior label has inconsistent binding')
        if not set(r['levels'])<={f.level for f in by_id[bid].floors}: raise InteriorRequirementConflict(f'{bid}: requested floor does not exist')
        if any(set(r['levels']) & set(other['levels']) for other in bindings.get(bid,[])):
            raise InteriorRequirementConflict(f'{bid}: overlapping floor requirements')
        labels[r['label']]=bid; occupied.add(bid)
        bindings.setdefault(bid,[]).append({**deepcopy(r),'building_id':bid})
    return bindings


def constrain_reservations(city, targets, bindings):
    """Set a requested gross plate before any entry/core/furniture is committed.

    Each rectangle preserves the street-facing edge and stays inside the original
    buildable plate. Unsupported area meanings are rejected, never reinterpreted.
    """
    from cityg.schemas import Bounds2D
    from cityg.serialization import to_primitive
    from cityg.planning.interior_frame import InteriorFrame
    buildings={b.id:b for b in city.iter_buildings()}
    for bid,rows in bindings.items():
        if bid not in targets: raise InteriorRequirementConflict(f'{bid}: explicit interiors lack a feasible reserved envelope')
        target=targets[bid]; target['requirements']=deepcopy(rows)
        areas={r['area_m2'] for r in rows if r['area_m2'] is not None}
        if not areas: continue
        if any(r['area_m2'] is not None and r['area_basis']!='floor_gross' for r in rows):
            raise InteriorRequirementConflict(f'{bid}: only floor_gross area can currently be realized; net/whole-building area requires upstream replanning')
        if len(areas)!=1: raise InteriorRequirementConflict(f'{bid}: different floor areas require a varying floorplate, unsupported by rectangular reservation')
        area=next(iter(areas)); frame=InteriorFrame(target['circulation_axis'])
        source=frame.bounds(Bounds2D(**target['verified_site_growth']['bounds'])
                            if 'verified_site_growth' in target else buildings[bid].footprint)
        if area>source.area+1e-6: raise InteriorRequirementConflict(f'{bid}: requested area {area} exceeds buildable area {source.area:.2f}')
        # Prefer a compact plate; long narrow leftovers cannot satisfy room capacity.
        width=min(source.width,math.sqrt(area)); depth=area/width
        if depth>source.depth: depth=source.depth; width=area/depth
        if min(width,depth)<6: raise InteriorRequirementConflict(f'{bid}: requested footprint has insufficient short-side clearance')
        x=source.min_x if frame.side(target['entrance_side'])=='west' else source.max_x-width
        y=source.center.y-depth/2
        target['footprint']=to_primitive(frame.bounds(Bounds2D(x,y,x+width,y+depth)))
        target['source_footprint']=to_primitive(buildings[bid].footprint)
        target['area_contract']={'basis':'floor_gross','target_m2':area,'tolerance_ratio':.05}
        target['dimension_policy']='explicit_floor_area_before_reference_capacity'
    return targets


def requirements_for(building, level=None):
    rows=getattr(building,'metadata',{}).get('interior_layout_contract',{}).get('requirements',[])
    return [r for r in rows if level is None or level in r['levels']]


def inventory_for(building, level, function):
    return [i for r in requirements_for(building,level) for i in r['inventory'] if i['room_function']==function]


def evaluate_requirements(city, rows, *, instruction=None):
    """Measure final realized hierarchy, not proposals, reference counts or quotes."""
    from cityg.agents.building_uses import label_key, named_building_uses
    claims = named_building_uses(instruction)
    buildings={b.id:b for b in city.iter_buildings()}; results=[]
    for r in rows:
        b=buildings.get(r['building_id'])
        for level in r['levels']:
            f=next((f for f in b.floors if f.level==level),None) if b else None
            item={'label':r['label'],'building_id':r['building_id'],'level':level,'source_quote':r['source_quote']}
            if f is None:
                results.append({**item,'status':'violated','reason':'missing_bound_floor'}); continue
            claim = claims.get(label_key(r['label']), {})
            expected_use = claim.get('function', r.get('building_function'))
            use_matches = expected_use is None or b.function == expected_use
            item.update(expected_building_function=expected_use, actual_building_function=b.function,
                        building_use_quote=claim.get('quote'))
            rooms=[room for room in f.rooms if room.function!='corridor']
            room_ids={room.id:room.function for room in rooms}
            counts=Counter((room_ids[o.room_id],o.category) for o in city.iter_objects() if o.room_id in room_ids)
            missing=sorted(set(r['required_functions'])-{room.function for room in rooms})
            deficits=[{**i,'placed':counts[i['room_function'],i['category']]} for i in r['inventory']
                      if counts[i['room_function'],i['category']]<i['min_count']]
            from cityg.planning.seating_contract import check_seating, seating_contracts
            seating = [check_seating(b,f,contract) for contract in seating_contracts(r)]
            actual=(b.footprint.area if r['area_basis']=='floor_gross' else
                    sum(room.bounds.area for room in rooms) if r['area_basis']=='rooms_net' else
                    b.footprint.area*len(b.floors))
            error=abs(actual-r['area_m2'])/r['area_m2'] if r['area_m2'] else None
            results.append({**item,'area_basis':r['area_basis'],'target_area_m2':r['area_m2'],
                'actual_area_m2':actual,'relative_area_error':error,'missing_functions':missing,
                'inventory_shortfalls':deficits,'single_table_seating':seating,
                'status':'violated' if not use_matches or missing or deficits or any(not v['ok'] for v in seating) or
                (error is not None and error>.05+1e-8) else 'satisfied'})
    return results
