#!/usr/bin/env python3
"""Summarize acquisition separately from runtime readiness; create a portable review gallery."""
from __future__ import annotations

import html
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from scripts.prepare_exterior_assets import write_json

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "assets/prepared/exterior_v3"


def main():
    records = []
    ph = json.loads((STAGE / "download_plan.json").read_text())
    audit = {r["asset_id"]: r for r in json.loads((STAGE / "audit.json").read_text())["assets"]}
    for entry in ph["assets"]:
        asset_id = "prepared_polyhaven_" + entry["id"]
        records.append({"id": asset_id, "category": entry["category"], "provider": "Poly Haven",
                        "license_id": "CC0-1.0", "source_url": f"https://polyhaven.com/a/{entry['id']}",
                        "acquisition": "reused_local" if entry.get("local_source") else "new_download",
                        "status": "candidate_pending_visual_and_placement_review", "runtime_ready": False,
                        "preview_kind": "CityG four-view render",
                        "preview": str(STAGE / "review/previews" / f"{asset_id}.png"),
                        "geometry_audit": audit[asset_id]})
    github_bytes, motion_files = 0, 0
    dependency_warnings = []
    for name in ("exterior_v3_sources", "exterior_v3_gazebo"):
        directory = ROOT / "assets/incoming" / name
        manifest = json.loads((directory / "acquisition_manifest.json").read_text())
        if manifest["failures"] or any(g["status"] != "downloaded_pending_conversion_review" for g in manifest["groups"]):
            raise ValueError(f"Acquisition incomplete: {name}")
        github_bytes += manifest["verified_bytes"]
        for group in manifest["groups"]:
            paths = [directory / f for f in group["local_files"]]
            if any(not p.is_file() for p in paths):
                raise ValueError(f"Source payload missing: {group['id']}")
            record = {**group, "acquisition": "new_download", "provider": group["repo"],
                      "status": "source_downloaded_pending_conversion_review", "runtime_ready": False,
                      "preview": None, "preview_kind": None}
            if group["category"] == "person_rigged_source":
                previews = [p for p in paths if p.name == group["id"] + ".png"]
                if previews:
                    record.update(preview=str(previews[0]), preview_kind="Upstream author preview, NOT CityG four-view render")
            if group["category"] == "animation_source":
                motion_files += sum(p.suffix.lower() == ".fbx" for p in paths)
            if any(p.suffix == ".glb" for p in paths):
                record.update(preview=str(STAGE / "source_review/review/previews" / f"review_v3_{group['id']}.png"),
                              preview_kind="CityG four-view render; source scene may contain multiple objects")
            # Preserve SDF model dependencies; a downloaded folder alone is not
            # proof that its assembled scene is self-contained.
            for path in paths:
                if path.suffix not in {".sdf", ".config"}:
                    continue
                package_root = directory / group["repo"].replace("/", "_") / group["revision"][:12]
                for uri in re.findall(r"model://([^<\s\"']+)", path.read_text()):
                    if not (package_root / uri).exists():
                        dependency_warnings.append({"id": group["id"], "file": str(path.relative_to(ROOT)), "missing_uri": "model://" + uri})
            records.append(record)
    models = [r for r in records if r["category"] != "animation_source"]
    summary = {"new_model_source_groups": sum(r["acquisition"] == "new_download" for r in models),
               "reused_model_source_groups": sum(r["acquisition"] == "reused_local" for r in models),
               "downloaded_motion_files": motion_files, "new_runtime_promotions": 0,
               "new_source_download_bytes": ph["total_bytes"] + github_bytes,
               "category_counts_including_reuse": dict(Counter(r["category"] for r in models)),
               "dependency_warning_count": len(dependency_warnings)}
    write_json(STAGE / "source_catalog.json", {"schema_version": "cityg.exterior_source_catalog.v1",
                                               "summary": summary, "records": records,
                                               "dependency_warnings": dependency_warnings})
    gallery = STAGE / "gallery"
    (gallery / "images").mkdir(parents=True, exist_ok=True)
    cards = []
    for record in records:
        image_markup = '<div class="pending">尚未转换渲染 / Pending conversion</div>'
        if record.get("preview") and Path(record["preview"]).is_file():
            name = re.sub(r"[^A-Za-z0-9_-]", "_", record["provider"] + "_" + record["id"]) + ".png"
            shutil.copy2(record["preview"], gallery / "images" / name)
            image_markup = f'<a href="images/{name}"><img loading="lazy" src="images/{name}" alt="{html.escape(record["id"])}"></a>'
        description = " | ".join(str(record.get(k) or "") for k in ("category", "provider", "license_id", "acquisition", "preview_kind"))
        cards.append(f'<article>{image_markup}<h3>{html.escape(record["id"])}</h3><p>{html.escape(description)}</p>'
                     f'<a href="{html.escape(record["source_url"], quote=True)}">Source / 来源</a><p>未自动投产</p></article>')
    gallery.joinpath("index.html").write_text('''<!doctype html><html lang="zh"><meta charset="utf-8">
<title>CityG 第三批资产收集与审核</title><style>
body{font:15px system-ui;margin:24px;background:#e9eeed;color:#243530}input{padding:10px;width:90%;margin:12px 0}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:16px}
article{background:white;padding:12px;border-radius:10px;overflow-wrap:anywhere}img{width:100%;height:290px;object-fit:contain}
.pending{height:290px;display:grid;place-items:center;background:#f0f2f1}p{line-height:1.5}h3{font-size:15px}</style>
<h1>第三批：已收集不等于已接入</h1><p>本页可连同 images 文件夹下载后直接打开，无需服务器。
人物图是上游作者预览；其余已有图片是 CityG 四视图。所有本批资产仍待审核、转换或放置适配。
搜索框可筛选类别、来源及名称。</p><input id="filter" placeholder="vehicle / person / fountain / roof ...">
<main>''' + "\n".join(cards) + '''</main><script>
document.querySelector('#filter').addEventListener('input',e=>{let q=e.target.value.toLowerCase();
document.querySelectorAll('article').forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(q));});
</script></html>''', encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(gallery / "index.html")


if __name__ == "__main__":
    main()
