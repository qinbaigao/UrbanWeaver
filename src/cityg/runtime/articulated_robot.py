"""URDF-derived FK/IK in metres, radians and Z-up. No physics/autonomy claim."""
import math
import xml.etree.ElementTree as ET
import numpy as np


def rotation(axis, angle):
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    result = np.eye(4)
    result[:3, :3] = np.eye(3) + math.sin(angle)*cross + (1-math.cos(angle))*(cross @ cross)
    return result


def origin_matrix(node):
    if node is None:
        return np.eye(4)
    xyz = [float(v) for v in node.get('xyz', '0 0 0').split()]
    roll, pitch, yaw = [float(v) for v in node.get('rpy', '0 0 0').split()]
    matrix = rotation((0, 0, 1), yaw) @ rotation((0, 1, 0), pitch) @ rotation((1, 0, 0), roll)
    matrix[:3, 3] = xyz
    return matrix


def parse_urdf(path):
    tree = ET.parse(path)
    links = {n.get('name'): {} for n in tree.findall('link')}
    joints = []
    for node in tree.findall('joint'):
        axis = node.find('axis')
        limit = node.find('limit')
        joint = {'name': node.get('name'), 'type': node.get('type'),
                 'parent': node.find('parent').get('link'), 'child': node.find('child').get('link'),
                 'origin': origin_matrix(node.find('origin')).tolist(),
                 'axis': [float(v) for v in (axis.get('xyz') if axis is not None else '1 0 0').split()]}
        if limit is not None:
            joint['limit'] = {k: float(v) for k, v in limit.attrib.items()}
        if node.find('mimic') is not None:
            raise ValueError('Mimic joints require explicit support')
        if joint['type'] not in ('fixed', 'revolute', 'continuous', 'prismatic'):
            raise ValueError('Unsupported joint type')
        joints.append(joint)
    roots = set(links) - {j['child'] for j in joints}
    if len(roots) != 1:
        raise ValueError('Expected a single URDF root')
    # Resolve topology, never depend on XML element order.
    ordered, reached = [], set(roots)
    while len(ordered) < len(joints):
        ready = [j for j in joints if j not in ordered and j['parent'] in reached]
        if not ready:
            raise ValueError('Disconnected or cyclic joint tree')
        for j in ready:
            if j['child'] in reached:
                raise ValueError('Multiple parents or cyclic joint tree')
            ordered.append(j)
            reached.add(j['child'])
    return {'root': roots.pop(), 'links': links, 'joints': ordered}


class RobotModel:
    def __init__(self, spec):
        self.spec = spec
        self.joints = spec['joints']
        self.origins = {j['name']: np.array(j['origin']) for j in self.joints}
        self.arm_names = ['torso_lift_joint', 'shoulder_pan_joint', 'shoulder_lift_joint',
                          'upperarm_roll_joint', 'elbow_flex_joint', 'forearm_roll_joint',
                          'wrist_flex_joint', 'wrist_roll_joint']
        self.limits = {j['name']: j.get('limit', {}) for j in self.joints}
        self.parents = {j['child']: j['parent'] for j in self.joints}

    def fk(self, values, base=(0, 0, 0), yaw=0.):
        root = rotation((0, 0, 1), yaw)
        root[:3, 3] = base
        frames = {self.spec['root']: root}
        for joint in self.joints:
            q = values.get(joint['name'], 0.)
            move = np.eye(4)
            if joint['type'] in ('continuous', 'revolute'):
                move = rotation(joint['axis'], q)
            elif joint['type'] == 'prismatic':
                move[:3, 3] = np.array(joint['axis']) * q
            frames[joint['child']] = frames[joint['parent']] @ self.origins[joint['name']] @ move
        return frames

    def effector(self, values, base=(0, 0, 0), yaw=0.):
        frame = self.fk(values, base, yaw)[self.spec['end_effector_link']].copy()
        frame[:3, 3] += frame[:3, :3] @ np.array(self.spec['grasp_offset'])
        return frame

    def solve(self, target, seed, *, orientation=None, tolerance=.003):
        """Bounded pose IK; callers still must check link collisions and continuity."""
        from scipy.optimize import least_squares
        from scipy.spatial.transform import Rotation
        low = np.array([self.limits[n].get('lower', -2*math.pi) for n in self.arm_names])
        high = np.array([self.limits[n].get('upper', 2*math.pi) for n in self.arm_names])
        initial = np.clip([seed.get(n, 0.) for n in self.arm_names], low+1e-8, high-1e-8)
        target = np.array(target)
        def residual(q):
            state = dict(seed, **dict(zip(self.arm_names, q)))
            frame = self.effector(state)
            pose = list((frame[:3, 3]-target)*10)
            if orientation is not None:
                pose.extend(Rotation.from_matrix(orientation.T @ frame[:3, :3]).as_rotvec()*2)
            # Soft continuity preference, never substitutes for a hard reach test.
            return np.r_[pose, (q-initial)*.002]
        result = least_squares(residual, initial, bounds=(low, high), max_nfev=180,
                               ftol=1e-9, xtol=1e-9, gtol=1e-9)
        values = dict(seed, **{n: float(v) for n, v in zip(self.arm_names, result.x)})
        frame = self.effector(values)
        error = float(np.linalg.norm(frame[:3, 3]-target))
        angular = 0. if orientation is None else float(np.linalg.norm(Rotation.from_matrix(orientation.T @ frame[:3, :3]).as_rotvec()))
        if error > tolerance or angular > .025:
            raise ValueError(f'IK unreachable: position={error:.5f} m rotation={angular:.5f} rad')
        return values

    def collision_boxes(self, values, base=(0, 0, 0), yaw=0.):
        """World AABBs enclose each official link collision mesh at this pose."""
        frames = self.fk(values, base, yaw)
        result = {}
        for name, spec in self.spec['links'].items():
            for i, bounds in enumerate(spec.get('collision_bounds', [])):
                lo, hi = np.array(bounds)
                corners = np.array([[x, y, z, 1.] for x in (lo[0], hi[0])
                                    for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
                points = (frames[name] @ corners.T).T[:, :3]
                result[f'{name}:{i}'] = np.array([points.min(axis=0), points.max(axis=0)])
        return result
