"""Curated mixed borders for paved parcels, distinct from residential lawns.

Only local, textured assets are used. Missing assets never turn into coloured
balls. Whole planting islands and fitted meshes must fit the usable polygon;
an empty/too-tight parcel is preferable to planting across an entrance.
"""
from collections import Counter, defaultdict
import math

from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.model import Vec3
from cityg.polygons import box_shape, geos, parcel_shape, polygon_parts, river_shape, road_shape


PALETTES = (
    ("gold_meadow", "flower_gazania", "flower_ursinia", "grass_medium_02", "shrub_02"),
    ("blue_border", "flower_heliophila", "periwinkle", "grass_medium_02", "searsia"),
    ("mixed_perennial", "flower_ursinia", "flower_heliophila", "grass_medium_02", "shrub_02"),
)
LEGACY = {"parcel_planting_bed", "parcel_flower_mass", "parcel_shrub_asset", "parcel_shrub"}
VERSION = "paved_mixed_border_v1"


def enrich_paved_parcels(compiler, city, scene):
    """Replace sparse generic planting only where a real mixed border fits.

    Also usable on an existing compiled scene without recompiling buildings.
    Stable IDs and seeded samples make a repeat application idempotent.
    """
    if not compiler.asset_registry_configured:
        return {"status": "skipped_no_asset_registry"}
    s = geos()
    previous = [p for p in scene.primitives if p.metadata.get("planting_system") == VERSION]
    base = [p for p in scene.primitives if p.metadata.get("planting_system") != VERSION]
    by_owner = defaultdict(list)
    for p in base:
        by_owner[p.owner_id].append(p)
    routes = [primitive_footprint(p).buffer(.6) for p in base
              if p.semantic_class == "frontage_connector" or p.metadata.get("frontage_role") == "entrance_path"]
    roads = [road_shape(r, r.sidewalk_width_m + .35) for r in city.road_network.segments]
    water = [river_shape(r, "reserve") for r in city.rivers]
    global_blocked = s.union_all(routes + roads + water)
    new = []; replaced = set(); records = []; asset_counts = Counter()
    for district in city.districts:
        for parcel in district.parcels:
            function = compiler._parcel_function(parcel, district.function)
            if not parcel.buildings or function not in {"commercial", "mixed_use", "civic"}:
                continue
            seed = compiler._parcel_seed(parcel.id, VERSION)
            palette = PALETTES[seed % len(PALETTES)]
            shape = parcel_shape(parcel)
            obstacles = [box_shape(b.footprint).buffer(1.0) for b in parcel.buildings]
            # Keep actual entrance approach clear even if no frontage connector
            # was emitted (e.g. an entrance too far away from the road).
            for b in parcel.buildings:
                angle = math.radians(float(b.metadata.get("orientation_deg", 0)))
                cx, cy = b.footprint.center.x, b.footprint.center.y
                dx, dy = b.entrance.x-cx, b.entrance.y-cy
                ex, ey = cx+dx*math.cos(angle)-dy*math.sin(angle), cy+dx*math.sin(angle)+dy*math.cos(angle)
                length = max(math.hypot(ex-cx, ey-cy), .001)
                obstacles.append(s.LineString([(ex, ey), (ex+8*(ex-cx)/length, ey+8*(ey-cy)/length)]).buffer(2.0))
            # Realized lower-floor slabs may extend beyond planning rectangles.
            floor_ids = {f.id for b in parcel.buildings for f in b.floors if f.level == 0}
            for owner in floor_ids:
                obstacles.extend(primitive_footprint(p).buffer(.8) for p in by_owner[owner]
                                 if p.semantic_class == "floor_slab")
            obstacles.extend(primitive_footprint(p).buffer(.35) for p in by_owner[parcel.id]
                if p.semantic_class not in LEGACY and p.center.z+p.size.z/2 > .3
                and p.semantic_class != "parcel_ground")
            available = shape.buffer(-.45).difference(global_blocked).difference(s.union_all(obstacles))
            borders = polygon_parts(shape.buffer(-2.5))
            if not borders or available.area < 24:
                continue
            target = min(6, max(2, round(available.area/500)))
            placed = []; parcel_items = []
            # Sampling a parcel's real perimeter handles slanted/irregular lots
            # without forcing a row of identical objects on every side.
            for attempt in range(target*24):
                border = borders[attempt % len(borders)].exterior
                t = ((seed % 1000)/1000 + attempt*.61803398875) % 1
                point = border.interpolate(t, normalized=True)
                before = border.interpolate((t*border.length-.2) % border.length)
                after = border.interpolate((t*border.length+.2) % border.length)
                angle = math.atan2(after.y-before.y, after.x-before.x)
                co, si = math.cos(angle), math.sin(angle)
                def world(x,y):
                    return (point.x+x*co-y*si, point.y+x*si+y*co)
                bed = s.Polygon([world(3.8*math.cos(i*math.tau/16), 1.65*math.sin(i*math.tau/16)) for i in range(16)])
                if not available.covers(bed) or any(bed.distance(old) < 4 for old in placed):
                    continue
                index = len(placed); prefix = f"{parcel.id}_mixed_border_{index:02d}"
                meta = {"parcel_id":parcel.id,"district_id":district.id,"parcel_function":function,
                        "site_detail":True,"site_feature":"mixed_border", "planting_system":VERSION,
                        "planting_palette":palette[0],"planting_bed_id":prefix}
                plants = []
                slots = [(-2.4,.15, "shrub",palette[4]),(-1.25,-.35,"plant",palette[1]),
                         (-.35,.55,"plant",palette[3]),(.25,-.55,"plant",palette[2]),
                         (1.25,.35,"plant",palette[1]),(2.45,-.1,"shrub",palette[4]),
                         (0,.1,"plant",palette[3])]
                for j,(x,y,category,tag) in enumerate(slots):
                    px,py = world(x,y)
                    scale = .88 + (compiler._parcel_seed(prefix,str(j))%23)/100
                    dimensions = (1.15,1.15,1.15) if category == "shrub" else ((.6,.6,.8) if tag.startswith("grass") else (1.35,1.35,.65))
                    size = Vec3(*(v*scale for v in dimensions))
                    item = compiler._outdoor_mesh(f"{prefix}_plant_{j:02d}",parcel.id,
                        Vec3(px,py,.10+size.z/2),size,float(compiler._parcel_seed(prefix,str(j),"yaw")%360),
                        "parcel_shrub_asset" if category == "shrub" else "parcel_plant_asset",
                        category,tag,"roads",metadata={**meta,"planting_role":tag},required_asset_tags=(tag,))
                    if item is not None and bed.covers(primitive_footprint(item)):
                        plants.append(item)
                if len(plants) < 4 or len({p.metadata['planting_role'] for p in plants}) < 2:
                    continue
                soil = polygon_mesh(prefix,parcel.id,bed,.10,.045,"parcel_planting_bed","mulch_warm",metadata=meta)
                parcel_items.extend([soil,*plants]); placed.append(bed)
                if len(placed) >= target:
                    break
            if parcel_items:
                new.extend(parcel_items); replaced.add(parcel.id)
                counts = Counter(p.metadata.get("asset_id") for p in parcel_items if p.metadata.get("asset_id"))
                asset_counts.update(counts)
                records.append({"parcel_id":parcel.id,"palette":palette[0],"bed_count":len(placed),"asset_counts":dict(counts)})
    # Existing planting is preserved if no usable asset/space was found. Also
    # preserve a previous successful border when local assets become unavailable.
    retained_old = [p for p in previous if p.owner_id not in replaced]
    removed = [p for p in base if p.owner_id in replaced and p.semantic_class in LEGACY]
    scene.primitives = [p for p in base if not(p.owner_id in replaced and p.semantic_class in LEGACY)] + retained_old + new
    report = {"version":VERSION,"changed_parcel_count":len(records),"parcels":records,
              "asset_counts":dict(asset_counts),"new_asset_instances":sum(asset_counts.values()),
              "removed_legacy_primitives":len(removed),"retained_previous_primitives":len(retained_old)}
    scene.metadata["parcel_planting"] = report
    return report
