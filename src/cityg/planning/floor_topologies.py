"""Metric-checked topology choices for the reserved rectangular interior path.

Topology IDs describe organization, not function. The agent assigns actual
functions and bounded weight adjustments; the full solver validates the result.
"""
import math
from cityg.planning.programs import TARGET_ROOM_AREA_RANGE_M2


def topology_catalog(geometry, fixed_count=None, references=(), allowed_functions=(), height=3.2, retain_unmatched=False, enumerate_all_counts=False):
    rows = []
    for example in geometry['feasible_topology_examples']:
        children = example['children_per_anchor']
        counts = example['groups_per_side']
        lo,hi=TARGET_ROOM_AREA_RANGE_M2
        # This invariant does not depend on weights/functions. Filter BEFORE
        # sparse/medium/dense sampling so valid intermediate counts survive.
        counts=[n for n in counts if lo<=geometry['usable_area_m2']/(2*n*(1+children))<=hi]
        if not counts:continue
        # Keep a small range of sparse/medium/dense organizations in context.
        selected = counts if references or enumerate_all_counts else sorted(set((counts[0], counts[len(counts)//2], counts[-1])))
        if fixed_count is not None:
            selected = [n for n in counts if 2*n*(1+children) == fixed_count]
        for count in selected:
            assumptions = example['assumptions']
            signature = (children,count,assumptions['anchor_weight'],assumptions['max_room_aspect_ratio'])
            key = 'c%d_g%d_w%d_a%d' % (*signature[:3], round(signature[3]*10))
            row = {'id':key, 'groups_per_side':count,
                'children_per_anchor':children, 'room_count':2*count*(1+children),
                'family':'residential_clusters' if children else 'double_loaded',
                **assumptions, 'max_room_depth_m':30,
                'slot_order':'group 0 anchor, then its children; group 1 anchor, then its children; ...',
                'metric_checked_at_unit_adjustments':True}
            if references:
                from cityg.planning.floor_reference_fit import compatible_references
                slot_info=[]
                for band in geometry['bands']:
                    width=band['width_m']/count; depth=band['depth_m']
                    front=depth if not children else min(depth-2.4,max(2.4,depth*min(.70,max(.25,
                        assumptions['anchor_weight']/(assumptions['anchor_weight']+children)))))
                    slots=[(width,front)] + ([(width/children,depth-front)]*children if children else [])
                    for _ in range(count):
                        for w,d in slots:
                            matches={fn:compatible_references(fn,w,d,height,references) for fn in allowed_functions}
                            slot_info.append({'width_m':round(w,3),'depth_m':round(d,3),
                                              'compatible_functions':{k:v for k,v in matches.items() if v}})
                # All groups on a band have the same nominal shape; disclose
                # compact anchor/child slots rather than repeating 32 entries.
                row['nominal_reference_slots'] = [
                    {'side':side,'group_slots':slot_info[side*count*(children+1):side*count*(children+1)+children+1]}
                    for side in range(2)]
                row['potential_reference_room_count']=sum(bool(s['compatible_functions']) for s in slot_info)
            rows.append(row)
    # Do not erase all organizations if current references cannot fit. The
    # submission gate reports that limitation, rather than inventing matches.
    matching=[r for r in rows if r.get('potential_reference_room_count',0)>0]
    if references and matching and not retain_unmatched: return matching
    return rows


def reference_choices_by_level(catalog, required_by_level):
    """Disclose level-specific semantic/size matches, not a building-wide hint.

    A topology fitting reception on the ground floor does not automatically
    fit bedrooms/living rooms upstairs. Suggestions leave choice to the Agent;
    actual allocation and reference-fit checks still validate adjusted weights.
    """
    result={}
    for level,required in required_by_level.items():
        choices=[]
        for candidate in catalog:
            slots={};index=0
            for side in candidate.get('nominal_reference_slots',[]):
                for _ in range(candidate['groups_per_side']):
                    for slot in side['group_slots']:
                        for function in slot['compatible_functions']:
                            if function in required: slots.setdefault(function,[]).append(index)
                        index+=1
            if slots:
                choices.append({'topology_id':candidate['id'],
                    'required_function_reference_slots':slots,'at_unit_weights':True})
        result[level]=choices
    return result


def expand_topology_brief(data, catalog):
    if not isinstance(data,dict) or set(data) != {'zones'} or not isinstance(data['zones'],list):
        raise ValueError('Expected zones containing topology selections')
    lookup = {r['id']:r for r in catalog}
    zones=[]
    for row in data['zones']:
        expected={'zone_id','start_level','end_level','role','use_type','topology_id',
                  'functions','weight_adjustments'}
        keyed=isinstance(row,dict) and 'required_function_slots' in row
        if keyed: expected=(expected-{'functions'})|{'required_function_slots','remaining_functions'}
        if not isinstance(row,dict) or set(row) != expected:
            raise ValueError('Topology zone fields must match the schema')
        topology=lookup.get(row['topology_id'])
        if topology is None: raise ValueError('Select an offered topology_id')
        count=topology['room_count']
        functions=row.get('functions')
        if keyed:
            slots=row['required_function_slots']; remaining=row['remaining_functions']
            if not isinstance(slots,dict) or not isinstance(remaining,list):
                raise ValueError('Required function slots must be a mapping and remaining_functions a list')
            indices=list(slots.values())
            if any(type(i) is not int or not 0<=i<count for i in indices) or len(set(indices))!=len(indices):
                raise ValueError(f'Required function slots must be distinct integers within 0..{count-1}')
            if len(remaining)+len(slots)!=count:
                raise ValueError(f'{row["topology_id"]} has {count} slots: provide exactly '
                                 f'{count-len(slots)} remaining_functions after mandatory assignments')
            functions=[None]*count
            for function,index in slots.items(): functions[index]=function
            rest=iter(remaining)
            functions=[next(rest) if f is None else f for f in functions]
        if not isinstance(functions,list) or len(functions) != count:
            raise ValueError(f'{row["topology_id"]} requires exactly {count} functions in slot order')
        scales=row['weight_adjustments']
        if not isinstance(scales,list) or len(scales) != count:
            raise ValueError(f'Provide exactly {count} weight_adjustments (1.0 preserves checked dimensions)')
        low,high=topology.get('weight_min',.8),topology.get('weight_max',1.2)
        if any(type(v) not in (float,int) or not math.isfinite(v) or not low<=v<=high for v in scales):
            raise ValueError(f'weight_adjustments must be finite within [{low},{high}]')
        width=1+topology['children_per_anchor']
        spaces=[]
        for i,(function,scale) in enumerate(zip(functions,scales)):
            group,slot=divmod(i,width)
            spaces.append({'key':f'g{group}_s{slot}', 'function':function,
                'weight':scale*(topology['anchor_weight'] if slot==0 else topology['each_child_weight']),
                'access_via':'circulation' if slot==0 else f'g{group}_s0',
                'group':f'g{group}', 'enclosure':topology['enclosure']})
        zones.append({k:row[k] for k in ('zone_id','start_level','end_level','role','use_type')} | {
            'family':topology['family'], 'min_room_width_m':topology['min_room_width_m'],
            'max_room_depth_m':topology['max_room_depth_m'],
            'max_room_aspect_ratio':topology['max_room_aspect_ratio'], 'spaces':spaces})
    return {'zones':zones}


def topology_schema(functions, use_types, catalog, floor_count, required_by_level=None):
    def enum(values): return {'type':'string','enum':list(values)}
    def obj(properties): return {'type':'object','additionalProperties':False,
                                'properties':properties,'required':list(properties)}
    def zone(level=None):
        properties={
            'zone_id':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,47}$'}, 'start_level':{'type':'integer','minimum':0},
            'end_level':{'type':'integer','minimum':0},'role':enum(['ground','typical','top']),
            'use_type':enum(use_types), 'topology_id':enum(r['id'] for r in catalog),
            'functions':{'type':'array','minItems':2,'maxItems':32,'items':enum(functions)},
            'weight_adjustments':{'type':'array','minItems':2,'maxItems':32,
                                  'items':{'type':'number','minimum':.8,'maximum':1.2}}}
        if level is not None:
            # Identifiers carry no design freedom; do not spend semantic retries on them.
            properties['zone_id']={'type':'string','const':f'level_{level}'}
            for field in ('start_level','end_level'): properties[field]={'type':'integer','const':level}
            properties['role']={'type':'string','const':
                'ground' if level==0 else 'top' if level==floor_count-1 else 'typical'}
            if required_by_level:
                properties.pop('functions')
                properties['required_function_slots']=obj({fn:{'type':'integer','minimum':0,'maximum':31}
                    for fn in required_by_level[str(level)]})
                properties['remaining_functions']={'type':'array','minItems':0,'maxItems':32,'items':enum(functions)}
        # Cardinality depends on the selected topology. Encode it as disjoint
        # alternatives instead of spending model retries on list arithmetic.
        import copy
        variants=[]
        for candidate in catalog:
            fields=copy.deepcopy(properties)
            count=candidate['room_count']
            fields['topology_id']={'type':'string','const':candidate['id']}
            fields['weight_adjustments']['items'].update(minimum=candidate.get('weight_min',.8),
                                                         maximum=candidate.get('weight_max',1.2))
            for key in ('weight_adjustments','functions'):
                if key in fields: fields[key].update(minItems=count,maxItems=count)
            if 'required_function_slots' in fields:
                mandatory=fields['required_function_slots']['properties']
                if len(mandatory)>count: continue
                for value in mandatory.values(): value['maximum']=count-1
                fields['remaining_functions'].update(minItems=count-len(mandatory),maxItems=count-len(mandatory))
            variants.append(obj(fields))
        # An impossible fixed-count contract must be rejected before request.
        if not variants: raise ValueError('No topology can preserve all mandatory room functions')
        return {'oneOf':variants}
    if 1<=floor_count<=4:
        return obj({'zones':{'type':'array','minItems':floor_count,'maxItems':floor_count,
                             'prefixItems':[zone(level) for level in range(floor_count)]}})
    return obj({'zones':{'type':'array','minItems':1,'maxItems':8,'items':zone()}})
