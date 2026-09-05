"""
Phase 3/4 - Collect additional REAL data + vulnerable/fixed pair tracking.

IMPORTANT - methodology and honesty note (read before trusting the counts):
Every sample below was individually fetched from a real, public, currently-
live GitHub repository via the GitHub REST API / raw.githubusercontent.com
(never fabricated, never paraphrased), read in full by a human-equivalent
review pass, and hand-transcribed here EXACTLY as it appears in the fetched
file (verified byte-for-byte against the fetched copies still present under
this session's scratch directory at collection time). Each row's provenance
(repository, exact commit SHA, file path, source URL) is real and was
independently confirmed via the GitHub API, not guessed.

This is a small, high-quality batch (17 samples), not the 250/class target
stated as "preferred" in the task brief. That target is explicitly NOT met.
See research_dataset/reports/FINAL_DATASET_REPORT.md Part 15 ("remaining
limitations") for why: collecting hundreds of independently-provenanced,
individually-verified real samples requires either (a) bulk authenticated
GitHub code search / cloning infrastructure not available in this execution
environment, or (b) a much larger number of manual fetch-and-review cycles
than were performed here. Per the task's own Phase 5 instruction ("If
250/250 cannot be achieved for a class, DO NOT fabricate or synthesize
labels. Instead report AVAILABLE / CONFIRMED / INSUFFICIENT and explain the
limitation"), this script reports the true, small, real number rather than
padding it.
"""
import json
import os
import sys

import pandas as pd

ROOT = r"F:\vibe cording"
OUT_DIR = os.path.join(ROOT, "research_dataset")

sys.path.insert(0, os.path.join(ROOT, "backend"))
from ml.feature_pipeline import normalize_code  # noqa: E402

COLLECTION_DATE = "2026-09-02"

