#!/usr/bin/env bash
# Rebuilds DualVulnDroid_VulnerableTestApp.apk from source.
# Run from this directory:  bash build_apk.sh
set -e

SDK="C:/Users/User/AppData/Local/Android/Sdk"
BT="$SDK/build-tools/35.0.0"
PLATFORM="$SDK/platforms/android-35/android.jar"
OUT="DualVulnDroid_VulnerableTestApp.apk"

echo "[1/5] compiling resources..."
rm -rf build/compiled && mkdir -p build/compiled
"$BT/aapt2.exe" compile --dir res -o build/compiled/res.zip

echo "[2/5] linking APK..."
"$BT/aapt2.exe" link \
  -o build/unsigned.apk \
  -I "$PLATFORM" \
  --manifest AndroidManifest.xml \
  -A assets \
  --min-sdk-version 21 \
  --target-sdk-version 33 \
  build/compiled/res.zip

echo "[3/5] adding native-library entries (for ABI detection)..."
cp build/unsigned.apk build/withlibs.apk
python -c "
import zipfile, os
apk = 'build/withlibs.apk'
base = 'extra'
with zipfile.ZipFile(apk, 'a', zipfile.ZIP_DEFLATED) as z:
    for root, _d, files in os.walk(base):
        for f in files:
            full = os.path.join(root, f)
            arc = os.path.relpath(full, base).replace(os.sep, '/')
            z.write(full, arc)
"

echo "[4/5] ensuring test keystore exists..."
if [ ! -f build/test-fixture.keystore ]; then
  keytool -genkeypair -v -keystore build/test-fixture.keystore \
    -storepass testfixture -keypass testfixture -alias testfixture \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=DualVulnDroid Test Fixture, OU=Testing, O=DualVulnDroid, L=NA, S=NA, C=LK"
fi

echo "[5/5] aligning and signing..."
"$BT/zipalign.exe" -f -p 4 build/withlibs.apk build/aligned.apk
"$BT/apksigner.bat" sign \
  --ks build/test-fixture.keystore \
  --ks-pass pass:testfixture --key-pass pass:testfixture \
  --ks-key-alias testfixture \
  --out "$OUT" build/aligned.apk

echo "done -> $OUT"
"$BT/apksigner.bat" verify --print-certs "$OUT" | head -2
