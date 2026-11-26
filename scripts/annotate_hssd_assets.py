"""Apply complete, snapshot-bound HSSD curation and conservative support probes.

Writes an all-asset annotated registry (disabled) plus a bounded trial registry.
No production promotion. Surface geometry certifies sampled visual contact only,
not load bearing, dynamics, exact collision meshes or articulation.
"""
import argparse
from collections import Counter
from dataclasses import replace
import html
import json
from pathlib import Path
import shutil
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from scripts.annotate_interior_assets import triangles, intersections, check_surface
from scripts.prepare_exterior_assets import write_json
from scripts.prepare_hssd_assets import sha256
from cityg.assets import AssetRegistry

ROOT = Path(__file__).resolve().parents[1]


def largest_rectangle(mask):
    """Largest all-true cell rectangle; deterministic and independent of geometry."""
    best = None; score = 0
    for first in range(mask.shape[0]):
        columns = np.ones(mask.shape[1], dtype=bool)
        for last in range(first, mask.shape[0]):
            columns &= mask[last]
            start = 0
            for col in range(mask.shape[1]+1):
                if col < mask.shape[1] and columns[col]:
                    continue
                area = (last-first+1)*(col-start)
                if area > score:
                    best = (first,last+1,start,col); score = area
                start = col+1
    return best


def front_accessible(mesh, x, y, z, dims, axis="+X"):
    """Sample a horizontal access ray above the shelf, rejecting closed cabinet fronts."""
    direction=0 if axis.endswith("X") else 1
    other=1-direction
    # Reuse the triangle ray routine with source front axis mapped to ray Z.
    ray_mesh=mesh[:,:,[other,2,direction]]
    hits=intersections(ray_mesh, y if direction==0 else x, z+.08/dims[2])
    origin=x if direction==0 else y
    sign=1 if axis.startswith("+") else -1
    return not bool(np.any((hits-origin)*sign > .003/dims[direction]))


def discover_supports(mesh, dims, kind, front_axis="+X"):
    """Only called for visually approved tables/open shelving, never arbitrary BBoxes."""
    physical=mesh*np.array(dims)
    normals=np.cross(physical[:,1]-physical[:,0],physical[:,2]-physical[:,0])
    lengths=np.linalg.norm(normals,axis=1)
    upward=mesh[normals[:,2]>.85*lengths]
    areas=lengths[normals[:,2]>.85*lengths]/2
    flat=np.ptp(upward[:,:,2],axis=1)*dims[2] < .002
    step=.001/dims[2]; planes={}
    for triangle,area in zip(upward[flat],areas[flat]):
        z=round(float(triangle[:,2].mean())/step)*step
        planes[z]=planes.get(z,0)+float(area)
    planes=[z for z,area in planes.items() if area>=.025 and -.49<=z<=.5001
            and (kind=="shelves" or z>=0)]
    planes.sort(reverse=kind=="top")
    coords=np.linspace(-.46,.46,19); tolerance=.003/dims[2]
    results=[]; failures=[]; used_z=[]
    for z in planes:
        z=min(.5,max(-.5,z))
        if any(abs(z-old)*dims[2]<.012 for old in used_z): continue
        supporting=upward[(upward[:,:,2].min(axis=1)<=z+tolerance)&(upward[:,:,2].max(axis=1)>=z-tolerance)]
        above=mesh[mesh[:,:,2].max(axis=1)>z+tolerance]
        valid=np.zeros((len(coords),len(coords)),dtype=bool)
        for ix,x in enumerate(coords):
            for iy,y in enumerate(coords):
                hits=intersections(supporting,x,y)
                if not len(hits) or np.min(np.abs(hits-z))>tolerance: continue
                upper=intersections(above,x,y); upper=upper[upper>z+tolerance]
                clearance=(upper.min()-z)*dims[2] if len(upper) else None
                valid[ix,iy]=(clearance is None if kind=="top" else clearance is not None and clearance>=.12
                              and front_accessible(mesh,x,y,z,dims,front_axis))
        cells=valid[:-1,:-1]&valid[1:,:-1]&valid[:-1,1:]&valid[1:,1:]
        found=False
        for attempt in range(3):
            rect=largest_rectangle(cells)
            if rect is None: break
            x0,x1,y0,y1=rect;cells[x0:x1,y0:y1]=False
            width=(coords[x1]-coords[x0])*.92;depth=(coords[y1]-coords[y0])*.92
            if min(width*dims[0],depth*dims[1])<.09 or width*depth*dims[0]*dims[1]<.02: continue
            spec={"id":f"{kind}_{len(results):02d}","kind":kind,
                  "center":[float((coords[x0]+coords[x1])/2),float((coords[y0]+coords[y1])/2),float(z)],
                  "size":[float(width),float(depth)]}
            try:
                checked=check_surface(mesh,dims,spec)
                clearance=checked["geometry_probe"]["sampled_clearance_m"]
                if kind=="top" and clearance is not None: raise ValueError("Obstruction above tabletop")
                if kind=="shelves":
                    if clearance is None or clearance<.12: raise ValueError("Unknown/insufficient shelf headroom")
                    for x in np.linspace(spec["center"][0]-width/2,spec["center"][0]+width/2,7):
                        for y in np.linspace(spec["center"][1]-depth/2,spec["center"][1]+depth/2,7):
                            if not front_accessible(mesh,x,y,z,dims,front_axis):
                                raise ValueError("Shelf blocked by front geometry")
                    spec["clearance_m"]=max(0,float(clearance-.005))
                    checked=check_surface(mesh,dims,spec)
                    checked["geometry_probe"]["front_access"]={"axis":front_axis,"samples":49,"height_above_plane_m":.08}
                checked["geometry_probe"]["proposal_method"]="semantic_allowlist_then_horizontal_planes_and_grid_rectangle"
                results.append(checked);found=True
            except ValueError as exc:
                failures.append(str(exc))
        if found: used_z.append(z)
        if kind=="top" and found: break
        if len(results)>=12: break
    return results[:12],failures