# ---------------------------------------------------------------------------
# CWE-295 samples
# ---------------------------------------------------------------------------
cwe295_samples = [
    # --- VULNERABLE ---
    dict(
        cwe="CWE-295", label="v0", language="Java",
        code='public void checkServerTrusted(X509Certificate[] chain,\n'
             '                               String authType) throws CertificateException {\n'
             '}',
        repository="phonegap/phonegap-plugin-contentsync",
        commit="867685a40db875216e758233cd9ff8a114351344",
        file_path="src/android/Sync.java",
        source_url="https://raw.githubusercontent.com/phonegap/phonegap-plugin-contentsync/867685a40db875216e758233cd9ff8a114351344/src/android/Sync.java",
        source_type="real_app_pre_fix_commit",
        evidence="Empty checkServerTrusted() body inside a TrustManager literally named trustAllCerts, "
                  "wired into an SSLContext used for HTTPS downloads. Accepts any server certificate chain "
                  "unconditionally - a real, publicly reported vulnerability (GitHub issue #185, 'Google Play "
                  "Blocker: Unsafe implementation of TrustManager'), fixed by removing this code entirely in "
                  "commit dbafa4c63a83a7c0e6d25e97d552fc4bb3570ba7.",
        evidence_strength="STRONG",
        collection_method="GitHub REST API (commit history + raw file fetch), manually reviewed",
        duplicate_group=None, license_if_available="Apache-2.0",
        pair_id="pair_phonegap_sync_trust",
    ),
    dict(
        cwe="CWE-295", label="v0", language="Java",
        code='public void checkClientTrusted(X509Certificate[] chain,\n'
             '                               String authType) throws CertificateException {\n'
             '}',
        repository="phonegap/phonegap-plugin-contentsync",
        commit="867685a40db875216e758233cd9ff8a114351344",
        file_path="src/android/Sync.java",
        source_url="https://raw.githubusercontent.com/phonegap/phonegap-plugin-contentsync/867685a40db875216e758233cd9ff8a114351344/src/android/Sync.java",
        source_type="real_app_pre_fix_commit",
        evidence="Empty checkClientTrusted() body in the same trustAllCerts TrustManager as above - accepts "
                  "any client certificate unconditionally. Same fix commit removed it entirely.",
        evidence_strength="STRONG",
        collection_method="GitHub REST API (commit history + raw file fetch), manually reviewed",
        duplicate_group=None, license_if_available="Apache-2.0",
        pair_id="pair_phonegap_sync_trust",
    ),
    dict(
        cwe="CWE-295", label="v0", language="Java",
        code='public boolean verify(String hostname, SSLSession session) {\n'
             '    return true;\n'
             '}',
        repository="phonegap/phonegap-plugin-contentsync",
        commit="867685a40db875216e758233cd9ff8a114351344",
        file_path="src/android/Sync.java",
        source_url="https://raw.githubusercontent.com/phonegap/phonegap-plugin-contentsync/867685a40db875216e758233cd9ff8a114351344/src/android/Sync.java",
        source_type="real_app_pre_fix_commit",
        evidence="HostnameVerifier.verify() unconditionally returns true (named DO_NOT_VERIFY in source), "
                  "disabling hostname validation entirely - accepts a valid cert for ANY hostname. Part of the "
                  "same reported/fixed vulnerability as the two rows above.",
        evidence_strength="STRONG",
        collection_method="GitHub REST API (commit history + raw file fetch), manually reviewed",
        duplicate_group=None, license_if_available="Apache-2.0",
        pair_id="pair_phonegap_sync_trust",
    ),
    dict(
        cwe="CWE-295", label="v0", language="Java",
        code='sc.init(null, trustAllCerts, new java.security.SecureRandom());',
        repository="phonegap/phonegap-plugin-contentsync",
        commit="867685a40db875216e758233cd9ff8a114351344",
        file_path="src/android/Sync.java",
        source_url="https://raw.githubusercontent.com/phonegap/phonegap-plugin-contentsync/867685a40db875216e758233cd9ff8a114351344/src/android/Sync.java",
        source_type="real_app_pre_fix_commit",
        evidence="SSLContext initialized with the all-trusting TrustManager array (trustAllCerts) and then "
                  "installed as the connection's SSLSocketFactory - the sink where the vulnerable TrustManager "
                  "is actually wired into the live HTTPS connection.",
        evidence_strength="STRONG",
        collection_method="GitHub REST API (commit history + raw file fetch), manually reviewed",
        duplicate_group=None, license_if_available="Apache-2.0",
        pair_id="pair_phonegap_sync_trust",
    ),
    dict(
        cwe="CWE-295", label="v0", language="Java",
        code='if ((certificates != null) && (certificates.length == 1)) {\n'
             '    certificates[0].checkValidity();\n'
             '}',
        repository="job4chris/Android-Self-Signed-SSL-certificate-example",
        commit="master (HEAD at collection time; file carries an internal @version tag from an earlier "
                "Apache HttpClient revision: 'EasyX509TrustManager.java 765355 2009-04-15')",
        file_path="src/org/ssl/EasyX509TrustManager.java",
        source_url="https://raw.githubusercontent.com/job4chris/Android-Self-Signed-SSL-certificate-example/master/src/org/ssl/EasyX509TrustManager.java",
        source_type="real_repo_current_file",
        evidence="For the single-certificate case (typical of a self-signed cert with no chain), the ONLY "
                  "check performed is certificates[0].checkValidity(), which verifies the certificate's date "
                  "range only - it does NOT check that the certificate is signed by any trusted CA. An "
                  "attacker-presented, currently-valid self-signed certificate passes this check unconditionally. "
                  "This exact 'EasyX509TrustManager' class/pattern is a documented historical vulnerability in "
                  "the Apache HttpClient ecosystem this file is derived from.",
        evidence_strength="STRONG",
        collection_method="GitHub raw file fetch, manually reviewed",
        duplicate_group=None, license_if_available="Apache-2.0",
        pair_id=None,
    ),
    dict(
        cwe="CWE-295", label="v0", language="Java",
        code='public void checkClientTrusted(X509Certificate[] chain, String authType) throws java.security.cert.CertificateException {\n'
             '}',
        repository="rfreedman/android-ssl",
        commit="master (HEAD at collection time)",
        file_path="src/main/java/com/chariotsolutions/example/http/CustomTrustManager.java",
        source_url="https://raw.githubusercontent.com/rfreedman/android-ssl/master/src/main/java/com/chariotsolutions/example/http/CustomTrustManager.java",
        source_type="real_repo_current_file",
        evidence="Empty checkClientTrusted() body - accepts any client certificate unconditionally. The "
                  "author's own comment on this method claims it is 'never invoked by client, only used in "
                  "server-side implementations' in this app's actual deployment context, which is a real "
                  "mitigating factor this evidence cannot independently verify from the code alone - hence "
                  "MODERATE rather than STRONG.",
        evidence_strength="MODERATE",
        collection_method="GitHub raw file fetch, manually reviewed",
        duplicate_group=None, license_if_available="unspecified (no LICENSE file found in repo root)",
        pair_id=None,
    ),
    # --- SAFE ---
    dict(
        cwe="CWE-295", label="v1", language="Java",
        code='standardTrustManager.checkClientTrusted(certificates, authType);',
        repository="job4chris/Android-Self-Signed-SSL-certificate-example",
        commit="master (HEAD at collection time)",
        file_path="src/org/ssl/EasyX509TrustManager.java",
        source_url="https://raw.githubusercontent.com/job4chris/Android-Self-Signed-SSL-certificate-example/master/src/org/ssl/EasyX509TrustManager.java",
        source_type="real_repo_current_file",
        evidence="Full, unconditional delegation of client-certificate validation to the platform's own "
                  "TrustManagerFactory-obtained standard trust manager - positive evidence of real validation, "
                  "not merely absence of a bypass.",
        evidence_strength="STRONG",
        collection_method="GitHub raw file fetch, manually reviewed",
        duplicate_group=None, license_if_available="Apache-2.0",
        pair_id=None,
    ),
    dict(
        cwe="CWE-295", label="v1", language="Java",
        code='standardTrustManager.checkServerTrusted(certificates, authType);',
        repository="job4chris/Android-Self-Signed-SSL-certificate-example",
        commit="master (HEAD at collection time)",
        file_path="src/org/ssl/EasyX509TrustManager.java",
        source_url="https://raw.githubusercontent.com/job4chris/Android-Self-Signed-SSL-certificate-example/master/src/org/ssl/EasyX509TrustManager.java",
        source_type="real_repo_current_file",
        evidence="Multi-certificate (full chain) branch: delegates entirely to the platform's standard trust "
                  "manager for server-certificate validation - the defensible/safe counterpart to the "
                  "single-certificate bypass captured as a vulnerable sample from this same file above.",
        evidence_strength="STRONG",
        collection_method="GitHub raw file fetch, manually reviewed",
        duplicate_group=None, license_if_available="Apache-2.0",
        pair_id=None,
    ),
    dict(
        cwe="CWE-295", label="v1", language="Java",
        code='originalX509TrustManager.checkServerTrusted(chain, authType);',
        repository="rfreedman/android-ssl",
        commit="master (HEAD at collection time)",
        file_path="src/main/java/com/chariotsolutions/example/http/CustomTrustManager.java",
        source_url="https://raw.githubusercontent.com/rfreedman/android-ssl/master/src/main/java/com/chariotsolutions/example/http/CustomTrustManager.java",
        source_type="real_repo_current_file",
        evidence="Primary path of checkServerTrusted() delegates to a TrustManagerFactory-obtained default "
                  "X509TrustManager before any custom fallback logic runs - positive evidence of real "
                  "certificate-chain validation.",
        evidence_strength="STRONG",
        collection_method="GitHub raw file fetch, manually reviewed",
        duplicate_group=None, license_if_available="unspecified (no LICENSE file found in repo root)",
        pair_id=None,
    ),
    dict(
        cwe="CWE-295", label="v1", language="Java",
        code='baselineTrustManager.checkServerTrusted(chain, authType, serverHostname);',
        repository="datatheorem/TrustKit-Android",
        commit="23d3572413b3ffecc0e3366ed10cbce655630abe",
        file_path="trustkit/src/main/java/com/datatheorem/android/trustkit/pinning/PinningTrustManager.java",
        source_url="https://raw.githubusercontent.com/datatheorem/TrustKit-Android/master/trustkit/src/main/java/com/datatheorem/android/trustkit/pinning/PinningTrustManager.java",
        source_type="real_library_current_file",
        evidence="Certificate-pinning TrustManager first delegates full chain validation to a baseline "
                  "(system) trust manager before performing additional pin verification - genuine positive "
                  "validation, not a bypass. TrustKit is a real, widely-used Android certificate-pinning "
                  "library (Data Theorem).",
        evidence_strength="STRONG",
        collection_method="GitHub REST API (commit lookup) + raw file fetch, manually reviewed",
        duplicate_group=None, license_if_available="MIT",
        pair_id=None,
    ),
    dict(
        cwe="CWE-295", label="v1", language="Java",
        code='throw new CertificateException("Certificate validation failed for " + serverHostname);',
        repository="datatheorem/TrustKit-Android",
        commit="23d3572413b3ffecc0e3366ed10cbce655630abe",
        file_path="trustkit/src/main/java/com/datatheorem/android/trustkit/pinning/PinningTrustManager.java",
        source_url="https://raw.githubusercontent.com/datatheorem/TrustKit-Android/master/trustkit/src/main/java/com/datatheorem/android/trustkit/pinning/PinningTrustManager.java",
        source_type="real_library_current_file",
        evidence="Pin-validation failure path actively throws CertificateException, enforcing rejection of "
                  "a chain that fails pinning - positive, active-enforcement evidence of safe behavior "
                  "(the opposite of an empty/no-op check).",
        evidence_strength="STRONG",
        collection_method="GitHub REST API (commit lookup) + raw file fetch, manually reviewed",
        duplicate_group=None, license_if_available="MIT",
        pair_id=None,
    ),
    dict(
        cwe="CWE-295", label="v1", language="Java",
        code='trustManagerFactory.init((KeyStore) null);',
        repository="datatheorem/TrustKit-Android",
        commit="23d3572413b3ffecc0e3366ed10cbce655630abe",
        file_path="trustkit/src/main/java/com/datatheorem/android/trustkit/pinning/SystemTrustManager.java",
        source_url="https://raw.githubusercontent.com/datatheorem/TrustKit-Android/master/trustkit/src/main/java/com/datatheorem/android/trustkit/pinning/SystemTrustManager.java",
        source_type="real_library_current_file",
        evidence="Initializes a TrustManagerFactory with the platform's default KeyStore (null = use system "
                  "default) specifically to retrieve and return the platform's real X509TrustManager for reuse "
                  "- the standard, documented, safe way to obtain platform-default certificate validation.",
        evidence_strength="STRONG",
        collection_method="GitHub REST API (commit lookup) + raw file fetch, manually reviewed",
        duplicate_group=None, license_if_available="MIT",
        pair_id=None,
    ),
]

