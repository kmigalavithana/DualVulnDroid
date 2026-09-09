#!/usr/bin/env python3
"""
Builds the 5 real, compiled APK fixtures used to validate
backend/apk_code_scanner.py end-to-end (real APK -> extraction ->
decompilation -> the existing CWE-89/CWE-295 detection pipeline ->
result). Not part of the research dataset - these are validation
fixtures only, analogous to test_fixtures/vulnerable_test_apk/.

Requires (same toolchain test_fixtures/vulnerable_test_apk/build_apk.sh
already depends on): a JDK, and Android SDK build-tools 35.0.0 +
platforms/android-35 at the path below.

Run from this directory: python build_fixtures.py
"""
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = r"C:\Users\User\AppData\Local\Android\Sdk"
BUILD_TOOLS = os.path.join(SDK, "build-tools", "35.0.0")
ANDROID_JAR = os.path.join(SDK, "platforms", "android-35", "android.jar")
AAPT2 = os.path.join(BUILD_TOOLS, "aapt2.exe")
D8 = os.path.join(BUILD_TOOLS, "d8.bat")
ZIPALIGN = os.path.join(BUILD_TOOLS, "zipalign.exe")
APKSIGNER = os.path.join(BUILD_TOOLS, "apksigner.bat")
JAVAC = shutil.which("javac") or r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot\bin\javac.exe"
KEYSTORE = os.path.join(HERE, "build", "test-fixture.keystore")

FIXTURES = [
    ("cwe89_vulnerable", "com.dualvulndroid.fixture.cwe89vuln", ["src/cwe89_vulnerable/VulnDao.java"]),
    ("cwe89_safe", "com.dualvulndroid.fixture.cwe89safe", ["src/cwe89_safe/SafeDao.java"]),
    ("cwe295_vulnerable", "com.dualvulndroid.fixture.cwe295vuln", ["src/cwe295_vulnerable/VulnCertClient.java"]),
    ("cwe295_safe", "com.dualvulndroid.fixture.cwe295safe", ["src/cwe295_safe/SafeCertClient.java"]),
    ("mixed_cwe89_cwe295", "com.dualvulndroid.fixture.mixed", ["src/mixed/VulnDao.java", "src/mixed/VulnCertClient.java"]),
]


def run(cmd, **kwargs):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, **kwargs)


def build_one(name, package, sources):
    work = os.path.join(HERE, "build", name)
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    classes_dir = os.path.join(work, "classes")
    os.makedirs(classes_dir)

    # 1. compile
    run([JAVAC, "-cp", ANDROID_JAR, "-d", classes_dir] + [os.path.join(HERE, s) for s in sources])

    # 2. dex
    dex_dir = os.path.join(work, "dex")
    os.makedirs(dex_dir)
    class_files = []
    for root, _dirs, files in os.walk(classes_dir):
        for f in files:
            if f.endswith(".class"):
                class_files.append(os.path.join(root, f))
    run([D8, "--output", dex_dir] + class_files)

    # 3. manifest
    manifest_path = os.path.join(work, "AndroidManifest.xml")
    with open(os.path.join(HERE, "manifest_template.xml"), encoding="utf-8") as f:
        manifest = f.read().replace("{package}", package)
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest)

    # 4. aapt2 link (no resources needed - manifest uses a literal label)
    unsigned = os.path.join(work, "unsigned.apk")
    run([
        AAPT2, "link", "-o", unsigned, "-I", ANDROID_JAR,
        "--manifest", manifest_path,
        "--min-sdk-version", "24", "--target-sdk-version", "34",
    ])

    # 5. add classes.dex into the linked APK (plain zip append - this is
    #    OUR OWN build-time script writing into a fresh, just-created zip
    #    we fully control, not extracting an untrusted upload, so normal
    #    zipfile.write() is fine here; apk_code_scanner.py's runtime
    #    UPLOAD-side path never extracts anything to disk, see its
    #    module docstring).
    withdex = os.path.join(work, "withdex.apk")
    shutil.copy(unsigned, withdex)
    with zipfile.ZipFile(withdex, "a", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(dex_dir, "classes.dex"), "classes.dex")

    # 6. zipalign + sign (reusing the same test-only keystore as
    #    test_fixtures/vulnerable_test_apk)
    aligned = os.path.join(work, "aligned.apk")
    run([ZIPALIGN, "-f", "-p", "4", withdex, aligned])

    out_apk = os.path.join(HERE, f"{name}.apk")
    run([
        APKSIGNER, "sign",
        "--ks", KEYSTORE, "--ks-pass", "pass:testfixture", "--key-pass", "pass:testfixture",
        "--ks-key-alias", "testfixture",
        "--out", out_apk, aligned,
    ])
    print(f"done -> {out_apk}")
    return out_apk


def ensure_keystore():
    # *.keystore is gitignored (same as test_fixtures/vulnerable_test_apk/
    # build/test-fixture.keystore) - self-generate a fresh test-only one
    # here too, rather than requiring it to already exist on a clean
    # checkout.
    if os.path.isfile(KEYSTORE):
        return
    os.makedirs(os.path.dirname(KEYSTORE), exist_ok=True)
    keytool = shutil.which("keytool") or r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot\bin\keytool.exe"
    run([
        keytool, "-genkeypair", "-v", "-keystore", KEYSTORE,
        "-storepass", "testfixture", "-keypass", "testfixture", "-alias", "testfixture",
        "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
        "-dname", "CN=DualVulnDroid APK Code-Scan Fixture, OU=Testing, O=DualVulnDroid, L=NA, S=NA, C=LK",
    ])


def main():
    ensure_keystore()
    for name, package, sources in FIXTURES:
        build_one(name, package, sources)


if __name__ == "__main__":
    main()
