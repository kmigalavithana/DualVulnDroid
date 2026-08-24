# Large Files Not Tracked in This Repository

Three files exceed GitHub's 100 MB per-file hard limit and are excluded from version control via `.gitignore`. They remain on local disk untouched; nothing was deleted. This document explains what each one is, why it isn't committed, and how to obtain or regenerate it.

## Excluded files

| File | Size | What it is |
|---|---|---|
| `backend/research_eval_artifacts/codebert/model/model.safetensors` | ~475.5 MB | Fine-tuned CodeBERT model weights (HuggingFace safetensors format) — the **authoritative** CodeBERT research-comparison result referenced throughout Chapters 7–8 of the thesis (accuracy 0.7976, CWE-89 recall 0.8621). |
| `backend/research_eval_artifacts/codebert_model_state_dict.pt` | ~475.6 MB | The same authoritative CodeBERT checkpoint, saved as a raw PyTorch state dict rather than safetensors. |
| `backend/research_eval_artifacts/codebert_final_artifacts/codebert_model_state_dict.pt` | ~475.6 MB | A **superseded/disputed** earlier CodeBERT training run (accuracy 0.8333 in that run) — explicitly **not** the version used in any thesis chapter's reported results. Kept on disk for provenance transparency, not as a production artifact. |

**Important provenance note:** only the unsuffixed `research_eval_artifacts/codebert/` directory's results are authoritative and cited in the thesis. The `codebert_final_artifacts/` and `codebert final result/` directories hold an earlier, disputed training run with different (and in one metric, opposite) conclusions, and were explicitly determined *not* authoritative during this project's evaluation work. Their small metric files (`test_metrics.json`, `y_pred.npy`, etc.) remain tracked in this repository for transparency about that history — only the large `.pt` weight file itself is excluded here.

## Why these aren't in the repository

- GitHub rejects any single file over 100 MB in a normal (non-LFS) push.
- These are pretrained-then-fine-tuned model weights, not source code — they are a research-comparison artifact only. **CodeBERT is not part of the production detection pipeline** (see the root `README.md` → "ML Models" / "Production Model" sections); XGBoost is the deployed model and its much smaller artifacts (`backend/xgboost_artifacts/`, under 1 MB total) are fully tracked.

## How to regenerate or obtain these files

1. **Regenerate from source**: the CodeBERT fine-tuning pipeline lives under `backend/research_eval/` (see that directory's own scripts) and was run against the same labelled dataset described in `backend/research_eval_artifacts/final_documentation/methodology.md`. Re-running that pipeline reproduces `model.safetensors`/`codebert_model_state_dict.pt` from scratch.
2. **Host externally**: if you want the exact trained weights without re-running training, upload `backend/research_eval_artifacts/codebert/model/model.safetensors` to a model host (e.g. the Hugging Face Hub) and link it here — this repository does not currently do so.
3. **Skip entirely**: everything else in this repository — the production XGBoost pipeline, the Decision Engine, the Flutter app, the IntelliJ plugin, and every other research-comparison model (SVM, Random Forest, LSTM) — works without these files. They are only needed if you want to independently re-verify or re-run CodeBERT-specific evaluation.

## Everything else

No other file in this repository exceeds GitHub's limits. The next-largest tracked file is `backend/research_eval_artifacts/random_forest/model.joblib` (~6.9 MB), well within normal git handling.
