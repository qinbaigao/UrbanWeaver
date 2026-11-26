"""Persist typed floor intent through later furnishing/repartition transactions.

These are checked model interpretations, not proof that all user intent was
understood. Scoped or conflicting statements remain deferred in agent traces.
"""
from copy import deepcopy

from cityg.planning.baseline import ROOM_FUNCTIONS
from cityg.planning.floor_access import check_floor_access


def bind_floor_access_contracts(city,receipts):
    goals={g['id']:g for g in city.metadata.get('design_goals',[])}
    contracts={}
    for bid,receipt in receipts.items():
        active=[r for r in receipt.get('objective',{}).get('access_constraints',[])
                if r.get('applicability')=='uniform']
        if not active:continue
        ids={key for r in active for key in r['supporting_goal_ids']}
        if not ids<=set(goals):raise ValueError('Access contract lost its quoted goal sources')
        contracts[bid]={'version':1,'rules':deepcopy(active),
            'goal_sources':{key:deepcopy(goals[key]) for key in sorted(ids)},
            'authority':'quoted_model_interpretation','scope':'all_realized_floors_of_bound_building'}
    if contracts:city.metadata['floor_access_contracts']=contracts


def validate_floor_access_contracts(city,report):
    contracts=city.metadata.get('floor_access_contracts',{})
    if contracts=={}:return
    buildings={b.id:b for b in city.iter_buildings()}
    if not isinstance(contracts,dict):
        report.add('error','invalid_floor_access_contract','Expected building-bound contracts',city.id);return
    try:goals={g['id']:g for g in city.metadata.get('design_goals',[])}
    except (KeyError,TypeError):
        report.add('error','invalid_floor_access_contract','Invalid quoted goal sources',city.id);return
    for bid,contract in contracts.items():
        try:
            building=buildings.get(bid)
            if building is None:raise ValueError('Bound building no longer exists')
            if contract.get('version')!=1 or contract.get('scope')!='all_realized_floors_of_bound_building':
                raise ValueError('Unsupported access contract scope/version')
            rules=contract['rules'];sources=contract['goal_sources']
            if not isinstance(rules,list) or not rules:raise ValueError('Empty access contract')
            for rule in rules:
                if (rule['predicate']!='not_through_room' or rule['applicability']!='uniform'
                        or rule['function'] not in ROOM_FUNCTIONS[building.function]
                        or not rule['supporting_goal_ids']):raise ValueError('Invalid uniform access predicate')
                for key in rule['supporting_goal_ids']:
                    if key not in goals or sources.get(key)!=goals[key]:
                        raise ValueError('Quoted access requirement changed or disappeared')
            if not building.floors:raise ValueError('Access contract has no realized floors')
            for floor in building.floors:
                try:check_floor_access(floor,rules)
                except ValueError as error:
                    report.add('error','floor_access_requirement_violated',str(error),floor.id,
                        responsible_ancestor=building.id,allowed_patch_scope=building.id)
        except (ValueError,KeyError,TypeError,AttributeError) as error:
            report.add('error','invalid_floor_access_contract',str(error),bid)
