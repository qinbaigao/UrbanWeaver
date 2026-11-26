"""Place whole functional furniture groups with metric asset grounding."""
from __future__ import annotations

import math
import random
import time
from copy import deepcopy

from cityg.schemas import Bounds2D, InteriorObject, Point2D
from cityg.planning.room_regions import region_bounds, reserved_bounds
from cityg.planning.room_constraints import (
    AXIS_ANGLES, placement_policy, wall_segments, contact_axis, wall_contact,
    usable_envelopes, group_relation_cost, circulation_check, ROOM_WALL_INSET_M,
    STORAGE, direction,
)


class RoomDesignInfeasible(ValueError):
    pass


def _front(obj):
    offset={"+X":0,"+Y":90,"-X":180,"-Y":-90}[obj.metadata.get("front_axis","+Y")]
    a=math.radians(obj.rotation_deg+offset)
    return math.cos(a), math.sin(a)


def service_bounds(obj):
    """Conservative front-use zone; members in the same group may share it."""
    fx,fy=_front(obj)
    half=(abs(fx)*obj.bounds.width+abs(fy)*obj.bounds.depth)/2
    center=Point2D(obj.position.x+fx*(half+.30),obj.position.y+fy*(half+.30))
    return Bounds2D(center.x-.28,center.y-.28,center.x+.28,center.y+.28)


