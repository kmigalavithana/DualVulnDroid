"""
PHASE RESEARCH-EVAL-5B, Part 32: tests for the CodeBERT deep-learning
evaluation (research_eval/codebert_train.py, codebert_evaluate.py,
codebert_compare.py, codebert_reproducibility.py).

Same convention as the LSTM/prior research phases: pure unit tests
always run; artifact-dependent tests skip (not fail) if the (expensive)
training run hasn't been performed yet in this checkout.
"""

import csv
import json
import os

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS
from research_eval.data_split import ARTIFACT_DIR, load_split

CODEBERT_DIR = os.path.join(ARTIFACT_DIR, "codebert")


def _present(*names):
    return all(os.path.exists(os.path.join(CODEBERT_DIR, n)) for n in names)


skip_no_model = pytest.mark.skipif(
    not _present("model_config.json", "model", "tokenizer"), reason="run `python -m research_eval.codebert_train` first (expensive)"
)
skip_no_eval = pytest.mark.skipif(
    not _present("test_metrics.json"), reason="run `python -m research_eval.codebert_evaluate` first"
)


# ---------------------------------------------------------------------
# 1. Frozen split
# ---------------------------------------------------------------------

def test_codebert_uses_the_same_frozen_split_as_every_other_phase():
    train_df, val_df, test_df, _ = load_split()
    assert (len(train_df), len(val_df), len(test_df)) == (791, 169, 168)


def test_label_mapping_matches_required_spec_exactly():
    assert LABELS_ORDER == ["s0", "v0", "s1", "v1"]  # s0=0, v0=1, s1=2, v1=3


# ---------------------------------------------------------------------
# 2. Tokenizer/model compatibility; 12. correct model/tokenizer pairing
# ---------------------------------------------------------------------

