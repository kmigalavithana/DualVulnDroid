"""
SmartApp: a separate product/module within the DualVulnDroid backend.

Everything SmartApp needs (the Google Play data provider, normalization,
and API routes) lives ONLY in this package. Nothing here imports, is
imported by, or otherwise touches predictor.py, dataflow.py,
security_features.py, the XGBoost model/ml/ training code, the existing
/predict or /developer/* security routes, or the IntelliJ/Android Studio
plugin. See router.py's module docstring for the mounted route prefix.
"""
