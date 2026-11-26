#!/usr/bin/env bash
set -euo pipefail

# Local-only, one-GPU Hunyuan worker. Prefer an explicit CITYG_ASSET_GPU;
# otherwise preserve an inherited CUDA_VISIBLE_DEVICES (used by the pipeline
# runner), and fall back to GPU 2 for backwards-compatible direct launches.
CITYG_ASSET_GPU="${CITYG_ASSET_GPU:-${CUDA_VISIBLE_DEVICES:-2}}"
export CUDA_VISIBLE_DEVICES="$CITYG_ASSET_GPU"
# Select the Python environment with Hunyuan3D and its CUDA extensions installed.
ASSET_PYTHON="${CITYG_ASSET_PYTHON:-python}"
if [[ -n "${CUDA_HOME:-}" ]]; then
  export PATH="$CUDA_HOME/bin:$PATH"
  export LD_LIBRARY_PATH="$CUDA_HOME/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export PYTHONPATH="${PYTHONPATH:-src}"

exec "${ASSET_PYTHON}" -u -m cityg.hunyuan_asset_service \
  --repo-path "${CITYG_HUNYUAN_REPO:-../Hunyuan3D-2}" \
  --model-root "${CITYG_HUNYUAN_MODEL_ROOT:-models/Hunyuan3D-2}" \
  --t2i-model "${CITYG_HUNYUAN_T2I_MODEL:-models/HunyuanDiT-v1.1-Diffusers-Distilled}" \
  --output-root assets/generated \
  --host 127.0.0.1 --port 8091 \
  --octree-resolution "${CITYG_OCTREE_RESOLUTION:-192}" \
  --shape-steps "${CITYG_SHAPE_STEPS:-5}" \
  --face-count "${CITYG_FACE_COUNT:-30000}" \
  --no-flashvdm
