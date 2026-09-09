# DualVulnDroid — APK Code-Scan Fixtures (Flutter APK Scan implementation phase)

Five deliberately minimal, real, compiled, zipaligned, signed Android packages built solely to
exercise `backend/apk_code_scanner.py` end-to-end: **real APK file → real DEX extraction → real
androguard decompilation → the existing `predictor.py`/`dataflow.py` CWE-89/CWE-295 pipeline (the
same one the IDE plugin uses) → result**. Each has no Activity, no resources beyond a manifest
label, and no functionality — just one or two classes planting an exact, known vulnerable or safe
pattern. None of this is fed to an endpoint as raw source text; every finding below was produced by
uploading the actual `.apk` file through the real `POST /upload-apk` flow.

Rebuild with `python build_fixtures.py` (needs Android SDK build-tools 35.0.0 + platform android-35
and a JDK, both already present on this machine — see `test_fixtures/vulnerable_test_apk/build_apk.sh`
for the same toolchain used elsewhere in this project). The signing keystore is gitignored
(`*.keystore`) and self-generated on first run, same as that other fixture's keystore.

## Fixtures and real, verified results

| Fixture | Planted | Expected | Verified result |
|---|---|---|---|
| `cwe89_vulnerable.apk` | `db.rawQuery("...'" + userInput + "'", null)` | 1 CWE-89 finding | **Yes** — 1 finding, `SQL Injection`, line 9 |
| `cwe89_safe.apk` | `db.rawQuery("... = ?", new String[]{userInput})` | 0 findings | **Yes** — 0 findings |
| `cwe295_vulnerable.apk` | `HostnameVerifier.verify()` unconditionally `return true` | 1 CWE-295 finding | **Yes** — 1 finding, `Certificate Validation` |
| `cwe295_safe.apk` | `HostnameVerifier` delegates to the real default verifier; `X509TrustManager` throws `CertificateException` | 0 findings | **Yes** — 0 findings |
| `mixed_cwe89_cwe295.apk` | Both the CWE-89 and CWE-295 vulnerable classes together | 2 findings, 1 of each, no cross-contamination | **Yes** — `cwe89Count=1`, `cwe295Count=1`, `totalFindings=2` |

## Why a decompiler-output normalization step was needed

`predictor.py`/`dataflow.py` expect ordinary Java/Kotlin source text (curly braces, real call syntax
like `.rawQuery(`, literal `+` string concatenation). An APK only contains compiled DEX bytecode.
Decompiling these fixtures with `androguard`'s `DecompilerDAD` and feeding the RAW output straight
into the unmodified analyzer produced **zero findings on the vulnerable fixtures** — a real, verified
false negative — because:

1. `javac` always lowers `"a" + b + "c"` to `new StringBuilder().append(a).append(b).append(c).toString()`.
   The unmodified `dataflow.py`'s `_has_concatenation()` only recognizes literal `+`/`.plus(`/`concat(`.
2. DEX has no boolean type — `return true;` compiles to `return 1;`. The unmodified analyzer's
   `HostnameVerifier.verify()` check looks for a literal `return true`.
3. A genuinely empty method (`{ }`) decompiles to an explicit `{ return; }` (DAD always makes the
   implicit end-of-method return visible) — read as "has a non-empty body" and downgraded from
   VULNERABLE to SUSPICIOUS by the unmodified analyzer's empty-body check.

`apk_code_scanner.py`'s `normalize_decompiled_source()` resugars all three back to the form a human
would have written, verified against these exact fixtures, **without changing `dataflow.py`/
`predictor.py` in any way** — that pipeline is shared with the already-audited IDE plugin and the
thesis's frozen evaluation results, and is never modified for this bridge.

## Safety note

These packages contain no exploit code, no payload, and no real endpoints — same EICAR-file-style
intent as `test_fixtures/vulnerable_test_apk/`. Do not publish to an app store; keep the
`-fixture`-labeled package names so none is ever mistaken for a real build.
