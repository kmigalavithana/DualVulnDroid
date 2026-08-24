"""
PHASE RESEARCH-EVAL-5B, Part 30: consolidates the reproducibility record
from artifacts already written by codebert_train.py/codebert_evaluate.py.

Run from backend/, AFTER codebert_train.py and codebert_evaluate.py:
    python -m research_eval.codebert_reproducibility
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_eval.data_split import ARTIFACT_DIR

OUT_DIR = os.path.join(ARTIFACT_DIR, "codebert")


def _file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    with open(os.path.join(OUT_DIR, "model_config.json")) as f:
        model_config = json.load(f)
    with open(os.path.join(OUT_DIR, "training_config.json")) as f:
        training_config = json.load(f)
    with open(os.path.join(OUT_DIR, "hardware.json")) as f:
        hardware = json.load(f)
    with open(os.path.join(OUT_DIR, "tokenizer", "sequence_length.json")) as f:
        seq_meta = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "split_metadata.json")) as f:
        split_meta = json.load(f)
    with open(os.path.join(OUT_DIR, "training_history.json")) as f:
        hist = json.load(f)["selected"]

    clean_dataset_hash = _file_hash(os.path.join(ARTIFACT_DIR, "clean_dataset.csv"))
    split_hash = hashlib.sha256(
        (open(os.path.join(ARTIFACT_DIR, "train_indices.json")).read() +
         open(os.path.join(ARTIFACT_DIR, "validation_indices.json")).read() +
         open(os.path.join(ARTIFACT_DIR, "test_indices.json")).read()).encode()
    ).hexdigest()

    info = {
        "checkpoint": model_config["checkpoint"],
        "python_version": hardware["python_version"],
        "torch_version": hardware["torch_version"],
        "transformers_version": hardware["transformers_version"],
        "device": hardware["device"],
        "gpu_available": hardware["gpu_available"],
        "gpu_note": hardware["gpu_note"],
        "random_seed": model_config["random_seed"],
        "dataset_hash_sha256": clean_dataset_hash,
        "split_hash_sha256": split_hash,
        "split_sizes": split_meta["split_sizes"],
        "max_sequence_length": seq_meta["chosen_max_length"],
        "class_weight": model_config["class_weight"],
        "selected_strategy": model_config["selected_strategy"],
        "selected_epoch": hist["best_epoch"],
        "selected_validation_macro_f1": hist["best_val_macro_f1"],
        "epochs_trained": hist["epochs_trained"],
        "training_hyperparameters": training_config,
        "model_artifact_path": "research_eval_artifacts/codebert/model/",
        "tokenizer_artifact_path": "research_eval_artifacts/codebert/tokenizer/",
        "label_mapping": model_config["label_mapping"],
    }
    with open(os.path.join(OUT_DIR, "reproducibility.json"), "w") as f:
        json.dump(info, f, indent=2)

    print(json.dumps(info, indent=2))
    return info


if __name__ == "__main__":
    main()
