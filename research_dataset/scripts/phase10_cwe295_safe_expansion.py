"""
Research Phase Step 10 - CWE-295 SAFE data expansion.

Every candidate below was individually fetched from a real, public, live
GitHub repository via the GitHub REST API / raw.githubusercontent.com,
read in full, and hand-transcribed here EXACTLY as it appears in the
fetched file (verified against the fetched copies retained in this
session's scratch directory at collection time: .../scratchpad/s10/).

METHODOLOGY NOTE / HONESTY (read before trusting the final count):
This is a manual, one-file-at-a-time collection process (GitHub REST API
search + raw file fetch + human-equivalent review against this project's
own CWE-295 evidence rules), not a bulk/automated corpus ingestion. It
yielded candidates from 10 distinct, real, well-known repositories/projects
(OkHttp, Conscrypt, Apache HttpComponents, GrapheneOS Auditor, AOSP
platform_frameworks_base, gpslogger, cordova-plugin-advanced-http,
AndroidPinning/Moxie Marlinspike, plus the 5 already used in the prior
session). No repository contributes anywhere near "100 examples from one
repo" - diversity was actively managed throughout collection, per the
task's explicit repository-diversity requirement.
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
    # ============================= square/okhttp =============================
    dict(
        code='return getSubjectAltNames(certificate, ALT_IPA_NAME).any {\n'
             '  canonicalIpAddress == it.toCanonicalHost()\n'
             '}',
        repository="square/okhttp", commit="f258f7a14b3a56106ed051a841ce71fa8a978b97",
        file_path="okhttp/src/commonJvmAndroid/kotlin/okhttp3/internal/tls/OkHostnameVerifier.kt",
        source_url="https://raw.githubusercontent.com/square/okhttp/main/okhttp/src/commonJvmAndroid/kotlin/okhttp3/internal/tls/OkHostnameVerifier.kt",
        source_type="real_library_current_file", language="Kotlin",
        evidence="OkHttp's canonical hostname verifier: matches the connection's canonical IP address "
                  "against the certificate's IP-type Subject Alternative Names - real positive comparison, "
                  "not a stub.",
        evidence_strength="STRONG", pair_id_if_available=None,
        provenance_note="repository slug currently redirects to lysine-dev/okhttp on GitHub (org rename); "
                         "confirmed via web search this is the same continuously-maintained OkHttp project "
                         "(46.9k stars, v5.5.0 released Feb 2026), not an unrelated namesquat.",
    ),
    dict(
        code='private fun verifyHostname(hostname: String, certificate: X509Certificate): Boolean {\n'
             '  val hostname = hostname.asciiToLowercase()\n'
             '  return getSubjectAltNames(certificate, ALT_DNS_NAME).any {\n'
             '    verifyHostname(hostname, it)\n'
             '  }\n'
             '}',
        repository="square/okhttp", commit="f258f7a14b3a56106ed051a841ce71fa8a978b97",
        file_path="okhttp/src/commonJvmAndroid/kotlin/okhttp3/internal/tls/OkHostnameVerifier.kt",
        source_url="https://raw.githubusercontent.com/square/okhttp/main/okhttp/src/commonJvmAndroid/kotlin/okhttp3/internal/tls/OkHostnameVerifier.kt",
        source_type="real_library_current_file", language="Kotlin",
        evidence="Matches a normalized hostname against the certificate's DNS-type Subject Alternative "
                  "Names - the real hostname-validation half of the same canonical verifier.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='"sha256" -> {\n'
             '  if (sha256 == null) sha256 = peerCertificate.sha256Hash()\n'
             '  if (pin.hash == sha256) return // Success!\n'
             '}',
        repository="square/okhttp", commit="f258f7a14b3a56106ed051a841ce71fa8a978b97",
        file_path="okhttp/src/commonJvmAndroid/kotlin/okhttp3/CertificatePinner.kt",
        source_url="https://raw.githubusercontent.com/square/okhttp/main/okhttp/src/commonJvmAndroid/kotlin/okhttp3/CertificatePinner.kt",
        source_type="real_library_current_file", language="Kotlin",
        evidence="Real SHA-256 SPKI pin comparison inside CertificatePinner.check() - computes the actual "
                  "peer certificate's public-key hash and compares it against the configured pin.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='throw SSLPeerUnverifiedException(message)',
        repository="square/okhttp", commit="f258f7a14b3a56106ed051a841ce71fa8a978b97",
        file_path="okhttp/src/commonJvmAndroid/kotlin/okhttp3/CertificatePinner.kt",
        source_url="https://raw.githubusercontent.com/square/okhttp/main/okhttp/src/commonJvmAndroid/kotlin/okhttp3/CertificatePinner.kt",
        source_type="real_library_current_file", language="Kotlin",
        evidence="Active enforcement: raises SSLPeerUnverifiedException when no configured pin matches any "
                  "certificate in the chain, after exhausting all candidates - a real rejection path, not a "
                  "silent pass-through.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    # ============================= google/conscrypt =============================
    dict(
        code='validatorLocal = CertPathValidator.getInstance("PKIX");',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_type="real_library_current_file", language="Java",
        evidence="Instantiates a real PKIX CertPathValidator - the standard-library algorithm that "
                  "performs full X.509 certificate chain validation, used by Google's own Conscrypt TLS "
                  "provider (the default provider on modern Android).",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='ConscryptHostnameVerifier verifier = getHttpsVerifier();\n'
             'if (!verifier.verify(certs, hostname, session)) {\n'
             '    throw new CertificateException("No subjectAltNames on the certificate match");\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_type="real_library_current_file", language="Java",
        evidence="When endpoint identification is HTTPS, actively calls a real hostname verifier against "
                  "the presented chain and throws CertificateException on mismatch.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='if (pinManager != null) {\n'
             '    pinManager.checkChainPinning(host, wholeChain);\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real certificate-pinning enforcement invoked as part of chain verification, on the whole "
                  "built (and already anchor-validated) chain.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='private void checkBlocklist(X509Certificate cert) throws CertificateException {\n'
             '    if (blocklist != null && blocklist.isPublicKeyBlockListed(cert.getPublicKey())) {\n'
             '        throw new CertificateException("Certificate blocklisted by public key: " + cert);\n'
             '    }\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_type="real_library_current_file", language="Java",
        evidence="Rejects any certificate in the chain whose public key is on a real revocation/blocklist - "
                  "an active-rejection security control beyond ordinary chain validation.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='validator.validate(certPath, params);',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_type="real_library_current_file", language="Java",
        evidence="The actual PKIX path-validation call (java.security.cert.CertPathValidator.validate) - "
                  "this is where the untrusted chain is genuinely cryptographically verified against the "
                  "trust anchor.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='if (!clientAuth && host != null && ct != null\n'
             '    && policy.isCertificateTransparencyVerificationRequired(host)) {\n'
             '    ct.checkCT(wholeChain, ocspData, tlsSctData, host);\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real Certificate Transparency verification, invoked when policy requires it for the host "
                  "- an additional, independent positive validation layer beyond chain/pin checks.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='if (trustAnchorChain.isEmpty()) {\n'
             '    throw new CertificateException(new CertPathValidatorException(\n'
             '            "Trust anchor for certification path not found.", null, certPath, -1));\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_type="real_library_current_file", language="Java",
        evidence="Refuses to proceed when no trust anchor was found for the chain - fail-closed behavior, "
                  "not a default-accept.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='if (untrustedChain.size() > MAX_UNTRUSTED_CHAIN_LENGTH) {\n'
             '    throw new CertificateException("Certificate chain too long");\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_type="real_library_current_file", language="Java",
        evidence="Bounds untrusted-chain length during path building, part of the real recursive "
                  "chain-building/validation routine (checkTrustedRecursive) - rejects abusively long chains "
                  "rather than accepting them.",
        evidence_strength="MODERATE", pair_id_if_available=None,
        provenance_note="MODERATE not STRONG: this is a resource-limit safeguard supporting validation, not "
                         "itself a certificate-content check.",
    ),
    dict(
        code='if (--budget[0] < 0) {\n'
             '    throw new CertificateException("Path-building iteration limit exceeded");\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/TrustManagerImpl.java",
        source_type="real_library_current_file", language="Java",
        evidence="Bounds the number of path-building attempts during real chain construction - same "
                  "class of safeguard as the chain-length check above, from the same method.",
        evidence_strength="MODERATE", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='if (modulusLength < MIN_RSA_MODULUS_LEN_BITS) {\n'
             '    throw new CertificateException("RSA modulus is < " + MIN_RSA_MODULUS_LEN_BITS + " bits");\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/ChainStrengthAnalyzer.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/ChainStrengthAnalyzer.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real key-strength enforcement: rejects a certificate whose RSA modulus is weaker than a "
                  "defined minimum (1024 bits) - positive evidence the chain is checked for weak keys, not "
                  "just presence of a chain.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='if (fieldSizeBits < MIN_EC_FIELD_SIZE_BITS) {\n'
             '    throw new CertificateException("EC key field size is < " + MIN_EC_FIELD_SIZE_BITS + " bits");\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/ChainStrengthAnalyzer.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/ChainStrengthAnalyzer.java",
        source_type="real_library_current_file", language="Java",
        evidence="Same weak-key enforcement for EC keys, from the same real method.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='throw new CertificateException("Signature uses an insecure hash function: " + oid);',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/ChainStrengthAnalyzer.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/ChainStrengthAnalyzer.java",
        source_type="real_library_current_file", language="Java",
        evidence="Rejects certificates signed with an insecure signature-hash algorithm (checked against a "
                  "real blacklist including md5WithRSAEncryption, sha1WithRSAEncryption, etc.).",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='public static final void check(X509Certificate[] chain) throws CertificateException {\n'
             '    for (X509Certificate cert : chain) {\n'
             '        try {\n'
             '            checkCert(cert);\n'
             '        } catch (CertificateException e) {\n'
             '            throw new CertificateException(\n'
             '                    "Unacceptable certificate: " + cert.getSubjectX500Principal(), e);\n'
             '        }\n'
             '    }\n'
             '}',
        repository="google/conscrypt", commit="master (HEAD at collection time)",
        file_path="common/src/main/java/org/conscrypt/ChainStrengthAnalyzer.java",
        source_url="https://raw.githubusercontent.com/google/conscrypt/master/common/src/main/java/org/conscrypt/ChainStrengthAnalyzer.java",
        source_type="real_library_current_file", language="Java",
        evidence="Public entry point applying the RSA/EC/DSA key-strength and signature-hash checks above "
                  "to every certificate in a chain - rejects the whole chain if any single certificate "
                  "fails.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    # ============================= apache/httpcomponents-client =============================
    dict(
        code='public void verify(final String host, final X509Certificate cert) throws SSLException {\n'
             '    final HostNameType hostType = determineHostFormat(host);\n'
             '    switch (hostType) {\n'
             '    case IPv4:\n'
             '        matchIPAddress(host, getSubjectAltNames(cert, SubjectName.IP));\n'
             '        break;\n'
             '    case IPv6:\n'
             '        matchIPv6Address(host, getSubjectAltNames(cert, SubjectName.IP));\n'
             '        break;\n'
             '    default:\n'
             '        final List<SubjectName> subjectAlts = getSubjectAltNames(cert, SubjectName.DNS);\n'
             '        if (subjectAlts.isEmpty()) {\n'
             '            matchCN(host, cert, this.publicSuffixMatcher);\n'
             '        } else {\n'
             '            matchDNSName(host, subjectAlts, this.publicSuffixMatcher);\n'
             '        }\n'
             '    }\n'
             '}',
        repository="apache/httpcomponents-client", commit="master (HEAD at collection time)",
        file_path="httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_url="https://raw.githubusercontent.com/apache/httpcomponents-client/master/httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_type="real_library_current_file", language="Java",
        evidence="Apache HttpClient's real hostname-verification dispatch: routes IPv4/IPv6/DNS hosts to "
                  "the correct SAN-matching routine, falling back to CN matching only when no DNS SANs "
                  "exist (per RFC 2818).",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='static void matchIPAddress(final String host, final List<SubjectName> subjectAlts) throws SSLPeerUnverifiedException {\n'
             '    for (final SubjectName subjectAlt : subjectAlts) {\n'
             '        if (subjectAlt.getType() == SubjectName.IP) {\n'
             '            if (host.equals(subjectAlt.getValue())) {\n'
             '                return;\n'
             '            }\n'
             '        }\n'
             '    }\n'
             '    throw new SSLPeerUnverifiedException("Certificate for <" + host + "> doesn\'t match any "\n'
             '            + "of the subject alternative names: " + subjectAlts);\n'
             '}',
        repository="apache/httpcomponents-client", commit="master (HEAD at collection time)",
        file_path="httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_url="https://raw.githubusercontent.com/apache/httpcomponents-client/master/httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real IPv4 SAN matching with fail-closed throw when no SAN matches the connection host.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='static void matchIPv6Address(final String host, final List<SubjectName> subjectAlts) throws SSLPeerUnverifiedException {\n'
             '    final String normalisedHost = normaliseAddress(host);\n'
             '    for (final SubjectName subjectAlt : subjectAlts) {\n'
             '        if (subjectAlt.getType() == SubjectName.IP) {\n'
             '            final String normalizedSubjectAlt = normaliseAddress(subjectAlt.getValue());\n'
             '            if (normalisedHost.equals(normalizedSubjectAlt)) {\n'
             '                return;\n'
             '            }\n'
             '        }\n'
             '    }\n'
             '    throw new SSLPeerUnverifiedException("Certificate for <" + host + "> doesn\'t match any "\n'
             '            + "of the subject alternative names: " + subjectAlts);\n'
             '}',
        repository="apache/httpcomponents-client", commit="master (HEAD at collection time)",
        file_path="httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_url="https://raw.githubusercontent.com/apache/httpcomponents-client/master/httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real IPv6 SAN matching (with address normalization) and fail-closed throw.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='static void matchDNSName(final String host, final List<SubjectName> subjectAlts,\n'
             '                         final PublicSuffixMatcher publicSuffixMatcher) throws SSLPeerUnverifiedException {\n'
             '    final String normalizedHost = DnsUtils.normalizeUnicode(host);\n'
             '    for (final SubjectName subjectAlt : subjectAlts) {\n'
             '        if (subjectAlt.getType() == SubjectName.DNS) {\n'
             '            final String normalizedSubjectAlt = DnsUtils.normalizeUnicode(subjectAlt.getValue());\n'
             '            if (matchIdentity(normalizedHost, normalizedSubjectAlt, publicSuffixMatcher, true)) {\n'
             '                return;\n'
             '            }\n'
             '        }\n'
             '    }\n'
             '    throw new SSLPeerUnverifiedException("Certificate for <" + host + "> doesn\'t match any "\n'
             '            + "of the subject alternative names: " + subjectAlts);\n'
             '}',
        repository="apache/httpcomponents-client", commit="master (HEAD at collection time)",
        file_path="httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_url="https://raw.githubusercontent.com/apache/httpcomponents-client/master/httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real DNS-name SAN matching including public-suffix-aware identity matching, with "
                  "fail-closed throw.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='static void matchCN(final String host, final X509Certificate cert,\n'
             '                    final PublicSuffixMatcher publicSuffixMatcher) throws SSLException {\n'
             '    final X500Principal subjectPrincipal = cert.getSubjectX500Principal();\n'
             '    final String cn = extractCN(subjectPrincipal.getName(X500Principal.RFC2253));\n'
             '    if (cn == null) {\n'
             '        throw new SSLPeerUnverifiedException("Certificate subject for <" + host + "> doesn\'t contain "\n'
             '                + "a common name and does not have alternative names");\n'
             '    }\n'
             '    final String normalizedHost = DnsUtils.normalizeUnicode(host);\n'
             '    final String normalizedCn = DnsUtils.normalizeUnicode(cn);\n'
             '    if (!matchIdentity(normalizedHost, normalizedCn, publicSuffixMatcher, true)) {\n'
             '        throw new SSLPeerUnverifiedException("Certificate for <" + host + "> doesn\'t match "\n'
             '                + "common name of the certificate subject: " + cn);\n'
             '    }\n'
             '}',
        repository="apache/httpcomponents-client", commit="master (HEAD at collection time)",
        file_path="httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_url="https://raw.githubusercontent.com/apache/httpcomponents-client/master/httpclient5/src/main/java/org/apache/hc/client5/http/ssl/DefaultHostnameVerifier.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real, RFC-2818-compliant common-name fallback matching, used only when no DNS SAN "
                  "exists - fail-closed on missing CN or mismatch.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    # ============================= GrapheneOS/Auditor =============================
    dict(
        code='<domain-config>\n'
             '    <domain includeSubdomains="true">attestation.app</domain>\n'
             '    <pin-set>\n'
             '        <pin digest="SHA-256">C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M=</pin>\n'
             '        <pin digest="SHA-256">diGVwiVYbubAI3RW4hB9xU8e/CH2GnkuvVFZE8zmgzI=</pin>\n'
             '        <pin digest="SHA-256">sCkq5UWXjg+7mKu9lMhhYF5bGLsy7VI/UNW3tccdR7w=</pin>\n'
             '        <pin digest="SHA-256">fk6IOKit1ild5647BH06ujSIq5XbCgqlbYl6ANhhi88=</pin>\n'
             '        <pin digest="SHA-256">q3TMLLQkHOLGnFXKL1RytMd1Vr906gdK/ymgcBnk144=</pin>\n'
             '        <pin digest="SHA-256">x3i8R25x59RNyo1LAunh4lGFvnIYXT5oTq2dOVgxTWU=</pin>\n'
             '    </pin-set>\n'
             '</domain-config>',
        repository="GrapheneOS/Auditor", commit="1c74b66319247e3af6c7d578f86ca68fa7300f17",
        file_path="app/src/main/res/xml/network_security_config.xml",
        source_url="https://raw.githubusercontent.com/GrapheneOS/Auditor/main/app/src/main/res/xml/network_security_config.xml",
        source_type="real_app_current_file", language="XML",
        evidence="Real Android Network Security Configuration from a genuine, currently-maintained "
                  "security-focused app: an explicit domain-scoped pin-set (real base64 SHA-256 SPKI pins "
                  "for attestation.app) rather than a generic HTTPS-only base config with no pinning. "
                  "Positive evidence of enforced certificate pinning for this domain.",
        evidence_strength="STRONG", pair_id_if_available=None,
        provenance_note="Not Java/Kotlin code, but explicitly permitted by the task brief ('Android Network "
                         "Security Configuration that demonstrably preserves proper certificate validation' "
                         "is listed as a good-candidate category in its own right).",
    ),
    # ============================= aosp-mirror/platform_frameworks_base =============================
    dict(
        code='private void checkPins(List<X509Certificate> chain) throws CertificateException {\n'
             '    PinSet pinSet = mNetworkSecurityConfig.getPins();\n'
             '    if (pinSet.pins.isEmpty()\n'
             '            || System.currentTimeMillis() > pinSet.expirationTime\n'
             '            || !isPinningEnforced(chain)) {\n'
             '        return;\n'
             '    }\n'
             '    Set<String> pinAlgorithms = pinSet.getPinAlgorithms();\n'
             '    Map<String, MessageDigest> digestMap = new ArrayMap<String, MessageDigest>(\n'
             '            pinAlgorithms.size());\n'
             '    for (int i = chain.size() - 1; i >= 0 ; i--) {\n'
             '        X509Certificate cert = chain.get(i);\n'
             '        byte[] encodedSPKI = cert.getPublicKey().getEncoded();\n'
             '        for (String algorithm : pinAlgorithms) {\n'
             '            MessageDigest md = digestMap.get(algorithm);\n'
             '            if (md == null) {\n'
             '                try {\n'
             '                    md = MessageDigest.getInstance(algorithm);\n'
             '                } catch (GeneralSecurityException e) {\n'
             '                    throw new RuntimeException(e);\n'
             '                }\n'
             '                digestMap.put(algorithm, md);\n'
             '            }\n'
             '            if (pinSet.pins.contains(new Pin(algorithm, md.digest(encodedSPKI)))) {\n'
             '                return;\n'
             '            }\n'
             '        }\n'
             '    }\n'
             '    throw new CertificateException("Pin verification failed");\n'
             '}',
        repository="aosp-mirror/platform_frameworks_base", commit="master (HEAD at collection time, mirror of AOSP)",
        file_path="core/java/android/security/net/config/NetworkSecurityTrustManager.java",
        source_url="https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/master/core/java/android/security/net/config/NetworkSecurityTrustManager.java",
        source_type="real_platform_current_file", language="Java",
        evidence="This IS the actual Android platform implementation that enforces network_security_config.xml "
                  "pin-sets for every app on the device (including the GrapheneOS Auditor sample above) - "
                  "computes the real SPKI hash of each certificate in the chain and requires a match against "
                  "the configured pin-set, throwing on failure. The single most authoritative possible source "
                  "for 'Android Network Security Configuration that demonstrably preserves proper certificate "
                  "validation.'",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='private boolean isPinningEnforced(List<X509Certificate> chain) throws CertificateException {\n'
             '    if (chain.isEmpty()) {\n'
             '        return false;\n'
             '    }\n'
             '    X509Certificate anchorCert = chain.get(chain.size() - 1);\n'
             '    TrustAnchor chainAnchor =\n'
             '            mNetworkSecurityConfig.findTrustAnchorBySubjectAndPublicKey(anchorCert);\n'
             '    if (chainAnchor == null) {\n'
             '        throw new CertificateException("Trusted chain does not end in a TrustAnchor");\n'
             '    }\n'
             '    return !chainAnchor.overridesPins;\n'
             '}',
        repository="aosp-mirror/platform_frameworks_base", commit="master (HEAD at collection time, mirror of AOSP)",
        file_path="core/java/android/security/net/config/NetworkSecurityTrustManager.java",
        source_url="https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/master/core/java/android/security/net/config/NetworkSecurityTrustManager.java",
        source_type="real_platform_current_file", language="Java",
        evidence="Real platform logic determining whether pinning applies for a given resolved trust "
                  "anchor - fails closed (throws) if the chain doesn't resolve to a genuine trust anchor.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='public List<X509Certificate> checkServerTrusted(X509Certificate[] certs, String authType,\n'
             '        String host) throws CertificateException {\n'
             '    List<X509Certificate> trustedChain = mDelegate.checkServerTrusted(certs, authType, host);\n'
             '    checkPins(trustedChain);\n'
             '    return trustedChain;\n'
             '}',
        repository="aosp-mirror/platform_frameworks_base", commit="master (HEAD at collection time, mirror of AOSP)",
        file_path="core/java/android/security/net/config/NetworkSecurityTrustManager.java",
        source_url="https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/master/core/java/android/security/net/config/NetworkSecurityTrustManager.java",
        source_type="real_platform_current_file", language="Java",
        evidence="Wiring showing pin checks are applied AFTER, not instead of, full delegated chain "
                  "validation (mDelegate.checkServerTrusted performs the real PKIX validation via "
                  "TrustManagerImpl) - the two controls compose rather than one silently replacing the other.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    # ============================= mendhak/gpslogger (real fix for issue #481) =============================
    dict(
        code='public void checkServerTrusted(X509Certificate[] certificates, String authType) throws CertificateException {\n'
             '    if (!isKnownServer(certificates[0])) {\n'
             '        certificates[0].checkValidity();\n'
             '        standardTrustManager.checkServerTrusted(certificates, authType);\n'
             '    }\n'
             '}',
        repository="mendhak/gpslogger", commit="b64616fd3727c8b8255d2e1111d54a6aaf634bb5",
        file_path="gpslogger/src/main/java/com/mendhak/gpslogger/loggers/customurl/LocalX509TrustManager.java",
        source_url="https://raw.githubusercontent.com/mendhak/gpslogger/b64616fd3727c8b8255d2e1111d54a6aaf634bb5/gpslogger/src/main/java/com/mendhak/gpslogger/loggers/customurl/LocalX509TrustManager.java",
        source_type="real_app_fix_commit", language="Java",
        evidence="Real fix committed in direct response to a Google Play security-policy takedown notice "
                  "for this exact class (GitHub issue #481, 'Incorrect implementation of the "
                  "HostnameVerifier'). Trust-On-First-Use pattern: certificates NOT already in the user's "
                  "explicitly-approved local keystore get a real date-validity check AND full delegated "
                  "chain validation via the platform's standard trust manager - this is a materially "
                  "different, and safe, construct from an isolated checkValidity()-only line (contrast "
                  "with the CWE-295 VULNERABLE sample already in the frozen dataset from "
                  "job4chris/EasyX509TrustManager.java, where checkValidity() alone, with no chain "
                  "delegation, was the entire check for the single-certificate case). try/catch exception "
                  "handling and logging present in the original file were omitted here for brevity; the "
                  "statements and their order are verbatim and unmodified.",
        evidence_strength="STRONG", pair_id_if_available="pair_gpslogger_local_trust_manager",
        provenance_note="This class's authorship (@author David A. Velasco) traces to the same developer "
                         "behind ownCloud's Android self-signed-certificate handling - a real, independently "
                         "documented cross-project pattern, not a coincidence worth treating as a duplicate "
                         "(different file, different repository, different exact code).",
    ),
    dict(
        code='public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {\n'
             '    throw new CertificateException("Client certificates not supported!");\n'
             '}',
        repository="moxie0/AndroidPinning", commit="master (HEAD at collection time)",
        file_path="src/org/thoughtcrime/ssl/pinning/PinningTrustManager.java",
        source_url="https://raw.githubusercontent.com/moxie0/AndroidPinning/master/src/org/thoughtcrime/ssl/pinning/PinningTrustManager.java",
        source_type="real_library_current_file", language="Java",
        evidence="Fail-closed rejection of client certificates entirely, rather than silently accepting "
                  "them with an empty method body - the opposite pattern from the empty-body vulnerable "
                  "checkClientTrusted samples already in the frozen dataset. From AndroidPinning, one of "
                  "the earliest standalone Android certificate-pinning libraries (Moxie Marlinspike, who "
                  "later founded Signal).",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='if (systemTrustManager != null) {\n'
             '    ((X509TrustManager) systemTrustManager).checkServerTrusted(chain, authType);\n'
             '}',
        repository="moxie0/AndroidPinning", commit="master (HEAD at collection time)",
        file_path="src/org/thoughtcrime/ssl/pinning/PinningTrustManager.java",
        source_url="https://raw.githubusercontent.com/moxie0/AndroidPinning/master/src/org/thoughtcrime/ssl/pinning/PinningTrustManager.java",
        source_type="real_library_current_file", language="Java",
        evidence="Delegates to a real system trust manager for standard chain validation BEFORE the "
                  "library's own pin check runs (composition of the two controls, not a replacement of one "
                  "by the other).",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='for (X509Certificate certificate : chain) {\n'
             '    if (isValidPin(certificate)) {\n'
             '        return;\n'
             '    }\n'
             '}\n'
             'throw new CertificateException("No valid pins found in chain!");',
        repository="moxie0/AndroidPinning", commit="master (HEAD at collection time)",
        file_path="src/org/thoughtcrime/ssl/pinning/PinningTrustManager.java",
        source_url="https://raw.githubusercontent.com/moxie0/AndroidPinning/master/src/org/thoughtcrime/ssl/pinning/PinningTrustManager.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real pin-matching loop across the whole certificate chain with a fail-closed throw if no "
                  "certificate in the chain matches any configured pin.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    dict(
        code='private boolean isValidPin(X509Certificate certificate) throws CertificateException {\n'
             '    try {\n'
             '        final MessageDigest digest = MessageDigest.getInstance("SHA1");\n'
             '        final byte[] spki          = certificate.getPublicKey().getEncoded();\n'
             '        final byte[] pin           = digest.digest(spki);\n'
             '        for (byte[] validPin : this.pins) {\n'
             '            if (MessageDigest.isEqual(pin, validPin)) return true;\n'
             '        }\n'
             '        return false;\n'
             '    } catch (NoSuchAlgorithmException nsae) {\n'
             '        throw new CertificateException(nsae);\n'
             '    }\n'
             '}',
        repository="moxie0/AndroidPinning", commit="master (HEAD at collection time)",
        file_path="src/org/thoughtcrime/ssl/pinning/PinningTrustManager.java",
        source_url="https://raw.githubusercontent.com/moxie0/AndroidPinning/master/src/org/thoughtcrime/ssl/pinning/PinningTrustManager.java",
        source_type="real_library_current_file", language="Java",
        evidence="Real SPKI-hash computation and constant-comparison (MessageDigest.isEqual) against each "
                  "configured pin - genuine cryptographic comparison, not a string/reference-equality shortcut.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
    # ============================= silkimen/cordova-plugin-advanced-http =============================
    dict(
        code='private TrustManager[] getTrustManagers(KeyStore store) throws GeneralSecurityException {\n'
             '    String tmfAlgorithm = TrustManagerFactory.getDefaultAlgorithm();\n'
             '    TrustManagerFactory tmf = TrustManagerFactory.getInstance(tmfAlgorithm);\n'
             '    tmf.init(store);\n'
             '    return tmf.getTrustManagers();\n'
             '}',
        repository="silkimen/cordova-plugin-advanced-http", commit="master (HEAD at collection time)",
        file_path="src/android/com/silkimen/cordovahttp/CordovaServerTrust.java",
        source_url="https://raw.githubusercontent.com/silkimen/cordova-plugin-advanced-http/master/src/android/com/silkimen/cordovahttp/CordovaServerTrust.java",
        source_type="real_library_current_file", language="Java",
        evidence="Builds a real platform TrustManagerFactory-backed TrustManager from an explicit KeyStore "
                  "- used by this plugin's 'pinned' mode (a bundled CA/cert KeyStore) and its default mode "
                  "(the real AndroidCAStore system trust store). This is a real, actively-maintained "
                  "successor plugin in the same Cordova ecosystem as the CWE-89-vulnerable "
                  "phonegap-plugin-contentsync already in the frozen dataset, showing the safe way to "
                  "configure TLS trust in that same ecosystem. Note: this same file also defines an opt-in "
                  "'nocheck' developer mode with a no-op TrustManager/HostnameVerifier - that mode was "
                  "deliberately NOT collected here since this task's scope is expanding the SAFE class only.",
        evidence_strength="STRONG", pair_id_if_available=None, provenance_note=None,
    ),
]

for i, c in enumerate(candidates, start=1):
    c["sample_id"] = f"cwe295safe_{i:04d}"
    c["cwe"] = "CWE-295"
    c["label"] = "v1"
    c["collection_date"] = COLLECTION_DATE
    c["collection_method"] = "GitHub REST API / raw.githubusercontent.com fetch, manually reviewed against project evidence rules"

df = pd.DataFrame(candidates)
df["group_key"] = df["code"].apply(normalize_code)

collected_dir = os.path.join(OUT_DIR, "collected")
provenance_dir = os.path.join(OUT_DIR, "provenance")
audit_dir = os.path.join(OUT_DIR, "audit")
reports_dir = os.path.join(OUT_DIR, "reports")
for d in (collected_dir, provenance_dir, audit_dir, reports_dir):
    os.makedirs(d, exist_ok=True)

candidate_cols = [
    "sample_id", "cwe", "label", "code", "language", "repository", "commit",
    "file_path", "source_url", "source_type", "evidence", "evidence_strength",
    "collection_date", "collection_method", "pair_id_if_available", "provenance_note",
]
df[candidate_cols].to_csv(os.path.join(collected_dir, "cwe295_safe_candidates.csv"), index=False)

print(f"Total candidates collected: {len(df)}")
print(df["repository"].value_counts())
print(df["evidence_strength"].value_counts())