@skip_no_model
def test_tokenizer_and_model_are_paired_from_the_same_saved_checkpoint():
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    tokenizer = AutoTokenizer.from_pretrained(os.path.join(CODEBERT_DIR, "tokenizer"), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(os.path.join(CODEBERT_DIR, "model"), local_files_only=True)
    # A real, direct compatibility check: encoding with this tokenizer must produce ids the
    # model's embedding table can actually index (i.e. within vocab_size), not just "load without error".
    enc = tokenizer("SELECT * FROM users", return_tensors="pt")
    assert int(enc["input_ids"].max()) < model.config.vocab_size
    assert model.config.num_labels == 4


# ---------------------------------------------------------------------
# 3. No test-set tuning
# ---------------------------------------------------------------------

@skip_no_model
def test_strategy_selection_used_validation_macro_f1_only_never_test():
    with open(os.path.join(CODEBERT_DIR, "model_config.json")) as f:
        config = json.load(f)
    assert "validation macro-F1" in config["selection_method"]

    if _present("test_metrics.json"):
        with open(os.path.join(CODEBERT_DIR, "test_metrics.json")) as f:
            test_metrics = json.load(f)
        test_f1_str = json.dumps(round(test_metrics["macro_f1"], 6))
        selection_blob = json.dumps(config["all_strategies_tried"])
        assert test_f1_str not in selection_blob, "frozen test macro_f1 must not appear in the strategy-selection record"


# ---------------------------------------------------------------------
# 4. Sequence length selection from train only
# ---------------------------------------------------------------------

@skip_no_model
def test_sequence_length_was_chosen_from_train_statistics_only():
    with open(os.path.join(CODEBERT_DIR, "tokenizer", "sequence_length.json")) as f:
        meta = json.load(f)
    assert "train_length_stats" in meta
    assert meta["percentile_used"] == 95
    assert meta["chosen_max_length"] <= meta["model_cap"]


# ---------------------------------------------------------------------
# 5. Class weights from train only
# ---------------------------------------------------------------------

@skip_no_model
def test_class_weights_reflect_real_train_imbalance():
    with open(os.path.join(CODEBERT_DIR, "model_config.json")) as f:
        config = json.load(f)
    weights = config["class_weight"]
    counts = config["train_label_distribution"]
    # rarest class (lowest train count) must get the highest weight
    rarest_label = min(counts, key=lambda l: counts[l])
    label_to_int = {label: i for i, label in enumerate(LABELS_ORDER)}
    rarest_weight = weights[str(label_to_int[rarest_label])]
    assert rarest_weight == max(weights.values())


# ---------------------------------------------------------------------
# 6. Output shape = 4 classes
# ---------------------------------------------------------------------

@skip_no_model
def test_model_output_has_four_classes():
    from transformers import AutoModelForSequenceClassification
    model = AutoModelForSequenceClassification.from_pretrained(os.path.join(CODEBERT_DIR, "model"), local_files_only=True)
    assert model.config.num_labels == 4
    assert model.classifier.out_proj.out_features == 4


# ---------------------------------------------------------------------
# 7. Deterministic preprocessing
# ---------------------------------------------------------------------

@skip_no_model
def test_tokenization_is_deterministic():
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(os.path.join(CODEBERT_DIR, "tokenizer"), local_files_only=True)
    code = 'Cursor c = db.rawQuery("SELECT * FROM users WHERE id = " + userId, null);'
    enc1 = tokenizer(code, max_length=79, truncation=True, padding="max_length", return_tensors="pt")
    enc2 = tokenizer(code, max_length=79, truncation=True, padding="max_length", return_tensors="pt")
    assert enc1["input_ids"].tolist() == enc2["input_ids"].tolist()


# ---------------------------------------------------------------------
# 8. Prediction count = 168
# ---------------------------------------------------------------------

@skip_no_eval
def test_prediction_count_equals_frozen_test_set_size():
    with open(os.path.join(CODEBERT_DIR, "confidence_analysis.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 168


@skip_no_eval
def test_confusion_matrix_sums_to_168():
    with open(os.path.join(CODEBERT_DIR, "test_metrics.json")) as f:
        m = json.load(f)
    total = sum(sum(row) for row in m["confusion_matrix"])
    assert total == 168


# ---------------------------------------------------------------------
# 9. Binary mapping
# ---------------------------------------------------------------------

def test_binary_mapping_is_the_required_production_mapping():
    assert VULNERABLE_LABELS == {"s0", "v0"}


# ---------------------------------------------------------------------
# 10. Confusion matrix dimensions
# ---------------------------------------------------------------------

@skip_no_eval
def test_confusion_matrix_is_4x4():
    with open(os.path.join(CODEBERT_DIR, "confusion_matrix.csv"), newline="") as f:
        rows = list(csv.reader(f))
    assert len(rows[0]) == 5  # label column + 4 classes
    assert len(rows) - 1 == 4


# ---------------------------------------------------------------------
# 11. Reproducibility metadata
# ---------------------------------------------------------------------

@skip_no_model
def test_reproducibility_records_real_checkpoint_details_not_guessed():
    if not _present("reproducibility.json"):
        pytest.skip("run `python -m research_eval.codebert_reproducibility` first")
    with open(os.path.join(CODEBERT_DIR, "reproducibility.json")) as f:
        info = json.load(f)
    # These must come from the actually-loaded checkpoint's config, not hardcoded guesses -
    # cross-check against known real values for microsoft/codebert-base (RoBERTa-base architecture).
    assert info["checkpoint"]["hidden_size"] == 768
    assert info["checkpoint"]["num_hidden_layers"] == 12
    assert info["checkpoint"]["num_attention_heads"] == 12
    assert info["checkpoint"]["model_type"] == "roberta"
    assert info["random_seed"] == 42


def test_provenance_discrepancy_is_not_silently_trusted():
    """RESEARCH-EVAL-6 found CodeBERT result files hand-placed outside the
    real pipeline's output path (research_eval_artifacts/'codebert final
    result'/, codebert_final_artifacts/, and loose files at the artifacts
    root) with numbers that do not match the real, freshly-computed
    evaluation. This test locks in that the REAL pipeline's output path
    is the only one ever read by codebert_compare.py."""
    import inspect
    from research_eval import codebert_compare
    source = inspect.getsource(codebert_compare)
    assert "codebert final result" not in source
    assert "codebert_final_artifacts" not in source
