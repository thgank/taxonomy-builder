#!/usr/bin/env bash
set -euo pipefail

DATABASE_URL="${DATABASE_URL:-}"
PROFILE_NAME="${PROFILE_NAME:-default}"
COLLECTION_ID="${COLLECTION_ID:-}"
MIN_SAMPLES="${MIN_SAMPLES:-50}"
MAX_STEP="${MAX_STEP:-0.03}"

if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi

python3 - "$DATABASE_URL" "$PROFILE_NAME" "$COLLECTION_ID" "$MIN_SAMPLES" "$MAX_STEP" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

database_url, profile_name, collection_id, min_samples, max_step = sys.argv[1:]
min_samples = int(min_samples)
max_step = float(max_step)
collection_id = collection_id or None

engine = create_engine(database_url)

if collection_id:
    scope_filter = "c.collection_id = :collection_id"
    params = {"collection_id": collection_id, "min_samples": min_samples}
else:
    scope_filter = "c.collection_id IS NULL OR c.collection_id IS NOT NULL"
    params = {"min_samples": min_samples}

q = text(
    f"""
    SELECT
        c.method,
        COALESCE(NULLIF(c.lang, ''), 'unknown') AS lang,
        c.final_score,
        CASE
            WHEN lower(l.label) IN ('accepted', 'approve', 'approved', 'true') THEN 1
            WHEN lower(l.label) IN ('rejected', 'reject', 'false') THEN 0
            ELSE NULL
        END AS y
    FROM taxonomy_edge_candidates c
    JOIN taxonomy_edge_labels l ON l.candidate_id = c.id
    WHERE {scope_filter}
      AND l.label IS NOT NULL
    """
)

with engine.connect() as conn:
    rows = conn.execute(q, params).mappings().all()

bucket: dict[tuple[str, str], dict[str, list[float]]] = {}
for row in rows:
    y = row["y"]
    if y is None:
        continue
    key = (str(row["lang"]), str(row["method"]))
    rec = bucket.setdefault(key, {"pos": [], "neg": []})
    if int(y) == 1:
        rec["pos"].append(float(row["final_score"] or 0.0))
    else:
        rec["neg"].append(float(row["final_score"] or 0.0))


def median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    n = len(ys)
    if n % 2 == 1:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2.0


lang_method_thresholds: dict[str, dict[str, float]] = {}
support: dict[str, int] = {}
for (lang, method), rec in bucket.items():
    pos = rec["pos"]
    neg = rec["neg"]
    n = len(pos) + len(neg)
    if n < min_samples or len(pos) < 5 or len(neg) < 5:
        continue
    tau = max(0.45, min(0.90, (median(pos) + median(neg)) / 2.0))
    lang_method_thresholds.setdefault(lang, {})[method] = round(tau, 4)
    support[f"{lang}:{method}"] = n

if not lang_method_thresholds:
    raise SystemExit("No groups with enough labels to recompute thresholds")

profile = {
    "lang_method_thresholds": lang_method_thresholds,
    "min_edge_accept_score": 0.64,
}
metrics = {
    "support": support,
    "min_samples": min_samples,
    "max_step": max_step,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

deactivate_sql = text(
    """
    UPDATE taxonomy_threshold_profiles
    SET is_active = false, updated_at = now()
    WHERE name = :name
      AND (:collection_id::uuid IS NULL OR collection_id = :collection_id::uuid)
      AND is_active = true
    """
)

insert_sql = text(
    """
    INSERT INTO taxonomy_threshold_profiles (
        id, collection_id, name, is_active, min_samples, profile, metrics, created_at, updated_at
    ) VALUES (
        uuid_generate_v4(), :collection_id::uuid, :name, true, :min_samples, :profile::jsonb, :metrics::jsonb, now(), now()
    )
    """
)

with engine.begin() as conn:
    conn.execute(deactivate_sql, {"name": profile_name, "collection_id": collection_id})
    conn.execute(
        insert_sql,
        {
            "collection_id": collection_id,
            "name": profile_name,
            "min_samples": min_samples,
            "profile": json.dumps(profile),
            "metrics": json.dumps(metrics),
        },
    )

print(json.dumps({"profile_name": profile_name, "collection_id": collection_id, "groups": len(support)}, indent=2))
PY
