# Dual-Vulnerability Detection Model Card

## Model Information
- **Model Type**: XGBoost
- **Version**: v2.0_enhanced
- **Objective**: Multi-class classification for Android code vulnerability detection
- **Classes**: 4 (s0, v0, s1, v1)
- **Target Vulnerabilities**:
  - CWE-89: SQL Injection
  - CWE-295: Improper Certificate Validation

## Performance Metrics
- **Test Accuracy**: 0.8545
- **Test Precision**: 0.8607
- **Test Recall**: 0.8545
- **Test F1-Score**: 0.8491

## Feature Engineering
- **Word-level TF-IDF**: True
- **Character-level TF-IDF**: True
- **Count Vectorization**: True
- **Total Features**: ~8000

## Data Processing
- **Splitting Strategy**: Stratified split with hash-based leak detection
- **Validation**: Cross-validation + holdout test set
- **Leakage Prevention**: ✓ Implemented

## Usage Instructions
1. Load the model: `xgb.Booster(model_file='xgboost_model.json')`
2. Load feature extractors from pickle files
3. Preprocess code using the same normalization pipeline
4. Extract features and predict

## Label Mapping
- s0 (0): SQL Injection Vulnerable
- v0 (1): Certificate Validation Vulnerable
- s1 (2): SQL Injection Secure
- v1 (3): Certificate Validation Secure

## Limitations
- Trained specifically on Android code patterns
- May require retraining for other programming languages
- Performance depends on code complexity and context

## Authors
- TG/2020/731 – W.A.T.I. Bandara (SQL Injection Focus)
- TG/2020/749 – H.P.G.L.P. Jayathilake (Certificate Validation Focus)
