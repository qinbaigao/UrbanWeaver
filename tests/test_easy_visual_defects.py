"""Guard the diagnostic's blindness and canonical/metric pose agreement."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from cityg.schemas import Point2D

spec=importlib.util.spec_from_file_location('easy_visual_defects',
    Path(__file__).resolve().parents[1]/'scripts/run_easy_visual_defects.py')
diagnostic=importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class EasyVisualDefectTests(unittest.TestCase):
    def object(self):
        return SimpleNamespace(id='shelf', room_id='room', category='bookcase',
            position=Point2D(5,6), rotation_deg=180, width_m=.5, depth_m=2,
            height_m=2, asset_id='asset', metadata={
                'group_key':'storage','private_truth':'outside',
                'metric_room_placement':{'center':[10,3], 'canonical_scale':[2,.5],
                    'dimensions_m':[1,1,2], 'canonical_binding':[5,6,.5,2,2,180,'asset']}})

    def test_translation_preserves_dual_coordinate_agreement(self):
        obj=self.object();diagnostic.move_metric(obj,12,5)
        self.assertEqual(obj.position,Point2D(6,10))
        self.assertEqual(obj.metadata['metric_room_placement']['center'],[12,5])
        self.assertEqual(obj.metadata['metric_room_placement']['canonical_binding'][:2],[6,10])

    def test_quarter_turn_rebinds_anisotropic_canonical_dimensions(self):
        obj=self.object();diagnostic.turn_metric(obj,90)
        self.assertEqual(obj.rotation_deg,270)
        self.assertEqual((obj.width_m,obj.depth_m),(2,.5))
        self.assertEqual(obj.metadata['metric_room_placement']['canonical_binding'],
                         [5,6,2,.5,2,270,'asset'])

    def test_public_context_excludes_truth_poses_and_contracts(self):
        floor=SimpleNamespace(objects=[self.object()])
        room=SimpleNamespace(id='room',function='office',metadata={'private_truth':'outside'})
        context=diagnostic.public_context(floor,room)
        encoded=json.dumps(context)
        for forbidden in ['private_truth','outside','metric_room_placement','position','canonical_binding']:
            self.assertNotIn(forbidden,encoded)
        self.assertEqual(context['room_group_bindings']['room'],[
            {'group_id':'storage','objects':[{'object_id':'shelf','category':'bookcase'}]}])


if __name__=='__main__':unittest.main()
