# Research Questions and Final Conclusion

## RQ1: What is the best overall model?

No universal winner. **XGBoost** achieves the best macro-F1 (0.7874) and the lowest FPR (0.1467) on the frozen test set. **SVM** achieves the best FNR (0.1828) and the best ROC-AUC (0.9025). **CodeBERT** achieves the best CWE-89 recall (0.8621). Each model is strongest on a different, security-relevant axis; none dominates on every metric.

## RQ2: Which approach is safest against missed vulnerabilities?

**SVM**, by overall FNR (0.1828), among the full-coverage models (i.e. models that classify every case, as opposed to the Decision Engine's deferred-review mechanism).

## RQ3: Does Deep Learning outperform classical ML?

No, not on this dataset. LSTM has the lowest macro-F1 (0.7448) among all five evaluated models and shows visible overfitting. CodeBERT is competitive (macro-F1 0.7780, best CWE-89 recall) but does not exceed XGBoost's macro-F1 or FPR, or SVM's FNR/ROC-AUC.

## RQ4: Is the Hybrid Decision Engine useful?

Yes, especially when it auto-decides: on the frozen test set, the currently-deployed Decision Engine thresholds produce an auto-decision precision of ~0.941 and an auto-decision FNR of just 3.03% on the 32.7% of cases it decides automatically — substantially safer than any single full-coverage model on those cases. Current coverage is limited (32.7%), meaning the majority of cases (67.3%) are deferred to manual review rather than auto-decided.

## RQ5: Should production switch away from XGBoost?

No, based on current evidence. XGBoost remains the most defensible production choice because of combined research performance and mature explainability/integration.

---

## Final Production Conclusion

> "XGBoost remains the selected production model. The selection is based not on dominance across every metric, but on the combined research evidence, competitive macro-F1/false-positive performance, mature SHAP support, and established integration with the Hybrid Decision Engine, FastAPI backend, and IntelliJ plugin. SVM and CodeBERT demonstrate useful security advantages on specific metrics, while LSTM underperforms in this dataset. These alternatives remain research findings pending additional labelled data and further robustness validation."
