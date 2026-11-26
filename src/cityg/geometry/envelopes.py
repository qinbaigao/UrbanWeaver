"""Convex loft shells and actual surface-aligned curtain-wall panels."""
from __future__ import annotations

import math

from cityg.envelopes import envelope_contract
from cityg.geometry.appearance import facade_material_style, facade_style_for_face
from cityg.geometry.facades import facade_style_for_function
from cityg.geometry.model import MaterialSpec
from cityg.geometry.path_mesh import inline_mesh, path_slab
from cityg.paths import PlanarPath2D
from cityg.schemas import Point2D


def mix(a, b, t):
    return tuple(x + (y-x)*t for x, y in zip(a, b))


def loft_mesh(identifier, owner, rings, semantic, material, layer, *, collision=False, metadata=None):
    n = len(rings[0])
    vertices = [p for ring in rings for p in ring]
    faces = []
    for k in range(len(rings)-1):
        for i in range(n):
            a, b = k*n+i, k*n+(i+1)%n
            faces.extend(((a, b, b+n), (a, b+n, a+n)))
    top = (len(rings)-1)*n
    for i in range(1, n-1):
        faces.extend(((0, i+1, i), (top, top+i, top+i+1)))
    mesh = inline_mesh(identifier, owner, vertices, faces, semantic, material,
                       collision=collision, metadata=metadata)
    mesh.layer_id = layer
    return mesh


def panel_mesh(identifier, owner, quad, semantic, material, layer, *, depth=.06, offset=0., metadata=None):
    # Horizontal edge crossed with the up/slope vector gives the outward normal
    # of a CCW convex envelope, including leaning/tapered facades.
    a, b, _, d = quad
    u, v = [b[i]-a[i] for i in range(3)], [d[i]-a[i] for i in range(3)]
    normal = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
    length = math.sqrt(sum(x*x for x in normal))
    if length < 1e-8:
        raise ValueError("degenerate facade panel")
    normal = [x/length for x in normal]
    vertices = [[p[i] + normal[i]*(offset+sign*depth/2) for i in range(3)]
                for sign in (-1, 1) for p in quad]
    faces = [(0,2,1),(0,3,2),(4,5,6),(4,6,7)]
    for i in range(4):
        j = (i+1)%4
        faces.extend(((i,j,j+4),(i,j+4,i+4)))
    result = inline_mesh(identifier, owner, vertices, faces, semantic, material,
        collision=False, metadata={**(metadata or {}), "surface_normal": normal})
    result.layer_id = layer
    return result


