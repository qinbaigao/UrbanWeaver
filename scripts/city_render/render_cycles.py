"""Render an approved city from a Viewer camera, without editing its source.

Blender --background --factory-startup --python-exit-code 1 --python THIS --
  --source COMPILED_SCENE --camera-json VIEW --output OUTPUT --width 3330
Repeated GLBs use Geometry Nodes instancing; procedural primitives are batched.
"""
import argparse
from collections import defaultdict,Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
import bpy
from mathutils import Matrix,Quaternion,Vector
from bpy_extras.object_utils import world_to_camera_view

sys.path.insert(0,str(Path(__file__).resolve().parent))
from camera import aerial_camera
from materials import city_material,daylight
from gltf_compat import blender_glb
from realism import enhance,atmosphere
from facade_variation import FACADE_SEMANTICS,facade_seeds
from facade_render import apply_rhythms
from waterfront import apply_waterfront, apply_water_tone, WATER_TONES
from background import configure_background

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

BOX_VERTS=np.array([[-.5,-.5,-.5],[.5,-.5,-.5],[.5,.5,-.5],[-.5,.5,-.5],
                    [-.5,-.5,.5],[.5,-.5,.5],[.5,.5,.5],[-.5,.5,.5]])
BOX_FACES=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

def local_mesh(p):
    kind=p['primitive_type'];meta=p['metadata']
    if kind=='path_mesh':return np.asarray(meta['mesh_vertices']),meta['mesh_triangles']
    if kind=='box':return BOX_VERTS,BOX_FACES
    # Spheres/cylinders only occur as small city fixtures. Keep analytic silhouettes.
    sides=16;verts=[];faces=[]
    if kind=='cylinder':
        for z in [-.5,.5]:verts.extend((.5*math.cos(i*math.tau/sides),.5*math.sin(i*math.tau/sides),z) for i in range(sides))
        faces=[tuple(reversed(range(sides))),tuple(range(sides,2*sides))]
        faces.extend((i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides))
    elif kind=='sphere':
        for j in range(9):
            phi=math.pi*j/8
            verts.extend((.5*math.sin(phi)*math.cos(i*math.tau/sides),.5*math.sin(phi)*math.sin(i*math.tau/sides),.5*math.cos(phi)) for i in range(sides))
        faces=[(j*sides+i,j*sides+(i+1)%sides,(j+1)*sides+(i+1)%sides,(j+1)*sides+i) for j in range(8) for i in range(sides)]
    else:raise ValueError('Unsupported primitive '+kind)
    return np.asarray(verts),faces

def batch_mesh(entries,mat,scale,index):
    vertices=[];faces=[];uv=[]
    for p in entries:
        v,f=local_mesh(p);size=np.array([p['size'][k] for k in 'xyz']);center=np.array([p['center'][k] for k in 'xyz'])
        local=v*size;theta=math.radians(p['rotation_z_deg']);c,s=math.cos(theta),math.sin(theta)
        world=local@np.array([[c,s,0],[-s,c,0],[0,0,1]])+center
        offset=len(vertices);vertices.extend(world.tolist())
        path_uv=world[:,[0,1]]/scale if p['primitive_type']=='path_mesh' else None
        for face in f:
            faces.append(tuple(offset+i for i in face))
            if path_uv is not None:coords=path_uv
            else:
                normal=np.cross(local[face[1]]-local[face[0]],local[face[2]]-local[face[0]])
                axes=[a for a in range(3) if a!=int(np.argmax(np.abs(normal)))]
                coords=local[:,axes]/scale
            uv.extend(coords[list(face)].tolist())
    mesh=bpy.data.meshes.new(f'batch_{index}');mesh.from_pydata(vertices,[],faces);mesh.update()
    uvs=mesh.uv_layers.new();uvs.data.foreach_set('uv',np.asarray(uv,dtype=np.float32).ravel())
    mesh.materials.append(mat);obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.scene.collection.objects.link(obj)
    return len(faces)

