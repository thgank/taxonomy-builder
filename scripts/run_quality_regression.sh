#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
API_KEY="${API_KEY:-dev-api-key-change-me}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-2}"
POLL_MAX_ATTEMPTS="${POLL_MAX_ATTEMPTS:-240}"
BASELINE_TAXONOMY_ID="${BASELINE_TAXONOMY_ID:-}"

COLLECTION_NAME="${COLLECTION_NAME:-quality-regression-$(date +%Y%m%d-%H%M%S)}"

DEFAULT_FILES=(
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/78ba6dab-7b3a-4f19-aea9-70a5d20d4992/A_grid_systems_long.txt"
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/12a6b740-e3b7-48eb-bab9-3fd2fcf809fb/B_market_operations_long.txt"
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/acd3aa8d-1327-41fd-9c7e-efd49d551ad9/C_renewables_long.txt"
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/a8d00309-bbb4-40dc-b515-da8d6a02915b/D_quality_storage_long.txt"
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/e7c593a9-79ad-4d6c-b1f4-8edfa60fcab0/10_energy_storage.txt"
)

if [ "$#" -gt 0 ]; then
  FILES=("$@")
else
  FILES=("${DEFAULT_FILES[@]}")
fi

for f in "${FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "Missing file: $f" >&2
    exit 1
  fi
done

if ! curl -fsS "$BASE_URL/actuator/health" >/dev/null 2>&1; then
  echo "API is not reachable at $BASE_URL. Start api-service first." >&2
  exit 1
fi

create_payload=$(printf '{"name":"%s","description":"post-fix quality regression run"}' "$COLLECTION_NAME")
create_resp="$(curl -fsS -X POST "$BASE_URL/api/collections" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "$create_payload")"

COLLECTION_ID="$(python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])' <<<"$create_resp")"
echo "Collection: $COLLECTION_ID"

upload_cmd=(curl -fsS -X POST "$BASE_URL/api/collections/$COLLECTION_ID/documents:upload" -H "X-API-Key: $API_KEY")
for f in "${FILES[@]}"; do
  upload_cmd+=(-F "files=@$f")
done
"${upload_cmd[@]}" >/tmp/taxonomy_upload_resp.json
echo "Uploaded files: ${#FILES[@]}"

JOB_PAYLOAD='{
  "type":"FULL_PIPELINE",
  "params":{
    "method_term_extraction":"both",
    "method_taxonomy":"hybrid",
    "max_terms":220,
    "min_freq":2,
    "min_doc_freq":2,
    "min_term_quality_score":0.40,
    "min_parent_doc_freq":3,
    "similarity_threshold":0.58
  }
}'

job_resp="$(curl -fsS -X POST "$BASE_URL/api/collections/$COLLECTION_ID/jobs" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "$JOB_PAYLOAD")"

JOB_ID="$(python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])' <<<"$job_resp")"
TAXONOMY_ID="$(python3 -c 'import sys,json; print(json.load(sys.stdin)["taxonomyVersionId"])' <<<"$job_resp")"
echo "Job: $JOB_ID"
echo "Taxonomy: $TAXONOMY_ID"

final_status=""
for i in $(seq 1 "$POLL_MAX_ATTEMPTS"); do
  sleep "$POLL_INTERVAL_SEC"
  job_json="$(curl -fsS "$BASE_URL/api/jobs/$JOB_ID" -H "X-API-Key: $API_KEY")"
  read -r status progress < <(python3 -c 'import sys,json; j=json.load(sys.stdin); print(j["status"], j.get("progress", 0))' <<<"$job_json")
  echo "[$i/$POLL_MAX_ATTEMPTS] status=$status progress=$progress"
  final_status="$status"
  if [ "$status" = "SUCCESS" ] || [ "$status" = "FAILED" ] || [ "$status" = "CANCELLED" ]; then
    break
  fi
done

if [ "$final_status" != "SUCCESS" ]; then
  echo "Job ended with status: $final_status" >&2
  curl -fsS "$BASE_URL/api/jobs/$JOB_ID/events" -H "X-API-Key: $API_KEY" > /tmp/taxonomy_job_events_failed.json
  echo "Saved events: /tmp/taxonomy_job_events_failed.json" >&2
  exit 1
fi

curl -fsS "$BASE_URL/api/jobs/$JOB_ID/events" -H "X-API-Key: $API_KEY" > /tmp/taxonomy_job_events.json
curl -fsS "$BASE_URL/api/taxonomies/$TAXONOMY_ID/export?format=json&include_orphans=true" -H "X-API-Key: $API_KEY" > /tmp/taxonomy_export_current.json
curl -fsS "$BASE_URL/api/taxonomies/$TAXONOMY_ID" -H "X-API-Key: $API_KEY" > /tmp/taxonomy_version_current.json

