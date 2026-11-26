"""Geometry-derived review diagrams and bounded exterior observation presets."""
import html
from cityg.observation import AdaptiveObservationPlanner


def review_views(city):
    planner=AdaptiveObservationPlanner(include_room_views=False)
    bird=planner._global_views(city)[0].to_dict()
    bird['view_id']='bird'
    if city.rivers:
        # Distant, nearly coplanar road/riverbank strips need more depth precision.
        # This elevated camera has no foreground geometry near the lens.
        bird['near_clip_m']=max(1.0,bird['camera_position'][2]*.1)
    center=city.bounds.center
    # Favor occupied, central streets, not a dense edge segment facing out of town.
    streets=sorted(planner._road_views(city,[]),key=lambda v:(
        not bool(v.semantic_context.get('adjacent_appearance_plans')),
        (v.camera_position[0]-center.x)**2+(v.camera_position[1]-center.y)**2,
        -len(v.coverage_entity_ids),v.view_id))
    selected=[bird];used=set()
    for v in streets:
        function=v.semantic_context.get('dominant_function')
        if used and function in used:continue
        view=v.to_dict();view['view_id']=f'street_{len(selected)}';selected.append(view);used.add(function)
        if len(selected)==3:break
    if len(selected)<3:
        first=selected[-1]['target_entity_ids'][0] if len(selected)>1 else None
        for v in streets:
            if v.target_entity_ids[0]!=first:
                view=v.to_dict();view['view_id']='street_2';selected.append(view);break
    feature=(planner._waterfront_views(city,[]) if city.rivers else planner._landscape_views(city,[]))
    if feature:
        # Use the specifically named available public-space anchor, if present.
        anchor=city.metadata.get('urban_layout_prototype',{}).get('public_space_anchor_id')
        v=next((v for v in feature if anchor in v.target_entity_ids),feature[0])
        view=v.to_dict();view['view_id']='feature';selected.append(view)
    for v in selected:
        if v['view_id'].startswith('street_'):
            x,y,z=v['camera_position'];tx,ty,tz=v['look_at']
            if (tx-x)*(center.x-x)+(ty-y)*(center.y-y)<0:
                v['look_at']=[2*x-tx,2*y-ty,tz]
        # Internal textured capture profile: keep real meshes/PBR, omit costly
        # shadow maps and HDR PMREM on headless CPU renderers. No UI mode change.
        v.update(render_profile='prototype_capture',appearance='presentation',auto_cutaway=False)
    return selected


def plan_svg(city):
    """Canonical parcels and planning envelopes, explicitly not facade geometry."""
    scale=1000/max(city.bounds.width,city.bounds.depth);pad=36
    w=city.bounds.width*scale+2*pad;h=city.bounds.depth*scale+2*pad+70
    def xy(x,y):return pad+(x-city.bounds.min_x)*scale,pad+(city.bounds.max_y-y)*scale
    def polygon(points,attrs):
        points=' '.join(f'{x:.2f},{y:.2f}' for x,y in (xy(p.x,p.y) for p in points))
        return f'<polygon points="{points}" {attrs}/>'
    def rect(b,attrs):
        x,y=xy(b.min_x,b.max_y)
        return f'<rect x="{x}" y="{y}" width="{b.width*scale}" height="{b.depth*scale}" {attrs}/>'
    def path(points,width,color):
        ps=' '.join(f'{x:.2f},{y:.2f}' for x,y in (xy(p.x,p.y) for p in points))
        return f'<polyline points="{ps}" fill="none" stroke="{color}" stroke-width="{width*scale}" stroke-linejoin="round" stroke-linecap="round"/>'
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="#f3f2eb"/>',
         f'<text x="36" y="24" font-size="16" font-family="sans-serif">{html.escape(city.name)} · north ↑</text>']
    for p in city.iter_parcels():
        attrs='fill="#e5e1d7" stroke="#c1bbaa" stroke-width="1"'
        svg.append(polygon(p.boundary,attrs) if p.boundary else rect(p.bounds,attrs))
    from cityg.schemas import Bounds2D
    for s in city.metadata.get('landscape_sites',[]):
        b=Bounds2D(**s['bounds']);color={'park':'#b3d19a','garden':'#cadba8','plaza':'#dbceaf'}[s['style']]
        svg.append(rect(b,f'fill="{color}" stroke="#8b9a7c" stroke-width="1"'))
        x,y=xy(b.center.x,b.center.y)
        svg.append(f'<text x="{x}" y="{y}" font-size="9" text-anchor="middle" font-family="sans-serif">{s["id"]}</text>')
    for r in city.rivers:svg.append(path(r.centerline,r.width_m+2*r.bank_width_m,'#9bc9bb'));svg.append(path(r.centerline,r.width_m,'#6ca8ca'))
    for r in city.road_network.segments:
        svg.append(path(r.centerline,r.width_m+2*r.sidewalk_width_m,'#c9c7c0'))
        svg.append(path(r.centerline,r.width_m,{'arterial':'#738088','collector':'#929da2'}.get(r.road_class,'#a9b0b2')))
    colors={'residential':'#ca916c','commercial':'#719db8','mixed_use':'#b78db0','public_service':'#b9ad6e','industrial':'#aaa'}
    for b in city.iter_buildings():
        svg.append(rect(b.footprint,f'fill="{colors.get(b.function,"#aaa")}" stroke="#414d53" stroke-width="1.1"'))
        x,y=xy(b.footprint.center.x,b.footprint.center.y)
        label=b.id.rsplit('_',1)[-1]+' / '+str(len(b.floors))+'F'
        svg.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#142b36">{label}</text>')
        x,y=xy(b.entrance.x,b.entrance.y);svg.append(f'<circle cx="{x}" cy="{y}" r="2" fill="#e15037"/>')
    svg.append(f'<text x="36" y="{h-45}" font-size="13" font-family="sans-serif">Building rectangles = planning envelopes; see 3D for actual massing. Labels: building ID suffix / floors.</text>')
    svg.append(f'<text x="36" y="{h-24}" font-size="13" font-family="sans-serif">Orange: housing · blue: business · purple: mixed · ochre: civic · red dot: entrance · green: public landscape</text></svg>')
    return ''.join(svg)