def validate_decisions(config, registry, stage):
    if config["candidate_registry_sha256"]!=sha256(stage/"candidate_registry.json"):
        raise ValueError("Candidate snapshot changed; repeat review")
    records={r.asset_id:r for r in registry.list_all()}
    if len(config["assets"])!=len(records) or {s["asset_id"] for s in config["assets"]}!=set(records):
        raise ValueError("Curation must cover every candidate exactly once")
    for spec in config["assets"]:
        record=records[spec["asset_id"]]
        if (sha256(registry.resolve_path(record.geometry_path))!=spec["output_sha256"] or
                record.metadata["output_sha256"]!=spec["output_sha256"]):
            raise ValueError("Geometry changed since review")
        if sha256(stage/"review/previews"/(record.asset_id+".png"))!=spec["preview_sha256"]:
            raise ValueError("Preview changed since review")
        if spec.get("top_preview_sha256") and sha256(stage/"review_top/previews"/(record.asset_id+".png"))!=spec["top_preview_sha256"]:
            raise ValueError("Top preview changed since review")
        if spec["front_axis"] not in {"+X","-X","+Y","-Y"} or not spec["note"].strip():
            raise ValueError("Missing orientation or review evidence")
        if spec["disposition"] not in {"trial","adapter","hold"} or spec["support_policy"] not in {"none","top","shelves"}:
            raise ValueError("Invalid disposition/support policy")
        if not spec["room_types"] or not spec["colors"] or not spec["material_appearance"]:
            raise ValueError("Incomplete semantic annotation")


