import zipfile
import os

manifest_content = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.vulnapp">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.READ_CONTACTS" />
    
    <application android:usesCleartextTraffic="true">
    </application>
</manifest>
"""

with open("AndroidManifest.xml", "w") as f:
    f.write(manifest_content)

with zipfile.ZipFile("f:/ANTY/test_app_vuln.apk", "w") as z:
    z.write("AndroidManifest.xml")

os.remove("AndroidManifest.xml")
print("Successfully generated f:/ANTY/test_app_vuln.apk")