def asset_template(path,index):
    before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(path))
    objects=list(set(bpy.data.objects)-before);meshobjs=[o for o in objects if o.type=='MESH']
    if not meshobjs:raise ValueError('Empty GLB '+str(path))
    # Importer converts glTF Y-up to Blender Z-up; CityG GLBs store normalized
    # Z-up data. Undo that conversion exactly as the room renderer does.
    correction=Matrix.Rotation(-math.pi/2,4,'X')
    bpy.context.view_layer.update()
    transforms={o:correction@o.matrix_world.copy() for o in meshobjs}
    for o in meshobjs:
        # A normalized GLB can have non-uniform parent scale and rotated children
        # (shear). Assigning that affine matrix to an unparented object's TRS can
        # explode near-singular planar meshes. Bake the full affine matrix into
        # mesh coordinates instead, then join identity-transformed objects.
        data=o.data.copy();indices=[p.material_index for p in data.polygons];data.materials.clear()
        for slot in o.material_slots:data.materials.append(slot.material)
        for polygon,material_index in zip(data.polygons,indices):polygon.material_index=material_index
        data.transform(transforms[o]);o.data=data;o.parent=None;o.matrix_world=Matrix.Identity(4)
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshobjs:o.select_set(True)
    bpy.context.view_layer.objects.active=meshobjs[0]
    if len(meshobjs)>1:bpy.ops.object.join()
    template=bpy.context.object
    for o in objects:
        try:
            if o!=template and o.name in bpy.data.objects:bpy.data.objects.remove(o,do_unlink=True)
        except ReferenceError:pass
    template.name=f'asset_template_{index}';template.hide_render=True;template.hide_set(True)
    return template

def asset_instances(entries,template,index):
    centers=np.asarray([[p['center'][k] for k in 'xyz'] for p in entries],dtype=np.float32)
    scales=np.asarray([[p['size'][k] for k in 'xyz'] for p in entries],dtype=np.float32)
    rotations=np.asarray([[0,0,math.radians(p['rotation_z_deg'])] for p in entries],dtype=np.float32)
    mesh=bpy.data.meshes.new(f'placement_points_{index}');mesh.from_pydata(centers.tolist(),[],[])
    for name,values in [('size',scales),('rotation',rotations)]:
        attr=mesh.attributes.new(name,'FLOAT_VECTOR','POINT');attr.data.foreach_set('vector',values.ravel())
    obj=bpy.data.objects.new(f'asset_instances_{index}',mesh);bpy.context.scene.collection.objects.link(obj)
    group=bpy.data.node_groups.new(f'instance_asset_{index}','GeometryNodeTree')
    group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    n=group.nodes;l=group.links;inp=n.new('NodeGroupInput');out=n.new('NodeGroupOutput');inst=n.new('GeometryNodeInstanceOnPoints')
    info=n.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=template;info.inputs['As Instance'].default_value=True
    l.new(inp.outputs['Geometry'],inst.inputs['Points']);l.new(info.outputs['Geometry'],inst.inputs['Instance'])
    for name,socket in [('size','Scale'),('rotation','Rotation')]:
        attr=n.new('GeometryNodeInputNamedAttribute');attr.data_type='FLOAT_VECTOR';attr.inputs['Name'].default_value=name
        l.new(attr.outputs['Attribute'],inst.inputs[socket])
    l.new(inst.outputs['Instances'],out.inputs['Geometry']);obj.modifiers.new('Shared original GLB instances','NODES').node_group=group

def configure_camera(scene,doc,params):
    data=bpy.data.cameras.new('Exact exported Viewer camera');obj=bpy.data.objects.new('Exact exported Viewer camera',data)
    scene.collection.objects.link(obj);scene.camera=obj;obj.location=params['position'];obj.rotation_mode='QUATERNION';obj.rotation_quaternion=Quaternion(params['quaternion'])
    data.sensor_fit='VERTICAL';data.sensor_height=24;data.lens=params['lens'];data.clip_start=params['near'];data.clip_end=params['far']
    scene.render.resolution_x=params['width'];scene.render.resolution_y=params['height'];scene.render.resolution_percentage=100
    scene.render.pixel_aspect_x=params['pixel_aspect_x'];scene.render.pixel_aspect_y=1
    bpy.context.view_layer.update()
    errors=[];p=doc['camera']['projection_matrix']
    for x in [-100,0,100]:
        for y in [-80,0,80]:
            local=Vector((x,y,-1000));world=obj.matrix_world@local
            actual=world_to_camera_view(scene,obj,world)
            expected=((p[0]*x/1000+1)/2,(p[5]*y/1000+1)/2)
            errors.extend([abs(actual[i]-expected[i]) for i in range(2)])
    error=max(errors);assert error<2e-5,error
    return error

