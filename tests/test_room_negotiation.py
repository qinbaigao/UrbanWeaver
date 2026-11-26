"""Room-only negotiation exercises actual placement, compilation and rollback."""
from copy import deepcopy
from pathlib import Path
import unittest

from cityg.assets import AssetRegistry, AssetResolver
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning.generation_prototypes import GenerationPrototypes, load_options
from cityg.planning.prototype_lab import make_lab
from cityg.planning.prototypes import reference_registry
from cityg.refinement.room_commit import negotiate_room_program
from cityg.transactions import fingerprint
from cityg.validation.local_room import room_compilation_gate


ROOT=Path(__file__).resolve().parents[1]


class RoomNegotiationTests(unittest.TestCase):
    def test_single_room_retry_compiles_and_does_not_claim_visual_resolution(self):
        runtime=GenerationPrototypes(load_options(ROOT/'configs/generation_prototypes.json'))
        city,targets=make_lab(runtime.floors.room_library,['office_private_v1','living_media_v1'])
        key,building,floor,room=targets[0]
        city.world_program=build_world_program(city,producer='test',seed=17)
        before=deepcopy(city)
        compiler=GeometryCompiler(asset_registry=AssetRegistry(ROOT/'assets/asset_registry.json'))
        registry=runtime.prepare_resources(compiler.asset_registry,compiler)
        prototype=runtime.floors.room_library.materialize(key)
        resolver=AssetResolver(reference_registry(registry,prototype),(),max_provider_calls=0)
        calls=[]
        def provider(draft,conflict):
            calls.append(conflict)
            return prototype.program(room.id)
        result,report,stats=negotiate_room_program(city,room.id,provider,
            failure='controlled prior proposal exceeded room capacity',asset_resolver=resolver,
            compiled_gate=room_compilation_gate(city,room.id,compiler))
        self.assertEqual(report['status'],'resolved',report)
        self.assertEqual(len(calls),1)
        self.assertFalse(report['visual_issue_resolution_proven'])
        self.assertEqual(report['authorized_roots'],[room.id])
        self.assertEqual(city,before)
        self.assertNotEqual(fingerprint(result),fingerprint(city))
        self.assertEqual(list(result.iter_buildings())[1],list(city.iter_buildings())[1])
        self.assertGreater(stats['placed_object_count'],0)
        # The exact same proposal may never bypass an actual compiled failure.
        rejected,report,_=negotiate_room_program(city,room.id,provider,failure='test',
            asset_resolver=resolver,compiled_gate=lambda _: {'ok':False,'reason':'controlled failure'})
        self.assertEqual(rejected,city)
        self.assertEqual(report['status'],'unresolved')
        self.assertFalse(report['verified_resolved'])

