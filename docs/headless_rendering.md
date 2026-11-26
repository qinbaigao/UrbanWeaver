# Headless Viewer rendering

**English** | [简体中文](headless_rendering.zh-CN.md)

CityG uses the Web Viewer itself as a lightweight render frontend. Playwright
launches Chromium without a desktop session; `headless_capture.py` asks it to
use SwiftShader, so this step does not require an RTX GPU or an Isaac Sim
installation.

Screenshot readiness is event-based rather than a fixed sleep. Every Viewer
geometry refresh starts a new asset generation and exposes its pending GLB
count through `window.citygObservation.waitForAssets`. Adaptive and standalone
renderers capture the canvas only after all assets in the current generation
were loaded or received an explicit fallback. `--wait-ms` is now only a short
post-load visual settling interval; `render_observation_plan.py` separately
accepts `--asset-timeout-ms` and records `asset_load_status.json`.

This is a readiness barrier, not proof of high-fidelity rendering. Inspect
`failed`/fallback/proxy counters and the active render profile; acceptance that
requires real assets rejects proxy substitutions even if `ready=true`.
Global review proxies cannot substantiate detailed furniture/facade claims.
Automated debug capture must not open desktop browser tabs. Per-view timing
records measure camera, asset wait and capture costs; they are not a speedup claim.

Automated capture injects the first observation before page initialization and
uses the `review` render profile by default. This prevents an unnecessary full
scene/HDR/PBR load before the intended camera is known. A complete observation
plan reuses one page and its persistent scene graph: camera-only views do not
rebuild geometry, while hierarchy changes reuse already instantiated GLBs.
`asset_load_status.json` records `render_profile`, `geometry_rebuild_count`,
`visible_primitive_count`, and `cached` alongside the load barrier counters.

## Recommended installation in `cityG`

```bash
conda activate cityG
python -m pip install playwright
python -m playwright install chromium
```

The two Python commands install the Playwright API and download the matching
browser binary. Playwright keeps browser binaries in its cache and the versions
should be reinstalled after upgrading Playwright. This follows the official
Playwright browser installation procedure ([browser docs](https://playwright.dev/python/docs/browsers)).

If the machine allows system package installation and reports missing shared
libraries, use:

```bash
python -m playwright install --with-deps chromium
```

This may require administrator privileges. Without administrator privileges,
install the Python package and browser only, then ask an administrator to add
the missing Linux libraries.

## Capture a CityG scene

For a single screenshot, use the following two-terminal workflow. For the
complete adaptive visual loop, prefer `cityg adaptive-review` below; it starts
and stops its own Viewer servers and renders both the pre-review and local
post-review plans.

Terminal A:

```bash
conda activate cityG
# Run from the UrbanWeaver repository root.
PYTHONPATH=src python -m cityg view outputs/mixed_district/final/openusd \
  --host 127.0.0.1 --port 5187 --no-browser
```

Terminal B:

```bash
conda activate cityG
# Run from the UrbanWeaver repository root.
python scripts/headless_capture.py \
  --url http://127.0.0.1:5187 \
  --output outputs/mixed_district/visual_review/view.png \
  --width 1600 --height 1000 --wait-ms 5000 \
  --quality-profile review --mode overview
```

Use `--quality-profile presentation` only for final paper figures; use
`interactive` for screenshots meant to match manual Viewer inspection.

Then submit the image to the optional VLM gate:

```bash
PYTHONPATH=src python -m cityg visual-review \
  outputs/mixed_district/visual_review/view.png \
  --output outputs/mixed_district/visual_review/report.json
```

## Complete adaptive review

```bash
PYTHONPATH=src python -m cityg adaptive-review \
  outputs/mixed_district/final/openusd \
  --output outputs/adaptive_review_run \
  --base-url http://127.0.0.1:8000/v1 \
  --model cityg-llm --max-tokens 1536 \
  --max-views 8 --max-building-refinements 1 --max-room-refinements 1
```

The command performs adaptive observation planning, batched VLM review, typed
entity binding, bounded Streetscape/Building/Room refinement, OpenUSD recompilation and
local post-review rendering. Chromium uses SwiftShader and does not require an
RTX GPU.

The integrated renderer keeps one generation-scoped Viewer page for a complete
observation plan, changes only the audited camera contract between views, and
waits for the asset barrier before every capture. This avoids reloading all
GLB/PBR assets for each street angle. WebGL readback and compositor fallback
both have hard timeouts, so an overloaded SwiftShader process cannot wait
forever. Street-bound findings additionally enter the bounded Streetscape
semantic repair path when `--max-streetscape-refinements` is non-zero.

Use `--no-sandbox` only when running inside a restricted container or under a
user that cannot create Chromium namespaces. It is not the default because the
Chromium sandbox is safer for ordinary user accounts.