def annotate(config, stage):
    registry=AssetRegistry(stage/"candidate_registry.json")
    validate_decisions(config,registry,stage)
    annotated=[]; trials=[]; reports=[]
    for spec in config["assets"]:
        record=registry.require(spec["asset_id"]); path=registry.resolve_path(record.geometry_path).resolve()
        disposition=spec["disposition"]; blockers=[]; supports=[]; probe_errors=[]
        if record.metadata["mesh_validation"]["triangle_count"]>config["max_trial_triangles"]:
            disposition="hold";blockers.append("geometry_lod_required")
        if disposition=="trial" and spec["placement_kind"] not in {"floor","surface"}:
            disposition="adapter";blockers.append("placement_adapter_required")
        if disposition=="trial":
            try:
                mesh=triangles(path)
                if spec["support_policy"]!="none":
                    supports,probe_errors=discover_supports(mesh,record.dimensions_m,spec["support_policy"],spec["front_axis"])
                    if not supports:
                        disposition="adapter";blockers.append("no_verified_support_rectangle")
            except (ValueError,KeyError) as exc:
                disposition="hold";blockers.append("geometry_probe_failed: "+str(exc))
        if spec["disposition"]!="trial": blockers.append(spec["note"])
        front_kind=spec["front_kind"]
        is_convention=front_kind=="convention_no_unique_front"
        rules={"kind":spec["placement_kind"],"upright":True,"scale_policy":"preserve_source_physical_proportions",
               "front_kind":front_kind,"no_automatic_nested_objects":True,
               "requires_room_placement_validation":True,"simulation_articulation":False}
        if spec["category"] in {"bed","wardrobe","bookcase","desk","bedside_table"}:
            rules["preferred_back_against_wall"]=True
            rules["front_access_clearance_m"] = .65 if spec["category"] in {"desk","wardrobe"} else .5
            rules["clearance_provenance"]="conservative_planning_hint_not_measured"
        if spec["placement_kind"]=="soft_support": rules["requires_backrest_or_soft_support"]=True
        if spec["placement_kind"]=="edge_clamp": rules["requires_desk_edge_mount"]=True
        if spec["placement_kind"]=="floor_overlay": rules["collision_policy"]="visual_floor_overlay_no_solid_bbox"
        if spec["category"] in {"cup","vase","tray","bowl","table_lamp","floor_lamp"}:
            rules["nested_support_approved"]=False
        evidence={"method":config["review_method"],"status":"visual_checked" if spec["disposition"]!="hold" else "hold",
            "note":spec["note"],"preview_sha256":spec["preview_sha256"],"output_sha256":spec["output_sha256"],
            "dimensions_m":list(record.dimensions_m),
            **({"top_preview_sha256":spec["top_preview_sha256"]} if spec.get("top_preview_sha256") else {})}
        meta={**record.metadata,"runtime_enabled":False,"indoor_pack_status":"annotated_"+disposition,
            "indoor_annotation_version":1,"physical_dimensions_m":list(record.dimensions_m),
            "annotation_geometry_sha256":spec["output_sha256"],"visual_review":evidence,
            "curation":{"index":spec["review_index"],"source_category":record.category,"disposition":disposition,
                        "blockers":blockers,"all_items_visually_reviewed":True},
            "appearance":{"style":spec["style"],"colors":spec["colors"],"material_appearance":spec["material_appearance"],
                          "provenance":"visual_estimate_not_measured_physical_material"},
            "placement_kind":spec["placement_kind"],"placement_rules":rules,
            "placement_anchor":{"kind":"bottom_center" if spec["placement_kind"] in {"floor","surface"} else "adapter_required",
                                "normalized_z":-.5,"up_axis":"+Z","stability_verified":False},
            "room_support_surfaces":supports,"support_annotation_status":"geometry_checked" if supports else "not_approved",
            "orientation":{**record.metadata["orientation"],"canonical_forward_axis":spec["front_axis"],
                           "orientation_confidence":"reviewed","front_evidence":spec["note"],
                           "front_kind":front_kind,"front_axis_is_convention":is_convention}}
        tags=tuple(dict.fromkeys(["indoor","hssd",spec["category"],spec["style"],*spec["colors"],*spec["material_appearance"]]))
        updated=replace(record,category=spec["category"],room_types=tuple(spec["room_types"]),tags=tags,metadata=meta)
        annotated.append(updated.to_dict())
        if disposition=="trial":
            trials.append(replace(updated,geometry_path=str(path),metadata={**meta,"runtime_enabled":True,"indoor_pack_status":"placement_trial"}).to_dict())
        reports.append({"asset_id":record.asset_id,"index":spec["review_index"],"category":spec["category"],
                        "disposition":disposition,"support_count":len(supports),"blockers":blockers,"probe_failures":probe_errors})
        print(spec["review_index"],spec["category"],disposition,"supports",len(supports),flush=True)
    write_json(stage/"annotated_registry.json",{"schema_version":"cityg.assets.v1","assets":annotated})
    write_json(stage/"placement_registry.json",{"schema_version":"cityg.assets.v1","assets":trials})
    if config.get("smoke_asset_indices"):
        wanted=set(config["smoke_asset_indices"])
        selected=[r for r in trials if r["metadata"]["curation"]["index"] in wanted]
        if {r["metadata"]["curation"]["index"] for r in selected}!=wanted:
            raise ValueError("Smoke allowlist contains a held/unverified asset")
        write_json(stage/"smoke_registry.json",{"schema_version":"cityg.assets.v1","assets":selected})
    write_json(stage/"annotation_report.json",{"asset_count":len(annotated),"trial_count":len(trials),
        "dispositions":dict(Counter(r["disposition"] for r in reports)),"support_count":sum(r["support_count"] for r in reports),
        "production_registry_changed":False,"assets":reports})