def compile_envelope(building, scene):
    primitive_start = len(scene.primitives)
    contract = envelope_contract(building)
    rings = contract["rings"]
    floors = sorted(building.floors, key=lambda f: f.elevation_m)
    layer = f"shell:{building.id}"
    config = contract["config"]
    curtain = config.get("facade_system", "punched") == "curtain_wall"
    style = facade_material_style(building, facade_style_for_function(
        building.function, variant_key=building.metadata.get("facade_style_override")))
    common = {"building_id": building.id, "exterior_envelope": True,
              "facade_system": "curtain_wall_v1" if curtain else "polygon_punched_v1",
              "interior_supported": False}
    scene.primitives.append(loft_mesh(f"{building.id}_envelope_collision", building.id,
        rings, "collision_envelope", "collision_proxy", layer, collision=True, metadata=common))
    material_ids = {m.id for m in scene.materials}
    for mat in (MaterialSpec("curtain_glass", (.17,.36,.44), roughness=.13, metallic=.03, opacity=.88),
                MaterialSpec("curtain_spandrel", (.10,.17,.21), roughness=.29, metallic=.15)):
        if mat.id not in material_ids:
            scene.materials.append(mat)
    n = len(rings[0])
    entry_edge, entry_bay, entry_point = (contract["entrance"][k] for k in ("edge","bay","point"))
    scene.metadata.setdefault("exterior_envelopes", {})[building.id] = contract
    scene.metadata.setdefault("facade_buildings", {})[building.id] = {
        **common, "appearance_plan": building.metadata.get("appearance_plan", {}),
        "window_count": 0, "entrance_anchor": contract["entrance"]}
    for ordinal, floor in enumerate(floors):
        lower, upper = rings[ordinal], rings[ordinal+1]
        slab_bottom = [[x,y,z-.16] for x,y,z in lower]
        scene.primitives.append(loft_mesh(f"{floor.id}_envelope_slab", floor.id,
            [slab_bottom, lower], "floor_slab", "concrete", layer, metadata=common))
        for edge in range(n):
            a,b = lower[edge], lower[(edge+1)%n]
            d,c = upper[edge], upper[(edge+1)%n]
            normal_angle = math.degrees(math.atan2(-(b[0]-a[0]), b[1]-a[1])) - float(building.metadata.get("orientation_deg", 0))
            side = ("east","north","west","south")[round(normal_angle/90)%4]
            face_style = facade_style_for_face(building, style, side)
            # Fixed bay counts across floors preserve aligned facade seams.
            edge_length = math.dist(rings[0][edge], rings[0][(edge+1)%n])
            count = max(1, min(32, round(edge_length / (2.6 if curtain else 3.4))))
            for bay in range(count):
                s0,s1 = bay/count, (bay+1)/count
                meta = {**common, "floor_level": floor.level, "edge": edge, "bay": bay}
                is_entry = ordinal == 0 and edge == entry_edge and bay == entry_bay
                if is_entry:
                    meta["entrance_anchor"] = True
                def patch(suffix, u0,u1,v0,v1,semantic,material,depth=.06,offset=.04):
                    quad = [mix(mix(a,b,u),mix(d,c,u),v)
                            for u,v in ((u0,v0),(u1,v0),(u1,v1),(u0,v1))]
                    scene.primitives.append(panel_mesh(f"{floor.id}_env_{edge}_{bay}_{suffix}",
                        floor.id, quad, semantic, material, layer, depth=depth, offset=offset, metadata=meta))
                gap = min((s1-s0)*.06, .035/max(edge_length, .01))
                if curtain:
                    patch("glass",s0+gap,s1-gap,.03,.79,
                          "curtain_wall_glass", "curtain_glass", .045)
                    patch("spandrel",s0,s1,.79,1,"exterior_wall","curtain_spandrel")
                else:
                    # Explicit wall strips around an opening, not an opaque box
                    # behind glass. Convex loft panels support sloping walls too.
                    ratio = min(.84, face_style.window_ratio)
                    shift = 0.
                    language = building.metadata.get("appearance_plan", {}).get("language")
                    if language == "paired_windows" and not is_entry:
                        shift = .10 if bay%2 == 0 and bay+1<count else -.10 if bay%2 else 0
                    u0,u1 = s0+(s1-s0)*((1-ratio)/2+shift),s0+(s1-s0)*((1+ratio)/2+shift)
                    v0 = .03 if is_entry else min(.30, face_style.sill_height_m/floor.height_m)
                    v1 = min(.89, v0 + (.69 if is_entry else face_style.window_height_ratio))
                    patch("wall_l",s0,u0,0,1,"exterior_wall",style.wall_material)
                    patch("wall_r",u1,s1,0,1,"exterior_wall",style.wall_material)
                    patch("wall_b",u0,u1,0,v0,"exterior_wall",style.wall_material)
                    patch("wall_t",u0,u1,v1,1,"exterior_wall",style.wall_material)
                    patch("window",u0,u1,v0,v1,"facade_window",style.glass_material)
                    if language == "shaded_bays" and not is_entry:
                        patch("shade",s0+(s1-s0)*.06,s1-(s1-s0)*.06,v1,v1+.025,
                              "facade_fin",style.accent_material,.45,.24)
                patch("mullion",s0,s0+gap*2,0,1,"facade_frame",style.frame_material,.11,.08)
                patch("transom",s0,s1,.78,.80,"facade_frame",style.frame_material,.11,.08)
                if is_entry:
                    # Closed, non-interactive door; the outdoor graph stops here.
                    patch("entry",s0+(s1-s0)*.26,s1-(s1-s0)*.26,.02,.66,
                          "entrance_portal", "curtain_glass", .08,.14)
                scene.metadata["facade_buildings"][building.id]["window_count"] += 1
    roof = rings[-1]
    scene.primitives.append(loft_mesh(f"{building.id}_envelope_roof",building.id,
        [roof, [[x,y,z+.15] for x,y,z in roof]], "roof", "roof", layer, metadata=common))
    start = building.entrance
    end = Point2D(entry_point[0],entry_point[1])
    if math.hypot(start.x-end.x,start.y-end.y) > .1:
        path = path_slab(f"{building.id}_envelope_access",building.id,
            PlanarPath2D((start,end)),1.6,.03,.06,"landscape_path","concrete",
            collision=False, metadata=common)
        path.layer_id = layer
        scene.primitives.append(path)
    # A curved facade has many quads, but should not cost one draw call per
    # mullion/pane. Batch by floor/material/semantic without losing ownership.
    groups = {}
    retained = []
    for primitive in scene.primitives[primitive_start:]:
        if "surface_normal" not in primitive.metadata or primitive.semantic_class == "entrance_portal":
            retained.append(primitive)
            continue
        key = (primitive.owner_id,primitive.semantic_class,primitive.material_id)
        groups.setdefault(key,[]).append(primitive)
    for (owner,semantic,material), members in groups.items():
        vertices,faces = [],[]
        for p in members:
            offset = len(vertices)
            vertices.extend([[p.center.x+v[0]*p.size.x,p.center.y+v[1]*p.size.y,p.center.z+v[2]*p.size.z]
                             for v in p.metadata["mesh_vertices"]])
            faces.extend(tuple(i+offset for i in f) for f in p.metadata["mesh_triangles"])
        mesh = inline_mesh(f"{owner}_envelope_{semantic}_{material}",owner,vertices,faces,
            semantic,material,collision=False,metadata={**common,"panel_count":len(members),
                "panels":[{"edge":p.metadata["edge"],"bay":p.metadata["bay"],
                           "surface_normal":p.metadata["surface_normal"]} for p in members]})
        mesh.layer_id = layer
        retained.append(mesh)
    scene.primitives[primitive_start:] = retained


