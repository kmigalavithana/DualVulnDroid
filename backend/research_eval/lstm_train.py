"""
PHASE RESEARCH-EVAL-5A: LSTM training on the FROZEN RESEARCH-EVAL-1
split (research_eval_artifacts/{train,validation,test}_indices.json,
clean_dataset.csv) - no new split, no re-cleaning.

Pipeline order (Part 4, strictly followed):
  clean dataset -> frozen split -> tokenizer applied to all splits ->
  VOCABULARY fit on TRAIN TOKENS ONLY -> validation/test encoded against
  the frozen vocabulary (unseen tokens -> <UNK>, never added to the vocab).

Framework: Keras 3 (TensorFlow backend) - already installed in this
environment (tensorflow==2.21.0, keras==3.15.0), per the spec's
preference for an already-available framework. CPU only (no CUDA on
native Windows for TF>=2.11 without WSL2/DirectML - documented, not
worked around).

Run from backend/:  python -m research_eval.lstm_train
"""

import json
import os
import platform
import random
import re
import sys
import time

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("PYTHONHASHSEED", "42")

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.evaluate import LABELS_ORDER  # ["s0","v0","s1","v1"] - already matches the required 0/1/2/3 mapping
from research_eval.data_split import load_split, ARTIFACT_DIR
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import f1_score

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

import keras
from keras import layers, models, callbacks

keras.utils.set_random_seed(SEED)

LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}  # s0=0, v0=1, s1=2, v1=3 - exactly the required mapping
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}

OUT_DIR = os.path.join(ARTIFACT_DIR, "lstm")
PAD_TOKEN, UNK_TOKEN = "<PAD>", "<UNK>"
MAX_VOCAB_SIZE = 4000
MIN_TOKEN_FREQUENCY = 1
SEQ_LENGTH_PERCENTILE = 95

# ---------------------------------------------------------------------
# Part 6: code-aware tokenizer (NOT a generic English tokenizer).
# Case-sensitive (deliberately, unlike ml/feature_pipeline.normalize_code's
# lowercasing) so API names like HostnameVerifier/X509TrustManager/
# SSLContext stay distinguishable from unrelated lowercase identifiers -
# documented as an intentional difference from the TF-IDF pipeline, not
# an oversight. String/char literals and numeric literals are normalized
# to placeholder tokens (same spirit as normalize_code(), reduces sparse
# per-sample noise) while identifiers/operators/punctuation are kept as
# real, discoverable tokens (rawQuery, execSQL, HostnameVerifier, etc.
# survive whole, since camelCase/snake_case identifiers are captured by
# a single regex alternative rather than being split further).
# ---------------------------------------------------------------------
_TOKEN_RE = re.compile(
    r'"[^"]*"'                       # string literal -> STRING
    r"|'[^']*'"                      # char/string literal -> CHAR
    r"|//.*"                         # line comment -> dropped
    r"|/\*.*?\*/"                    # block comment -> dropped
    r"|\b\d+\.\d+\b"                 # float -> NUM
    r"|\b\d+\b"                      # int -> NUM
    r"|[A-Za-z_][A-Za-z0-9_]*"       # identifier / API name, kept whole
    r"|==|!=|<=|>=|&&|\|\||\+\+|--|->|::"  # multi-char operators
    r"|[{}()\[\];,.]"                # structural punctuation
    r"|[+\-*/%=<>!&|^~?:]",          # single-char operators
    re.DOTALL,
)


def tokenize_code(code: str) -> list:
    if not isinstance(code, str):
        return []
    tokens = []
    for m in _TOKEN_RE.finditer(code):
        t = m.group(0)
        if t.startswith("//") or t.startswith("/*"):
            continue  # comments carry no cross-sample signal, dropped rather than tokenized
        if t.startswith('"') and t.endswith('"'):
            tokens.append("STRING")
        elif t.startswith("'") and t.endswith("'"):
            tokens.append("CHAR")
        elif re.fullmatch(r"\d+(\.\d+)?", t):
            tokens.append("NUM")
        else:
            tokens.append(t)
    return tokens


