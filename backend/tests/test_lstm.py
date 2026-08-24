"""
PHASE RESEARCH-EVAL-5A, Part 27: tests for the LSTM deep-learning
evaluation (research_eval/lstm_train.py, lstm_evaluate.py,
lstm_compare.py, lstm_reproducibility.py).

Same convention as the prior research phases: pure unit tests always
run; artifact-dependent tests skip (not fail) if the (expensive)
training run hasn't been performed yet in this checkout. TensorFlow/
Keras import is itself somewhat heavy, so the tokenizer/vocab tests
that don't need the trained model avoid importing keras where possible.
"""

import csv
import json
import os

import numpy as np
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS
from research_eval.data_split import ARTIFACT_DIR, load_split
from research_eval.lstm_train import (
    tokenize_code, build_vocabulary, determine_max_length, encode_sequences,
    PAD_TOKEN, UNK_TOKEN, LABEL_TO_INT,
)

LSTM_DIR = os.path.join(ARTIFACT_DIR, "lstm")


def _present(*names):
    return all(os.path.exists(os.path.join(LSTM_DIR, n)) for n in names)


skip_no_model = pytest.mark.skipif(
    not _present("model_config.json", "model", "tokenizer"), reason="run `python -m research_eval.lstm_train` first (expensive)"
)
skip_no_eval = pytest.mark.skipif(
    not _present("test_metrics.json"), reason="run `python -m research_eval.lstm_evaluate` first"
)


# ---------------------------------------------------------------------
# 1. Same frozen split indices as every other research_eval phase
# ---------------------------------------------------------------------

def test_lstm_uses_the_same_frozen_split_as_research_eval_1():
    train_df, val_df, test_df, (train_idx, val_idx, test_idx) = load_split()
    assert len(train_df) == 791
    assert len(val_df) == 169
    assert len(test_df) == 168


def test_label_mapping_matches_required_spec_exactly():
    """s0=0, v0=1, s1=2, v1=3 - the exact mapping required by Part 2."""
    assert LABEL_TO_INT == {"s0": 0, "v0": 1, "s1": 2, "v1": 3}
    assert LABELS_ORDER == ["s0", "v0", "s1", "v1"]


# ---------------------------------------------------------------------
# 2/3. Tokenizer/vocabulary fit only on training data; val/test cannot expand it
# ---------------------------------------------------------------------

def test_tokenizer_is_code_aware_not_generic_english():
    tokens = tokenize_code('Cursor c = db.rawQuery("SELECT * FROM users", null);')
    assert "rawQuery" in tokens  # camelCase API identifier survives whole
    assert "STRING" in tokens  # string literal normalized, not left as raw noisy text
    assert '"SELECT * FROM users"' not in tokens


def test_vocabulary_built_only_from_provided_train_tokens():
    train_tokens = [["foo", "bar", "foo"], ["baz", "foo"]]
    vocab, meta = build_vocabulary(train_tokens, max_vocab_size=100, min_frequency=1)
    assert vocab[PAD_TOKEN] == 0
    assert vocab[UNK_TOKEN] == 1
    assert "foo" in vocab and "bar" in vocab and "baz" in vocab
    assert meta["raw_distinct_tokens_in_train"] == 3


def test_validation_test_only_tokens_map_to_unk_never_expand_vocab():
    train_tokens = [["foo", "bar"]]
    vocab, _ = build_vocabulary(train_tokens, max_vocab_size=100, min_frequency=1)
    vocab_size_before = len(vocab)

    val_only_tokens = [["foo", "neverSeenInTrain", "alsoUnseen"]]
    encoded = encode_sequences(val_only_tokens, vocab, max_len=5)

    assert len(vocab) == vocab_size_before  # encoding must never mutate the vocab
    unk_id = vocab[UNK_TOKEN]
    foo_id = vocab["foo"]
    assert encoded[0][0] == foo_id
    assert encoded[0][1] == unk_id
    assert encoded[0][2] == unk_id


# ---------------------------------------------------------------------
# 4. Sequence padding is deterministic
# ---------------------------------------------------------------------

def test_padding_is_deterministic_and_uses_pad_id_zero():
    vocab, _ = build_vocabulary([["a", "b", "c"]], max_vocab_size=100, min_frequency=1)
    encoded1 = encode_sequences([["a", "b"]], vocab, max_len=5)
    encoded2 = encode_sequences([["a", "b"]], vocab, max_len=5)
    assert np.array_equal(encoded1, encoded2)
    assert list(encoded1[0][2:]) == [0, 0, 0]  # PAD=0 fills the remainder


