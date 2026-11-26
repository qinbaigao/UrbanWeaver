"""Bounded, render-only facade geometry variation on existing planar windows.

No boolean holes or interiors are claimed: this is opaque exterior glazing over
the existing shell. Non-planar surfaces, ground floors and curtain walls stay as-is.
"""
from collections import defaultdict, Counter
from copy import deepcopy
import math

STYLES = {'horizontal_ribbon', 'vertical_strip', 'paired_storeys'}
REMOVABLE = {'facade_window', 'facade_frame', 'window_backing',
             'facade_language_detail', 'facade_zone_band', 'facade_fin'}


def axes(p):
    angle = math.radians(p['rotation_z_deg']); c, s = math.cos(angle), math.sin(angle)
    along_x = p['size']['x'] >= p['size']['y']
    tangent = (c, s) if along_x else (-s, c)
    side = p['metadata']['facade_side']
    nx, ny = {'north': (0, 1), 'south': (0, -1), 'east': (1, 0), 'west': (-1, 0)}[side]
    normal = (c*nx-s*ny, s*nx+c*ny)
    return tangent, normal, 'x' if along_x else 'y'


def coordinates(p):
    tangent, normal, axis = axes(p); x, y = p['center']['x'], p['center']['y']
    return x*tangent[0]+y*tangent[1], x*normal[0]+y*normal[1], p['size'][axis]


def surface_key(p):
    m = p['metadata']
    return (p['layer_id'], m['massing_part'], m['facade_side'], round(p['rotation_z_deg'], 5), round(coordinates(p)[1], 2))


def box(template, suffix, u, z, width, height, material, semantic, depth=.06, offset=.075):
    p = deepcopy(template); tangent, normal, axis = axes(template)
    _, d, _ = coordinates(template)
    p['id'] = template['id'] + '_rhythm_' + suffix
    p['center'] = dict(x=tangent[0]*u+normal[0]*(d+offset), y=tangent[1]*u+normal[1]*(d+offset), z=z)
    p['size'] = dict(x=width if axis=='x' else depth, y=width if axis=='y' else depth, z=height)
    p['material_id'] = material; p['semantic_class'] = semantic
    p['metadata']['render_only_facade_rhythm'] = True
    p['collision_enabled'] = False
    return p


def split_rows(rows):
    """Never bridge a courtyard gap or independently exposed facade segment."""
    ordered = sorted(rows, key=lambda p: coordinates(p)[0]); runs = []
    for p in ordered:
        u, _, width = coordinates(p)
        if not runs:
            runs.append([p]); continue
        prev = runs[-1][-1]; pu, _, pw = coordinates(prev)
        if u-pu > 1.8*max(width,pw):runs.append([p])
        else:runs[-1].append(p)
    return runs


def split_columns(rows):
    ordered = sorted(rows, key=lambda p:p['metadata']['floor_level']); runs=[]
    for p in ordered:
        if not runs:
            runs.append([p]); continue
        prev=runs[-1][-1]
        if (p['metadata']['floor_level'] != prev['metadata']['floor_level']+1
                or p['center']['z']-prev['center']['z'] > 2.4*max(p['size']['z'],prev['size']['z'])):
            runs.append([p])
        else:runs[-1].append(p)
    return runs


