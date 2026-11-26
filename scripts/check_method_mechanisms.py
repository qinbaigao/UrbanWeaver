"""Offline controlled negotiation branches, using the existing CityG engine.

These are engineering probes with deterministic proposal providers, not VLM
experiments. Every accepted candidate is compiled and independently checked.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from cityg.ccwp import entity_index
from cityg.geometry import GeometryCompiler
from cityg.geometry.validation import GeometryValidator
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.planning.negotiation import negotiate
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.subtree_transactions import FloorSubtreePlanner
from cityg.transactions import fingerprint


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    city=BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(
        CitySpec(building_count=2,min_floors=2,max_floors=2,width_m=180,depth_m=140))
    before=deepcopy(city);building=next(city.iter_buildings());floor=building.floors[0]
    room=next(r for r in floor.rooms if r.function!='corridor')
    count=lambda c:sum(r.function!='corridor' for r in entity_index(c)[floor.id].rooms)
    requested=6 if count(city)!=6 else 7
    conflict={'conflict_id':'controlled_floor_capacity','entity_id':room.id,
              'base_fingerprint':fingerprint(city),'requested_floor_room_count':requested}
    def compile_gate(candidate):
        geometry=GeometryCompiler().compile(candidate)
        return GeometryValidator().validate(candidate,geometry).to_dict()
    def room_cannot_change_partition(*_):
        raise ValueError('Room-local furnishing cannot satisfy a floor partition count')
    def floor_strategy(draft,scope,issue):
        return FloorSubtreePlanner().replace(draft,scope,{'room_count':issue['requested_floor_room_count']}).city
    cases={}
    definitions=[('authorized_parent',[floor.id],3,True,'resolved'),
                 ('locked_parent',[room.id],3,True,'needs_authorization'),
                 ('exhausted_budget',[floor.id],1,True,'budget_exhausted'),
                 ('independent_resolution_rejects',[floor.id],3,False,'unresolved')]
    for name,authority,budget,resolution,expected in definitions:
        candidate,receipt=negotiate(city,conflict,authorized_roots=authority,
            strategies={'room':room_cannot_change_partition,'floor':floor_strategy},
            compiled_gate=compile_gate,
            resolution_gate=lambda c,issue:resolution and count(c)==requested,
            source='user_edit',max_attempts=budget)
        outside=list(candidate.iter_buildings())[1]==list(city.iter_buildings())[1]
        protected=(next(candidate.iter_buildings()).entrance==building.entrance and
                   next(candidate.iter_buildings()).vertical_connectors==building.vertical_connectors)
        unchanged=city==before
        accepted=receipt['status']=='resolved'
        post=compile_gate(candidate) if accepted else None
        check=(receipt['status']==expected and outside and protected and unchanged
               and ((count(candidate)==requested and post['ok']) if accepted else candidate==city))
        cases[name]={'ok':check,'receipt':receipt,'outside_building_unchanged':outside,
            'entrance_core_preserved':protected,'source_unchanged':unchanged,
            'room_count_before':count(city),'room_count_after':count(candidate),
            'post_compilation_check':post}
        save_json(cases[name],output/(name+'.json'))
    result={'ok':all(r['ok'] for r in cases.values()),'model_calls':0,
        'scope':'controlled_offline_existing_negotiation_not_paper_efficacy',
        'M1':'partial_interface_and_protected_geometry_checks',
        'M2':'not_exercised_no_visual_or_joint_acquisition_policy',
        'M3':'authorized_floor_escalation_rollback_budget_independent_gate',
        'cases':{k:{'ok':v['ok'],'status':v['receipt']['status']} for k,v in cases.items()}}
    save_json(result,output/'acceptance.json');return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    result=run(p.parse_args().output);print(json.dumps(result,indent=2))
    return 0 if result['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
