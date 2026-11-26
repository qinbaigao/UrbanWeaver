import unittest
from pathlib import Path

from cityg.planning.floor_topologies import topology_catalog, reference_choices_by_level
from cityg.planning.generation_prototypes import GenerationPrototypes, load_options


class FloorReferenceDisclosureTests(unittest.TestCase):
    def test_reception_fit_does_not_imply_upper_living_room_fit(self):
        # Frozen dimensions of the second-seed failure; no outputs dependency.
        runtime=GenerationPrototypes(load_options(Path(__file__).resolve().parents[1]/
                                                  'configs/reliability_prototypes.json'))
        references=runtime.floor_context({'prototype_id':'none'})['room_dimensions']
        geometry={'bands':[{'width_m':58.28,'depth_m':6.4}]*2,
            'usable_area_m2':2*58.28*6.4,
            'feasible_topology_examples':[{'children_per_anchor':0,'groups_per_side':[8,9],
                'assumptions':{'anchor_weight':2,'each_child_weight':1,'min_room_width_m':2.4,
                               'max_room_aspect_ratio':2.8,'enclosure':'closed'}}]}
        catalog=topology_catalog(geometry,references=references,
            allowed_functions=['reception','living_room','bedroom','kitchen','bathroom'])
        result=reference_choices_by_level(catalog,{'0':['reception','living_room'],
                                                   '1':['living_room','bedroom','kitchen','bathroom']})
        self.assertIn('c0_g8_w2_a28',[r['topology_id'] for r in result['0']])
        self.assertNotIn('c0_g8_w2_a28',[r['topology_id'] for r in result['1']])
        living=next(r for r in result['1'] if r['topology_id']=='c0_g9_w2_a28')
        self.assertEqual(living['required_function_reference_slots']['living_room'],list(range(18)))