# ---------------------------------------------------------------------
# Part 7: vocabulary - TRAIN TOKENS ONLY.
# ---------------------------------------------------------------------

def build_vocabulary(train_token_lists, max_vocab_size=MAX_VOCAB_SIZE, min_frequency=MIN_TOKEN_FREQUENCY):
    from collections import Counter
    counts = Counter(t for tokens in train_token_lists for t in tokens)
    counts = {t: c for t, c in counts.items() if c >= min_frequency}
    # Sort by frequency desc, then alphabetically for full determinism on ties.
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    kept = ranked[: max_vocab_size - 2]  # reserve 2 slots for PAD/UNK

    vocab = {PAD_TOKEN: 0, UNK_TOKEN: 1}
    for token, _ in kept:
        vocab[token] = len(vocab)

    return vocab, {
        "raw_distinct_tokens_in_train": len(counts),
        "vocab_size": len(vocab),
        "min_frequency": min_frequency,
        "max_vocab_size_cap": max_vocab_size,
        "oov_strategy": f"any token not in the train-fit vocabulary (including all validation/test-only tokens) maps to {UNK_TOKEN} (id=1) - never added to the vocabulary",
        "most_frequent_20": [t for t, _ in ranked[:20]],
    }


def determine_max_length(train_token_lists, percentile=SEQ_LENGTH_PERCENTILE):
    lengths = np.array([len(t) for t in train_token_lists])
    max_len = int(np.ceil(np.percentile(lengths, percentile)))
    max_len = max(max_len, 1)
    return max_len, {
        "percentile_used": percentile,
        "chosen_max_length": max_len,
        "train_length_stats": {"min": int(lengths.min()), "max": int(lengths.max()), "mean": float(lengths.mean()), "median": float(np.median(lengths))},
    }


def truncation_rate(token_lists, max_len):
    if not token_lists:
        return 0.0
    return float(np.mean([len(t) > max_len for t in token_lists]))


def encode_sequences(token_lists, vocab, max_len):
    unk_id = vocab[UNK_TOKEN]
    encoded = np.zeros((len(token_lists), max_len), dtype=np.int32)  # 0 = PAD
    for i, tokens in enumerate(token_lists):
        ids = [vocab.get(t, unk_id) for t in tokens[:max_len]]
        encoded[i, : len(ids)] = ids
    return encoded


# ---------------------------------------------------------------------
# Part 9: model architecture.
# ---------------------------------------------------------------------

def build_model(vocab_size, embedding_dim, lstm_units, dropout, learning_rate, num_classes=4):
    model = models.Sequential([
        layers.Input(shape=(None,), dtype="int32"),
        layers.Embedding(vocab_size, embedding_dim, mask_zero=True),
        layers.SpatialDropout1D(dropout),
        layers.Bidirectional(layers.LSTM(lstm_units)),
        layers.Dropout(dropout),
        layers.Dense(64, activation="relu"),
        layers.Dense(num_classes, activation="softmax"),
    ])
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


class MacroF1History(callbacks.Callback):
    """Keras has no built-in macro-F1 metric - computed here at the end
    of every epoch on VALIDATION ONLY (never test), and used both for
    EarlyStopping/ReduceLROnPlateau (via a synthetic logged metric) and
    for final candidate selection (Part 11/14/15)."""

    def __init__(self, X_val, y_val):
        super().__init__()
        self.X_val, self.y_val = X_val, y_val
        self.val_macro_f1_history = []

    def on_epoch_end(self, epoch, logs=None):
        probs = self.model.predict(self.X_val, verbose=0)
        preds = np.argmax(probs, axis=1)
        f1 = f1_score(self.y_val, preds, average="macro", zero_division=0)
        self.val_macro_f1_history.append(float(f1))
        logs = logs or {}
        logs["val_macro_f1"] = f1


