# Phase 14A — Live IntelliJ Plugin Validation: Attempt Record

**Outcome: sandbox launch NOT attempted. Resource prerequisite not met. Bounded test-suite re-run completed instead.**

## 1. Prerequisite check (measured, not estimated)

| Resource | Free | Total | Notes |
|---|---|---|---|
| RAM (before any action) | 3.12 GB | 15.75 GB | ~20% free |
| RAM (after running the plain `test` task only) | 2.70 GB | 15.75 GB | Dropped further just from the Gradle daemon + lightweight test task - not from an IDE launch |
| Disk C: | 0.43 GB | — | Critically low |
| Disk D: | 0.22 GB | — | Critically low |
| Disk F: (project + IntelliJ Platform SDK cache) | 169.2 GB | — | Ample |
| Windows memory state | "Memory Compression" process holding 1.1 GB | — | Indicates the OS is already under real memory pressure, not just a low free-memory number |

The IntelliJ Platform SDK (`IC-251.23774.435`) is already fully cached under `DualVulnDroid\.intellijPlatform\localPlatformArtifacts\` on F:, so a launch would not need to download anything - the constraint is available RAM, not missing artifacts or disk space for the platform itself.

## 2. Decision

`./gradlew runIde` (or an equivalent UI-driving sandbox test) launches a full IntelliJ Platform JVM instance, which - even without custom `-Xmx` overrides in `build.gradle.kts` (none are set; plugin defaults apply) - typically needs on the order of 2 GB+ of heap for startup, indexing, and plugin loading, on top of whatever the rest of the system is already using. With only 2.70-3.12 GB free and the OS already compressing memory pages, adding that load risks system-wide thrashing, an OOM kill mid-run, or a hang - exactly the "severe resource exhaustion" scenario the task instructions said to stop short of.

**Decision: do not launch the sandbox. Do not fabricate a UI validation result.**

## 3. What was actually run instead

`./gradlew.bat test --rerun --console=plain` - the same bounded, non-UI test task already proven safe in Phase 12 (this does not open an IDE window; it runs JUnit tests inside a lightweight test fixture).

- **Environment:** Windows 11 Pro 10.0.26200, project at `F:\vibe cording\DualVulnDroid`, Gradle via `gradlew.bat`, configuration cache reused, IntelliJ Platform Gradle plugin, IC-251.23774.435.
- **Command:** `./gradlew.bat test --rerun --console=plain` (forced fresh execution, not a cache hit - `Task :test` executed, no `UP-TO-DATE` label).
- **Build time:** `BUILD SUCCESSFUL in 29s` (14 actionable tasks: 2 executed, 12 up-to-date).
- **Result:** 46 tests, 0 failures, 0 skipped, 0 errors (from JUnit XML reports under `build/test-results/test/*.xml`, not console text).
- **Failures:** none.

## 4. Item-by-item status (Section 5/6 of the request)

| Item | Status | Reason |
|---|---|---|
| SQL vulnerable code detection | NOT VALIDATED (live UI) | Covered at logic level by `SqlConcatenationAnalyzerTest` (13 tests, passing); no live annotation observed |
| Parameterized SQL (safe) | NOT VALIDATED (live UI) | Same - logic-level only |
| Certificate validation vulnerable | NOT VALIDATED (live UI) | Covered at logic level by `CertificateFixAnalyzerTest` (8 tests, passing); no live annotation observed |
| Certificate validation safe | NOT VALIDATED (live UI) | Same - logic-level only |
| Unrelated safe code | NOT VALIDATED (live UI) | No live scan run to observe absence of false annotation |
| Real-time annotations | NOT VALIDATED | Requires the IDE sandbox |
| Tooltip contents | NOT VALIDATED | Requires the IDE sandbox |
| CWE/severity/confidence display | NOT VALIDATED (live UI) | Underlying data covered by `FindingModelTest` (5 tests, passing) and the backend's real `/predict`/`/developer/scan` responses (verified in Phase 12); not observed rendered in the IDE |
| SHAP/evidence display | NOT VALIDATED | Requires the IDE sandbox |
| Alt+Enter intention | NOT VALIDATED | Requires the IDE sandbox |
| Shared FindingDetailView | NOT VALIDATED | Requires the IDE sandbox |
| Jump-to-source | NOT VALIDATED | Requires the IDE sandbox |
| Scan Project | NOT VALIDATED (live UI) | File-collection logic covered by `ProjectFileCollectorTest` (6 tests, passing); UI flow not observed |
| Batch scanning | NOT VALIDATED (live UI) | Parsing logic covered by `BatchScanParsingTest` (7 tests, passing); UI flow not observed |
| Quick Fix preview/diff | NOT VALIDATED (live UI) | Safety logic covered by `QuickFixSafetyTest` (3 tests, passing); preview/diff rendering not observed |
| Re-scan after Quick Fix | NOT VALIDATED | Requires the IDE sandbox (`FixVerificationRunner.kt` exists and is exercised only indirectly by unit tests, not a live re-scan) |
| Screenshots | NOT CAPTURED | No live UI session was run; none fabricated |
| Kotlin/Gradle test suite | **PASS** | 46/46, 0 failures, forced fresh execution, this session |

## 5. Remaining limitation

Live IntelliJ plugin UI validation remains an open gap, carried forward from Phase 12 through Phase 13 and now Phase 14A. It requires either (a) freeing meaningful RAM on this machine (closing other applications) before a retry, or (b) running the sandbox on a machine/session with more available headroom. No production code or test was changed in this phase; no test was weakened.
