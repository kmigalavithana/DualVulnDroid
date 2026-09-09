import os
import sys
sys.path.insert(0, r"F:\vibe cording\backend")

from apk_code_scanner import scan_apk_for_code_vulnerabilities

FIXTURE_DIR = r"F:\vibe cording\test_fixtures\apk_code_scan_fixtures"

for apk_name in [
    "cwe89_vulnerable.apk", "cwe89_safe.apk",
    "cwe295_vulnerable.apk", "cwe295_safe.apk",
    "mixed_cwe89_cwe295.apk",
]:
    print(f"=========== {apk_name} ===========")
    result = scan_apk_for_code_vulnerabilities(os.path.join(FIXTURE_DIR, apk_name))
    print(f"dex_entries_found={result.dex_entries_found} classes_total={result.classes_total} "
          f"files_scanned={result.files_scanned} files_skipped_thirdparty={result.files_skipped_thirdparty} "
          f"decompile_errors={result.decompile_errors} truncated={result.truncated}")
    print(f"findings: {len(result.findings)}")
    for f in result.findings:
        print(f"  - {f['cwe']} ({f['type']}) file={f['file']} line={f['line']} "
              f"confidence={f['confidence']} severity={f['severity']}")
        print(f"    explanation={f['explanation']}")
