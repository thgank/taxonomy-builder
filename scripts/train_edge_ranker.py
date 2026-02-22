#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sqlalchemy import create_engine, text


DEFAULT_FEATURES = [
    "base_score",
    "semantic_similarity",
    "lexical_similarity",
    "cooccurrence_support",
    "parent_validity",
    "parent_doc_freq",
    "child_doc_freq",
    "df_gap",
    "token_len_gap",
    "projected_parent_outdegree",
]


def _load_labeled_rows(engine, limit: int) -> list[dict]:
    query = text(
        """
        WITH manual AS (
            SELECT
                c.id AS candidate_id,
                c.feature_vector,
                c.final_score,
                c.method,
                c.lang,
                CASE
                    WHEN lower(l.label) IN ('accepted', 'approve', 'approved', 'true') THEN 1
                    WHEN lower(l.label) IN ('rejected', 'reject', 'false') THEN 0
                    ELSE NULL
                END AS y,
                1.0 AS label_weight
            FROM taxonomy_edge_candidates c
            JOIN taxonomy_edge_labels l ON l.candidate_id = c.id
            WHERE l.label IS NOT NULL
        ),
        weak AS (
            SELECT
                c.id AS candidate_id,
                c.feature_vector,
                c.final_score,
                c.method,
                c.lang,
                CASE
                    WHEN c.decision = 'accepted' AND c.final_score >= 0.82 THEN 1
                    WHEN c.decision = 'rejected' AND c.final_score <= 0.52 THEN 0
                    ELSE NULL
                END AS y,
                0.45 AS label_weight
            FROM taxonomy_edge_candidates c
            WHERE c.decision IN ('accepted', 'rejected')
        )
        SELECT *
        FROM (
            SELECT * FROM manual
            UNION ALL
            SELECT * FROM weak
        ) q
        WHERE y IS NOT NULL
        ORDER BY random()
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()
    out = []
    for row in rows:
        fv = row["feature_vector"] or {}
        if isinstance(fv, str):
            try:
                fv = json.loads(fv)
            except Exception:
                fv = {}
        out.append(
            {
                "features": fv,
                "y": int(row["y"]),
                "weight": float(row["label_weight"] or 1.0),
            }
        )
    return out


def _to_matrix(rows: list[dict], feature_names: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = []
    y = []
    w = []
    for row in rows:
        fv = row["features"] or {}
        x.append([float(fv.get(name, 0.0) or 0.0) for name in feature_names])
        y.append(int(row["y"]))
        w.append(float(row["weight"]))
    return np.asarray(x, dtype=float), np.asarray(y, dtype=int), np.asarray(w, dtype=float)


def _build_model():
    try:
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            n_estimators=240,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=20,
            random_state=42,
        ), "lightgbm"
    except Exception:
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_leaf_nodes=31,
            max_iter=240,
            random_state=42,
        ), "sklearn_hgb"


def main() -> int:
    parser = argparse.ArgumentParser(description="Train edge ranker from candidate/label history.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--output", default="data/models/edge_ranker.joblib")
    parser.add_argument("--max-samples", type=int, default=250000)
    parser.add_argument("--min-samples", type=int, default=800)
    parser.add_argument("--feature-list", default=",".join(DEFAULT_FEATURES))
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required")

    feature_names = [x.strip() for x in args.feature_list.split(",") if x.strip()]
    engine = create_engine(args.database_url)
    rows = _load_labeled_rows(engine, args.max_samples)
    if len(rows) < args.min_samples:
        raise SystemExit(f"Not enough training samples: {len(rows)} < {args.min_samples}")

    x, y, w = _to_matrix(rows, feature_names)
    pos = int((y == 1).sum())
    neg = int((y == 0).sum())
    if pos == 0 or neg == 0:
        raise SystemExit("Training needs both positive and negative labels")

    model, model_name = _build_model()
    model.fit(x, y, sample_weight=w)

    metadata = {
        "model_name": model_name,
        "feature_names": feature_names,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "samples": int(len(rows)),
        "positives": pos,
        "negatives": neg,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_name_": feature_names,
            "metadata": metadata,
        },
        out_path,
    )
    print(json.dumps(metadata, indent=2))
    print(f"Saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
