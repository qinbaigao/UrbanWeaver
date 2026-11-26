"""Camera-only contract for a curated city aerial render (no Blender dependency)."""
import math


def aerial_camera(doc, source, primitive_count, width):
    if doc.get('schema')!='cityg.render_view' or doc.get('schema_version')!=1:
        raise ValueError('Unsupported camera handoff')
    axes=doc['coordinate_system']
    expected={'space':'scene_world','up_axis':'Z','units':'meters','handedness':'right',
              'matrix_layout':'column_major','quaternion_order':'xyzw'}
    if any(axes.get(k)!=v for k,v in expected.items()):raise ValueError('Unsupported coordinates')
    ref=doc['scene_ref'];v=doc['visibility'];c=doc['camera']
    if ref['original_source']!=str(source) or ref['total_primitives']!=primitive_count:
        raise ValueError('Camera and source package do not match')
    if v['mode'] not in ('overview','full') or v.get('xray_shells') or v.get('hierarchy_display'):
        raise ValueError('Only intact city overview/full views are supported')
    if doc['selection'].get('district_id') not in ('all',None,'') or v.get('presentation_focus_id'):
        raise ValueError('Scoped city views need an explicit scope adapter')
    if (doc.get('replay') or {}).get('loaded') or v.get('door_states'):
        raise ValueError('Dynamic snapshots require pose adaptation')
    if c['projection']!='perspective' or c.get('view_offset') or c.get('film_offset_mm',0):
        raise ValueError('Only symmetric perspective cameras are supported')
    for key,count in [('camera_position',3),('look_at',3),('quaternion_xyzw',4),('matrix_world',16),('projection_matrix',16)]:
        if len(c[key])!=count or not all(math.isfinite(x) for x in c[key]):raise ValueError(key)
    q=c['quaternion_xyzw'];fov=c['vertical_fov_deg'];aspect=c['aspect'];near=c['near_clip_m'];far=c['far_clip_m']
    if abs(sum(x*x for x in q)-1)>1e-6 or not (0<fov<179 and 0<near<far and 0<aspect<100):raise ValueError('Invalid frustum')
    if any(abs(c['matrix_world'][12+i]-c['camera_position'][i])>1e-6 for i in range(3)):raise ValueError('Inconsistent camera matrix')
    f=1/math.tan(math.radians(fov)/2)
    projection=[f/aspect,0,0,0,0,f,0,0,0,0,-(far+near)/(far-near),-1,0,0,-2*far*near/(far-near),0]
    if max(abs(a-b) for a,b in zip(projection,c['projection_matrix']))>1e-6:raise ValueError('Inconsistent projection')
    height=round(width/aspect)
    if min(width,height)<16:raise ValueError('Invalid resolution')
    return {'position':c['camera_position'],'quaternion':[q[3],*q[:3]],
            'width':width,'height':height,'pixel_aspect_x':aspect/(width/height),
            'lens':24*f/2,'near':near,'far':far}