def attach_facade_identity(raw,doc):
    """Recover the compiled batching order without changing any geometry.

    The original compiler emits each primitive's faces consecutively. Validate
    topology counts before attaching identity-bound shader attributes to caches.
    """
    geometry=json.loads(raw.read_text());groups=defaultdict(list)
    layers={v['id']:v['layer_type'] for v in geometry['layers']}
    semantics=set(doc['visibility']['enabled_semantics'])
    for p in geometry['primitives']:
        if (p['primitive_type']!='mesh' and p['semantic_class'] in semantics
            and p['semantic_class']!='collision_envelope' and not p['metadata'].get('viewer_room_only')
            and layers.get(p['layer_id']) in ('roads','root','district','building_shell')):
            groups[(p['material_id'],p['semantic_class'])].append(p)
    batch=0;updated=0
    for (mid,semantic),entries in groups.items():
        for offset in range(0,len(entries),2500):
            chunk=entries[offset:offset+2500]
            if semantic in FACADE_SEMANTICS:
                mesh=bpy.data.objects[f'batch_{batch}'].data
                values=[];vertex_count=0
                for p in chunk:
                    vertices,faces=local_mesh(p);vertex_count+=len(vertices)
                    values.extend([facade_seeds(p)]*len(faces))
                if len(values)!=len(mesh.polygons) or vertex_count!=len(mesh.vertices):
                    raise ValueError(f'Cached facade topology mismatch: batch {batch}')
                values=np.asarray(values,dtype=np.float32)
                for index,name in enumerate(('cityg_panel_seed','cityg_building_age')):
                    attribute=mesh.attributes.get(name) or mesh.attributes.new(name,'FLOAT','FACE')
                    attribute.data.foreach_set('value',values[:,index].copy())
                updated+=1
            batch+=1
    return updated