def train_one_candidate(candidate, X_train, y_train, X_val, y_val, class_weight, vocab_size, max_epochs=40):
    keras.utils.set_random_seed(SEED)  # reset before every candidate for a fair, reproducible comparison
    model = build_model(vocab_size, candidate["embedding_dim"], candidate["lstm_units"], candidate["dropout"], candidate["learning_rate"])

    f1_tracker = MacroF1History(X_val, y_val)
    early_stop = callbacks.EarlyStopping(monitor="val_macro_f1", mode="max", patience=8, restore_best_weights=True)
    reduce_lr = callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=4, min_lr=1e-6)

    start = time.time()
    history = model.fit(
        X_train, y_train, validation_data=(X_val, y_val),
        epochs=max_epochs, batch_size=32, class_weight=class_weight,
        callbacks=[f1_tracker, early_stop, reduce_lr], verbose=0,
    )
    elapsed = time.time() - start

    best_epoch = int(np.argmax(f1_tracker.val_macro_f1_history))
    best_val_f1 = float(f1_tracker.val_macro_f1_history[best_epoch])

    training_history = {
        "loss": [float(v) for v in history.history["loss"]],
        "val_loss": [float(v) for v in history.history["val_loss"]],
        "accuracy": [float(v) for v in history.history["accuracy"]],
        "val_accuracy": [float(v) for v in history.history["val_accuracy"]],
        "val_macro_f1": f1_tracker.val_macro_f1_history,
        "epochs_trained": len(history.history["loss"]),
        "best_epoch": best_epoch,
        "best_val_macro_f1": best_val_f1,
        "training_seconds": elapsed,
    }
    return model, training_history


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    train_df, val_df, test_df, (train_idx, val_idx, test_idx) = load_split()
    print(f"[lstm_train] frozen split: train={len(train_df)} val={len(val_df)} test={len(test_df)}")

    train_tokens = [tokenize_code(c) for c in train_df["vulnerable_line"]]
    val_tokens = [tokenize_code(c) for c in val_df["vulnerable_line"]]
    test_tokens = [tokenize_code(c) for c in test_df["vulnerable_line"]]

    vocab, vocab_meta = build_vocabulary(train_tokens)
    max_len, length_meta = determine_max_length(train_tokens)

    truncation = {
        "train": truncation_rate(train_tokens, max_len),
        "validation": truncation_rate(val_tokens, max_len),
        "test": truncation_rate(test_tokens, max_len),
    }
    print(f"[lstm_train] vocab_size={vocab_meta['vocab_size']} max_len={max_len} truncation={truncation}")

    X_train = encode_sequences(train_tokens, vocab, max_len)
    X_val = encode_sequences(val_tokens, vocab, max_len)
    X_test = encode_sequences(test_tokens, vocab, max_len)
    y_train = np.array([LABEL_TO_INT[l] for l in train_df["label"]])
    y_val = np.array([LABEL_TO_INT[l] for l in val_df["label"]])
    y_test = np.array([LABEL_TO_INT[l] for l in test_df["label"]])

    # Part 10: class weights from TRAIN ONLY.
    class_weight_arr = compute_class_weight("balanced", classes=np.arange(len(LABELS_ORDER)), y=y_train)
    class_weight = {i: float(w) for i, w in enumerate(class_weight_arr)}
    train_label_counts = {label: int(np.sum(y_train == LABEL_TO_INT[label])) for label in LABELS_ORDER}
    print(f"[lstm_train] train label distribution: {train_label_counts}, class_weight: {class_weight}")

    # Part 14: small, pre-declared validation-only hyperparameter search.
    candidates = [
        {"name": "A_small", "embedding_dim": 64, "lstm_units": 64, "dropout": 0.3, "learning_rate": 1e-3},
        {"name": "B_default", "embedding_dim": 128, "lstm_units": 128, "dropout": 0.3, "learning_rate": 1e-3},
        {"name": "C_more_dropout", "embedding_dim": 128, "lstm_units": 128, "dropout": 0.5, "learning_rate": 1e-3},
        {"name": "D_lower_lr", "embedding_dim": 128, "lstm_units": 128, "dropout": 0.3, "learning_rate": 3e-4},
    ]

    results = []
    best_model, best_history, best_candidate = None, None, None
    for cand in candidates:
        print(f"[lstm_train] training candidate {cand['name']}: {cand}")
        model, hist = train_one_candidate(cand, X_train, y_train, X_val, y_val, class_weight, len(vocab))
        results.append({"candidate": cand, "history_summary": {
            "epochs_trained": hist["epochs_trained"], "best_epoch": hist["best_epoch"], "best_val_macro_f1": hist["best_val_macro_f1"],
        }})
        print(f"[lstm_train]   -> best_val_macro_f1={hist['best_val_macro_f1']:.4f} at epoch {hist['best_epoch']} ({hist['epochs_trained']} epochs trained)")
        if best_history is None or hist["best_val_macro_f1"] > best_history["best_val_macro_f1"]:
            best_model, best_history, best_candidate = model, hist, cand

    print(f"[lstm_train] SELECTED candidate: {best_candidate['name']} (val_macro_f1={best_history['best_val_macro_f1']:.4f}) - FREEZING.")

    # --- Save everything (Part 25/26) ---
    model_dir = os.path.join(OUT_DIR, "model")
    os.makedirs(model_dir, exist_ok=True)
    best_model.save(os.path.join(model_dir, "lstm_model.keras"))

    tokenizer_dir = os.path.join(OUT_DIR, "tokenizer")
    os.makedirs(tokenizer_dir, exist_ok=True)
    with open(os.path.join(tokenizer_dir, "vocabulary.json"), "w") as f:
        json.dump(vocab, f, indent=2)
    with open(os.path.join(tokenizer_dir, "vocabulary_metadata.json"), "w") as f:
        json.dump(vocab_meta, f, indent=2)
    with open(os.path.join(tokenizer_dir, "sequence_length.json"), "w") as f:
        json.dump({**length_meta, "truncation_rates": truncation}, f, indent=2)

    model_config = {
        "label_mapping": LABEL_TO_INT,
        "selected_candidate": best_candidate,
        "all_candidates_tried": results,
        "selection_method": "max validation macro-F1 across the 4 pre-declared candidates (validation only, test never touched)",
        "vocab_size": len(vocab), "max_sequence_length": max_len,
        "class_weight": class_weight, "train_label_distribution": train_label_counts,
        "random_seed": SEED,
        "architecture": "Embedding(mask_zero) -> SpatialDropout1D -> Bidirectional(LSTM) -> Dropout -> Dense(64,relu) -> Dense(4,softmax)",
        "bidirectional_context_used": True,
        "optimizer": "Adam", "loss": "sparse_categorical_crossentropy",
        "callbacks": "EarlyStopping(monitor=val_macro_f1, patience=8, restore_best_weights=True), ReduceLROnPlateau(monitor=val_loss, factor=0.5, patience=4)",
        "max_epochs_cap": 40, "batch_size": 32,
    }
    with open(os.path.join(OUT_DIR, "model_config.json"), "w") as f:
        json.dump(model_config, f, indent=2)

    with open(os.path.join(OUT_DIR, "training_history.json"), "w") as f:
        json.dump({"selected": best_history, "all_candidates": results}, f, indent=2)

    hardware = {
        "platform": platform.platform(), "processor": platform.processor(),
        "python_version": sys.version, "keras_version": keras.__version__,
        "keras_backend": keras.backend.backend(),
        "gpu_available": False,
        "gpu_note": "TensorFlow>=2.11 has no native Windows GPU support without WSL2/TensorFlow-DirectML - CPU-only training, documented not worked around.",
    }
    with open(os.path.join(OUT_DIR, "hardware.json"), "w") as f:
        json.dump(hardware, f, indent=2)

    print(f"[lstm_train] done. Artifacts saved under {OUT_DIR}")
    return best_model, model_config, (X_test, y_test, test_idx)


if __name__ == "__main__":
    main()
