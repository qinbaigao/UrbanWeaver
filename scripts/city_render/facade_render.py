"""Apply approved facade plans to a private cached Blender city."""
from collections import defaultdict
import hashlib
import json

import bpy
from facade_rhythms import plan


def apply_rhythms(raw, doc, config, batch_mesh):
    scene=bpy.context.scene; key=hashlib.sha256(config.read_bytes()).hexdigest()
    if scene.get('cityg_facade_rhythms'):
        if scene['cityg_facade_rhythms']!=key:raise ValueError('Facade config changed; use original base cache')
        return json.loads(scene['cityg_facade_rhythm_report'])
    if scene.get('cityg_render_look'):raise ValueError('Facade geometry variant requires the clean base cache')
    geometry=json.loads(raw.read_text());config_doc=json.loads(config.read_text())
    layers={v['id']:v['layer_type'] for v in geometry['layers']};enabled=set(doc['visibility']['enabled_semantics'])
    selected=[p for p in geometry['primitives'] if p['semantic_class'] in enabled and p['semantic_class']!='collision_envelope'
              and not p['metadata'].get('viewer_room_only') and layers.get(p['layer_id']) in ('roads','root','district','building_shell')]
    removed,added,report=plan(selected,config_doc['buildings'])
    if not added:raise ValueError('No feasible facade replacements')
    groups=defaultdict(list);specs={s['id']:s for s in geometry['materials']}
    for p in selected:
        if p['primitive_type']!='mesh':groups[(p['material_id'],p['semantic_class'])].append(p)
    changed=[];batch=0
    for (mid,semantic),entries in groups.items():
        for offset in range(0,len(entries),2500):
            chunk=entries[offset:offset+2500]
            if any(p['id'] in removed for p in chunk):
                name=f'batch_{batch}';old=bpy.data.objects[name]
                # Keep existing material and object identity; rebuild only this
                # affected batch, leaving GLB instances and all other meshes alone.
                keep=[p for p in chunk if p['id'] not in removed]
                temp=f'facade_rebuild_{batch}'
                batch_mesh(keep,old.data.materials[0],specs[mid].get('texture_scale_m') or 4,temp)
                new=bpy.data.objects['batch_'+temp];old.data=new.data
                bpy.data.objects.remove(new,do_unlink=True);changed.append(name)
            batch+=1
    palette={
        'rhythm_glass_ribbon':((.10,.19,.21),.16,.18),
        'rhythm_glass_vertical':((.14,.21,.27),.18,.18),
        'rhythm_light_stone':((.72,.73,.68),.65,0),
        'rhythm_dark_metal':((.055,.067,.075),.32,.35),
    }
    groups=defaultdict(list)
    for p in added:groups[p['material_id']].append(p)
    added_names=[]
    for index,(mid,entries) in enumerate(groups.items()):
        color,rough,metal=palette[mid]
        mat=bpy.data.materials.new(mid);mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough
        bs.inputs['Metallic'].default_value=metal
        if 'glass' in mid:
            bs.inputs['IOR'].default_value=1.46;bs.inputs['Coat Weight'].default_value=.28
            bs.inputs['Coat Roughness'].default_value=.12
        for offset in range(0,len(entries),2500):
            name=f'facade_rhythm_{index}_{offset}'
            batch_mesh(entries[offset:offset+2500],mat,4,name);added_names.append('batch_'+name)
    report.update(config_sha256=key,config_path=str(config.resolve()),references=config_doc['references'],
                  changed_meshes=changed,new_meshes=added_names)
    scene['cityg_facade_rhythms']=key;scene['cityg_facade_rhythm_report']=json.dumps(report)
    print('CITYG facade rhythm',report['building_count'],report['style_counts'],flush=True)
    return report
