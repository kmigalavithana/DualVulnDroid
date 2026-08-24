"""
PHASE RESEARCH-EVAL-1, Part 15/Q: consolidates the reproducibility record
required by the spec (Python/scikit-learn/XGBoost versions, dataset size,
feature dimensions, random seed, hyperparameters per model) from the
artifacts already written by the other research_eval scripts. Run this
LAST, after data_split.py, features.py, and all three train_*.py scripts.

Run from backend/:  python -m research_eval.reproducibility
"""

import json
import os
import platform
import sys

import sklearn
import xgboost

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_eval.data_split import ARTIFACT_DIR

MODEL_DIRS = {"linear_svm": "svm", "random_forest": "random_forest", "xgboost": "xgboost"}


def main():
    with open(os.path.join(ARTIFACT_DIR, "split_metadata.json")) as f:
        split_meta = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "shared_features", "feature_metadata.json")) as f:
        feature_meta = json.load(f)

    model_hyperparams = {}
    for name, dirname in MODEL_DIRS.items():
        meta_path = os.path.join(ARTIFACT_DIR, dirname, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                model_hyperparams[name] = json.load(f)["final_hyperparameters"]

    info = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "scikit_learn_version": sklearn.__version__,
        "xgboost_version": xgboost.__version__,
        "random_seed": split_meta["random_seed"],
        "dataset": {
            "raw_row_count": split_meta["raw_row_count"],
            "excluded_conflicting_label_rows": split_meta["excluded_conflicting_label_rows"],
            "clean_row_count": split_meta["clean_row_count"],
            "split_sizes": split_meta["split_sizes"],
        },
        "feature_dimensions": {
            "total": feature_meta["total_feature_dims"],
            "text": feature_meta["text_feature_dims"],
            "security": feature_meta["security_feature_dims"],
        },
        "final_hyperparameters_per_model": model_hyperparams,
    }

    with open(os.path.join(ARTIFACT_DIR, "reproducibility_info.json"), "w") as f:
        json.dump(info, f, indent=2)

    print(json.dumps(info, indent=2))
    return info


if __name__ == "__main__":
    main()
