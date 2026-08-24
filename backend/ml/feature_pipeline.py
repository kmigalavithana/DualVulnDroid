"""
The SINGLE shared feature-construction pipeline used by both model
training (ml/train.py, ml/dataset_prep.py) and live inference
(predictor.py). This exists specifically so training and inference can
never drift apart - there is exactly one place that turns code text into
a feature vector.

Run scripts in this package from the `backend/` directory, e.g.:
    cd backend
    python -m ml.dataset_prep
    python -m ml.train

(matches the existing project convention - predictor.py already assumes
backend/ is the working directory for its own relative artifact paths).
"""

import json
import os
import re
import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer

from security_features import extract_security_feature_vector, FEATURE_NAMES as SECURITY_FEATURE_NAMES

# Same vectorizer configuration as the originally shipped artifacts
# (xgboost_artifacts/preprocessing_config.json), kept unchanged so the
# text-feature portion of the pipeline is a controlled variable in the
# ablation study - only the added security features vary between configs.
WORD_VECTORIZER_PARAMS = dict(max_features=5000, ngram_range=(1, 3))
CHAR_VECTORIZER_PARAMS = dict(max_features=2000, ngram_range=(2, 5), analyzer="char")
COUNT_VECTORIZER_PARAMS = dict(max_features=1000, ngram_range=(1, 2))


def load_production_feature_config(artifact_dir="ml/artifacts"):
    """
    Reads ml/artifacts/training_config.json to find out which security
    feature subset the CURRENTLY PRODUCTION model was trained with (the
    4 ablation configs use different subsets - see ml/train.py). Anything
    that loads xgboost_model.json for inference must build its feature
    matrix with these exact same settings, or XGBoost will reject the
    column-count mismatch (or worse, silently misalign columns).

    Returns (include_security: bool, security_feature_subset: list|None).
    Defaults to the full hybrid feature set if no training_config.json is
    found (e.g. before ml/train.py has ever been run).
    """
    config_path = os.path.join(artifact_dir, "training_config.json")
    if not os.path.exists(config_path):
        return True, None
    with open(config_path) as f:
        config = json.load(f)
    return (
        config.get("production_include_security_features", True),
        config.get("production_security_feature_subset", None),
    )


def fit_vectorizers(train_codes):
    """Fits fresh word/char/count vectorizers on the TRAINING split only
    (never on val/test - that would leak vocabulary from held-out data)."""
    normalized = [normalize_code(c) for c in train_codes]

    word_vectorizer = TfidfVectorizer(**WORD_VECTORIZER_PARAMS).fit(normalized)
    char_vectorizer = TfidfVectorizer(**CHAR_VECTORIZER_PARAMS).fit(normalized)
    count_vectorizer = CountVectorizer(**COUNT_VECTORIZER_PARAMS).fit(normalized)

    return word_vectorizer, char_vectorizer, count_vectorizer


def normalize_code(code: str) -> str:
    """
    Text normalization applied before TF-IDF/count vectorization.
    Moved here verbatim from the original predictor.py so there is a
    single implementation shared by training and inference.
    """
    code = code.lower()
    code = re.sub(r'//.*', ' ', code)
    code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.DOTALL)
    code = re.sub(r'"[^"]*"', ' STRING ', code)
    code = re.sub(r"'[^']*'", " CHAR ", code)
    code = re.sub(r'\b\d+\b', ' NUMBER ', code)
    code = re.sub(r'\s+', ' ', code)
    return code.strip()


def build_text_feature_names(word_vectorizer, char_vectorizer, count_vectorizer) -> list:
    """Feature names for the TF-IDF/count portion, in the exact hstack order."""
    return list(
        list(word_vectorizer.get_feature_names_out())
        + list(char_vectorizer.get_feature_names_out())
        + list(count_vectorizer.get_feature_names_out())
    )


def full_feature_names(word_vectorizer, char_vectorizer, count_vectorizer,
                        include_security=True, security_feature_subset=None) -> list:
    """Must be called with the SAME include_security/security_feature_subset
    used to build the matching feature matrix, or the names will misalign
    with the columns (see build_feature_matrix)."""
    names = build_text_feature_names(word_vectorizer, char_vectorizer, count_vectorizer)
    if include_security:
        names = names + list(security_feature_subset if security_feature_subset is not None else SECURITY_FEATURE_NAMES)
    return names


def build_feature_matrix(codes, word_vectorizer, char_vectorizer, count_vectorizer,
                          include_security=True, security_feature_subset=None):
    """
    codes: iterable of raw code strings (NOT pre-normalized - normalization
           happens here, identically for train and inference).
    *_vectorizer: already-FITTED sklearn vectorizers (fit only on the
           training split - see ml/train.py).
    include_security: if False, returns only the TF-IDF/count matrix
           (used for the "baseline" ablation configuration).
    security_feature_subset: optional list of feature names (subset of
           SECURITY_FEATURE_NAMES) to include instead of all of them -
           used by the ablation study to isolate structural vs data-flow
           feature groups.

    Returns a scipy sparse matrix, shape (n_samples, n_features).
    """
    codes = list(codes)
    normalized = [normalize_code(c) for c in codes]

    word_matrix = word_vectorizer.transform(normalized)
    char_matrix = char_vectorizer.transform(normalized)
    count_matrix = count_vectorizer.transform(normalized)

    parts = [word_matrix, char_matrix, count_matrix]

    if include_security:
        if security_feature_subset is None:
            sec_rows = [extract_security_feature_vector(c) for c in codes]
        else:
            idx = [SECURITY_FEATURE_NAMES.index(n) for n in security_feature_subset]
            sec_rows = [[extract_security_feature_vector(c)[i] for i in idx] for c in codes]
        sec_matrix = csr_matrix(np.array(sec_rows, dtype=np.float64))
        parts.append(sec_matrix)

    return hstack(parts).tocsr()
