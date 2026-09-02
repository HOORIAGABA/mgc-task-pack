"""
MGC Leads — baseline conversion model.

Data decisions (see README for full rationale):
  DROPPED (post-creation / leaky):
    lead_id, crm_record_hash,
    calls_made, total_call_seconds, whatsapp_replies,
    site_visits, token_amount_received_pkr
  DROPPED (high null / low signal):
    bedrooms (39.3% null), area (5.2% null, high cardinality)
  KEPT:
    source, city, property_type, budget_pkr_lac,
    is_overseas, referred_by_existing_client, has_financing_approved,
    agent_experience_years, first_response_minutes

Metric: recall — with 6.9% conversion rate, missing a convertible lead
is far costlier than a false alarm.
"""

import csv
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------- load ----------
def load(path=None):
    if path is None:
        path = _DATA_DIR / "leads.csv"
    return list(csv.DictReader(open(path, encoding="utf-8")))

# ---------- clean ----------
CAT_COLS = ["source", "city", "property_type"]
BOOL_COLS = ["is_overseas", "referred_by_existing_client", "has_financing_approved"]
NUM_COLS = ["budget_pkr_lac", "agent_experience_years", "first_response_minutes"]

def clean(rows):
    for r in rows:
        r["city"] = r["city"].strip().lower().title() if r["city"] else "unknown"
        r["source"] = r["source"].strip() if r["source"] else "unknown"
        r["property_type"] = r["property_type"].strip() if r["property_type"] else "unknown"

    for c in NUM_COLS:
        vals = sorted([float(r[c]) for r in rows if r[c]])
        med = vals[len(vals) // 2]
        for r in rows:
            r[c] = float(r[c]) if r[c] else med

    for c in BOOL_COLS:
        for r in rows:
            r[c] = int(r[c]) if r[c] else 0

    return rows

# ---------- feature matrix ----------
def build_features(rows):
    cat_values = defaultdict(set)
    for r in rows:
        for c in CAT_COLS:
            cat_values[c].add(r[c])
    cat_values = {c: sorted(v) for c, v in cat_values.items()}

    def row_to_vec(r):
        vec = []
        for c in CAT_COLS:
            for v in cat_values[c]:
                vec.append(1 if r[c] == v else 0)
        vec.extend([r[c] for c in BOOL_COLS])
        vec.extend([r[c] for c in NUM_COLS])
        return vec

    X = np.array([row_to_vec(r) for r in rows], dtype=float)
    y = np.array([int(r["converted"]) for r in rows])
    return X, y, cat_values

# ---------- train ----------
def train_model():
    """Train on full CSV, return (model, scaler, cat_values, medians)."""
    rows = load()
    rows = clean(rows)

    medians = {}
    for c in NUM_COLS:
        vals = sorted([float(r[c]) for r in rows])
        medians[c] = vals[len(vals) // 2]

    X, y, cat_values = build_features(rows)
    scaler = StandardScaler()
    X_s = scaler.fit_transform(X)

    lr = LogisticRegression(max_iter=500, C=1.0, class_weight="balanced", random_state=42)
    lr.fit(X_s, y)

    return lr, scaler, cat_values, medians

# ---------- main ----------
def main():
    rows = load()
    rows = clean(rows)
    X, y, cat_values = build_features(rows)

    rng = random.Random(42)
    idx = list(range(len(X)))
    rng.shuffle(idx)
    n = int(len(X) * 0.8)
    train_idx, test_idx = idx[:n], idx[n:]
    X_tr, X_te = X[train_idx], X[test_idx]
    y_tr, y_te = y[train_idx], y[test_idx]

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    pos = y_tr.sum()
    print(f"Train: {len(X_tr)} rows  |  Test: {len(X_te)} rows")
    print(f"Class balance (train): {int(pos)} converted ({pos*100/len(y_tr):.1f}%)\n")

    models = [
        ("Logistic Regression", LogisticRegression(
            max_iter=500, C=1.0, class_weight="balanced", random_state=42), True),
        ("Random Forest", RandomForestClassifier(
            n_estimators=100, max_depth=6, class_weight="balanced",
            random_state=42, n_jobs=-1), False),
    ]

    results = []
    for name, model, needs_scale in models:
        Xtr = X_tr_s if needs_scale else X_tr
        Xte = X_te_s if needs_scale else X_te
        model.fit(Xtr, y_tr)
        prob = model.predict_proba(Xte)[:, 1]
        pred = (prob >= 0.5).astype(int)
        results.append({
            "name": name,
            "accuracy": accuracy_score(y_te, pred),
            "precision": precision_score(y_te, pred),
            "recall": recall_score(y_te, pred),
            "f1": f1_score(y_te, pred),
            "auc": roc_auc_score(y_te, prob),
        })

    results.sort(key=lambda r: -r["recall"])

    print("=" * 72)
    print(f"{'Model':<25s} {'Acc':>6s} {'Prec':>6s} {'Recall':>7s} {'F1':>6s} {'AUC':>6s}")
    print("-" * 72)
    for r in results:
        marker = " <-- chosen" if r == results[0] else ""
        print(f"{r['name']:<25s} {r['accuracy']:>5.1%} {r['precision']:>5.1%} {r['recall']:>6.1%} {r['f1']:>5.1%} {r['auc']:>5.3f}{marker}")
    print("=" * 72)
    print(f"\nChosen metric: recall (6.9% class imbalance -> missing converts is costly)")

    # --- Feature importance from best model ---
    best_name = results[0]["name"]
    print(f"\nTop 10 features (by {best_name} coefficient):")
    lr = LogisticRegression(max_iter=500, C=1.0, class_weight="balanced", random_state=42)
    lr.fit(X_tr_s, y_tr)
    cat_names = []
    for c in CAT_COLS:
        for v in cat_values[c]:
            cat_names.append(f"{c}={v}")
    feat_names = cat_names + BOOL_COLS + NUM_COLS
    coef_pairs = sorted(zip(feat_names, lr.coef_[0]), key=lambda x: -abs(x[1]))
    for name, coef in coef_pairs[:10]:
        print(f"  {'+' if coef > 0 else '-'} {name:<45} {coef:>+7.3f}")

if __name__ == "__main__":
    main()