python3 - <<'PY'
import json
from pathlib import Path

version = json.loads(Path("/tmp/taxonomy_version_current.json").read_text())
metrics = (version.get("qualityMetrics") or {})
structural = metrics.get("structural") or {}
edge_conf = metrics.get("edge_confidence") or {}
connectivity = metrics.get("graph_connectivity") or {}
risk = metrics.get("risk") or {}
cur = {
    "total_nodes": structural.get("total_concepts"),
    "high_quality_nodes": structural.get("high_quality_concepts"),
    "candidate_concepts": structural.get("candidate_concepts"),
    "edge_count": version.get("edgeCount"),
    "coverage": structural.get("coverage"),
    "coverage_high_quality": structural.get("coverage_high_quality"),
    "coverage_candidate_set": structural.get("coverage_candidate_set"),
    "avg_edge_score": edge_conf.get("avg_score"),
    "largest_component_ratio": (connectivity.get("all_concepts") or {}).get("largest_component_ratio"),
    "hubness": (connectivity.get("all_concepts") or {}).get("hubness"),
    "component_count": structural.get("component_count"),
    "fragmentation_index": structural.get("fragmentation_index"),
    "low_score_edges": risk.get("low_score_edge_count"),
    "low_score_edge_ratio": risk.get("low_score_edge_ratio"),
    "orientation_risk": risk.get("orientation_risk_count"),
    "manual_disagreement_rate": (metrics.get("manual_review") or {}).get("manual_disagreement_rate"),
    "cross_lang_consistency": (metrics.get("cross_lang_consistency") or {}).get("cross_lang_consistency"),
    "quality_score_10": metrics.get("quality_score_10"),
}
print("=== Current Run Metrics ===")
print(json.dumps(cur, indent=2))
print("=== By-Language Graph Connectivity ===")
print(json.dumps(connectivity.get("by_language") or {}, indent=2))
PY

echo "=== Last Events (tail) ==="
python3 - <<'PY'
import json
events = json.load(open("/tmp/taxonomy_job_events.json"))
for e in events[-10:]:
    print(f'[{e.get("level","?")}] {e.get("message","")}')
PY

if [ -n "$BASELINE_TAXONOMY_ID" ]; then
  curl -fsS "$BASE_URL/api/taxonomies/$BASELINE_TAXONOMY_ID" -H "X-API-Key: $API_KEY" > /tmp/taxonomy_version_baseline.json
  python3 - <<'PY'
import json
from pathlib import Path

def m(path: Path):
    d = json.loads(path.read_text())
    qm = (d.get("qualityMetrics") or {})
    structural = qm.get("structural") or {}
    edge_conf = qm.get("edge_confidence") or {}
    return {
        "coverage": structural.get("coverage") or 0.0,
        "coverage_high_quality": structural.get("coverage_high_quality") or 0.0,
        "coverage_candidate_set": structural.get("coverage_candidate_set") or 0.0,
        "edge_count": d.get("edgeCount") or 0.0,
        "avg_edge_score": edge_conf.get("avg_score") or 0.0,
        "largest_component_ratio": ((qm.get("graph_connectivity") or {}).get("all_concepts") or {}).get("largest_component_ratio") or 0.0,
        "fragmentation_index": (qm.get("risk") or {}).get("fragmentation_index") or 0.0,
        "low_score_edge_ratio": (qm.get("risk") or {}).get("low_score_edge_ratio") or 0.0,
        "manual_disagreement_rate": (qm.get("manual_review") or {}).get("manual_disagreement_rate") or 0.0,
        "cross_lang_consistency": (qm.get("cross_lang_consistency") or {}).get("cross_lang_consistency") or 0.0,
        "quality_score_10": qm.get("quality_score_10") or 0.0,
    }
cur = m(Path("/tmp/taxonomy_version_current.json"))
base = m(Path("/tmp/taxonomy_version_baseline.json"))
print("=== Baseline Delta (current - baseline) ===")
for k in (
    "coverage",
    "coverage_high_quality",
    "coverage_candidate_set",
    "edge_count",
    "avg_edge_score",
    "largest_component_ratio",
    "fragmentation_index",
    "low_score_edge_ratio",
    "manual_disagreement_rate",
    "cross_lang_consistency",
    "quality_score_10",
):
    print(f"{k}: {cur[k]:.6f} - {base[k]:.6f} = {cur[k]-base[k]:+.6f}")
PY
fi

echo "Artifacts:"
echo "  /tmp/taxonomy_upload_resp.json"
echo "  /tmp/taxonomy_job_events.json"
echo "  /tmp/taxonomy_export_current.json"
echo "  /tmp/taxonomy_version_current.json"
