"""Expand static GLB DAG nodes into a tree for Blender; retain binary mesh/maps."""
from copy import deepcopy
import json
from pathlib import Path
import struct


def static_tree(doc):
    nodes=doc.get('nodes',[]);seen=set();duplicate=False
    for node in nodes:
        for child in node.get('children',[]):
            if child in seen:duplicate=True
            seen.add(child)
    roots=[i for scene in doc.get('scenes',[]) for i in scene.get('nodes',[])]
    if any(i in seen for i in roots) or len(roots)!=len(set(roots)):duplicate=True
    reachable=set()
    def visit(index,stack):
        if index in stack:raise ValueError('Cyclic GLB graph')
        if index in reachable:return
        reachable.add(index)
        for child in nodes[index].get('children',[]):visit(child,stack|{index})
    for root in roots:visit(root,set())
    # Blender 4.2 can materialize orphan roots which Three.js correctly omits.
    # Keep only nodes reachable from declared scenes (e.g. omit hidden source
    # modelling floors outside the normalized metro entrance scene).
    if doc.get('scenes') and len(reachable)!=len(nodes):duplicate=True
    if not duplicate:return doc,False
    if doc.get('skins') or doc.get('animations'):raise ValueError('Cannot expand animated/skinned GLB without pose rebinding')
    result=deepcopy(doc);tree=[]
    def clone(index,stack):
        if index in stack:raise ValueError('Cyclic GLB graph')
        original=nodes[index];node=deepcopy(original);new=len(tree);tree.append(node)
        if 'children' in original:node['children']=[clone(i,stack|{index}) for i in original['children']]
        return new
    for scene in result.get('scenes',[]):scene['nodes']=[clone(i,set()) for i in scene.get('nodes',[])]
    result['nodes']=tree
    return result,True


def blender_glb(source,cache):
    source=Path(source);data=source.read_bytes()
    magic,version,length=struct.unpack_from('<4sII',data)
    if magic!=b'glTF' or version!=2 or length!=len(data):raise ValueError('Invalid GLB '+str(source))
    size,kind=struct.unpack_from('<II',data,12)
    if kind!=0x4E4F534A:raise ValueError('Missing GLB JSON chunk')
    doc=json.loads(data[20:20+size]);normalized,changed=static_tree(doc)
    if not changed:return source,False
    if any(x.get('uri') and not x['uri'].startswith('data:') for x in doc.get('images',[])+doc.get('buffers',[])):
        raise ValueError('GLB graph adaptation requires embedded resources')
    payload=json.dumps(normalized,separators=(',',':')).encode();payload+=b' '*((-len(payload))%4)
    tail=data[20+size:];output=struct.pack('<4sII',b'glTF',2,20+len(payload)+len(tail))+struct.pack('<II',len(payload),kind)+payload+tail
    import hashlib
    target=Path(cache)/(hashlib.sha256(data).hexdigest()[:16]+'.glb');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(output)
    return target,True
