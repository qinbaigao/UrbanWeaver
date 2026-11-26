"""Auditable, conservative acceptance of parsed requirements and detail budgets."""
from collections import Counter

from cityg.agents.requirement_contracts import explicit_contract
from cityg.serialization import to_primitive


def create_ledger(requirement, spec, *, prototype_options=None):
    values = to_primitive(spec)
    contract = explicit_contract(requirement)
    rows = []
    for key in ("building_count", "min_floors", "max_floors", "width_m", "depth_m"):
        rows.append({"id": "spec."+key, "kind": "hard", "expected": values[key],
                     "origin": "explicit_contract" if key in contract else "parsed_spec",
                     "status": "pending", "check": key})
    rows.append({"id": "spec.functions", "kind": "hard", "check": "functions",
                 "origin": "parsed_spec", "expected": sorted({z.function for z in spec.zones}), "status": "pending"})
    if spec.room_count_strategy == 'fixed':
        rows.append({'id': 'spec.rooms_per_floor', 'kind': 'hard', 'check': 'rooms_per_floor',
                     'expected': spec.rooms_per_floor, 'origin': 'parsed_spec', 'status': 'pending'})
    rows.append({"id": "instruction.semantic_review", "kind": "unclassified",
                 "origin": "user", "source_text": requirement, "status": "unverified",
                 "reason": "Numeric checks do not prove complete natural-language or visual satisfaction."})
    return {"schema_version": 1, "original_instruction": requirement, "parsed_spec": values,
            "explicit_contract": contract, "requirements": rows,
            "detail_budget": prototype_options, "status": "pending"}


def evaluate_ledger(ledger, city, prototype_report=None, *, compiled_manifest=None, final=False):
    buildings = list(city.iter_buildings())
    actual = {"building_count": len(buildings), "min_floors": min((len(b.floors) for b in buildings), default=0),
              "max_floors": max((len(b.floors) for b in buildings), default=0),
              "width_m": city.bounds.width, "depth_m": city.bounds.depth,
              "functions": sorted({b.function for b in buildings})}
    actual['rooms_per_floor'] = {f.id: sum(r.function != 'corridor' for r in f.rooms) for f in city.iter_floors()}
    for row in ledger["requirements"]:
        key = row.get("check")
        if key not in actual:
            continue
        row["actual"] = actual[key]
        if key == "min_floors": ok = actual[key] >= row["expected"]
        elif key == "max_floors": ok = actual[key] <= row["expected"]
        elif key == "functions": ok = set(row["expected"]) <= set(actual[key])
        elif key == 'rooms_per_floor': ok = all(n == row['expected'] for n in actual[key].values())
        else: ok = actual[key] == row["expected"]
        row["status"] = "satisfied" if ok else "violated"
    if prototype_report is not None:
        ledger["prototype_execution"] = {k: prototype_report[k] for k in ("status", "summary")}
    # A planning citation is traceability, never proof of semantic satisfaction.
    for goal in ledger.get('design_goals',[]):
        goal['planning_evidence']=[{'room_id':r['room_id'],'prototype_id':r['prototype_id'],
            'reason':r.get('selection_reason'),'design_adjustments':r.get('design_adjustments',{})}
            for r in (prototype_report or {}).get('rooms',[]) if goal['id'] in r.get('goal_ids',[])]
        goal['status']='unverified'
    from cityg.interior_requirements import evaluate_requirements
    interior = evaluate_requirements(city,ledger.get('bound_interior_requirements',[]),
                                     instruction=ledger.get('original_instruction'))
    ledger['interior_acceptance'] = interior
    from cityg.urban_requirements import evaluate as evaluate_urban
    urban = evaluate_urban(city, ledger['parsed_spec'].get('urban_requirements', []))
    ledger['urban_acceptance'] = urban
    ledger['requirements'] = [r for r in ledger['requirements'] if r.get('check')!='urban_relation']
    ledger['requirements'].extend({'id': 'urban.'+r['id'], 'kind': 'hard',
        'check':'urban_relation', 'origin':'quoted_parsed_requirement',
        'status':r['status'], 'actual':r['checks']} for r in urban if r['strength']=='hard')
    ledger['requirements'] = [r for r in ledger['requirements'] if r.get('check')!='bound_interior']
    ledger['requirements'].extend({'id':f"interior.{r['building_id']}.{r['level']}",
        'kind':'hard','origin':'quoted_parsed_requirement','check':'bound_interior',**r} for r in interior)
    walks = ledger['parsed_spec'].get('walking_requirements', [])
    ledger['requirements'] = [r for r in ledger['requirements'] if r.get('check') != 'compiled_walk']
    if walks:
        if final or compiled_manifest is not None:
            from cityg.walking_requirements import assess
            ledger['requirements'].extend(assess(city, ledger.get('bound_interior_requirements', []),
                                                 walks, compiled_manifest))
        else:
            ledger['requirements'].extend({'id':f'walking.{i+1}', 'check':'compiled_walk', 'kind':'hard',
                'expected':walk, 'status':'pending'} for i,walk in enumerate(walks))
    ledger["summary"] = dict(Counter(r["status"] for r in ledger["requirements"]))
    ledger["status"] = "violated" if ledger["summary"].get("violated") else "checked_with_unverified_semantics"
    if ledger['status'] != 'violated' and any(r.get('check')=='compiled_walk' and r['status']=='unverified'
                                              for r in ledger['requirements']):
        ledger['status'] = 'required_route_unverified'
    return ledger