def validate_envelope_geometry(city, scene, report):
    """Check the realized shell rather than trusting its capability metadata."""
    from collections import Counter
    from cityg.envelopes import envelope_config
    for building in city.iter_buildings():
        if not envelope_config(building):
            continue
        expected = envelope_contract(building)
        actual = scene.metadata.get("exterior_envelopes", {}).get(building.id)
        if actual != expected:
            report.add("error", "stale_exterior_envelope", "Compiled floor-ring contract differs from canonical parameters", building.id)
        hulls = [p for p in scene.primitives if p.owner_id == building.id
                 and p.semantic_class == "collision_envelope" and p.collision_enabled]
        if len(hulls) != 1:
            report.add("error", "exterior_collision_missing", "Expected one actual loft collision mesh", building.id)
            continue
        hull = hulls[0]
        vertices = hull.metadata.get("mesh_vertices", [])
        faces = hull.metadata.get("mesh_triangles", [])
        valid_mesh = bool(vertices and faces) and all(
            isinstance(p, (list, tuple)) and len(p) == 3
            and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p)
            for p in vertices
        ) and all(
            isinstance(face, (list, tuple)) and len(face) == 3
            and all(type(i) is int and 0 <= i < len(vertices) for i in face)
            and len(set(face)) == 3 for face in faces
        )
        if not valid_mesh:
            report.add("error", "exterior_collision_invalid", "Exterior collision has invalid vertices or triangles", building.id)
            continue
        expected_vertices = [p for ring in expected["rings"] for p in ring]
        world = [[hull.center.x+p[0]*hull.size.x, hull.center.y+p[1]*hull.size.y,
                  hull.center.z+p[2]*hull.size.z] for p in vertices]
        if len(world) != len(expected_vertices) or any(math.dist(a,b)>1e-5 for a,b in zip(world,expected_vertices)):
            report.add("error", "exterior_collision_mismatch", "Collision mesh does not follow the floor rings", building.id)
        edges = Counter(tuple(sorted((face[i],face[(i+1)%3]))) for face in faces for i in range(3))
        if not edges or any(count != 2 for count in edges.values()):
            report.add("error", "exterior_collision_open", "Exterior collision mesh is not watertight", building.id)
        owned = [p for p in scene.primitives if p.layer_id == f"shell:{building.id}"]
        if sum(p.semantic_class == "entrance_portal" for p in owned) != 1:
            report.add("error", "exterior_entry_count", "Expected one realized closed entrance", building.id)
        if not any(p.semantic_class == "roof" for p in owned):
            report.add("error", "exterior_roof_missing", "Exterior envelope requires a roof cap", building.id)
        for floor in building.floors:
            if not any(p.owner_id == floor.id and p.semantic_class == "floor_slab" for p in owned):
                report.add("error", "exterior_floor_plate_missing", "Envelope is missing a horizontal floor plate", floor.id)