def panels(rows, style):
    out=[]
    if style=='horizontal_ribbon':
        for run in split_rows(rows):
            t=run[0]; low=min(coordinates(p)[0]-coordinates(p)[2]/2 for p in run)
            high=max(coordinates(p)[0]+coordinates(p)[2]/2 for p in run)
            z=sum(p['center']['z'] for p in run)/len(run)
            height=min(p['size']['z'] for p in run)*.88
            mid=(low+high)/2; width=high-low
            out.append(box(t,'ribbon',mid,z,width,height,'rhythm_glass_ribbon','facade_window'))
            for j,zz in enumerate((z-height/2-.065,z+height/2+.065)):
                out.append(box(t,f'ledge{j}',mid,zz,width,.13,'rhythm_light_stone','facade_frame',depth=.24,offset=.10))
            for j,p in enumerate(run[:-1]):
                u=(coordinates(p)[0]+coordinates(run[j+1])[0])/2
                out.append(box(t,f'mullion{j}',u,z,.045,height,'rhythm_dark_metal','facade_frame',offset=.12))
    else:
        for run in split_columns(rows):
            groups=[run] if style=='vertical_strip' else [run[i:i+2] for i in range(0,len(run),2)]
            for group in groups:
                t=group[0]; u,_,width=coordinates(t)
                width=min(coordinates(p)[2] for p in group)*(.76 if style=='vertical_strip' else .85)
                bottom=min(p['center']['z']-p['size']['z']/2 for p in group)
                top=max(p['center']['z']+p['size']['z']/2 for p in group)
                z=(bottom+top)/2; height=top-bottom
                out.append(box(t,'column',u,z,width,height,'rhythm_glass_vertical','facade_window'))
                for j,uu in enumerate((u-width/2-.09,u+width/2+.09)):
                    out.append(box(t,f'jamb{j}',uu,z,.18,height,'rhythm_light_stone','facade_frame',depth=.24,offset=.10))
                for j,zz in enumerate((bottom-.045,top+.045)):
                    out.append(box(t,f'cap{j}',u,zz,width+.36,.09,'rhythm_light_stone','facade_frame',depth=.24,offset=.10))
                # Thin opaque spandrels conceal actual floor edges; a vertical
                # window band is not an uninterrupted opening through slabs.
                for j,p in enumerate(group[:-1]):
                    zz=(p['center']['z']+group[j+1]['center']['z'])/2
                    out.append(box(t,f'spandrel{j}',u,zz,width,.22,'rhythm_dark_metal','facade_frame',offset=.13))
    return out


def plan(primitives, assignments):
    if not set(assignments.values()) <= STYLES:raise ValueError('Unknown facade rhythm')
    windows=defaultdict(list); unsafe=set(); balcony_faces=set()
    for p in primitives:
        bid=p['layer_id'].removeprefix('shell:');m=p['metadata']
        if bid not in assignments:continue
        if p['semantic_class'] in ('balcony_slab','balcony_rail'):
            if all(k in m for k in ('massing_part','facade_side')):
                balcony_faces.add((bid,m['massing_part'],m['facade_side']))
            else:unsafe.add(bid)
        if p['semantic_class']=='facade_window':
            if p['primitive_type']!='box' or 'curtainwall' in m.get('facade_style',''):unsafe.add(bid)
            elif all(k in m for k in ('massing_part','facade_side','floor_level')) and m['floor_level']>=1:
                windows[bid].append(p)
    added=[]; replaced=set(); active={}; scopes=set()
    for bid,rows in sorted(windows.items()):
        rows=[p for p in rows if (bid,p['metadata']['massing_part'],p['metadata']['facade_side']) not in balcony_faces]
        if not rows or bid in unsafe or max(p['metadata']['floor_level'] for p in rows)<3:continue
        style=assignments[bid]; groups=defaultdict(list)
        for p in rows:
            key=surface_key(p)
            key+= (p['metadata']['floor_level'],) if style=='horizontal_ribbon' else (round(coordinates(p)[0],2),)
            groups[key].append(p)
        for group in groups.values():added.extend(panels(group,style))
        active[bid]=style
        for p in rows:
            m=p['metadata']; scopes.add((bid,m['massing_part'],m['facade_side'],m['floor_level']))
    for p in primitives:
        m=p['metadata'];bid=p['layer_id'].removeprefix('shell:')
        if (p['semantic_class'] in REMOVABLE and p['primitive_type']=='box'
                and (bid,m.get('massing_part'),m.get('facade_side'),m.get('floor_level')) in scopes):
            replaced.add(p['id'])
    assert len({p['id'] for p in added})==len(added)
    report={'assignments':active,'building_count':len(active),'style_counts':dict(Counter(active.values())),
            'removed_primitives':len(replaced),'added_primitives':len(added),
            'skipped_buildings':sorted(set(assignments)-set(active)),
            'preserved_balcony_faces':[list(k) for k in sorted(balcony_faces)],
            'scope':'Exterior upper-floor window/frame/spandrel replacement only; ground entries, massing, roofs and non-selected buildings unchanged',
            'simulation_claim':False}
    return replaced,added,report