# ---------------------------------------------------------------------------
# CWE-89 samples (owncloud/android, CVE-2023-24804 / GHSL-2022-059)
# ---------------------------------------------------------------------------
cwe89_samples = [
    dict(
        cwe="CWE-89", label="s0", language="Kotlin",
        code='count = db.delete(\n'
             '    ProviderTableMeta.FILE_TABLE_NAME,\n'
             '    ProviderTableMeta._ID + "=" +\n'
             '            uri.pathSegments[1] +\n'
             '            if (!TextUtils.isEmpty(where))\n'
             '                " AND ($where)"\n'
             '            else\n'
             '                "", whereArgs\n'
             ')',
        repository="owncloud/android",
        commit="53e4dee38022a851aa5d8950cfc6bd8848574e15",
        file_path="owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_url="https://raw.githubusercontent.com/owncloud/android/53e4dee38022a851aa5d8950cfc6bd8848574e15/owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_type="real_app_cve_confirmed",
        evidence="CVE-2023-24804 (GHSL-2022-059, GitHub Security Lab advisory). uri.pathSegments[1] (an "
                  "external, caller-controlled ContentProvider URI segment) is concatenated directly into the "
                  "SQL selection string passed to db.delete(), with no escaping - a real, publicly disclosed, "
                  "CVE-assigned SQL injection reaching a live production Android app's ContentProvider.",
        evidence_strength="STRONG",
        collection_method="WebSearch (GitHub Security Lab advisory) + GitHub API tag/commit resolution + raw "
                           "file fetch, manually reviewed",
        duplicate_group=None, license_if_available="GPL-2.0",
        pair_id="pair_owncloud_fileprovider_id_where",
    ),
    dict(
        cwe="CWE-89", label="s0", language="Kotlin",
        code='sqlQuery.appendWhere(ProviderTableMeta._ID + "=" + uri.pathSegments[1])',
        repository="owncloud/android",
        commit="53e4dee38022a851aa5d8950cfc6bd8848574e15",
        file_path="owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_url="https://raw.githubusercontent.com/owncloud/android/53e4dee38022a851aa5d8950cfc6bd8848574e15/owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_type="real_app_cve_confirmed",
        evidence="Same CVE-2023-24804 disclosure. appendWhere() appends the raw, unescaped concatenated string "
                  "(including the external uri.pathSegments[1] value) directly onto the query builder's WHERE "
                  "clause - the FILE_TABLE_NAME query path uses the non-escaping appendWhere(), in contrast to "
                  "the CAPABILITIES query path in the same file which uses appendWhereEscapeString() (see the "
                  "paired safe sample from this same file).",
        evidence_strength="STRONG",
        collection_method="WebSearch (GitHub Security Lab advisory) + GitHub API tag/commit resolution + raw "
                           "file fetch, manually reviewed",
        duplicate_group=None, license_if_available="GPL-2.0",
        pair_id="pair_owncloud_fileprovider_appendwhere",
    ),
    dict(
        cwe="CWE-89", label="s1", language="Kotlin",
        code='sqlQuery.appendWhereEscapeString(ProviderTableMeta._ID + "=" + uri.pathSegments[1])',
        repository="owncloud/android",
        commit="53e4dee38022a851aa5d8950cfc6bd8848574e15",
        file_path="owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_url="https://raw.githubusercontent.com/owncloud/android/53e4dee38022a851aa5d8950cfc6bd8848574e15/owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_type="real_app_cve_confirmed",
        evidence="Structurally identical operation to the vulnerable appendWhere() sample above (same file, "
                  "same _ID pattern) but for the CAPABILITIES query path, using appendWhereEscapeString() - "
                  "Android's SQLiteQueryBuilder API specifically designed to safely escape a value before "
                  "embedding it in a WHERE clause. Positive evidence of safe handling, from the same "
                  "CVE-disclosed file, of the same untrusted input.",
        evidence_strength="STRONG",
        collection_method="WebSearch (GitHub Security Lab advisory) + GitHub API tag/commit resolution + raw "
                           "file fetch, manually reviewed",
        duplicate_group=None, license_if_available="GPL-2.0",
        pair_id="pair_owncloud_fileprovider_appendwhere",
    ),
    dict(
        cwe="CWE-89", label="s1", language="Kotlin",
        code='count = db.delete(ProviderTableMeta.CAPABILITIES_TABLE_NAME, where, whereArgs)',
        repository="owncloud/android",
        commit="53e4dee38022a851aa5d8950cfc6bd8848574e15",
        file_path="owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_url="https://raw.githubusercontent.com/owncloud/android/53e4dee38022a851aa5d8950cfc6bd8848574e15/owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_type="real_app_cve_confirmed",
        evidence="Standard parameterized SQLiteDatabase.delete(table, whereClause, whereArgs) usage - where "
                  "and whereArgs are passed through as separate arguments (no concatenation), and this same "
                  "function has a guard (if (where != null && whereArgs == null) throw IllegalArgumentException) "
                  "enforcing that a non-null selection must come with parameterized args. This is the safe "
                  "counterpart, in the same CVE-disclosed file, to the vulnerable SINGLE_FILE-case concatenation "
                  "sample above.",
        evidence_strength="STRONG",
        collection_method="WebSearch (GitHub Security Lab advisory) + GitHub API tag/commit resolution + raw "
                           "file fetch, manually reviewed",
        duplicate_group=None, license_if_available="GPL-2.0",
        pair_id="pair_owncloud_fileprovider_id_where",
    ),
    dict(
        cwe="CWE-89", label="s1", language="Kotlin",
        code='CAPABILITIES -> return db.update(ProviderTableMeta.CAPABILITIES_TABLE_NAME, values, selection, selectionArgs)',
        repository="owncloud/android",
        commit="53e4dee38022a851aa5d8950cfc6bd8848574e15",
        file_path="owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_url="https://raw.githubusercontent.com/owncloud/android/53e4dee38022a851aa5d8950cfc6bd8848574e15/owncloudApp/src/main/java/com/owncloud/android/providers/FileContentProvider.kt",
        source_type="real_app_cve_confirmed",
        evidence="Standard parameterized SQLiteDatabase.update(table, values, selection, selectionArgs) usage "
                  "- selection and selectionArgs passed through separately, no string concatenation.",
        evidence_strength="STRONG",
        collection_method="WebSearch (GitHub Security Lab advisory) + GitHub API tag/commit resolution + raw "
                           "file fetch, manually reviewed",
        duplicate_group=None, license_if_available="GPL-2.0",
        pair_id=None,
    ),
]

