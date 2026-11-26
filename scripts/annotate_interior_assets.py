"""Offline, geometry-checked support annotation for an explicit indoor allowlist.

Uses numpy only during curation. Runtime does not need triangle queries or Blender.
Normals/height probes validate curator-selected patches; they do not invent semantics.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from cityg.asset_curation import _read_gltf
from cityg.assets import AssetRegistry
from cityg.facade_runtime import _node_matrix
from cityg.serialization import save_json

ROOT = Path(__file__).resolve().parents[1]


def triangles(path):
    document, buffers = _read_gltf(path)
    if document.get("skins") or document.get("animations"):
        raise ValueError("Only static geometry may be annotated")
    def accessor(index):
        a = document["accessors"][index]
        if a.get("sparse") or a.get("normalized"):
            raise ValueError("Unsupported sparse/normalized geometry accessor")
        view = document["bufferViews"][a["bufferView"]]
        dtype = np.dtype({5126:"<f4",5125:"<u4",5123:"<u2",5121:"u1"}[a["componentType"]])
        width = {"VEC3":3,"SCALAR":1}[a["type"]]
        return np.ndarray((a["count"],width), dtype=dtype, buffer=buffers[view["buffer"]],
            offset=view.get("byteOffset",0)+a.get("byteOffset",0),
            strides=(view.get("byteStride",width*dtype.itemsize),dtype.itemsize)).copy()
    result=[]
    def walk(index, parent, ancestors):
        if index in ancestors: raise ValueError("Cyclic node graph")
        node=document["nodes"][index]; matrix=parent@np.array(_node_matrix(node))
        if "mesh" in node:
            for primitive in document["meshes"][node["mesh"]]["primitives"]:
                if primitive.get("mode",4)!=4: raise ValueError("Expected triangles")
                vertices=accessor(primitive["attributes"]["POSITION"])
                vertices=(np.column_stack((vertices,np.ones(len(vertices))))@matrix.T)[:,:3]
                indices=accessor(primitive["indices"]).ravel() if "indices" in primitive else np.arange(len(vertices))
                result.append(vertices[indices.reshape(-1,3)])
        for child in node.get("children",[]): walk(child,matrix,ancestors|{index})
    for root in document["scenes"][document.get("scene",0)]["nodes"]: walk(root,np.eye(4),set())
    value=np.concatenate(result)
    if not np.isfinite(value).all(): raise ValueError("Nonfinite geometry")
    if not np.allclose([value.min(axis=(0,1)),value.max(axis=(0,1))],[[-.5]*3,[.5]*3],atol=1e-4):
        raise ValueError("Expected canonical centered unit bounds")
    return value


def intersections(mesh,x,y):
    a=mesh[:,0]; u=mesh[:,1]-a; v=mesh[:,2]-a
    determinant=u[:,0]*v[:,1]-u[:,1]*v[:,0]
    valid=np.abs(determinant)>1e-12
    det=np.where(valid,determinant,1)
    s=((x-a[:,0])*v[:,1]-(y-a[:,1])*v[:,0])/det
    t=(u[:,0]*(y-a[:,1])-u[:,1]*(x-a[:,0]))/det
    mask=valid & (s>=-1e-7)&(t>=-1e-7)&(s+t<=1+1e-7)
    return a[mask,2]+s[mask]*u[mask,2]+t[mask]*v[mask,2]


def check_surface(mesh,dimensions,spec):
    cx,cy,z=spec["center"]; w,d=spec["size"]
    if (not all(np.isfinite(v) for v in [cx,cy,z,w,d]) or w<=0 or d<=0 or
            abs(cx)+w/2>.5 or abs(cy)+d/2>.5 or abs(z)>.5):
        raise ValueError("Invalid normalized patch")
    tolerance=.003/dimensions[2]
    physical=mesh*np.array(dimensions)
    normals=np.cross(physical[:,1]-physical[:,0],physical[:,2]-physical[:,0])
    # Allow tiny bevel/grain slopes inside the 3 mm height envelope, but never
    # accept an underside or near-vertical side as a support plane.
    upward=mesh[normals[:,2]>.5*np.linalg.norm(normals,axis=1)]
    residuals=[]; clearances=[]
    # Includes edges, not just patch center: avoid crossing holes or raised trim.
    for x in np.linspace(cx-w/2,cx+w/2,13):
        for y in np.linspace(cy-d/2,cy+d/2,13):
            heights=intersections(mesh,x,y)
            supporting=intersections(upward,x,y)
            if not len(supporting) or np.min(np.abs(supporting-z))>tolerance:
                raise ValueError(f"Unsupported patch {spec['id']} at ({x:.3f},{y:.3f}); z={z:.4f}, hits={heights.tolist()}")
            residuals.append(float(np.min(np.abs(supporting-z))*dimensions[2]))
            higher=heights[heights>z+tolerance]
            if len(higher): clearances.append(float((higher.min()-z)*dimensions[2]))
    clearance=min(clearances) if clearances else None
    if clearance is not None and spec.get("clearance_m",0)>clearance-.003:
        raise ValueError(f"Patch clearance too large: {spec['id']}, available {clearance}")
    return {**spec,"verified":True,
        **({"clearance_fraction":spec["clearance_m"]/dimensions[2]} if spec.get("clearance_m") else {}),
        "geometry_probe":{"samples":169,
        "max_height_residual_m":max(residuals),"sampled_clearance_m":clearance,
        "method":"curated_rectangle_with_13x13_triangle_height_probes"}}


def annotate(config,stage):
    registry=AssetRegistry(stage/"candidate_registry.json")
    reviews=json.loads((stage/"visual_review.json").read_text())["assets"]
    records=[]
    for name,spec in config["assets"].items():
        record=registry.require(name); path=registry.resolve_path(record.geometry_path)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=spec["output_sha256"] or digest!=record.metadata["output_sha256"]:
            raise ValueError(f"Annotation snapshot changed: {name}")
        review=reviews.get(name,{})
        if review.get("status")!="visual_checked" or review.get("output_sha256")!=digest:
            raise ValueError(f"Unreviewed/held asset: {name}")
        if review.get("dimensions_m") != list(record.dimensions_m):
            raise ValueError(f"Physical scale changed since review: {name}")
        if spec["placement_kind"] not in ("floor", "surface"):
            raise ValueError("Only floor and supported-surface placement implemented")
        if spec["front_axis"] not in ("+X","-X","+Y","-Y") or not spec.get("front_evidence"):
            raise ValueError("Explicit semantic front and visual evidence required")
        mesh=triangles(path)
        support=[check_surface(mesh,record.dimensions_m,s) for s in spec.get("surfaces",[])]
        metadata={**record.metadata,"runtime_enabled":True,"indoor_pack_status":"placement_trial",
            "placement_kind":spec["placement_kind"],"indoor_annotation_version":1,
            "room_support_surfaces":support,"support_annotation_status":"geometry_checked",
            "placement_anchor":{"kind":"bottom_center","normalized_z":-.5,"up_axis":"+Z"},
            "orientation":{**record.metadata["orientation"],"canonical_forward_axis":spec["front_axis"],
                "orientation_confidence":"reviewed","front_evidence":spec["front_evidence"]},
            "visual_review":review,"annotation_geometry_sha256":digest,
            "physical_dimensions_m":list(record.dimensions_m)}
        # Some earlier download plans retained bundle-level manual_only after
        # explicit single-node extraction. Clear only for proven single components.
        tags=record.tags
        if "manual_only" in tags:
            if len(record.metadata.get("source_selected_nodes",[]))!=1:
                raise ValueError("Cannot promote an unsplit manual bundle")
            tags=tuple(t for t in tags if t!="manual_only")
            metadata["placement_rules"]={**metadata.get("placement_rules",{}),"manual_only":False}
        records.append(replace(record,tags=tags,geometry_path=str(path.resolve()),metadata=metadata))
        print("Annotated",name,len(support),"support patches",flush=True)
    # Trial registry only: production registry remains untouched until integration validation.
    save_json({"schema_version":"cityg.assets.v1","assets":[r.to_dict() for r in records]},stage/"placement_registry.json")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["inspect","annotate"])
    parser.add_argument("--staging",type=Path,default=ROOT/"assets/prepared/interior_v1")
    parser.add_argument("--config",type=Path,default=ROOT/"configs/interior_asset_annotations.json")
    parser.add_argument("--asset",action="append",default=[])
    args=parser.parse_args()
    if args.action=="annotate": annotate(json.loads(args.config.read_text()),args.staging);return
    registry=AssetRegistry(args.staging/"candidate_registry.json")
    for name in args.asset:
        record=registry.require(name); mesh=triangles(registry.resolve_path(record.geometry_path))
        physical=mesh*np.array(record.dimensions_m)
        normal=np.cross(physical[:,1]-physical[:,0],physical[:,2]-physical[:,0])
        area=np.linalg.norm(normal,axis=1)/2
        horizontal=normal[:,2]>1.999*area
        sums={}
        for z,a in zip(mesh[horizontal].mean(axis=1)[:,2],area[horizontal]):
            key=round(float(z),4);sums[key]=sums.get(key,0)+float(a)
        print(name,record.dimensions_m,record.metadata["output_sha256"])
        print("horizontal patches normalized z/area m2",sorted(sums.items(),key=lambda p:-p[1])[:15])
        print("center ray normalized z",sorted(intersections(mesh,0,0).tolist()))


if __name__=="__main__":main()
