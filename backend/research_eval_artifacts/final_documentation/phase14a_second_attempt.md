# Phase 14A — Second Attempt: Headless IntelliJ Platform Integration Tests

**Outcome: real GUI sandbox still NOT launched (this agent has no screen-capture/GUI-interaction tooling - a capability gap resources don't fix). Instead, 9 new tests were written and run that drive the REAL registered plugin classes inside a real (headless) IntelliJ Platform test fixture against the REAL running FastAPI backend. All 9 passed.**

## 1. Resource check (before launching anything)

| Resource | Value |
|---|---|
| Free RAM | 7.43 GB (of 15.75 GB total) |
| Free C: | 7.57 GB |
| Free F: | 169.57 GB |
| Leftover Python/Java/Gradle processes | none found |

A large improvement over the prior attempt (2.70-3.12 GB free RAM, 0.43 GB free C:). This resolved the resource-based stop condition. What it did NOT resolve: this agent has no tool that can observe a rendered GUI window, simulate keyboard/mouse input into it, or capture a real screenshot of one. That is a tooling limitation of the agent environment, not of the machine.

Given a choice between (a) escalating to real IntelliJ-Platform-test-fixture-driven verification, (b) launching `runIde` for the user to drive manually, or (c) leaving the gap as-is, the user chose (a).

## 2. What was built

`DualVulnDroid/src/test/kotlin/com/dualvulndroid/dualvulndroid/LiveAnnotatorIntegrationTest.kt` - a `BasePlatformTestCase`-based test class. Unlike every other test in this module (which tests isolated Kotlin functions directly, no IDE machinery involved), this class drives the actual registered plugin classes exactly as the live IDE does:

- `CodeSentinelAnnotator.collectInformation()` / `.doAnnotate()` - the real `ExternalAnnotator` registered in `plugin.xml` for Java/Kotlin, making a real HTTP call to the real FastAPI backend (started for this session at `http://127.0.0.1:8000`, current production XGBoost model, current production Decision Engine thresholds - both unchanged).
- `ShowFindingDetailsIntention` - the real Alt+Enter intention.
- `SqlFixLocator` / `CertificateFixLocator` + the real `SafeSqlQuickFixJava` / `SafeHostnameVerifierQuickFixJava` classes - the exact PSI-mutation code path the live editor uses, including the real, unmodified `FixVerificationRunner.runAsync()` side effect.

This is a genuine escalation in rigor over the pre-existing 46 unit tests (which never touch the annotator/intention/locator classes at all), while remaining honestly short of a human/agent watching pixels: `.apply()`'s `Annotation`/tooltip HTML construction, and `MyToolWindow`'s Swing rendering, are not re-exercised - only the real data these are built from.

## 3. A real finding surfaced while building this

The first draft used a plain, single-parameter SQL concatenation (`String query = "..." + userId; db.rawQuery(query, null);` - the same idiom used elsewhere in this project's fixtures). Verified against the real backend, this landed on `decision=SUSPICIOUS_REVIEW`, `vulnerable=false` - meaning **the real-time annotator does not highlight it at all**, since `CodeSentinelAnnotator.doAnnotate()` only builds a result when `response.vulnerable==true`. This is not a bug; it is the current production Decision Engine's calibrated, conservative behavior (documented in Phase 12/13: 32.7% auto-decision coverage, most cases deferred to manual review) showing up concretely at the level of "would a developer actually see a red squiggly for this line." The test fixture was changed to a traced-external-source variant (`getIntent().getStringExtra(...)`, the same shape as the backend's own `test_api.py::TRACED_SQL` fixture), verified to cross the real `VULNERABLE` threshold (confidence 60.78%, severity CRITICAL) before being used. Both variants are real; only the second one is currently visible as a live annotation under production thresholds.

A second, smaller finding: in the Quick-Fix test fixture (with an unrelated `unrelatedMethod()` above the vulnerable code), the real backend's per-line detections also flagged the unrelated method's declaration line as "SQL Injection" alongside the real sink line - a real, observed characteristic of the current line-level detection output, not a test artifact. The test was made robust to this by selecting the finding whose line text actually contains the sink call (`rawQuery`) rather than just matching on type.

## 4. Real evidence captured (from JUnit stdout, this run)

| Case | Result |
|---|---|
| A. SQL vulnerable | `severity=CRITICAL confidence=75.19 decision=VULNERABLE evidenceCount=3` - 1 real annotation-worthy finding |
| B. SQL safe (parameterized) | `findings=0` - no annotation, correctly |
| C. Certificate vulnerable | `severity=CRITICAL confidence=99.46 decision=VULNERABLE` |
| D. Certificate safe | `findings=0` |
| E. Unrelated safe | `findings=0` |
| Alt+Enter | Intention reports itself available (`"DualVulnDroid: Show finding details"`, `startInWriteAction=false`); `invoke()` runs the real `MyToolWindow.showFinding()` path without throwing, against a really-registered `ToolWindow`. `isActive`/`isVisible` were logged (`false`/`false`) but NOT asserted on - not reliably meaningful in a headless light fixture with no real window manager. |
| Quick Fix - SQL | Real diff applied (314 → 322 chars); unrelated method and method signature byte-for-byte untouched; old concatenation gone. Real synchronous re-scan: `vulnerable=false`. Independently, the real async `FixVerificationRunner` also fired for real and reported *"Before: SQL Injection - 76% confidence / After: SQL Injection not detected / Result: Vulnerability appears resolved"* - two independent real confirmations. |
| Quick Fix - Certificate | Real diff applied; unrelated field untouched; delegating replacement (`getDefaultHostnameVerifier`) present. Real re-scan: `vulnerable=false`. |
| Unsupported certificate pattern | The real backend did not flag this particular shape as vulnerable at all (`findings=0`), so live fix-availability wasn't directly exercised for it this time - the "never auto-fix this shape" guarantee remains proven at the locator/unit-test level (`CertificateFixAnalyzerTest`). |

## 5. Test suite result

`./gradlew test --rerun` (forced fresh execution, `Task :test` genuinely ran, no `UP-TO-DATE`):

- **Build time:** 38s, `BUILD SUCCESSFUL`
- **Result:** 55 tests, 0 failures, 0 skipped, 0 errors (46 pre-existing + 9 new), from JUnit XML reports.

Two intermediate failures were hit and fixed while developing the new tests (both are development iteration, not evidence of a production bug):
1. Dereferencing the Quick Fix's `getStartElement()`/`getEndElement()` (`SmartPsiElementPointer`-backed) immediately after construction returned null in this light fixture - fixed by re-locating the same real PSI element directly via `PsiTreeUtil` instead.
2. The real `FixVerificationRunner`'s async re-scan popped a real result dialog during test teardown, which IntelliJ's test framework fails by default (`TestDialog.FATAL`) - fixed with `TestDialogManager.setTestDialog(TestDialog.OK)`, the standard, sanctioned IntelliJ test utility for this exact situation (no production code touched).

## 6. Cleanup

The real backend process started for this session (`uvicorn app:app`) and the Gradle daemon spun up for these runs were both stopped afterward. Free RAM returned to 7.77 GB (from a low of ~5.98 GB during the test run) - no lingering processes.

## 7. What remains open

Human-eyes GUI validation (pixel rendering, actual mouse/keyboard Alt+Enter, real screenshots) is still not performed - this agent has no tool for it, independent of machine resources. What Section 5's test-status table below calls "PASS" is scoped explicitly to headless-platform-verified behavior, never to a human-observed rendered UI.