all_samples = cwe295_samples + cwe89_samples

rows = []
for i, s in enumerate(all_samples, start=1):
    row = dict(s)
    row["sample_id"] = f"collected_{i:04d}"
    row["collection_date"] = COLLECTION_DATE
    rows.append(row)

df = pd.DataFrame(rows)
df["group_key"] = df["code"].apply(normalize_code)

# ---- Duplicate/leakage check against the ORIGINAL 1687-row dataset (read-only) ----
raw = pd.read_csv(os.path.join(ROOT, "dataset .csv"))
raw_norm = set(raw["vulnerable_line"].apply(normalize_code))
df["overlaps_original_dataset_normalized"] = df["group_key"].isin(raw_norm)

# ---- Internal duplicate check among the newly collected samples ----
internal_dupe_mask = df["group_key"].duplicated(keep=False)
df["internal_normalized_duplicate"] = internal_dupe_mask

collected_dir = os.path.join(OUT_DIR, "collected")
cols = [
    "sample_id", "cwe", "label", "language", "code", "repository", "commit",
    "file_path", "source_url", "source_type", "evidence", "evidence_strength",
    "collection_method", "duplicate_group", "license_if_available",
    "collection_date", "pair_id",
    "overlaps_original_dataset_normalized", "internal_normalized_duplicate",
]
df[cols].to_csv(os.path.join(collected_dir, "collected_samples.csv"), index=False)