def run(args):
    if args.water_tone != 'original' and not args.waterfront:
        raise ValueError('--water-tone requires --waterfront')
    if args.transparent_background and args.look != 'base':
        raise ValueError('Transparent background requires base look without composited haze')
    started=time.monotonic();source=args.source.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    doc=json.loads(args.camera_json.read_text());raw=source/'geometry_manifest.json'
    inputs={'camera':digest(args.camera_json),'geometry':digest(raw)}
    (output/'render_view.json').write_bytes(args.camera_json.read_bytes())
    if args.resume:
        bpy.ops.wm.open_mainfile(filepath=str(args.resume.resolve()))
        report=json.loads((args.resume.resolve().parent/'scene_build.json').read_text());assert report['inputs']==inputs
        (output/'scene_build.json').write_text(json.dumps(report,indent=2)+'\n')
        count=report['source_primitives']
        if args.rebuild_assets:
            unique={}
            for path,key in report['asset_hashes'].items():
                if key in unique:continue
                index=len(unique);unique[key]=index
                if args.rebuild_asset_index and index not in args.rebuild_asset_index:continue
                old=bpy.data.objects[f'asset_template_{index}']
                compatible,changed=blender_glb(path,output/'compatible_assets');new=asset_template(compatible,index)
                if changed:report['static_graph_adapters'][path]=str(compatible)
                for group in bpy.data.node_groups:
                    for node in group.nodes:
                        if node.bl_idname=='GeometryNodeObjectInfo' and node.inputs['Object'].default_value==old:
                            node.inputs['Object'].default_value=new
                bpy.data.objects.remove(old,do_unlink=True);new.name=f'asset_template_{index}'
                print('CITYG affine-safe template',index,path,flush=True)
            bpy.ops.outliner.orphans_purge(do_recursive=True)
            report['asset_transform_policy']='Full GLB world affine matrices baked into vertices before instancing; no lossy TRS decomposition'
            (output/'scene_build.json').write_text(json.dumps(report,indent=2)+'\n')
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        print('CITYG loading compiled geometry',flush=True);geometry=json.loads(raw.read_text());count=len(geometry['primitives'])
        if geometry.get('city_id') and geometry['city_id']!=doc['scene_ref']['city_id']:raise ValueError('Wrong city')
        params=aerial_camera(doc,source,count,args.width)
        layers={v['id']:v['layer_type'] for v in geometry['layers']};semantics=set(doc['visibility']['enabled_semantics'])
        selected=[p for p in geometry['primitives'] if p['semantic_class'] in semantics and p['semantic_class']!='collision_envelope'
                  and not p['metadata'].get('viewer_room_only') and layers.get(p['layer_id']) in ('roads','root','district','building_shell')]
        specs={s['id']:s for s in geometry['materials']};groups=defaultdict(list);assets=defaultdict(list)
        for p in selected:
            if p['primitive_type']=='mesh':assets[p['metadata']['asset_geometry_path']].append(p)
            else:groups[(p['material_id'],p['semantic_class'])].append(p)
        report={'inputs':inputs,'source_primitives':count,'selected_primitives':len(selected),'semantics':dict(Counter(p['semantic_class'] for p in selected)),
                'policy':'All authored exterior semantics; no navigation proxies, screen-space asset dropping, UI grid, diagnostic overlays or selection highlight. Geometry/placement untouched.',
                'material_adaptation':'Compiled PBR maps, glass reflection/transmission, metre-scale ground/roof variation, water micro-normal; curated HDR and sunlight.',
                'asset_instances':sum(map(len,assets.values())),'asset_sources':len(assets)}
        faces=0;batch=0
        for (mid,semantic),entries in groups.items():
            mat=city_material(specs[mid],semantic,source);scale=specs[mid].get('texture_scale_m') or 4
            for offset in range(0,len(entries),2500):
                faces+=batch_mesh(entries[offset:offset+2500],mat,scale,batch);batch+=1
            print('CITYG procedural',semantic,mid,len(entries),flush=True)
        report['procedural_batches']=batch;report['procedural_faces']=faces
        hashes={};templates={};adapted={}
        for i,(path,entries) in enumerate(assets.items()):
            key=digest(path);hashes[path]=key
            if key not in templates:
                compatible,changed=blender_glb(path,output/'compatible_assets')
                if changed:adapted[path]=str(compatible)
                print('CITYG importing',path,'graph_expanded',changed,flush=True)
                templates[key]=asset_template(compatible,len(templates))
            asset_instances(entries,templates[key],i)
            print('CITYG asset',i+1,len(assets),Path(path).name,len(entries),flush=True)
        report['unique_asset_contents']=len(templates);report['asset_hashes']=hashes;report['static_graph_adapters']=adapted
        (output/'scene_build.json').write_text(json.dumps(report,indent=2)+'\n')
        del geometry,selected,groups,assets
    scene=bpy.context.scene;params=aerial_camera(doc,source,count,args.width)
    if args.facade_rhythms:
        if args.look!='base':raise ValueError('Facade preview uses clean base shading, not weathering/haze look')
        report['facade_rhythms']=apply_rhythms(raw,doc,args.facade_rhythms,batch_mesh)
        (output/'facade_rhythms.json').write_text(json.dumps(report['facade_rhythms'],indent=2)+'\n')
        report['policy']='Original massing/environment with approved private upper-floor facade replacement; source and Viewer unchanged'
        scene.use_nodes=False
    elif scene.get('cityg_facade_rhythms'):
        raise ValueError('Facade-edited cache requires its matching --facade-rhythms config')
    report['projection_error_normalized']=configure_camera(scene,doc,params)
    daylight(scene,args.hdr.resolve(),rotation_deg=args.sky_rotation,exposure=args.exposure,
             sun_azimuth=args.sun_azimuth,sun_elevation=args.sun_elevation,sun_energy=args.sun_energy,world_strength=args.world_strength)
    if args.look=='realism_v1':
        if not scene.get('cityg_facade_identity'):
            report['facade_identity_batches']=attach_facade_identity(raw,doc)
            scene['cityg_facade_identity']=report['facade_identity_batches']
        else:report['facade_identity_batches']=int(scene['cityg_facade_identity'])
        report['look_changes']=enhance(scene);atmosphere(scene)
        report['look_revision']=scene['cityg_render_look']
        report['atmosphere']='Depth-based aerial perspective; start 250 m, range 2000 m, maximum mix 0.07; not volumetric simulation'
    elif scene.get('cityg_render_look'):
        raise ValueError('Base look requires a base cache, not a previously enhanced scene')
    report['look']=args.look
    if args.waterfront:
        if args.look!='base':raise ValueError('Waterfront display requires clean base shading without haze')
        report['waterfront']=apply_waterfront(scene,doc,report,Path(__file__).resolve().parents[2],asset_instances)
        (output/'waterfront.json').write_text(json.dumps(report['waterfront'],indent=2)+'\n')
        report['water_tone']=apply_water_tone(args.water_tone)
        (output/'water_tone.json').write_text(json.dumps(report['water_tone'],indent=2)+'\n')
    elif scene.get('cityg_waterfront'):
        raise ValueError('Waterfront cache requires --waterfront; use previous facade cache to revert')
    scene.render.engine='CYCLES';scene.cycles.samples=args.samples;scene.cycles.use_denoising=True
    scene.cycles.adaptive_threshold=.025;scene.cycles.max_bounces=8;scene.cycles.diffuse_bounces=4;scene.cycles.glossy_bounces=4
    scene.cycles.transmission_bounces=6;scene.cycles.transparent_max_bounces=12
    scene.cycles.sample_clamp_indirect=4
    if args.device=='CUDA':
        prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
        for device in prefs.devices:device.use=device.type=='CUDA'
        if not any(d.type=='CUDA' for d in prefs.devices):raise RuntimeError('Requested CUDA unavailable')
        scene.cycles.device='GPU'
    else:scene.cycles.device='CPU'
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_depth='8'
    report['background']=configure_background(scene,args.transparent_background)
    target=output/(args.name+'.png');scene.render.filepath=str(target)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output/(args.name+'.blend')),compress=True)
    print('CITYG rendering',target,params['width'],params['height'],args.samples,flush=True)
    bpy.ops.render.render(write_still=True)
    report.update(resolution=[params['width'],params['height']],samples=args.samples,device=args.device,
                  camera_file=str(args.camera_json.resolve()),camera_adjusted=False,sky=str(args.hdr.resolve()),
                  sky_rotation_deg=args.sky_rotation,exposure=args.exposure,elapsed_seconds=time.monotonic()-started)
    report['sun']={'azimuth_deg':args.sun_azimuth,'elevation_deg':args.sun_elevation,'energy':args.sun_energy,'world_strength':args.world_strength}
    (output/(args.name+'_render.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('CITYG finished',json.dumps({'image':str(target),'seconds':report['elapsed_seconds']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--camera-json',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--width',type=int,default=3330);p.add_argument('--samples',type=int,default=128)
    p.add_argument('--hdr',type=Path,required=True);p.add_argument('--sky-rotation',type=float,default=110);p.add_argument('--exposure',type=float,default=.4)
    p.add_argument('--sun-azimuth',type=float,default=225);p.add_argument('--sun-elevation',type=float,default=42)
    p.add_argument('--sun-energy',type=float,default=3.5);p.add_argument('--world-strength',type=float,default=.4)
    p.add_argument('--device',choices=['CPU','CUDA'],default='CPU');p.add_argument('--name',default='city_aerial');p.add_argument('--resume',type=Path)
    p.add_argument('--look',choices=['base','realism_v1'],default='base',help='Private offline material/atmosphere variant; never modifies compiled scene or Viewer')
    p.add_argument('--facade-rhythms',type=Path,help='Approved render-only upper-floor facade geometry variants; requires base look')
    p.add_argument('--waterfront',action='store_true',help='River PBR and distant-land continuation for the approved aerial view')
    p.add_argument('--water-tone',choices=tuple(WATER_TONES),default='original',help='Water body palette only; requires --waterfront')
    p.add_argument('--transparent-background',action='store_true',help='RGBA PNG without environment background or decorative distant terrain; preserves world lighting and city geometry')
    p.add_argument('--rebuild-assets',action='store_true',help='Refresh GLB templates in a cached scene without recompiling city geometry')
    p.add_argument('--rebuild-asset-index',type=int,action='append',help='Optionally refresh only selected template indices')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
