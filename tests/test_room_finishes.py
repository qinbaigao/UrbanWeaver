from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cityg.assets import MaterialLibrary, MaterialRecord
from cityg.geometry import GeometryCompiler
from cityg.geometry.model import GeometryScene, Vec3
from cityg.geometry.room_finishes import apply_room_finishes
from cityg.planning.prototype_lab import make_lab
from cityg.planning.prototypes import LayoutPrototypeLibrary
from cityg.planning.room_envelope import metric_envelope


class RoomFinishTests(unittest.TestCase):
    def setUp(self):
        library = LayoutPrototypeLibrary(Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1')
        self.city, targets = make_lab(library, ['bedroom_double_v1'])
        _, self.building, self.floor, self.room = targets[0]
        self.room.metadata['room_finishes'] = {'floor': 'floor_pbr', 'wall': 'wall_pbr'}
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        texture = Path(self.temporary.name)/'texture.jpg'
        texture.write_bytes(b'texture placeholder, compiler does not decode')
        materials = MaterialLibrary()
        for key in ('floor_pbr', 'wall_pbr'):
            materials.register(MaterialRecord(key, (1,1,1), base_color_path=str(texture), texture_scale_m=2))
        self.compiler = GeometryCompiler(material_library=materials)
        self.scene = GeometryScene('test', 'z_up')
        self.bounds = metric_envelope(self.building, self.floor, self.room)['bounds']

    def wall(self, rooms):
        return self.compiler._box('wall', self.floor.id,
            Vec3(self.bounds.center.x, self.bounds.min_y, 1.5), Vec3(2,.12,3), 0,
            'interior_wall', 'default', f'floor:{self.floor.id}', metadata={'room_ids': rooms})

    def test_floor_is_metric_and_wall_finish_is_bound(self):
        wall = self.wall([self.room.id])
        apply_room_finishes(self.compiler, self.building, self.floor, self.room, self.scene, [wall])
        floor = self.scene.primitives[0]
        self.assertEqual(floor.owner_id, self.room.id)
        self.assertAlmostEqual(floor.size.x, self.bounds.width)
        self.assertAlmostEqual(floor.size.y, self.bounds.depth)
        self.assertAlmostEqual(floor.center.z+floor.size.z/2, self.floor.elevation_m)
        self.assertFalse(floor.collision_enabled)
        self.assertEqual(wall.material_id, 'wall_pbr')
        self.assertEqual(len(self.scene.materials), 2)
        self.assertEqual(self.scene.metadata['room_finishes'][self.room.id], self.room.metadata['room_finishes'])

    def test_shared_wall_only_receives_room_side_skin(self):
        wall = self.wall([self.room.id, 'neighbor'])
        apply_room_finishes(self.compiler, self.building, self.floor, self.room, self.scene, [wall])
        self.assertEqual(wall.material_id, 'default')
        panel = self.scene.primitives[1]
        self.assertEqual(panel.metadata['room_ids'], [self.room.id])
        self.assertGreater(panel.center.y, wall.center.y)
        self.assertEqual(panel.size.x, wall.size.x)
        self.assertEqual(panel.size.z, wall.size.z)
        self.assertFalse(panel.collision_enabled)

    def test_opt_in_and_missing_material_fail_explicitly(self):
        spec = self.room.metadata.pop('room_finishes')
        apply_room_finishes(self.compiler, self.building, self.floor, self.room, self.scene, [])
        self.assertFalse(self.scene.primitives)
        self.room.metadata['room_finishes'] = {**spec, 'wall': 'missing'}
        with self.assertRaisesRegex(ValueError, 'Missing room finish material'):
            apply_room_finishes(self.compiler, self.building, self.floor, self.room, self.scene, [])

    def test_unsupported_geometry_is_not_given_a_guessed_rectangle(self):
        with patch('cityg.geometry.room_finishes.metric_envelope', return_value={'status':'unsupported'}):
            with self.assertRaisesRegex(ValueError, 'supported realized'):
                apply_room_finishes(self.compiler, self.building, self.floor, self.room, self.scene, [])


if __name__ == '__main__':
    unittest.main()