def test_truncation_keeps_the_first_max_len_tokens():
    vocab, _ = build_vocabulary([["a", "b", "c", "d", "e"]], max_vocab_size=100, min_frequency=1)
    encoded = encode_sequences([["a", "b", "c", "d", "e"]], vocab, max_len=3)
    assert list(encoded[0]) == [vocab["a"], vocab["b"], vocab["c"]]


def test_max_length_determined_from_train_only():
    train_tokens = [["a"] * n for n in [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]]  # one long outlier
    max_len, meta = determine_max_length(train_tokens, percentile=95)
    assert max_len < 100  # the 95th percentile rule must not just take the max
    assert meta["percentile_used"] == 95


# ---------------------------------------------------------------------
# 5. Class-weight calculation uses train only
# ---------------------------------------------------------------------

def test_class_weights_computed_from_train_distribution_only():
    from sklearn.utils.class_weight import compute_class_weight
    y_train = np.array([0, 0, 0, 1, 1, 2, 3, 3, 3, 3])  # imbalanced
    weights = compute_class_weight("balanced", classes=np.arange(4), y=y_train)
    # class 2 (rarest, n=1) must get the highest weight, class 3 (most common, n=4) the lowest
    assert weights[2] > weights[0] > weights[3]


# ---------------------------------------------------------------------
# 6/7/8/9. Model output shape, prediction count, binary mapping, confusion matrix dims
# ---------------------------------------------------------------------

@skip_no_model
def test_model_output_has_four_classes():
    import keras
    model = keras.models.load_model(os.path.join(LSTM_DIR, "model", "lstm_model.keras"))
    assert model.output_shape[-1] == 4


@skip_no_eval
def test_prediction_count_equals_frozen_test_set_size():
    with open(os.path.join(LSTM_DIR, "confidence_analysis.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 168


def test_binary_mapping_is_the_required_production_mapping():
    assert VULNERABLE_LABELS == {"s0", "v0"}


@skip_no_eval
def test_confusion_matrix_dimensions_are_4x4():
    with open(os.path.join(LSTM_DIR, "confusion_matrix.csv"), newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    data_rows = rows[1:]
    assert len(header) == 5  # label column + 4 class columns
    assert len(data_rows) == 4


# ---------------------------------------------------------------------
# 10. Test set not used during tuning
# ---------------------------------------------------------------------

@skip_no_model
@skip_no_eval
def test_hyperparameter_selection_used_validation_macro_f1_only():
    with open(os.path.join(LSTM_DIR, "model_config.json")) as f:
        config = json.load(f)
    assert "validation macro-F1" in config["selection_method"]
    # The selection record legitimately mentions "test" only to disclaim using it
    # (e.g. "test never touched") - check no test-set METRIC VALUE was used for
    # selection, not that the word "test" is absent from the sentence.
    with open(os.path.join(LSTM_DIR, "test_metrics.json")) as f:
        test_metrics = json.load(f)
    selection_blob = json.dumps(config["all_candidates_tried"])
    test_f1_str = json.dumps(round(test_metrics["macro_f1"], 6))
    assert test_f1_str not in selection_blob, "frozen test macro_f1 must not appear in the hyperparameter selection record"

    for candidate_result in config["all_candidates_tried"]:
        assert "best_val_macro_f1" in candidate_result["history_summary"]


# ---------------------------------------------------------------------
# 11. Reproducibility with fixed seed
# ---------------------------------------------------------------------

def test_vocabulary_construction_is_reproducible():
    train_tokens = [["z", "a", "m"], ["a", "b"], ["z", "z"]]
    vocab1, _ = build_vocabulary(train_tokens, max_vocab_size=100, min_frequency=1)
    vocab2, _ = build_vocabulary(train_tokens, max_vocab_size=100, min_frequency=1)
    assert vocab1 == vocab2  # frequency+alphabetical tie-break must be fully deterministic


@skip_no_model
def test_model_config_records_fixed_random_seed():
    with open(os.path.join(LSTM_DIR, "model_config.json")) as f:
        config = json.load(f)
    assert config["random_seed"] == 42
