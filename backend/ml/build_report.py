"""
Assembles the final Phase 3 research report artifact by injecting the
real, already-computed JSON results (ml/reports/*.json,
ml/data/dataset_report.json) into a static HTML/CSS/JS template. No
numbers are hand-typed here - everything renders from the actual files
on disk.
"""
import json
import os

REPORT_DIR = "ml/reports"
DATA_DIR = "ml/data"
OUT_PATH = r"C:\Users\User\AppData\Local\Temp\claude\f--vibe-cording\72b14021-7812-4edb-8285-257bca3811bb\scratchpad\dualvulndroid_phase3_report.html"

with open(os.path.join(REPORT_DIR, "report_data_trimmed.json")) as f:
    MODEL_DATA = json.load(f)
with open(os.path.join(DATA_DIR, "dataset_report.json")) as f:
    DATASET = json.load(f)
with open(os.path.join(REPORT_DIR, "shap_summary.json")) as f:
    SHAP = json.load(f)
with open(os.path.join("ml/artifacts", "training_config.json")) as f:
    TRAIN_CONFIG = json.load(f)
with open(os.path.join(REPORT_DIR, "model_comparison.json")) as f:
    FULL = json.load(f)
with open(os.path.join("ml/artifacts", "decision_engine_thresholds.json")) as f:
    CALIB = json.load(f)

EXPD = FULL["experiment_d_hybrid_decision_engine"]

TEMPLATE = open("ml/report_template.html", encoding="utf-8").read()

TEMPLATE = TEMPLATE.replace("__MODEL_DATA_JSON__", json.dumps(MODEL_DATA))
TEMPLATE = TEMPLATE.replace("__DATASET_JSON__", json.dumps(DATASET))
TEMPLATE = TEMPLATE.replace("__SHAP_JSON__", json.dumps(SHAP))
TEMPLATE = TEMPLATE.replace("__TRAIN_CONFIG_JSON__", json.dumps(TRAIN_CONFIG))
TEMPLATE = TEMPLATE.replace("__EXPD_JSON__", json.dumps(EXPD))
TEMPLATE = TEMPLATE.replace("__CALIB_JSON__", json.dumps(CALIB))

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(TEMPLATE)

print(f"wrote {OUT_PATH}, {len(TEMPLATE)} bytes")