def place_room_design(detail, building, floor, room, program, seed, *, existing_objects=None):
    started=time.monotonic()
    stats={'candidate_count':0,'rejected_candidates':0,'prior_pose_candidates':0,
           'group_count':len(program.design.groups),'protected_group_count':len(program.design.protected_groups)}
    design=program.design
    design.validate(detail.catalog)
    from cityg.planning.furnishing_brief import check_capacity
    check_capacity(room, design.furnishing_brief, design.groups)
    # Legacy placement kept a 32 cm perimeter everywhere. Explicit contact
    # layouts instead reserve 12 cm for the wall half-thickness and a gap.
    wall_inset=ROOM_WALL_INSET_M
    usable=room.bounds.inset(wall_inset)
    doors,_=detail._door_clearance_zones(floor,room)
    zones={z["id"]:z for z in design.zones}
    regions={z['id']:region_bounds(room.bounds,z['bounds_uv']) for z in design.zones if 'bounds_uv' in z}
    reservations=reserved_bounds(room.bounds, design.reserved_areas)
    walls=wall_segments(floor,room)
    locked=[]
    for key in design.protected_groups:
        group=next(g for g in design.groups if g["id"]==key)
        previous=next((g for g in room.metadata.get("room_design",{}).get("groups",[]) if g["id"]==key),None)
        if previous != group:
            raise RoomDesignInfeasible(f"protected group {key} cannot change its design; explicitly unprotect it first")
        member_ids = {i["id"] for i in [group["anchor"], *group["members"]]}
        old_dressing = [i for i in room.metadata.get("room_design", {}).get("surface_items", [])
                        if i["support_member_id"] in member_ids]
        new_dressing = [i for i in design.surface_items if i["support_member_id"] in member_ids]
        if old_dressing != new_dressing:
            raise RoomDesignInfeasible(f"protected group {key} cannot change its surface items")
        old=[o for o in floor.objects if o.room_id==room.id and o.metadata.get("group_key")==key]
        expected={item["id"]:item["category"] for item in [group["anchor"],*group["members"]]}
        if {o.metadata.get("design_member_id"):o.category for o in old}!=expected:
            raise RoomDesignInfeasible(f"protected group {key} has missing or different existing instances")
        locked.extend(deepcopy(old))
    # Resolve every asset before layout; actual dimensions feed the solver.
    assets={}
    existing=[o for o in (floor.objects if existing_objects is None else existing_objects)
              if o.room_id==room.id and not o.asset_id.startswith('procedural::')]
    for group in design.groups:
        if group["id"] in design.protected_groups:
            continue
        for item in [group["anchor"],*group["members"]]:
            base=detail.catalog[item["category"]]
            support_kinds={request['surface'] for request in design.surface_items
                           if request['support_member_id']==item['id']}
            matches=[o for o in existing if o.category==item['category']
                     and o.metadata.get('design_member_id')==item['id']]
            if not matches:
                # Opaque group IDs may change in a whole-room proposal. Reuse
                # a unique existing same-role asset, never guess among several.
                matches=[o for o in existing if o.category==item['category']]
            preferred=matches[0].asset_id if len({o.asset_id for o in matches})==1 else None
            assets[item["id"]]=detail._resolve_asset(base,room_type=room.function,
                style=program.style+" "+design.palette,support_kinds=support_kinds,
                preferred_asset_id=preferred) or base
    # Prose/palette edits must not reshuffle an otherwise unchanged layout.
    rng=random.Random(f"{seed}:{room.id}:groups_v1")
    previous_anchors={o.metadata.get('group_key'):o for o in floor.objects
                      if o.room_id==room.id and o.id==o.metadata.get('group_anchor_id')}

    def make(item, group, x, y, angle):
        asset=assets[item["id"]]
        return InteriorObject(
            id=f"{room.id}_design_{item['id']}", room_id=room.id, category=asset.category,
            asset_id=asset.id, position=Point2D(x,y), width_m=asset.width_m,
            depth_m=asset.depth_m,height_m=asset.height_m,
            rotation_deg=detail._rotation_for_front(asset.front_axis,angle),
            metadata={"planner":"room_groups_v2", "required":True, "front_axis":asset.front_axis,
                      # Procedural bed geometry has its headboard at local +Y.
                      # For meshes, opposite semantic front is an explicit
                      # inference until the registry supplies a headboard axis.
                      "head_axis": asset.head_axis or ("+Y" if asset.id==detail.catalog[item["category"]].id else
                          {"+X":"-X","-X":"+X","+Y":"-Y","-Y":"+Y"}[asset.front_axis]
                      ),
                      "orientation_confidence":asset.orientation_confidence,
                      "group_id":f"{room.id}_{group['id']}", "group_key":group["id"],
                      "design_member_id":item["id"],"zone_id":group["zone"], "room_type":room.function,
                      "room_palette":design.palette, "placement_strategy":"group",
                      "group_anchor_id":f"{room.id}_design_{group['anchor']['id']}"})

    def group_at(group, x,y,angle):
        anchor=make(group["anchor"],group,x,y,angle)
        result=[anchor]
        front=_front(anchor); right=(front[1],-front[0])
        for item in group["members"]:
            axis={"front":front,"back":(-front[0],-front[1]),"right":right,"left":(-right[0],-right[1])}[item["side"]]
            tangent=(-axis[1],axis[0])
            facing=math.degrees(math.atan2(-axis[1],-axis[0])) if item["face_anchor"] else angle
            obj=make(item,group,x,y,facing)
            half_a=(abs(axis[0])*anchor.bounds.width+abs(axis[1])*anchor.bounds.depth)/2
            half_b=(abs(axis[0])*obj.bounds.width+abs(axis[1])*obj.bounds.depth)/2
            lateral=(abs(tangent[0])*obj.bounds.width+abs(tangent[1])*obj.bounds.depth+.18)*item["slot"]
            # Bedside furniture belongs beside the head, not halfway down the
            # mattress. Align back edges using the actual asset head axis and
            # extents; keep requested side, gap, facing and slot unchanged.
            alignment="center"
            if (anchor.category=="bed" and obj.category=="bedside_table"
                    and item["side"] in {"left","right"} and not item["face_anchor"]):
                hx,hy=direction(anchor,contact_axis(anchor,"head"))
                along=hx*tangent[0]+hy*tangent[1]
                if abs(along)>.999:
                    head_a=(abs(hx)*anchor.bounds.width+abs(hy)*anchor.bounds.depth)/2
                    head_b=(abs(hx)*obj.bounds.width+abs(hy)*obj.bounds.depth)/2
                    lateral+=along*(head_a-head_b)
                    alignment="head_edge"
            # gap_m is a preferred minimum. The wire contract historically
            # allowed .15m, but collision checking reserves .16m; enforcing the
            # physical margin here avoids impossible groups regardless of pose.
            effective_gap=max(item["gap_m"],detail.object_clearance_m+.01,
                              .80 if anchor.category in STORAGE and item["side"]=="front" else 0)
            distance=half_a+half_b+effective_gap
            obj.position=Point2D(x+axis[0]*distance+tangent[0]*lateral,y+axis[1]*distance+tangent[1]*lateral)
            obj.metadata.update(group_side=item["side"],face_anchor=item["face_anchor"],
                                requested_gap_m=item["gap_m"],effective_gap_m=effective_gap,
                                group_alignment=alignment)
            result.append(obj)
        return result

    def valid(objects):
        for obj in objects:
            region=regions.get(obj.metadata.get('zone_id'))
            if region and not region.contains_bounds(obj.bounds):
                return False
            if any(area.overlaps_area(obj.bounds) for area in reservations):
                return False
            if obj.id!=obj.metadata.get("group_anchor_id"): continue
            group=next(g for g in design.groups if g["id"]==obj.metadata.get("group_key"))
            policy=placement_policy(group)
            if policy.get('facing'):
                desired={'north':(0,1),'south':(0,-1),'east':(1,0),'west':(-1,0)}[policy['facing']]
                actual=_front(obj)
                if actual[0]*desired[0]+actual[1]*desired[1] < .999:
                    return False
            if policy["mode"]=="wall":
                side,gap=wall_contact(obj,room,policy)
                if policy["wall"] not in ("auto",side) or gap < wall_inset-1e-5 or gap>policy["max_gap_m"]+1e-5:
                    return False
        return (all(detail._relation_position_valid(o,objects,usable,doors) for o in objects)
                and all(usable_envelopes(o,objects,usable) for o in objects)
                and group_relation_cost(design.group_relations,objects) is not None)

    def candidates(group, placed, tx, ty):
        policy=placement_policy(group)
        old=previous_anchors.get(group['id'])
        if old is not None:
            # Use existing realized metric coordinates, never template UVs.
            # Every seed still passes all current constraints below.
            angle=math.degrees(math.atan2(*reversed(_front(old))))
            for dx,dy in ((0,0),(.25,0),(-.25,0),(0,.25),(0,-.25),(.5,0),(-.5,0),(0,.5),(0,-.5)):
                stats['prior_pose_candidates']+=1
                yield old.position.x+dx,old.position.y+dy,angle,None
        # Wall-bound anchors use actual extents, never room-fraction guesses.
        if policy["mode"]=="wall":
            for wall in walls:
                if policy["wall"] not in ("auto",wall["side"]): continue
                sample=make(group["anchor"],group,0,0,0)
                normal={"north":90,"south":-90,"east":0,"west":180}[wall["side"]]
                contact=contact_axis(sample,policy["contact"])
                rotation=normal-AXIS_ANGLES[contact]
                angle=rotation+AXIS_ANGLES[sample.metadata["front_axis"]]
                sample=make(group["anchor"],group,0,0,angle)
                horizontal=wall["side"] in ("north","south")
                extent=sample.bounds.width/2 if horizontal else sample.bounds.depth/2
                normal_extent=sample.bounds.depth/2 if horizontal else sample.bounds.width/2
                gap=wall_inset
                if gap>policy["max_gap_m"]: continue
                lo,hi=wall["start"]+extent+gap,wall["end"]-extent-gap
                # Fit the full group along the wall rather than sampling only
                # the anchor's range. A wide side member can otherwise push all
                # useful samples out of the room despite a feasible interval.
                members=group_at(group,0,0,angle)
                lower=min(o.bounds.min_x if horizontal else o.bounds.min_y for o in members)
                upper=max(o.bounds.max_x if horizontal else o.bounds.max_y for o in members)
                lo=max(lo,(usable.min_x if horizontal else usable.min_y)-lower)
                hi=min(hi,(usable.max_x if horizontal else usable.max_y)-upper)
                region=regions.get(group['zone'])
                if region:
                    lo=max(lo,(region.min_x if horizontal else region.min_y)-lower)
                    hi=min(hi,(region.max_x if horizontal else region.max_y)-upper)
                if lo>hi: continue
                target=usable.min_x+tx*usable.width if horizontal else usable.min_y+ty*usable.depth
                tangents={min(hi,max(lo,target)),lo,hi,(lo+hi)/2}
                tangents.update(lo+(hi-lo)*i/12 for i in range(13))
                sign=-1 if wall["side"] in ("north","east") else 1
                normal_position=wall["boundary"]+sign*(normal_extent+gap)
                for tangent in sorted(tangents):
                    x,y=(tangent,normal_position) if horizontal else (normal_position,tangent)
                    yield x,y,angle,wall
            return
        points={(tx,ty),*((x/6,y/6) for x in range(1,6) for y in range(1,6))}
        if design.furnishing_brief is not None:
            # A fixed 5x5 grid can cap feasible workstations in a long office
            # regardless of area. Add bounded, metric-spaced anchor candidates.
            asset = assets[group["anchor"]["id"]]
            nx = max(5, min(16, int(usable.width/(asset.width_m+.25))))
            ny = max(5, min(16, int(usable.depth/(asset.depth_m+.75))))
            points.update((x/(nx+1), y/(ny+1)) for x in range(1,nx+1) for y in range(1,ny+1))
        # Cross-group alignments need candidates along already placed anchors,
        # otherwise a coarse room grid may never offer a valid relation.
        for obj in placed:
            if obj.id!=obj.metadata.get("group_anchor_id"): continue
            px=(obj.position.x-usable.min_x)/usable.width
            py=(obj.position.y-usable.min_y)/usable.depth
            points.update((px,t) for t in (1/6,1/3,.5,2/3,5/6))
            points.update((t,py) for t in (1/6,1/3,.5,2/3,5/6))
        points=sorted(points); rng.shuffle(points)
        region=regions.get(group['zone'])
        if region:
            # Add a bounded region-local lattice; a room-wide coarse grid can
            # otherwise miss feasible positions in a small functional cluster.
            points += [((region.min_x+region.width*x/8-usable.min_x)/usable.width,
                        (region.min_y+region.depth*y/8-usable.min_y)/usable.depth)
                       for x in range(1,8) for y in range(1,8)]
        for px,py in points:
            angles = ({'north':90,'south':270,'east':0,'west':180}[policy['facing']],) if policy.get('facing') else (0,90,180,270)
            for angle in angles:
                yield usable.min_x+px*usable.width,usable.min_y+py*usable.depth,angle,None

        # Additional bounded anchors derived from the whole functional group.
        # A room-wide lattice can miss a narrow feasible interval between the
        # wall and a doorway even when the complete furniture group fits.
        from cityg.planning.room_constraints import use_envelopes, CHAIRS
        angles = ({'north':90,'south':270,'east':0,'west':180}[policy['facing']],) if policy.get('facing') else (0,90,180,270)
        for angle in angles:
            members = group_at(group, 0, 0, angle)
            boxes = [o.bounds for o in members]
            # Chair pull-back is mandatory. Other furniture may have several
            # alternative access sides; leave those to the unchanged checker.
            boxes.extend(area for o in members if o.category in CHAIRS for area in use_envelopes(o))
            left = usable.min_x - min(b.min_x for b in boxes)
            right = usable.max_x - max(b.max_x for b in boxes)
            bottom = usable.min_y - min(b.min_y for b in boxes)
            top = usable.max_y - max(b.max_y for b in boxes)
            if left > right or bottom > top:
                continue
            for u in (.02, .25, .5, .75, .98):
                for v in (.02, .25, .5, .75, .98):
                    yield left+(right-left)*u, bottom+(top-bottom)*v, angle, None

    # Place constrained anchors first. Locked groups are obstacles from the
    # start; an infeasible local repair never implicitly unlocks them.
    groups=sorted((g for g in design.groups if g["id"] not in design.protected_groups),
                  key=lambda g:placement_policy(g)["mode"]!="wall")
    beam=[(locked,0.0)]
    for group in groups:
        position=zones[group["zone"]]["position"]
        tx,ty={"north":(.5,.78),"south":(.5,.22),"west":(.22,.5),"east":(.78,.5),"center":(.5,.5)}[position]
        if group['zone'] in regions:
            center=regions[group['zone']].center
            tx,ty=(center.x-usable.min_x)/usable.width,(center.y-usable.min_y)/usable.depth
        next_beam=[]
        for placed,cost in beam:
            for x,y,angle,wall in candidates(group,placed,tx,ty):
                stats['candidate_count']+=1
                members=group_at(group,x,y,angle)
                all_objects=placed+members
                if not valid(all_objects):
                    stats['rejected_candidates']+=1
                    continue
                if wall:
                    members[0].metadata["wall_binding"]={**wall,
                        "contact_axis":contact_axis(members[0],placement_policy(group)["contact"]),
                        "gap_m":round(wall_contact(members[0],room,placement_policy(group))[1],6)}
                px,py=(x-usable.min_x)/usable.width,(y-usable.min_y)/usable.depth
                # Penalize relation violations as well as soft-zone distance.
                previous=group_relation_cost(design.group_relations,placed) or 0
                relational=group_relation_cost(design.group_relations,all_objects) or 0
                old=previous_anchors.get(group['id'])
                displacement=(0 if old is None else
                    2*((x-old.position.x)**2+(y-old.position.y)**2)/max(1,usable.width*usable.depth))
                next_beam.append((all_objects,cost+(px-tx)**2+(py-ty)**2+4*(relational-previous)+displacement))
        if not next_beam:
            actual_sizes={item['id']:{'category':item['category'],
                'dimensions_m':[assets[item['id']].width_m,assets[item['id']].depth_m,assets[item['id']].height_m],
                'front_axis':assets[item['id']].front_axis}
                for item in [group['anchor'],*group['members']]}
            raise RoomDesignInfeasible(f"group {group['id']} cannot fit with furniture/door/use clearance; "
                f"failed_group={group['id']}; protected_groups={list(design.protected_groups)}; "
                f"room_size_m={[room.bounds.width,room.bounds.depth]}; candidates={stats['candidate_count']}; "
                f"resolved_group_assets={actual_sizes}; "
                "change this group's arrangement: reduce oversized preferred gap_m within allowed bounds or move seats to other sides/slots. "
                "Physical dimensions and enforced access/use clearances cannot change. If still infeasible request wider scope; do not delete required members")
        next_beam.sort(key=lambda state:state[1])
        # Retain distinct anchor configurations; duplicate states otherwise
        # consume the entire beam after symmetric member arrangements.
        beam=[]; seen=set()
        for state in next_beam:
            signature=tuple((o.id,round(o.position.x,3),round(o.position.y,3),round(o.rotation_deg%360,2)) for o in state[0])
            if signature not in seen:
                seen.add(signature); beam.append(state)
            if len(beam)>=12: break
    result=None; navigation={}
    for objects,_ in beam:
        if not valid(objects): continue
        navigation=circulation_check(objects,room,floor,usable)
        if navigation["ok"]:
            result=objects; break
    if result is None:
        raise RoomDesignInfeasible("no complete layout has connected use spaces: "+navigation.get("reason","invalid protected groups"))
    for obj in result:
        # Preserve protected objects byte-for-byte, including their metadata.
        if obj.metadata.get("group_key") not in design.protected_groups:
            obj.metadata["room_circulation"]=navigation
    area=sum(o.bounds.area for o in result)
    # Density is a soft occupancy budget, never an instruction to delete members.
    if area/usable.area>min(.70,max(.20,program.density+.15)):
        raise RoomDesignInfeasible("furniture occupancy exceeds requested density budget")
    stats['elapsed_s']=round(time.monotonic()-started,6)
    room.metadata['layout_solver_diagnostics']=stats
    return result
