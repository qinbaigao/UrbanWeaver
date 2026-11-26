# UrbanWeaver

**From Streets to Rooms: Building Fine-Grained Urban Simulation Environments**

UrbanWeaver turns a text brief into a city with connected streets, buildings, floors, rooms and furniture. Its agents exchange spatial constraints across scales, check candidate layouts against the compiled geometry, and can revise a bounded part of a scene. You can export the result to OpenUSD, explore it in the bundled Web Viewer, or edit an existing city. The Python package and CLI are named `cityg`.

## Generate a first city offline

From the repository root in a Python 3.10 or 3.11 environment, run:

```bash
python -m pip install -e .
python -m cityg generate --spec examples/research_specs/01_residential_neighborhood.json \
  --output outputs/first_city --backend openusd
python -m cityg validate outputs/first_city/city.json
python -m cityg view outputs/first_city
```

This example uses the deterministic planner and procedural geometry. It runs on CPU. The Viewer ships prebuilt.

## Generate from a text instruction

Start an OpenAI-compatible multimodal model server, set the model name and endpoints in a local copy of the configuration, and install Chromium for visual review:

```bash
cp configs/full_pipeline.env configs/pipeline.local.env
python -m pip install playwright pillow 'shapely>=2.1,<3'
python -m playwright install chromium
CITYG_CONFIG=configs/pipeline.local.env bash scripts/run_cityg_pipeline.sh \
  "Build a mixed district with ten buildings, connected streets, and a small park. Furnish ten rooms across three buildings." \
  outputs/mixed_district
```

Set `LLM_BASE_URL`, `VLM_BASE_URL`, `LLM_MODEL` and `VLM_MODEL` for your service. The defaults use a local endpoint on port 8000 serving `cityg-llm`. Choose an empty output directory. The runner prints the generation, review and portable Viewer paths as it finishes.

## Assets and optional services

The repository includes procedural geometry, asset metadata and preparation scripts. To reproduce textured scenes, obtain the corresponding meshes, textures and model weights from their upstream sources. The asset registries describe both procedural and downloadable items. For available sources see [the source catalog](assets/external_sources.json) and [third-party notices](THIRD_PARTY_NOTICES.md).

To install the optional PBR ground textures used by the material integration tests, run `python scripts/download_polyhaven_ground_materials.py`.

To enable missing-asset generation, configure an existing Hunyuan worker with `ASSET_GENERATION_ENABLED=true` and `ASSET_URL`. To start a worker locally, prepare its model environment and CUDA extensions, set `ASSET_WORKER_AUTO_START=true`, and export `CITYG_ASSET_PYTHON`, `CITYG_HUNYUAN_REPO`, `CITYG_HUNYUAN_MODEL_ROOT` and `CITYG_HUNYUAN_T2I_MODEL`. The worker GPU is selected by `ASSET_WORKER_GPU` in the pipeline configuration.

## Working with the result

- For supported edit instructions and protected scene state, see [scene editing](docs/editing.md).
- For reproducible screenshots and visual review, see [headless rendering](docs/headless_rendering.md).
- For CPU physics validation, use the separate environment in [ovphysx.yml](environments/ovphysx.yml).
- The project code is licensed under [Apache 2.0](LICENSE). Third-party components and assets retain their upstream terms.
