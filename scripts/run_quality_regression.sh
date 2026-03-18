#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
API_KEY="${API_KEY:-dev-api-key-change-me}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-2}"
POLL_MAX_ATTEMPTS="${POLL_MAX_ATTEMPTS:-240}"
BASELINE_TAXONOMY_ID="${BASELINE_TAXONOMY_ID:-}"
SAVE_REPORT="${SAVE_REPORT:-false}"
REPORT_DIR="${REPORT_DIR:-}"

COLLECTION_NAME="${COLLECTION_NAME:-quality-regression-$(date +%Y%m%d-%H%M%S)}"

DEFAULT_FILES=(
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/78ba6dab-7b3a-4f19-aea9-70a5d20d4992/A_grid_systems_long.txt"
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/12a6b740-e3b7-48eb-bab9-3fd2fcf809fb/B_market_operations_long.txt"
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/acd3aa8d-1327-41fd-9c7e-efd49d551ad9/C_renewables_long.txt"
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/a8d00309-bbb4-40dc-b515-da8d6a02915b/D_quality_storage_long.txt"
  "data/uploads/174016a9-2a7a-4ab4-9bfd-9273aa1aa247/e7c593a9-79ad-4d6c-b1f4-8edfa60fcab0/10_energy_storage.txt"
)

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_quality_regression.sh [--save-report] [--report-dir <path>] [file1 file2 ...]

Options:
  --save-report        Save detailed run artifacts + generated relations files
  --report-dir <path>  Output directory for saved report (default: reports/quality_runs/<collection_name>)
  -h, --help           Show this help

Env alternatives:
  SAVE_REPORT=true
  REPORT_DIR=reports/quality_runs/my_run
EOF
}

FILES=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --save-report)
      SAVE_REPORT=true
      shift
      ;;
    --report-dir)
      if [ "$#" -lt 2 ]; then
        echo "--report-dir requires a path" >&2
        exit 1
      fi
      REPORT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [ "$#" -gt 0 ]; do
        FILES+=("$1")
        shift
      done
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      FILES+=("$1")
      shift
      ;;
  esac
done

if [ "${#FILES[@]}" -eq 0 ]; then
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

printf '%s\n' "$job_json" > /tmp/taxonomy_job_current.json

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

save_report_lc="$(printf '%s' "$SAVE_REPORT" | tr '[:upper:]' '[:lower:]')"
if [ "$save_report_lc" = "true" ]; then
  if [ -z "$REPORT_DIR" ]; then
    REPORT_DIR="reports/quality_runs/$COLLECTION_NAME"
  fi
  export REPORT_DIR
  mkdir -p "$REPORT_DIR"
  cp /tmp/taxonomy_upload_resp.json "$REPORT_DIR/taxonomy_upload_resp.json"
  cp /tmp/taxonomy_job_current.json "$REPORT_DIR/taxonomy_job_current.json"
  cp /tmp/taxonomy_job_events.json "$REPORT_DIR/taxonomy_job_events.json"
  cp /tmp/taxonomy_export_current.json "$REPORT_DIR/taxonomy_export_current.json"
  cp /tmp/taxonomy_version_current.json "$REPORT_DIR/taxonomy_version_current.json"
  if [ -f /tmp/taxonomy_version_baseline.json ]; then
    cp /tmp/taxonomy_version_baseline.json "$REPORT_DIR/taxonomy_version_baseline.json"
  fi

  python3 - <<'PY'
import csv
import json
import os
from pathlib import Path

