"""
PHASE RESEARCH-EVAL-5B: fine-tunes a REAL pretrained CodeBERT checkpoint
(microsoft/codebert-base, a RoBERTa-architecture encoder pretrained on
source code + natural language) on the FROZEN RESEARCH-EVAL-1 split.

Data leakage note (Part 4): unlike the from-scratch LSTM (RESEARCH-EVAL-
5A), CodeBERT's tokenizer is NOT fit on this project's data at all - it
is the official pretrained BPE tokenizer shipped with the checkpoint,
loaded read-only. "Leakage" here means something narrower and different
from the LSTM case: never using validation/test data to pick hyper-
parameters, sequence length, checkpoint/strategy, or early-stopping -
all of which this script strictly confines to TRAIN (weights, class
counts) and VALIDATION (macro-F1 for selection). This distinction
(PRETRAINED KNOWLEDGE vs TASK-SPECIFIC FINE-TUNING) is documented
explicitly, not glossed over.

HF cache is redirected off the C: drive (which had <2GB free at the
start of this phase) to F:/hf_cache via HF_HOME - a real, measured
environment constraint, not a style choice.

Run from backend/:  python -m research_eval.codebert_train
"""

import json
import os
import platform
import random
import sys
import time

os.environ.setdefault("HF_HOME", "F:/hf_cache")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.evaluate import LABELS_ORDER
from research_eval.data_split import load_split, ARTIFACT_DIR
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import f1_score

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

import torch
import transformers
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification, get_linear_schedule_with_warmup

torch.manual_seed(SEED)

CHECKPOINT = "microsoft/codebert-base"
LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}  # s0=0, v0=1, s1=2, v1=3
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}

OUT_DIR = os.path.join(ARTIFACT_DIR, "codebert")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEQ_LENGTH_PERCENTILE = 95
MODEL_MAX_USABLE_LENGTH = 512  # RoBERTa/CodeBERT: max_position_embeddings=514 reserves 2 positions

LEARNING_RATE = 2e-5
BATCH_SIZE = 8
MAX_EPOCHS = 5
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.1
EARLY_STOP_PATIENCE = 2


class CodeDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: v[idx] for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


def determine_max_length(tokenizer, train_texts, percentile=SEQ_LENGTH_PERCENTILE, cap=MODEL_MAX_USABLE_LENGTH):
    """TRAIN ONLY, per Part 9 - tokenized (not raw character) length, using
    the real CodeBERT tokenizer, capped at the model's usable max length."""
    lengths = [len(tokenizer.encode(t, add_special_tokens=True)) for t in train_texts]
    lengths = np.array(lengths)
    raw_choice = int(np.ceil(np.percentile(lengths, percentile)))
    chosen = min(raw_choice, cap)
    return chosen, {
        "percentile_used": percentile, "raw_percentile_value": raw_choice, "model_cap": cap,
        "chosen_max_length": chosen,
        "train_length_stats": {"min": int(lengths.min()), "max": int(lengths.max()), "mean": float(lengths.mean()), "median": float(np.median(lengths))},
    }


def truncation_rate(tokenizer, texts, max_len):
    if not texts:
        return 0.0
    lengths = [len(tokenizer.encode(t, add_special_tokens=True)) for t in texts]
    return float(np.mean([l > max_len for l in lengths]))


def encode_texts(tokenizer, texts, max_len):
    return tokenizer(list(texts), max_length=max_len, truncation=True, padding="max_length", return_tensors="pt")


def apply_freeze_strategy(model, strategy):
    """Part 12: three pre-declared strategies. roberta encoder layers are
    at model.roberta.encoder.layer[i] for CodeBERT's RobertaForSequenceClassification."""
    for p in model.parameters():
        p.requires_grad = True  # start from "everything trainable", then freeze as needed

    if strategy == "A_frozen_encoder":
        for p in model.roberta.parameters():
            p.requires_grad = False
        # classifier head (RobertaClassificationHead) remains trainable
    elif strategy == "B_last2_unfrozen":
        for p in model.roberta.parameters():
            p.requires_grad = False
        n_layers = len(model.roberta.encoder.layer)
        for layer in model.roberta.encoder.layer[n_layers - 2:]:
            for p in layer.parameters():
                p.requires_grad = True
    elif strategy == "C_full_finetune":
        pass  # everything already trainable
    else:
        raise ValueError(strategy)

    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    n_total = sum(p.numel() for p in model.parameters())
    return n_trainable, n_total


def evaluate_macro_f1(model, loader):
    model.eval()
    all_preds, all_labels, total_loss, n_batches = [], [], 0.0, 0
    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels").to(DEVICE)
            batch = {k: v.to(DEVICE) for k, v in batch.items()}
            out = model(**batch, labels=labels)
            total_loss += out.loss.item()
            n_batches += 1
            preds = torch.argmax(out.logits, dim=1).cpu().numpy()
            all_preds.extend(preds.tolist())
            all_labels.extend(labels.cpu().numpy().tolist())
    f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    return f1, total_loss / max(n_batches, 1)


