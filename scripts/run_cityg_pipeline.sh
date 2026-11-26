#!/usr/bin/env bash
# CityG: natural language -> agentic OpenUSD city -> adaptive VLM review.
# Public interface: instruction and output directory. All other knobs live in
# configs/full_pipeline.env.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
CONFIG_FILE="${CITYG_CONFIG:-${PROJECT_ROOT}/configs/full_pipeline.env}"

usage() {
  cat >&2 <<'EOF'
Usage:
  scripts/run_cityg_pipeline.sh "<city requirement>" <output-directory>

Example:
  scripts/run_cityg_pipeline.sh \
    "构建一个包含住宅、商业和公共服务、道路连通并具有不同建筑高度的 8 栋社区" \
    outputs/full_pipeline_demo

Edit configs/full_pipeline.env to change model endpoints, budgets, asset worker,
review limits, or backend settings.
EOF
}

die() {
  echo "[cityg] ERROR: $*" >&2
  exit 2
}

is_true() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

check_http() {
  local url="$1"
  curl -fsS --max-time "${HEALTH_TIMEOUT:-8}" "${url}" >/dev/null 2>&1
}

if [[ $# -ne 2 ]]; then
  usage
  exit 2
fi

INSTRUCTION="$1"
OUTPUT_PATH="$2"
[[ -n "${INSTRUCTION//[[:space:]]/}" ]] || die "instruction must not be empty"

[[ -f "${CONFIG_FILE}" ]] || die "missing config: ${CONFIG_FILE}"
# shellcheck disable=SC1090
source "${CONFIG_FILE}"
export CITYG_PROGRESS="${CITYG_PROGRESS:-true}"
export CITYG_PROGRESS_INTERVAL="${CITYG_PROGRESS_INTERVAL:-30}"

# Preserve the full log and the child's exit code; only curated summaries reach
# the terminal. In particular, do not print Chromium HTTP logs or model payloads.
run_logged() {
  local log_path="$1"
  shift
  "$@" 2>&1 | tee "${log_path}" | awk '/^\[cityg-progress\]/ { print; fflush(); }'
  local -a codes=("${PIPESTATUS[@]}")
  if [[ "${codes[0]}" -ne 0 ]]; then return "${codes[0]}"; fi
  if [[ "${codes[1]}" -ne 0 ]]; then return "${codes[1]}"; fi
  return "${codes[2]}"
}

PYTHON_BIN="${PYTHON_BIN:-python}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-8}"
MODEL_TIMEOUT="${MODEL_TIMEOUT:-180}"
MODEL_MAX_TOKENS="${MODEL_MAX_TOKENS:-6144}"
MODEL_SEED="${MODEL_SEED:-17}"
ASSET_REGISTRY="${ASSET_REGISTRY:-assets/asset_registry.json}"
MATERIAL_LIBRARY="${MATERIAL_LIBRARY:-assets/material_library.json}"
FACADE_ASSET_INDEX="${FACADE_ASSET_INDEX:-assets/facades/asset_annotations_reviewed.json}"
OUTDOOR_ASSET_MANIFEST="${OUTDOOR_ASSET_MANIFEST:-assets/outdoor/pack.json}"
INCOMING_ASSET_ROOT="${INCOMING_ASSET_ROOT:-assets/incoming}"
EXTERNAL_ASSET_CACHE="${EXTERNAL_ASSET_CACHE:-assets/external_cache}"
INCOMING_ASSET_MANIFEST="${INCOMING_ASSET_MANIFEST:-assets/incoming_manifest.json}"
EXTERNAL_ASSET_SOURCES="${EXTERNAL_ASSET_SOURCES:-assets/external_sources.json}"
REVIEW_SUBDIR="${REVIEW_SUBDIR:-visual_review}"
ASSET_WORKER_GPU="${ASSET_WORKER_GPU:-0}"

case "${OUTPUT_PATH}" in
  /*) ;;
  *) OUTPUT_PATH="${PROJECT_ROOT}/${OUTPUT_PATH}" ;;
esac
OUTPUT_PATH="$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "${OUTPUT_PATH}")"
case "${ASSET_REGISTRY}" in
  /*) ;;
  *) ASSET_REGISTRY="${PROJECT_ROOT}/${ASSET_REGISTRY}" ;;
esac
case "${OUTDOOR_ASSET_MANIFEST}" in
  /*) ;;
  *) OUTDOOR_ASSET_MANIFEST="${PROJECT_ROOT}/${OUTDOOR_ASSET_MANIFEST}" ;;
esac
case "${FACADE_ASSET_INDEX}" in
  /*) ;;
  *) FACADE_ASSET_INDEX="${PROJECT_ROOT}/${FACADE_ASSET_INDEX}" ;;
esac
for path_variable in INCOMING_ASSET_ROOT EXTERNAL_ASSET_CACHE INCOMING_ASSET_MANIFEST EXTERNAL_ASSET_SOURCES; do
  path_value="${!path_variable}"
  case "${path_value}" in
    /*) ;;
    *) printf -v "${path_variable}" '%s/%s' "${PROJECT_ROOT}" "${path_value}" ;;
  esac
done

require_command curl
require_command tee
require_command awk
require_command "${PYTHON_BIN}"

if [[ -e "${OUTPUT_PATH}" ]] && find "${OUTPUT_PATH}" -mindepth 1 -print -quit | grep -q .; then
  die "output directory is not empty: ${OUTPUT_PATH}"
fi

cd "${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

if [[ ! -f "${ASSET_REGISTRY}" ]]; then
  die "asset registry not found: ${ASSET_REGISTRY}"
fi

LLM_BASE_URL="${LLM_BASE_URL:-http://127.0.0.1:8000/v1}"
LLM_MODEL="${LLM_MODEL:-cityg-llm}"
VLM_BASE_URL="${VLM_BASE_URL:-${LLM_BASE_URL}}"
VLM_MODEL="${VLM_MODEL:-${LLM_MODEL}}"
ASSET_URL="${ASSET_URL:-http://127.0.0.1:8091}"

echo "[cityg] project: ${PROJECT_ROOT}"
echo "[cityg] output:  ${OUTPUT_PATH}"
echo "[cityg] model:   ${LLM_MODEL} @ ${LLM_BASE_URL}"

check_http "${LLM_BASE_URL}/models" || die "LLM endpoint unavailable: ${LLM_BASE_URL}"
if [[ "${VLM_BASE_URL}" != "${LLM_BASE_URL}" ]]; then
  check_http "${VLM_BASE_URL}/models" || die "VLM endpoint unavailable: ${VLM_BASE_URL}"
fi
echo "[cityg] model endpoints: ready; live progress=${CITYG_PROGRESS}"

ASSET_WORKER_PID=""
ASSET_AVAILABLE=false
ASSET_LOG_TMP="$(mktemp)"
cleanup() {
  if [[ -n "${ASSET_WORKER_PID}" ]] && kill -0 "${ASSET_WORKER_PID}" 2>/dev/null; then
    kill "${ASSET_WORKER_PID}" 2>/dev/null || true
    wait "${ASSET_WORKER_PID}" 2>/dev/null || true
  fi
  rm -f "${ASSET_LOG_TMP}"
}
trap cleanup EXIT

if is_true "${ASSET_GENERATION_ENABLED:-false}"; then
  [[ "${ASSET_WORKER_GPU}" =~ ^[0-9]+$ ]] || die "ASSET_WORKER_GPU must be a non-negative GPU index, got: ${ASSET_WORKER_GPU}"
  if check_http "${ASSET_URL}/health"; then
    ASSET_AVAILABLE=true
    echo "[cityg] asset worker: available at ${ASSET_URL}"
  elif is_true "${ASSET_WORKER_AUTO_START:-false}" && [[ -n "${ASSET_WORKER_CMD:-}" ]]; then
    echo "[cityg] asset worker: starting configured worker"
    CUDA_VISIBLE_DEVICES="${ASSET_WORKER_GPU}" bash -lc "${ASSET_WORKER_CMD}" >"${ASSET_LOG_TMP}" 2>&1 &
    ASSET_WORKER_PID="$!"
    for worker_attempt in $(seq 1 "${ASSET_START_ATTEMPTS:-30}"); do
      if [[ "$(( (worker_attempt - 1) % 5 ))" -eq 0 ]]; then
        echo "[cityg] asset worker: waiting for health (${worker_attempt}/${ASSET_START_ATTEMPTS:-30})"
      fi
      if check_http "${ASSET_URL}/health"; then
        ASSET_AVAILABLE=true
        break
      fi
      sleep "${ASSET_START_INTERVAL:-2}"
    done
    if is_true "${ASSET_AVAILABLE}"; then
      echo "[cityg] asset worker: started (pid ${ASSET_WORKER_PID})"
    else
      echo "[cityg] WARNING: asset worker did not become healthy" >&2
      cat "${ASSET_LOG_TMP}" >&2 || true
      if is_true "${ASSET_REQUIRE_HEALTH:-false}"; then
        die "Hunyuan asset worker failed to start at ${ASSET_URL}"
      fi
      echo "[cityg] WARNING: using procedural fallback" >&2
    fi
  else
    echo "[cityg] WARNING: asset worker unavailable; using procedural fallback" >&2
    if is_true "${ASSET_REQUIRE_HEALTH:-false}"; then
      die "ASSET_REQUIRE_HEALTH=true but ${ASSET_URL}/health is unavailable"
    fi
  fi
fi

if is_true "${INCOMING_ASSET_CURATION_ENABLED:-true}"; then
  if [[ -d "${INCOMING_ASSET_ROOT}" ]]; then
    echo "[cityg] incoming assets: canonicalizing and refreshing local tags"
    "${PYTHON_BIN}" -m cityg asset-curate \
      --incoming "${INCOMING_ASSET_ROOT}" \
      --cache "${EXTERNAL_ASSET_CACHE}" \
      --registry "${ASSET_REGISTRY}" \
      --manifest "${INCOMING_ASSET_MANIFEST}" \
      --source-catalog "${EXTERNAL_ASSET_SOURCES}"
  else
    echo "[cityg] incoming assets: no local download directory; external records will fall back safely"
  fi
fi

if is_true "${OUTDOOR_ASSET_PACK_ENABLED:-true}"; then
  OUTDOOR_ARGS=(
    -m cityg outdoor-assets
    --registry "${ASSET_REGISTRY}"
    --output "${OUTDOOR_ASSET_MANIFEST}"
    --max-generated-assets "${OUTDOOR_MAX_GENERATED_ASSETS:-4}"
  )
  if is_true "${OUTDOOR_ASSET_GENERATION_ENABLED:-true}" && is_true "${ASSET_AVAILABLE}"; then
    OUTDOOR_ARGS+=(--generate --asset-url "${ASSET_URL}" --timeout "${ASSET_TIMEOUT:-1800}")
    if ! is_true "${ASSET_TEXTURE:-true}"; then
      OUTDOOR_ARGS+=(--no-texture)
    fi
  fi
  echo "[cityg] outdoor assets: auditing and filling the semantic pack"
  "${PYTHON_BIN}" "${OUTDOOR_ARGS[@]}"
fi

mkdir -p "${OUTPUT_PATH}"
AGENT_LOG_TMP="$(mktemp)"
AGENT_ARGS=(
  -m cityg agent-build
  --requirement "${INSTRUCTION}"
  --output "${OUTPUT_PATH}"
  --base-url "${LLM_BASE_URL}"
  --model "${LLM_MODEL}"
  --timeout "${MODEL_TIMEOUT}"
  --max-tokens "${MODEL_MAX_TOKENS}"
  --model-seed "${MODEL_SEED}"
  --max-attempts "${MAX_ATTEMPTS:-3}"
  --max-calls-per-agent "${MAX_CALLS_PER_AGENT:-4}"
  --max-building-floor-calls "${MAX_BUILDING_FLOOR_CALLS:-12}"
  --interior-building-limit "${INTERIOR_BUILDING_LIMIT:-0}"
  --interior-floor-limit "${INTERIOR_FLOOR_LIMIT:-2}"
  --max-streetscape-calls "${MAX_STREETSCAPE_CALLS:-3}"
  --max-repair-rounds "${MAX_REPAIR_ROUNDS:-3}"
  --max-total-model-calls "${MAX_TOTAL_MODEL_CALLS:-48}"
  --max-total-tokens "${MAX_TOTAL_TOKENS:-0}"
  --max-touched-entities "${MAX_TOUCHED_ENTITIES:-48}"
  --max-wall-time "${MAX_WALL_TIME:-1200}"
  --backend "${BACKEND:-openusd}"
  --asset-registry "${ASSET_REGISTRY}"
)

if ! is_true "${BUILDING_FLOOR_AGENT_ENABLED:-true}"; then
  AGENT_ARGS+=(--disable-building-floor-agent)
fi
if [[ -n "${PROTOTYPE_CONFIG:-}" ]]; then
  [[ -f "${PROTOTYPE_CONFIG}" ]] || die "prototype config not found: ${PROTOTYPE_CONFIG}"
  AGENT_ARGS+=(--prototype-config "${PROTOTYPE_CONFIG}")
fi
if ! is_true "${STREETSCAPE_AGENT_ENABLED:-true}"; then
  AGENT_ARGS+=(--disable-streetscape-agent)
fi
if ! is_true "${INCLUDE_INTERIORS:-true}"; then
  AGENT_ARGS+=(--no-interiors)
  echo "[cityg] city-scale mode: interior geometry compilation disabled"
fi

if [[ -n "${MATERIAL_LIBRARY:-}" && -f "${MATERIAL_LIBRARY}" ]]; then
  AGENT_ARGS+=(--material-library "${MATERIAL_LIBRARY}")
fi
if is_true "${FACADE_ASSET_SYSTEM_ENABLED:-true}"; then
  if [[ -f "${FACADE_ASSET_INDEX}" ]]; then
    AGENT_ARGS+=(--facade-asset-index "${FACADE_ASSET_INDEX}")
    echo "[cityg] facade assets: enabled from ${FACADE_ASSET_INDEX}"
  else
    echo "[cityg] WARNING: facade asset index missing; using procedural facade grammar" >&2
  fi
fi

if is_true "${MEMORY_ENABLED:-false}"; then
  AGENT_ARGS+=(--memory-store "${OUTPUT_PATH}.memory.sqlite")
fi
if is_true "${INCLUDE_INTERIORS:-true}" && [[ "${HERO_ROOM_REFINEMENTS:-0}" =~ ^[0-9]+$ ]] && [[ "${HERO_ROOM_REFINEMENTS:-0}" -gt 0 ]]; then
  AGENT_ARGS+=(--adaptive-room-refinements "${HERO_ROOM_REFINEMENTS}")
fi
if is_true "${ASSET_GENERATION_ENABLED:-false}" && is_true "${ASSET_AVAILABLE}"; then
  AGENT_ARGS+=(
    --generate-missing-assets
    --asset-url "${ASSET_URL}"
    --asset-timeout "${ASSET_TIMEOUT:-1800}"
    --max-generated-assets "${MAX_GENERATED_ASSETS:-8}"
  )
  if ! is_true "${ASSET_TEXTURE:-true}"; then
    AGENT_ARGS+=(--no-asset-texture)
  fi
fi

echo "[cityg] stage 1/2: LLM planning, deterministic compilation and validation"
set +e
run_logged "${AGENT_LOG_TMP}" "${PYTHON_BIN}" -u "${AGENT_ARGS[@]}"
AGENT_RC="$?"
set -e
mkdir -p "${OUTPUT_PATH}/logs"
mv "${AGENT_LOG_TMP}" "${OUTPUT_PATH}/logs/agent_build.log"
if [[ "${AGENT_RC}" -ne 0 && "${AGENT_RC}" -ne 3 ]]; then
  cat "${OUTPUT_PATH}/logs/agent_build.log" >&2
  die "agent-build failed with exit code ${AGENT_RC}"
fi
if [[ "${AGENT_RC}" -eq 3 ]]; then
  echo "[cityg] WARNING: partial furnishing coverage; retaining scene and continuing visual review" >&2
fi

SCENE_PATH="${OUTPUT_PATH}/final/openusd"
[[ -f "${SCENE_PATH}/city.json" ]] || die "agent-build did not produce ${SCENE_PATH}/city.json"

REVIEW_PATH="${OUTPUT_PATH}/${REVIEW_SUBDIR}"
echo "[cityg] stage 2/2: adaptive screenshots, VLM review, local refinement and recheck"
REVIEW_ARGS=(
  -m cityg adaptive-review
  "${SCENE_PATH}"
  --output "${REVIEW_PATH}"
  --base-url "${VLM_BASE_URL}"
  --model "${VLM_MODEL}"
  --timeout "${MODEL_TIMEOUT}"
  --max-tokens "${MODEL_MAX_TOKENS}"
  --viewer-port "${VIEWER_PORT:-0}"
  --asset-load-timeout "${REVIEW_ASSET_LOAD_TIMEOUT:-180}"
  --max-views "${REVIEW_MAX_VIEWS:-8}"
  --max-building-refinements "${REVIEW_MAX_BUILDING_REFINEMENTS:-1}"
  --max-room-refinements "$(is_true "${INCLUDE_INTERIORS:-true}" && echo "${REVIEW_MAX_ROOM_REFINEMENTS:-1}" || echo 0)"
  --max-room-layout-refinements "$(is_true "${INCLUDE_INTERIORS:-true}" && echo "${REVIEW_MAX_ROOM_LAYOUT_REFINEMENTS:-1}" || echo 0)"
  --max-streetscape-refinements "${REVIEW_MAX_STREETSCAPE_REFINEMENTS:-2}"
  --max-archetype-candidates "${REVIEW_MAX_ARCHETYPE_CANDIDATES:-4}"
  --batch-size "${REVIEW_BATCH_SIZE:-4}"
  --seed "${REVIEW_SEED:-17}"
  --asset-registry "${ASSET_REGISTRY}"
)
if ! is_true "${REVIEW_ARCHETYPE_CONTACT_SHEETS:-true}"; then
  REVIEW_ARGS+=(--no-archetype-contact-sheets)
fi
if is_true "${MEMORY_ENABLED:-false}"; then
  REVIEW_ARGS+=(--memory-store "${OUTPUT_PATH}.memory.sqlite")
fi
if is_true "${FACADE_ASSET_SYSTEM_ENABLED:-true}" && [[ -f "${FACADE_ASSET_INDEX}" ]]; then
  REVIEW_ARGS+=(--facade-asset-index "${FACADE_ASSET_INDEX}")
fi
if is_true "${ASSET_GENERATION_ENABLED:-false}" && is_true "${ASSET_AVAILABLE}"; then
  REVIEW_ARGS+=(
    --generate-missing-assets
    --asset-url "${ASSET_URL}"
    --asset-timeout "${ASSET_TIMEOUT:-1800}"
    --max-generated-assets "${REVIEW_MAX_GENERATED_ASSETS:-4}"
  )
  if ! is_true "${ASSET_TEXTURE:-true}"; then
    REVIEW_ARGS+=(--no-asset-texture)
  fi
fi
set +e
run_logged "${OUTPUT_PATH}/logs/adaptive_review.log" "${PYTHON_BIN}" -u "${REVIEW_ARGS[@]}"
REVIEW_RC="$?"
set -e
if [[ "${REVIEW_RC}" -ne 0 ]]; then
  cat "${OUTPUT_PATH}/logs/adaptive_review.log" >&2
  die "adaptive-review failed with exit code ${REVIEW_RC}"
fi

REPORT_PATH="${REVIEW_PATH}/adaptive_review_report.json"
PIPELINE_RC="${AGENT_RC}"
if [[ -f "${REPORT_PATH}" ]]; then
  if "${PYTHON_BIN}" - "${REPORT_PATH}" "${AGENT_RC}" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
review = data.get("review", {})
print("[cityg] aggregated issues:", len(review.get("aggregated_issues", [])))
print("[cityg] post-review issues:", len(data.get("review_after", {}).get("aggregated_issues", [])))
print("[cityg] touched entities:", ", ".join(data.get("touched_entity_ids", [])) or "none")
print("[cityg] before/after images:", len(data.get("before_images", [])), "/", len(data.get("after_images", [])))
comparisons = data.get("traces", {}).get("building_visual_comparison", [])
print("[cityg] building contact sheets:", len(comparisons),
      "ranked:", sum(bool(item.get("available")) for item in comparisons))
assets = data.get("asset_resolver") or {}
print("[cityg] generated room assets:", assets.get("generated_assets", 0))
coverage = data.get("furnishing_coverage")
if coverage is None:
    sys.exit(int(sys.argv[2]))
print("[cityg] post-review verified furnishing:", coverage["verified_rooms"], "/", coverage["target_rooms"])
sys.exit(0 if coverage["target_met"] else 3)
PY
  then
    PIPELINE_RC=0
  else
    PIPELINE_RC=$?
  fi
fi

if [[ -f "${ASSET_LOG_TMP}" ]]; then
  cp "${ASSET_LOG_TMP}" "${OUTPUT_PATH}/logs/${ASSET_WORKER_LOG:-asset_worker.log}" || true
fi
cat <<EOF
[cityg] pipeline stages finished (agent-build: ${AGENT_RC}, pipeline: ${PIPELINE_RC}; 3 means partial furnishing coverage)
[cityg] base run: ${OUTPUT_PATH}/final
[cityg] visual review: ${REVIEW_PATH}
[cityg] report: ${REPORT_PATH}
[cityg] portable viewer: ${REVIEW_PATH}/viewer_after
EOF
exit "${PIPELINE_RC}"
