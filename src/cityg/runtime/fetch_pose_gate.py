"""Local Fetch heading selection against the unchanged compiled environment."""
import math
import numpy as np
from cityg.runtime.articulated_robot import rotation
from cityg.runtime.articulated_validation import box_planes,convex_overlap,transform_planes
from cityg.runtime.city_transport_validation import static_world
from cityg.runtime.elevator_transit import transit_task_from_dict
from cityg.runtime.mobile_geometry import door_pose
from cityg.runtime.transport import Box


class FetchPoseGate:
    def __init__(self,scene,task,model):
        self.task=task;self.model=model
        self.static=static_world(scene,task)
        self.planes={b.id:box_planes(b) for b in self.static}
        self.bounds={b.id:self.box_bounds(b) for b in self.static}
        self.lo=np.array([self.bounds[b.id][0] for b in self.static])
        self.hi=np.array([self.bounds[b.id][1] for b in self.static])
        self.lifts={k:transit_task_from_dict(v) for k,v in task['lifts'].items()}
        self.cache={}

    @staticmethod
    def box_bounds(box):
        half=np.abs(rotation((0,0,1),math.radians(box.yaw))[:3,:3])@(np.array(box.size)/2)
        return np.array([np.array(box.center)-half,np.array(box.center)+half])

    def hit(self,root,yaw,q,state):
        key=tuple(np.floor(root).astype(int))
        if key not in self.cache:
            k=np.array(key)
            self.cache[key]=[self.static[i] for i in np.nonzero(np.all(self.hi>k-2,axis=1)&np.all(self.lo<k+3,axis=1))[0]]
        # Dynamic IDs are excluded from static_world; update their small cache
        # in place rather than copying all city obstacle dictionaries per pose.
        nearby=list(self.cache[key]);planes=self.planes;bounds=self.bounds
        dynamic=[door_pose(Box(**v['box']),state['doors'][k],v['hinge']) for k,v in self.task['doors'].items()]
        for k,lift in self.lifts.items():
            s=state['lifts'][k];dynamic.extend((*lift.cabin(s['z']),*lift.door_boxes(s['z'],s['opening'],s['landing_z'])))
        for b in dynamic:
            if np.linalg.norm(np.array(b.center)-root)>4:continue
            nearby.append(b);planes[b.id]=box_planes(b);bounds[b.id]=self.box_bounds(b)
        fk=self.model.fk(q,root,yaw)
        checks=[]
        for key,b in self.model.collision_boxes(q,root,yaw).items():
            name,part=key.rsplit(':',1)
            checks.append((name,b,transform_planes(self.model.spec['links'][name]['collision_hulls'][int(part)],fk[name])))
        ee=self.model.effector(q,root,yaw);normals=np.r_[ee[:3,:3].T,-ee[:3,:3].T]
        half=np.array(self.task['object']['size'])/2;extent=np.abs(ee[:3,:3])@half
        checks.append(('payload',np.array([ee[:3,3]-extent,ee[:3,3]+extent]),np.c_[normals,-normals@ee[:3,3]-np.tile(half,2)]))
        for name,(lo,hi),hull in checks:
            for b in nearby:
                if np.any(bounds[b.id][1]<=lo) or np.any(bounds[b.id][0]>=hi):continue
                if convex_overlap(hull,planes[b.id],tolerance=.001):return {'link':name,'obstacle':b.id}
        return None