report_dir = Path(os.environ["REPORT_DIR"])
version_path = report_dir / "taxonomy_version_current.json"
export_path = report_dir / "taxonomy_export_current.json"
events_path = report_dir / "taxonomy_job_events.json"
version = json.loads(version_path.read_text())
export = json.loads(export_path.read_text())
events = json.loads(events_path.read_text())
quality = (version.get("qualityMetrics") or {})
structural = quality.get("structural") or {}
risk = quality.get("risk") or {}
connectivity = quality.get("graph_connectivity") or {}
summary = {
    "collection_id": export.get("collectionId"),
    "taxonomy_version_id": export.get("taxonomyVersionId"),
    "quality_score_10": quality.get("quality_score_10"),
    "coverage": structural.get("coverage"),
    "coverage_candidate_set": structural.get("coverage_candidate_set"),
    "largest_component_ratio": (connectivity.get("all_concepts") or {}).get("largest_component_ratio"),
    "component_count": risk.get("component_count"),
    "fragmentation_index": risk.get("fragmentation_index"),
    "low_score_edge_ratio": risk.get("low_score_edge_ratio"),
    "low_score_edge_count": risk.get("low_score_edge_count"),
    "edge_count": version.get("edgeCount"),
    "event_count": len(events),
}
(report_dir / "processing_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

nodes = export.get("nodes") or []
node_label = {str(n.get("id")): str(n.get("label", "")) for n in nodes}
edges = export.get("edges") or []
edge_rows = []
for edge in edges:
    parent = node_label.get(str(edge.get("parent")), str(edge.get("parent")))
    child = node_label.get(str(edge.get("child")), str(edge.get("child")))
    score = float(edge.get("score", 0.0) or 0.0)
    evidence = edge.get("evidence") or {}
    if isinstance(evidence, list):
        evidence = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
    if not isinstance(evidence, dict):
        evidence = {}
    method = str(evidence.get("method", "unknown"))
    sem = float(evidence.get("semantic_similarity", 0.0) or 0.0)
    lex = float(evidence.get("lexical_similarity", 0.0) or 0.0)
    cooc = float(evidence.get("cooccurrence_support", 0.0) or 0.0)
    snippets = evidence.get("retrieval_snippets") or []
    snippet = ""
    if snippets and isinstance(snippets, list) and isinstance(snippets[0], dict):
        snippet = str(snippets[0].get("snippet", "")).replace("\n", " ").strip()
    edge_rows.append({
        "parent": parent,
        "child": child,
        "score": round(score, 4),
        "method": method,
        "semantic_similarity": round(sem, 4),
        "lexical_similarity": round(lex, 4),
        "cooccurrence_support": round(cooc, 4),
        "snippet": snippet[:500],
    })

edge_rows.sort(key=lambda x: x["score"], reverse=True)

with (report_dir / "relations.tsv").open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(
        f,
        fieldnames=[
            "parent",
            "child",
            "score",
            "method",
            "semantic_similarity",
            "lexical_similarity",
            "cooccurrence_support",
            "snippet",
        ],
        delimiter="\t",
    )
    w.writeheader()
    w.writerows(edge_rows)

lines = []
lines.append("# Built Relations")
lines.append("")
lines.append(f"- taxonomy_version_id: `{export.get('taxonomyVersionId')}`")
lines.append(f"- collection_id: `{export.get('collectionId')}`")
lines.append(f"- total_edges: **{len(edge_rows)}**")
lines.append("")
for i, row in enumerate(edge_rows, start=1):
    lines.append(
        f"{i}. `{row['parent']}` -> `{row['child']}` "
        f"(score={row['score']:.4f}, method={row['method']})"
    )
    if row["snippet"]:
        lines.append(f"   snippet: {row['snippet']}")

(report_dir / "relations.md").write_text("\n".join(lines), encoding="utf-8")
PY
  echo "Saved detailed report: $REPORT_DIR"
  echo "  - $REPORT_DIR/processing_summary.json"
  echo "  - $REPORT_DIR/relations.md"
  echo "  - $REPORT_DIR/relations.tsv"
fi

echo "Artifacts:"
echo "  /tmp/taxonomy_upload_resp.json"
echo "  /tmp/taxonomy_job_current.json"
echo "  /tmp/taxonomy_job_events.json"
echo "  /tmp/taxonomy_export_current.json"
echo "  /tmp/taxonomy_version_current.json"