def train_one_strategy(strategy, model, train_loader, val_loader, class_weights_tensor, max_epochs=MAX_EPOCHS):
    n_trainable, n_total = apply_freeze_strategy(model, strategy)
    model.to(DEVICE)

    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    total_steps = len(train_loader) * max_epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(WARMUP_RATIO * total_steps), num_training_steps=total_steps)
    loss_fn = torch.nn.CrossEntropyLoss(weight=class_weights_tensor.to(DEVICE))

    history = {"train_loss": [], "val_loss": [], "val_macro_f1": []}
    best_f1, best_epoch, best_state, epochs_without_improvement = -1.0, -1, None, 0

    start = time.time()
    for epoch in range(max_epochs):
        model.train()
        epoch_loss, n_batches = 0.0, 0
        for batch in train_loader:
            labels = batch.pop("labels").to(DEVICE)
            batch = {k: v.to(DEVICE) for k, v in batch.items()}
            optimizer.zero_grad()
            out = model(**batch)
            loss = loss_fn(out.logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable_params, 1.0)
            optimizer.step()
            scheduler.step()
            epoch_loss += loss.item()
            n_batches += 1

        train_loss = epoch_loss / max(n_batches, 1)
        val_f1, val_loss = evaluate_macro_f1(model, val_loader)
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_macro_f1"].append(val_f1)
        print(f"[codebert_train]   [{strategy}] epoch {epoch}: train_loss={train_loss:.4f} val_loss={val_loss:.4f} val_macro_f1={val_f1:.4f}")

        if val_f1 > best_f1:
            best_f1, best_epoch = val_f1, epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= EARLY_STOP_PATIENCE:
                print(f"[codebert_train]   [{strategy}] early stopping at epoch {epoch} (no improvement for {EARLY_STOP_PATIENCE} epochs)")
                break

    elapsed = time.time() - start
    model.load_state_dict(best_state)  # restore best-validation-F1 weights

    return model, {
        "strategy": strategy, "n_trainable_params": int(n_trainable), "n_total_params": int(n_total),
        "history": history, "best_epoch": best_epoch, "best_val_macro_f1": float(best_f1),
        "epochs_trained": len(history["train_loss"]), "training_seconds": elapsed,
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    train_df, val_df, test_df, (train_idx, val_idx, test_idx) = load_split()
    print(f"[codebert_train] frozen split: train={len(train_df)} val={len(val_df)} test={len(test_df)} device={DEVICE}")

    tokenizer = AutoTokenizer.from_pretrained(CHECKPOINT)
    print(f"[codebert_train] tokenizer loaded: {CHECKPOINT}, vocab_size={tokenizer.vocab_size}")

    max_len, length_meta = determine_max_length(tokenizer, list(train_df["vulnerable_line"]))
    truncation = {
        "train": truncation_rate(tokenizer, list(train_df["vulnerable_line"]), max_len),
        "validation": truncation_rate(tokenizer, list(val_df["vulnerable_line"]), max_len),
        "test": truncation_rate(tokenizer, list(test_df["vulnerable_line"]), max_len),
    }
    print(f"[codebert_train] max_len={max_len} truncation={truncation}")

    train_enc = encode_texts(tokenizer, train_df["vulnerable_line"], max_len)
    val_enc = encode_texts(tokenizer, val_df["vulnerable_line"], max_len)
    y_train = np.array([LABEL_TO_INT[l] for l in train_df["label"]])
    y_val = np.array([LABEL_TO_INT[l] for l in val_df["label"]])

    train_ds = CodeDataset(train_enc, y_train)
    val_ds = CodeDataset(val_enc, y_val)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, generator=torch.Generator().manual_seed(SEED))
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    class_weight_arr = compute_class_weight("balanced", classes=np.arange(len(LABELS_ORDER)), y=y_train)
    class_weights_tensor = torch.tensor(class_weight_arr, dtype=torch.float32)
    class_weight = {i: float(w) for i, w in enumerate(class_weight_arr)}
    train_label_counts = {label: int(np.sum(y_train == LABEL_TO_INT[label])) for label in LABELS_ORDER}
    print(f"[codebert_train] train label distribution: {train_label_counts}, class_weight: {class_weight}")

    strategies = ["A_frozen_encoder", "B_last2_unfrozen", "C_full_finetune"]
    results = []
    best_model, best_result = None, None
    for strategy in strategies:
        print(f"[codebert_train] === strategy {strategy} ===")
        torch.manual_seed(SEED)
        model = AutoModelForSequenceClassification.from_pretrained(CHECKPOINT, num_labels=len(LABELS_ORDER))
        model, result = train_one_strategy(strategy, model, train_loader, val_loader, class_weights_tensor)
        results.append(result)
        if best_result is None or result["best_val_macro_f1"] > best_result["best_val_macro_f1"]:
            best_model, best_result = model, result
        del model
        if DEVICE.type == "cpu":
            import gc
            gc.collect()

    print(f"[codebert_train] SELECTED strategy: {best_result['strategy']} (val_macro_f1={best_result['best_val_macro_f1']:.4f}) - FREEZING.")

    model_dir = os.path.join(OUT_DIR, "model")
    os.makedirs(model_dir, exist_ok=True)
    best_model.save_pretrained(model_dir)

    tokenizer_dir = os.path.join(OUT_DIR, "tokenizer")
    os.makedirs(tokenizer_dir, exist_ok=True)
    tokenizer.save_pretrained(tokenizer_dir)

    config = best_model.config
    checkpoint_info = {
        "model_name": CHECKPOINT, "model_version_note": "as resolved by transformers.AutoModelForSequenceClassification.from_pretrained at run time",
        "tokenizer_name": CHECKPOINT, "hidden_size": config.hidden_size, "num_hidden_layers": config.num_hidden_layers,
        "num_attention_heads": config.num_attention_heads, "max_position_embeddings": config.max_position_embeddings,
        "model_type": config.model_type,
    }
    with open(os.path.join(OUT_DIR, "model_config.json"), "w") as f:
        json.dump({
            "checkpoint": checkpoint_info, "label_mapping": LABEL_TO_INT,
            "selected_strategy": best_result["strategy"], "all_strategies_tried": [
                {"strategy": r["strategy"], "n_trainable_params": r["n_trainable_params"], "n_total_params": r["n_total_params"],
                 "best_epoch": r["best_epoch"], "best_val_macro_f1": r["best_val_macro_f1"], "epochs_trained": r["epochs_trained"],
                 "training_seconds": r["training_seconds"]}
                for r in results
            ],
            "selection_method": "max validation macro-F1 across the 3 pre-declared fine-tuning strategies (validation only, test never touched)",
            "max_sequence_length": max_len, "class_weight": class_weight, "train_label_distribution": train_label_counts,
            "random_seed": SEED,
            "architecture": "CodeBERT (RoBERTa encoder) -> pooled [CLS] representation -> RobertaClassificationHead (dropout -> dense -> dropout -> out_proj) -> 4 classes",
        }, f, indent=2)

    with open(os.path.join(OUT_DIR, "training_config.json"), "w") as f:
        json.dump({
            "learning_rate": LEARNING_RATE, "batch_size": BATCH_SIZE, "max_epochs": MAX_EPOCHS,
            "weight_decay": WEIGHT_DECAY, "warmup_ratio": WARMUP_RATIO, "early_stopping_patience": EARLY_STOP_PATIENCE,
            "optimizer": "AdamW", "lr_schedule": "linear warmup then linear decay (get_linear_schedule_with_warmup)",
            "loss": "CrossEntropyLoss with train-only class weights", "gradient_clipping_max_norm": 1.0,
            "device": str(DEVICE), "seed": SEED,
        }, f, indent=2)

    with open(os.path.join(OUT_DIR, "training_history.json"), "w") as f:
        json.dump({"selected": best_result, "all_strategies": results}, f, indent=2)

    with open(os.path.join(tokenizer_dir, "sequence_length.json"), "w") as f:
        json.dump({**length_meta, "truncation_rates": truncation}, f, indent=2)

    ram_info = {}
    try:
        import psutil
        vm = psutil.virtual_memory()
        ram_info = {"total_gb": round(vm.total / 1e9, 2), "available_gb": round(vm.available / 1e9, 2)}
    except ImportError:
        ram_info = {"note": "psutil not installed - RAM not measured programmatically"}

    hardware = {
        "platform": platform.platform(), "processor": platform.processor(), "python_version": sys.version,
        "torch_version": torch.__version__, "transformers_version": transformers.__version__,
        "device": str(DEVICE), "gpu_available": torch.cuda.is_available(),
        "gpu_note": "CPU-only run - no CUDA GPU detected/available in this environment." if not torch.cuda.is_available() else None,
        "ram": ram_info,
        "hf_cache_location": os.environ.get("HF_HOME"),
    }
    with open(os.path.join(OUT_DIR, "hardware.json"), "w") as f:
        json.dump(hardware, f, indent=2)

    print(f"[codebert_train] done. Artifacts saved under {OUT_DIR}")
    return best_model, tokenizer, max_len


if __name__ == "__main__":
    main()
