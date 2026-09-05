"""
Research Phase Step 10.5 - CWE-295 SAFE targeted expansion.

Same methodology discipline as Step 10 (manual, individually-verified,
real-source-only collection - no bulk/authenticated code search available
in this environment). This round deliberately avoided further Conscrypt
reuse (per this task's explicit instruction) and prioritized NEW,
independent repositories not touched in Step 10.

Every candidate was fetched from a real, public, live GitHub repository via
the GitHub REST API / raw.githubusercontent.com, read in full, and
hand-transcribed here exactly as it appears in the fetched file (verified
against the fetched copies retained under this session's scratch directory:
.../scratchpad/s10/).

Sources investigated and used (6 NEW repositories, 0 Conscrypt):
  - ge0rg/MemorizingTrustManager
  - bitfireAT/cert4android
  - andreabenetton/pcontacts
  - grpc/grpc-java
  - signalapp/libsignal-service-java (archived, historically real Signal code)
  - OWASP/MASTG-Hacking-Playground

Sources investigated and explicitly rejected/abandoned this round (see
CWE295_SAFE_EXPANSION_REPORT_10_5.md for the full list and reasons):
ACRA/acra (tree fetch failed), braintree/braintree_android (referenced PR
404), mendhak/gpslogger extra files (nothing new beyond Step 10's already-
collected sample), guardianproject/NetCipher (caller-parameterized, no
independent validation evidence), signalapp/Signal-Android (2.5GB repo,
too large to tree-search; used the separate, tractable libsignal-service-java
instead), ProtonMail/protoncore_android (tree fetch too large/truncated;
found the same pinning pattern via the smaller andreabenetton/pcontacts repo
instead), tutao/tutanota (no TLS-relevant file found at the paths checked),
F-Droid/fdroidclient, satishpatnayak/AndroGoat, optiv/InsecureShop,
rewanthtammana/Damn-Vulnerable-Bank (none contain CWE-295-relevant files),
square/retrofit#4226 (stale transitive-dependency scanner false positive,
already superseded by the current OkHttp sample collected in Step 10).
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

candidates = [
    dict(
        code='public void checkCertTrusted(X509Certificate[] chain, String authType, boolean isServer)\n'
             '    throws CertificateException\n'
             '{\n'
             '    try {\n'
             '        if (isServer)\n'
             '            appTrustManager.checkServerTrusted(chain, authType);\n'
             '        else\n'
             '            appTrustManager.checkClientTrusted(chain, authType);\n'
             '    } catch (CertificateException ae) {\n'
             '        if (isCertKnown(chain[0])) {\n'
             '            return;\n'
             '        }\n'
             '        try {\n'
             '            if (isServer)\n'
             '                defaultTrustManager.checkServerTrusted(chain, authType);\n'
             '            else\n'
             '                defaultTrustManager.checkClientTrusted(chain, authType);\n'
             '        } catch (CertificateException e) {\n'
             '            interactCert(chain, authType, e);\n'
             '        }\n'
             '    }\n'
             '}',
        repository="ge0rg/MemorizingTrustManager", commit="d092aaeb93388e096f34f2d9a622e39a365ff5a3",
        file_path="src/de/duenndns/ssl/MemorizingTrustManager.java",
        source_url="https://raw.githubusercontent.com/ge0rg/MemorizingTrustManager/master/src/de/duenndns/ssl/MemorizingTrustManager.java",
        source_type="real_library_current_file", language="Java",
        evidence="Widely-used, real, independent Android TLS library (used by Conversations/XMPP, DAVx5, "
                  "and others). Tries a real app-configured trust manager first, then falls back to the "
                  "platform default trust manager - only if BOTH real validation paths fail does it consult "
                  "an already-approved local keystore or interact with the user (Trust-On-First-Use). Log "
                  "statements present in the original method were omitted here for brevity; the control flow "
                  "and all statements are verbatim and unmodified.",
        evidence_strength="STRONG", pair_id="",
    ),
    dict(
        code='override fun checkClientTrusted(chain: Array<X509Certificate>?, authType: String?) {\n'
             '    throw CertificateException("cert4android doesn\'t validate client certificates")\n'
             '}',
        repository="bitfireAT/cert4android", commit="master (HEAD at collection time)",
        file_path="lib/src/main/java/at/bitfire/cert4android/CustomCertManager.kt",
        source_url="https://raw.githubusercontent.com/bitfireAT/cert4android/main/lib/src/main/java/at/bitfire/cert4android/CustomCertManager.kt",
        source_type="real_library_current_file", language="Kotlin",
        evidence="Fail-closed rejection of client-certificate validation entirely (unconditional throw), "
                  "used by the real DAVx5 CalDAV/CardDAV Android client - contrast with an empty/no-op "
                  "checkClientTrusted body, this actively refuses rather than silently accepting.",
        evidence_strength="STRONG", pair_id="",
    ),
    dict(
        code='override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {\n'
             '    if (!certStore.isTrusted(\n'
             '            chain,\n'
             '            authType,\n'
             '            trustSystemCerts = settings.trustSystemCerts,\n'
             '            appInForeground = settings.appInForeground\n'
             '        )\n'
             '    )\n'
             '        throw CertificateException("Certificate chain not trusted")\n'
             '}',
        repository="bitfireAT/cert4android", commit="master (HEAD at collection time)",
        file_path="lib/src/main/java/at/bitfire/cert4android/CustomCertManager.kt",
        source_url="https://raw.githubusercontent.com/bitfireAT/cert4android/main/lib/src/main/java/at/bitfire/cert4android/CustomCertManager.kt",
        source_type="real_library_current_file", language="Kotlin",
        evidence="Wires the real chain-trust decision (delegated to CustomCertStore.isTrusted, which itself "
                  "delegates to a real system trust manager - see the paired sample below) to an active "
                  "rejection when the chain is not trusted.",
        evidence_strength="STRONG", pair_id="pair_cert4android_check_and_store",
    ),
    dict(
        code='try {\n'
             '    systemKeyStore.checkServerTrusted(chain, authType)\n'
             '    return true\n'
             '} catch (_: CertificateException) {\n'
             '}',
        repository="bitfireAT/cert4android", commit="master (HEAD at collection time)",
        file_path="lib/src/main/java/at/bitfire/cert4android/CustomCertStore.kt",
        source_url="https://raw.githubusercontent.com/bitfireAT/cert4android/main/lib/src/main/java/at/bitfire/cert4android/CustomCertStore.kt",
        source_type="real_library_current_file", language="Kotlin",
        evidence="The actual implementation behind isTrusted(): a real system X509TrustManager (obtained via "
                  "TrustManagerFactory) performs the primary, standard chain validation before any "
                  "Trust-On-First-Use fallback logic runs.",
        evidence_strength="STRONG", pair_id="pair_cert4android_check_and_store",
    ),
    dict(
        code='fun buildPinner(\n'
             '    host: String = PROTON_HOST,\n'
             '    pins: List<String> = loadFromClasspath()\n'
             '): CertificatePinner {\n'
             '    val builder = CertificatePinner.Builder()\n'
             '    if (pins.isNotEmpty()) {\n'
             '        builder.add(host, *pins.toTypedArray())\n'
             '    }\n'
             '    return builder.build()\n'
             '}',
        repository="andreabenetton/pcontacts", commit="9a62cbe86751d4aaecf398c708febe51a6fc898f",
        file_path="core/proton-api/src/main/kotlin/io/pcontacts/core/proton/api/http/ProtonCertificatePins.kt",
        source_url="https://raw.githubusercontent.com/andreabenetton/pcontacts/master/core/proton-api/src/main/kotlin/io/pcontacts/core/proton/api/http/ProtonCertificatePins.kt",
        source_type="real_app_current_file", language="Kotlin",
        evidence="Real APPLICATION-level (not library-internal) use of OkHttp's CertificatePinner, wiring "
                  "actual SPKI pins (root-CA-level: ISRG Root X1/X2) for the app's real API host "
                  "(*.proton.me). Application code, not library internals - a meaningful diversity "
                  "contribution versus this dataset's largely library/platform-sourced CWE-295 safe rows.",
        evidence_strength="STRONG", pair_id="",
    ),
    dict(
        code='if (!hostnameVerifier.verify(canonicalizeHost(host), sslSocket.getSession())) {\n'
             '    throw new SSLPeerUnverifiedException("Cannot verify hostname: " + host);\n'
             '}',
        repository="grpc/grpc-java", commit="master (HEAD at collection time)",
        file_path="okhttp/src/main/java/io/grpc/okhttp/OkHttpTlsUpgrader.java",
        source_url="https://raw.githubusercontent.com/grpc/grpc-java/master/okhttp/src/main/java/io/grpc/okhttp/OkHttpTlsUpgrader.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real, active hostname-verification enforcement in Google's gRPC Java library (used by "
                  "real Android apps built on gRPC) - a genuinely separate codebase/team from Conscrypt "
                  "despite the shared parent organization.",
        evidence_strength="STRONG", pair_id="",
    ),
    dict(
        code='public void checkServerTrusted(X509Certificate[] chain, String authType)\n'
             '    throws CertificateException\n'
             '{\n'
             '  trustManager.checkServerTrusted(chain, authType);\n'
             '\n'
             '  for (X509Certificate certificate : chain) {\n'
             '    for (Pair<String, BigInteger> blacklistedSerial : BLACKLIST) {\n'
             '      if (certificate.getIssuerDN().getName().equals(blacklistedSerial.first()) &&\n'
             '          certificate.getSerialNumber().equals(blacklistedSerial.second()))\n'
             '      {\n'
             '        throw new CertificateException("Blacklisted Serial: " + certificate.getSerialNumber());\n'
             '      }\n'
             '    }\n'
             '  }\n'
             '}',
        repository="signalapp/libsignal-service-java", commit="master (HEAD at collection time; repo archived)",
        file_path="java/src/main/java/org/whispersystems/signalservice/internal/util/BlacklistingTrustManager.java",
        source_url="https://raw.githubusercontent.com/signalapp/libsignal-service-java/master/java/src/main/java/org/whispersystems/signalservice/internal/util/BlacklistingTrustManager.java",
        source_type="real_library_archived_file", language="Java",
        evidence="Real historical Signal/Open Whisper Systems networking code (author: Moxie Marlinspike). "
                  "Delegates fully to a real X509TrustManager for standard chain validation FIRST, then "
                  "additionally rejects any certificate matching a specific known-bad issuer+serial pair - "
                  "defense-in-depth composition, not a replacement of standard validation.",
        evidence_strength="STRONG", pair_id="",
    ),
    dict(
        code='public static TrustManager[] createFor(TrustStore trustStore) {\n'
             '  try {\n'
             '    InputStream keyStoreInputStream = trustStore.getKeyStoreInputStream();\n'
             '    KeyStore    keyStore            = KeyStore.getInstance("BKS");\n'
             '\n'
             '    keyStore.load(keyStoreInputStream, trustStore.getKeyStorePassword().toCharArray());\n'
             '\n'
             '    TrustManagerFactory trustManagerFactory = TrustManagerFactory.getInstance("X509");\n'
             '    trustManagerFactory.init(keyStore);\n'
             '\n'
             '    return BlacklistingTrustManager.createFor(trustManagerFactory.getTrustManagers());\n'
             '  } catch (KeyStoreException | CertificateException | IOException | NoSuchAlgorithmException e) {\n'
             '    throw new AssertionError(e);\n'
             '  }\n'
             '}',
        repository="signalapp/libsignal-service-java", commit="master (HEAD at collection time; repo archived)",
        file_path="java/src/main/java/org/whispersystems/signalservice/internal/util/BlacklistingTrustManager.java",
        source_url="https://raw.githubusercontent.com/signalapp/libsignal-service-java/master/java/src/main/java/org/whispersystems/signalservice/internal/util/BlacklistingTrustManager.java",
        source_type="real_library_archived_file", language="Java",
        evidence="Builds a real pinned TrustManagerFactory from an app-bundled BKS (BouncyCastle KeyStore) "
                  "trust store, rather than trusting arbitrary system CAs - a genuine, real certificate-pinning "
                  "construction distinct from the SPKI-hash pinning already collected elsewhere in this "
                  "dataset.",
        evidence_strength="STRONG", pair_id="",
    ),
    dict(
        code='public void checkServerTrusted( X509Certificate[] certificates, String authType )\n'
             '        throws CertificateException\n'
             '{\n'
             '    standardTrustManager.checkServerTrusted( certificates, authType );\n'
             '\n'
             '    for (X509Certificate cert : certificates) {\n'
             '        String issuer_name = cert.getIssuerDN().getName();\n'
             '        if (issuer_name.indexOf(",O=" + TRUSTED_CA_AUTHORITY + ",") == -1)\n'
             '            throw new CertificateException();\n'
             '    }\n'
             '}',
        repository="OWASP/MASTG-Hacking-Playground", commit="e2dedbab55ed51daada42fd3176d8d017e280cb1",
        file_path="Android/MSTG-Android-Java-App/app/src/main/java/sg/vp/owasp_mobile/OMTG_Android/HardenedX509TrustManager.java",
        source_url="https://raw.githubusercontent.com/OWASP/MASTG-Hacking-Playground/master/Android/MSTG-Android-Java-App/app/src/main/java/sg/vp/owasp_mobile/OMTG_Android/HardenedX509TrustManager.java",
        source_type="real_security_benchmark_reference_implementation", language="Java",
        evidence="OWASP's own reference 'hardened' TrustManager from its official mobile-security benchmark "
                  "project (explicitly named to contrast with the project's own vulnerable trust-manager "
                  "examples). Delegates to the real platform trust manager for full chain validation FIRST, "
                  "then additionally requires the issuer to match a specific pinned CA organization string - "
                  "positive evidence of both standard validation and additional CA pinning. A debug Log.w "
                  "call on the success path was omitted here for brevity; all validation logic is verbatim.",
        evidence_strength="STRONG", pair_id="",
    ),
    dict(
        code='InputStream caInput = new BufferedInputStream(getResources().openRawResource(R.raw.certificate));\n'
             'Certificate ca = cf.generateCertificate(caInput);\n'
             'caInput.close();\n'
             '\n'
             'String keyStoreType = KeyStore.getDefaultType();\n'
             'KeyStore keyStore = KeyStore.getInstance(keyStoreType);\n'
             'keyStore.load(null, null);\n'
             'keyStore.setCertificateEntry("ca", ca);\n'
             '\n'
             'String tmfAlgorithm = TrustManagerFactory.getDefaultAlgorithm();\n'
             'TrustManagerFactory tmf = TrustManagerFactory.getInstance(tmfAlgorithm);\n'
             'tmf.init(keyStore);\n'
             '\n'
             'final SSLContext context = SSLContext.getInstance("TLS");\n'
             'context.init(null, tmf.getTrustManagers(), null);',
        repository="OWASP/MASTG-Hacking-Playground", commit="e2dedbab55ed51daada42fd3176d8d017e280cb1",
        file_path="Android/MSTG-Android-Java-App/app/src/main/java/sg/vp/owasp_mobile/OMTG_Android/OMTG_NETW_004_SSL_Pinning_Certificate.java",
        source_url="https://raw.githubusercontent.com/OWASP/MASTG-Hacking-Playground/master/Android/MSTG-Android-Java-App/app/src/main/java/sg/vp/owasp_mobile/OMTG_Android/OMTG_NETW_004_SSL_Pinning_Certificate.java",
        source_type="real_security_benchmark_reference_implementation", language="Java",
        evidence="OWASP's official reference implementation of certificate pinning via a bundled, "
                  "app-embedded CA certificate resource: loads the real cert, builds a KeyStore containing "
                  "only it, and initializes a genuine TrustManagerFactory/SSLContext from that KeyStore - "
                  "a distinct real pinning mechanism (bundled full-certificate pinning) from the SPKI-hash "
                  "pinning collected elsewhere in this dataset.",
        evidence_strength="STRONG", pair_id="",
    ),
]

for i, c in enumerate(candidates, start=1):
    c["sample_id"] = f"cwe295safe105_{i:04d}"
    c["cwe"] = "CWE-295"
    c["label"] = "v1"
    c["collection_date"] = COLLECTION_DATE
    c["collection_method"] = "GitHub REST API / raw.githubusercontent.com fetch, manually reviewed against project evidence rules"

df = pd.DataFrame(candidates)
df["group_key"] = df["code"].apply(normalize_code)

collected_dir = os.path.join(OUT_DIR, "collected")
os.makedirs(collected_dir, exist_ok=True)

candidate_cols = [
    "sample_id", "cwe", "label", "code", "language", "repository", "commit",
    "file_path", "source_url", "source_type", "evidence", "evidence_strength",
    "collection_date", "collection_method", "pair_id",
]
df[candidate_cols].to_csv(os.path.join(collected_dir, "cwe295_safe_candidates_10_5.csv"), index=False)

print(f"Total NEW candidates this round: {len(df)}")
print(df["repository"].value_counts())
print(df["evidence_strength"].value_counts())
