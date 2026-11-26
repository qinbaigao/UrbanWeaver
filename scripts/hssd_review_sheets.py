"""Render numbered six-asset review sheets from existing four-view PNGs.

No asset conversion or approval. Screenshots use a headless browser and local
files, never opening a desktop browser or contacting a model service.
"""
import argparse
import html
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, default=Path("assets/prepared/hssd_v1"))
    parser.add_argument("--review-dir", default="review", choices=["review", "review_top"])
    args = parser.parse_args(); stage = args.staging.resolve()
    records = list(enumerate(json.loads((stage/"candidate_registry.json").read_text())["assets"], 1))
    records = [(n,r) for n,r in records if (stage/args.review_dir/"previews"/(r["asset_id"]+".png")).is_file()]
    dest = stage/args.review_dir/"sheets"; dest.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width":1440,"height":1160}, device_scale_factor=1)
        for start in range(0,len(records),6):
            cards=[]
            for number, record in records[start:start+6]:
                meta=record["metadata"]; image=stage/args.review_dir/"previews"/(record["asset_id"]+".png")
                caption=f"#{number:03d} {record['category']} | {meta['display_name']}"
                details=f"{record['asset_id'][-8:]} | {tuple(round(v,3) for v in record['dimensions_m'])} m | {meta['mesh_validation']['triangle_count']} tri"
                cards.append(f'<article><h3>{html.escape(caption)}</h3><img src="{image.as_uri()}"><p>{html.escape(details)}</p></article>')
            doc=dest/f"sheet_{start//6+1:02d}.html"
            doc.write_text('<!doctype html><meta charset="utf-8"><style>body{margin:8px;font:14px sans-serif}main{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}h3{height:34px;margin:0;font-size:15px}p{margin:1px;font-size:13px}img{width:100%}article{min-width:0}</style><main>'+"".join(cards)+'</main>')
            page.goto(doc.as_uri()); page.wait_for_function("Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)")
            page.screenshot(path=str(doc.with_suffix(".png")), full_page=True)
        browser.close()
    print(dest)


if __name__=="__main__": main()
