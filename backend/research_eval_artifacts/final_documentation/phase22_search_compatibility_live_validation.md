# Phase 22 — Search & Compatibility Live Validation (attempt record)

## 1. Environment

| Item | Value |
|---|---|
| Physical RAM free (pre-launch) | 6.63 GB (of 15.75 GB) |
| C: free disk | 17.19 GB |
| Java/Gradle/emulator processes at start | None |
| Backend | Already running from Phase 21 (never stopped between phases), confirmed healthy via `GET /` before launch |
| MySQL | Already running from Phase 21, confirmed listening on 3306 |
| Flutter APK | The existing debug APK was confirmed current — no `lib/` source file is newer than it, so it was reused without a rebuild |
| Selected AVD | `Medium_Phone_API_36.1`, same configuration that completed Phase 21 successfully |

Before touching the emulator, the exact target test definitions were
re-confirmed by reading `phase14b_android_validation.md` directly (not
re-derived): **Search sub-cases are A (known application, already PASS),
B (unknown application), C (empty prompt state, already PASS), D (network
error). Compatibility sub-cases are A (COMPATIBLE, already PASS), B
(INCOMPATIBLE), C (NOT_AVAILABLE / missing device info).** This phase's
four targets are exactly B and D (Search) and B and C (Compatibility) —
no new test case was invented.

Real data to exercise these cases was identified in advance from the live
MySQL database (read-only query, no data modified): the application
**Snaptube** (id 1, `com.snaptube.premium`) has a real, completed scan
with `min_sdk_version = 21`, `target_sdk_version = 35`, risk `HIGH` — the
same real app used for the COMPATIBLE case in Phase 14B. The plan was to
reuse Snaptube with a device Android version below 21 for the INCOMPATIBLE
case, and with no Android version supplied at all for the NOT_AVAILABLE
case. The existing test account from Phase 21 (`ZZPhase21Tester`,
`Xphase21tester@dualvulndroid.test`) was identified for reuse to avoid an
unnecessary second registration.

## 2. Emulator attempt

`Medium_Phone_API_36.1` was cold-booted (`-no-snapshot-load
-no-boot-anim`, default/auto GPU mode — the same configuration that
completed the entire Phase 21 session without incident). Boot completed
in 42 seconds.

**Immediately after boot**, `dumpsys window` showed `Application Not
Responding: com.android.systemui`. Following the same bounded
wait-and-recheck protocol used in every prior instability episode this
project has recorded, the check was repeated after 8s, 15s, and 20s
additional waits (43s total): **the ANR did not clear at any point.**

RAM was re-measured during the ANR: 4.00 GB free — healthy, not
degrading, ruling out RAM exhaustion as the cause (consistent with every
prior finding once RAM itself was no longer the limiting factor).
`qemu-system-x86_64` CPU time measured 1178.4 seconds against roughly 110
seconds of elapsed wall time — the same extreme, multi-core-saturating
CPU consumption pattern documented in Phases 17 and 19, and consistent
with Phase 18's graphics-pipeline diagnostic finding.

## 3. Decision

Per this phase's explicit instruction ("If the emulator becomes unstable:
STOP immediately... Do not force the emulator"), the attempt was stopped
here rather than cycling through alternative configurations. The emulator
was shut down cleanly (`adb emu kill`, confirmed terminated across 5
checks); RAM recovered to 6.99 GB, confirming the emulator itself was the
cause. The backend and MySQL were left running and independently
reconfirmed healthy afterward (`GET /` succeeded) — this attempt did not
disturb them.

**The Flutter application was never installed, launched, or interacted
with this phase.** No screenshot was captured for any of the four target
cases — capturing one during an ANR state would not constitute genuine
application evidence.

This result is consistent with Phase 21's own stated limitation: that
session's stability was reported as an observed outcome, not attributed
to any specific, reproducible cause, since no controlled isolation test
was performed. This phase's failure, under an identical configuration, is
further evidence that the underlying instability (per Phase 18's
diagnosis) is intermittent rather than fixed by any configuration change
made so far.

## 4. Bugs found

None — no application code was reached this phase, so no application-level
defect could be observed or introduced. No production code, ML model,
Decision Engine, or chatbot logic was touched.

## 5. Final status table

| Test ID | Area | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| Search-B | Search | Unknown/unrecognised application query returns an honest "no results" empty state, no crash | Not reached — emulator ANR before app launch | **NOT VALIDATED** | None captured (Section 2) |
| Search-D | Search | Backend unreachable during a search shows the app's typed network-error state with retry, no crash | Not reached | **NOT VALIDATED** | None captured |
| Compatibility-B | Compatibility | A device Android version below an app's real `min_sdk_version` (Snaptube, 21) yields an INCOMPATIBLE result | Not reached | **NOT VALIDATED** | None captured |
| Compatibility-C | Compatibility | No device Android version supplied yields a NOT_AVAILABLE result for that check | Not reached | **NOT VALIDATED** | None captured |

**Totals:** 0 Search cases live-validated this phase, 0 Compatibility
cases live-validated this phase, 0 screenshots captured. Automated test
coverage for these cases is unchanged from before this phase (still the
existing `test_compatibility.py`/`test_api.py` suites, not re-run this
phase since no code changed). No existing genuine PASS result (Phase 21's
chatbot/mobile validations, or Phase 14B's Search-A/C and
Compatibility-A) was downgraded, retested, or altered.

**Search and Compatibility live-validation gaps are NOT closed.** The
exact reason: the Android emulator entered a persistent, non-recovering
System UI ANR immediately after boot, under the identical configuration
that completed Phase 21 successfully, and RAM was confirmed healthy
throughout (ruling out the resource-exhaustion explanation that applied
in earlier phases). Per explicit instruction, the attempt was stopped
rather than forced or retried under a different configuration this phase.

## 6. Remaining limitations

- All four target cases (Search-B, Search-D, Compatibility-B,
  Compatibility-C) remain exactly as before this phase: NOT VALIDATED.
- The intermittent nature of this instability — stable for all of Phase
  21, unstable again in Phase 22 under the same configuration — suggests
  the underlying cause (Phase 18's graphics-pipeline diagnosis) has not
  been durably resolved; it appears to vary by session rather than by any
  configuration choice tested so far.
- Real data for a future attempt is already identified and does not need
  re-deriving: Snaptube (application id 1, `min_sdk_version=21`) for both
  Compatibility sub-cases, and the existing `ZZPhase21Tester` account for
  login, avoiding a second registration.