def gallery(stage):
    records=json.loads((stage/"annotated_registry.json").read_text())["assets"]
    production=AssetRegistry(ROOT/"assets/asset_registry.json")
    promoted=0
    target=stage/"gallery"; (target/"images").mkdir(parents=True,exist_ok=True)
    cards=[]
    for r in records:
        m=r["metadata"]; cur=m["curation"]; ap=m["appearance"]; evidence=m["visual_review"]
        image_name=r["asset_id"]+".png"; source=stage/"review/previews"/image_name
        if sha256(source)!=evidence["preview_sha256"]: raise ValueError("Stale annotated gallery preview")
        shutil.copy2(source,target/"images"/image_name)
        pictures=f'<a href="images/{image_name}"><img loading="lazy" src="images/{image_name}"></a>'
        if evidence.get("top_preview_sha256"):
            top=stage/"review_top/previews"/image_name
            if sha256(top)!=evidence["top_preview_sha256"]: raise ValueError("Stale top preview")
            shutil.copy2(top,target/"images"/("top_"+image_name))
            pictures+=f'<a href="images/top_{image_name}">补充俯视/斜视</a>'
        title=f"#{cur['index']:03d} {r['category']} | {m['display_name']}"
        active=production.get(r["asset_id"])
        enabled=bool(active and active.metadata.get("indoor_pack_status")=="production_accepted"
                     and active.metadata.get("runtime_enabled") is True
                     and active.metadata.get("annotation_geometry_sha256")==m["annotation_geometry_sha256"])
        promoted+=int(enabled)
        title+=(" | 正式库已启用" if enabled else " | 未正式启用")
        detail=f"{cur['disposition']} | {ap['style']} | {', '.join(ap['colors'])} | {', '.join(r['room_types'])}"
        facing=f"正面 {m['orientation']['canonical_forward_axis']} ({m['orientation']['front_kind']}) | {m['placement_kind']} | {len(m['room_support_surfaces'])} 个支撑区域"
        cards.append(f'<article data-state="{cur["disposition"]}">{pictures}<h3>{html.escape(title)}</h3><p>{html.escape(detail)}</p>'
            f'<p>{html.escape(facing)}</p><p>{html.escape(evidence["note"])}</p><p>{html.escape(str(r["dimensions_m"]))} m | {m["mesh_validation"]["triangle_count"]} tri</p>'
            f'<p>{r["asset_id"]}</p><a href="{html.escape(m["source_url"],quote=True)}">来源 · CC BY-NC 4.0</a></article>')
    report=json.loads((stage/"annotation_report.json").read_text())
    summary=f"全部 {len(records)} 项已标注；准备状态 {report['dispositions']}；{report['support_count']} 个支撑区域；正式库已启用 {promoted} 项。"
    (target/"index.html").write_text('<!doctype html><meta charset="utf-8"><title>CityG HSSD 标注资产库</title>'
      '<style>body{font:14px system-ui;margin:20px;background:#eef2f0}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(350px,1fr));gap:12px}article{background:white;padding:12px;overflow-wrap:anywhere}img{width:100%}article[hidden]{display:none}input{width:85%;padding:12px}[data-state=hold]{border-top:5px solid #bd6565}[data-state=adapter]{border-top:5px solid #d6af4b}[data-state=trial]{border-top:5px solid #539477}</style>'
      '<h1>CityG HSSD 标注资产库</h1><p>'+html.escape(summary)+'</p><p>trial=准备阶段可进入摆放试验；adapter=需专用放置或支撑逻辑；hold=暂缓。是否正式启用另见卡片标题（导出时状态）。材质为目视估计；支撑采样不等于物理承重验证。</p>'
      '<p>原图角标是来源暂定 +X；实际标注正面以卡片文字为准。CC BY-NC 4.0，外部资产需用户自行下载。</p>'
      '<input placeholder="搜索类别、风格、房间、状态、编号" oninput="document.querySelectorAll(\'article\').forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(this.value.toLowerCase()))"><main>'+"".join(cards)+'</main>',encoding="utf-8")
    print(target/"index.html")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["annotate","gallery"])
    parser.add_argument("--staging",type=Path,default=ROOT/"assets/prepared/hssd_v1")
    parser.add_argument("--config",type=Path,default=ROOT/"configs/hssd_asset_annotations.json")
    args=parser.parse_args()
    if args.action=="annotate": annotate(json.loads(args.config.read_text()),args.staging)
    else: gallery(args.staging)


if __name__=="__main__": main()