# ---- provenance.csv (subset of fields the task specifies for provenance) ----
provenance_cols = [
    "sample_id", "repository", "file_path", "commit", "language", "cwe",
    "label", "source_url", "source_type", "collection_method",
    "license_if_available", "collection_date",
]
df[provenance_cols].to_csv(os.path.join(OUT_DIR, "provenance.csv"), index=False)

# ---- vulnerable_fixed_pairs.csv ----
pair_rows = []
for pid, group in df.dropna(subset=["pair_id"]).groupby("pair_id"):
    vuln_ids = group[group["label"].isin(["s0", "v0"])]["sample_id"].tolist()
    safe_ids = group[group["label"].isin(["s1", "v1"])]["sample_id"].tolist()
    if vuln_ids and safe_ids:
        for v_id in vuln_ids:
            for s_id in safe_ids:
                pair_rows.append({"pair_id": pid, "vulnerable_sample_id": v_id, "fixed_sample_id": s_id})
    elif vuln_ids and not safe_ids:
        for v_id in vuln_ids:
            pair_rows.append({"pair_id": pid, "vulnerable_sample_id": v_id, "fixed_sample_id": None})

pairs_df = pd.DataFrame(pair_rows)
pairs_df.to_csv(os.path.join(OUT_DIR, "vulnerable_fixed_pairs.csv"), index=False)

summary = {
    "total_collected": int(len(df)),
    "by_cwe_and_label": df.groupby(["cwe", "label"]).size().to_dict(),
    "by_evidence_strength": df.groupby(["cwe", "evidence_strength"]).size().to_dict(),
    "overlaps_original_dataset_normalized_count": int(df["overlaps_original_dataset_normalized"].sum()),
    "internal_normalized_duplicate_count": int(df["internal_normalized_duplicate"].sum()),
    "pairs_recorded": int(len(pairs_df)),
    "repositories_used": sorted(df["repository"].unique().tolist()),
}
with open(os.path.join(OUT_DIR, "audit", "phase3_4_collection_summary.json"), "w", encoding="utf-8") as f:
    json.dump({k: (v if not isinstance(v, dict) else {str(kk): vv for kk, vv in v.items()}) for k, v in summary.items()}, f, indent=2)

print(json.dumps({k: (v if not isinstance(v, dict) else {str(kk): vv for kk, vv in v.items()}) for k, v in summary.items()}, indent=2))
