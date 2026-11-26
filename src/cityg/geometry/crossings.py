"""Connect painted crossings to the compiled sidewalks with physical curb ramps."""
from collections import defaultdict
from math import cos, radians, sin

from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.polygons import geos


def connect_crossings(primitives):
    """Cut both curb mouths and median together, only where both landings exist."""
    try:
        s = geos()
    except RuntimeError:
        # Preserve the dependency-free compilation profile on rectangular maps.
        return {"curb_ramp_pairs": 0, "curb_ramp_status": "requires_geospatial"}

    cuttable = {
        "sidewalk",
        "curb",
        "road_median",
        "sidewalk_frontage_strip",
        "sidewalk_furnishing_strip",
        "bicycle_lane_surface",
    }
    by_road = defaultdict(list)
    crossings = defaultdict(lambda: defaultdict(list))
    for item in primitives:
        if item.semantic_class in cuttable:
            by_road[item.owner_id].append(item)
        elif item.semantic_class == "crosswalk":
            crossings[item.owner_id][item.metadata["junction_side"]].append(item)

    replacements = {}
    ramps = []
    omitted = 0
    for road, groups in crossings.items():
        surfaces = [(p, primitive_footprint(p)) for p in by_road[road]]
        sidewalks = s.union_all([g for p, g in surfaces if p.semantic_class == "sidewalk"])
        landing_surface = sidewalks.buffer(1e-7)
        cuts = defaultdict(list)
        reserved = []
        for end, stripes in groups.items():
            # Choose a stripe near the centre of the crossing with enough paved
            # landing on BOTH sides. Test actual clipped geometry at bends.
            for _, stripe in sorted(
                enumerate(stripes), key=lambda pair: abs(pair[0] - (len(stripes) - 1) / 2)
            ):
                az = radians(stripe.rotation_z_deg)
                ux, uy = cos(az), sin(az)
                x, y = stripe.center.x, stripe.center.y

                def point(along, across):
                    return (x + along * ux - across * uy, y + along * uy + across * ux)

                def rectangle(left, right, width=1.0):
                    return s.Polygon(
                        [
                            point(-width, left),
                            point(width, left),
                            point(width, right),
                            point(-width, right),
                        ]
                    )

                # The markings stop 0.45 m short of the street edge. The toe
                # overlaps that line by 5 cm; 1.8 m run takes up a 15 cm rise.
                toe = stripe.size.y / 2 - 0.05
                back = toe + 1.8
                if toe <= 0:
                    continue
                landings = [
                    rectangle(sign * (toe + 0.55), sign * (back + 0.15)) for sign in (-1, 1)
                ]
                if not all(landing_surface.covers(g) for g in landings):
                    continue
                band = rectangle(-back, back)
                if any(band.intersects(old) for old in reserved):
                    continue
                break
            else:
                for stripe in stripes:
                    replacements[stripe.id] = None
                omitted += 1
                continue
            reserved.append(band)
            # The paint is wider along the street than the actual curb and median openings.
            stripe.metadata["crossing_passage_xy"] = list(
                rectangle(-toe - 0.01, toe + 0.01).exterior.coords
            )[:-1]
            for sign, side in ((1, "left"), (-1, "right")):
                area = rectangle(sign * toe, sign * back)

                def height(px, py):
                    lateral = sign * ((py - y) * ux - (px - x) * uy)
                    return 0.15 * (lateral - toe) / (back - toe)

                ramp = polygon_mesh(
                    f"{road}_curb_ramp_{end}_{side}",
                    road,
                    area,
                    height,
                    0.05,
                    "curb_ramp",
                    "concrete",
                    collision=True,
                    metadata={"junction_side": end, "side": side, "pedestrian": True},
                )
                ramps.append(ramp)
                for p, g in surfaces:
                    if p.semantic_class != "road_median" and g.intersection(area).area > 1e-8:
                        cuts[p.id].append(area)
            for p, g in surfaces:
                if p.semantic_class == "road_median" and g.intersects(band):
                    cuts[p.id].append(band)
        for p, g in surfaces:
            if p.id in cuts:
                remainder = g.difference(s.union_all(cuts[p.id]))
                replacements[p.id] = polygon_mesh(
                    p.id,
                    road,
                    remainder,
                    p.center.z + p.size.z / 2,
                    p.size.z,
                    p.semantic_class,
                    p.material_id,
                    collision=p.collision_enabled,
                    metadata={**p.metadata, "curb_openings_cut": True},
                )
    primitives[:] = [
        replacements.get(p.id, p) for p in primitives if replacements.get(p.id, p) is not None
    ]
    primitives.extend(ramps)
    return {"curb_ramp_pairs": len(ramps) // 2, "crossings_omitted_no_landing": omitted}
