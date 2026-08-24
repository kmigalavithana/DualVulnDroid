# Phase 17 — Lightweight Android Emulator Live Validation (attempt record)

## 1. AVD inspection (Section 1 of this phase's instruction)

Two AVDs are installed: `Pixel_4` and `Medium_Phone_API_36.1`. Their
`config.ini` files were compared directly:

| Setting | Pixel_4 | Medium_Phone_API_36.1 |
|---|---|---|
| `hw.ramSize` | 2048 MB | 2048 MB |
| `hw.cpu.ncore` | 4 | 4 |
| `abi.type` / system image | x86_64, `android-36.1/google_apis_playstore` | x86_64, `android-36.1/google_apis_playstore` (same image) |
| `hw.lcd.width` x `hw.lcd.height` @ density | 1080x2280 @440dpi | 1080x2400 @420dpi |
| `vm.heapSize` | 256 MB | 336 MB |

**Finding:** the two installed AVDs are not meaningfully different in the
resource dimension that matters (guest RAM allocation and CPU core count are
identical; screen resolution/density are within a few percent of each
other). Neither is a "lightweight" alternative to the other in any real
sense — `Medium_Phone_API_36.1` is not a lower-RAM device profile, just a
different skin on the same system image. No new system image was downloaded
(none was needed, since both already share the same installed image);
`Pixel_4` was not deleted. Per the instruction's own fallback ("if no
suitable lightweight AVD exists, report the available AVDs"), this is
effectively that situation — `Medium_Phone_API_36.1` was used anyway, since
it was explicitly the only non-Pixel_4 option and the instruction directed
using it if `Pixel_4` was not to be reattempted, but this record is explicit
that it was not expected, and did not turn out, to be materially lighter.

## 2. Resource gate (Section 2)

Checked before any build or launch action, and again immediately before the
emulator launch itself:

| Item | Value |
|---|---|
| Physical RAM total | 15.75 GB |
| Physical RAM free (start of phase) | 6.53 GB |
| F: free disk space | 167.69 GB |
| Selected AVD | `Medium_Phone_API_36.1` |
| Configured AVD RAM | 2048 MB (guest) |
| Java/Gradle/Flutter/emulator processes running (start of phase) | None |

The existing debug APK (`build/app/outputs/flutter-apk/app-debug.apk`,
dated 2026-08-19) predated the Phase 15/16 UI changes (dashboard FAB, chat
screen polish, theme/login/splash changes, all dated 2026-08-22), so it did
not contain what this phase needed to validate. A fresh `flutter build apk
--debug` was run (76.2s, succeeded) *before* launching any emulator, while
RAM was fully free. This left one Gradle daemon (`java.exe`, 698 MB)
resident; per the instruction to "close only clearly unnecessary
emulator/build processes," it was stopped cleanly (`./gradlew --stop`,
confirmed "1 Daemon stopped") once the build finished — this is a build
process, not a running application, IDE, or unrelated user program. No
other process, and no agent/IDE session, was closed. RAM immediately before
the emulator launch: **6.72 GB free**, no Java/Gradle/emulator process
running — the healthiest pre-launch reading recorded anywhere in this
project's validation history.

## 3. Emulator launch and outcome

`Medium_Phone_API_36.1` was cold-booted (`-no-snapshot-load`). Boot
completed in 33 seconds; `adb devices` showed `emulator-5554  device`.

**Immediately post-boot RAM:** 3.83 GB free (`qemu-system-x86_64` working
set 2.91 GB) — above the 2.79–2.87 GB band that caused Phase 14C's ANR, and
the best post-boot reading this project has recorded.

**System UI check** (`dumpsys window`, `mCurrentFocus`) immediately after
boot showed: `Application Not Responding: com.android.systemui` — the same
failure signature as Phase 14C, now occurring despite materially healthier
RAM. Following the same bounded wait-and-recheck protocol used in Phase
14C, the check was repeated after 6s, 10s, 18s, and 30s additional waits
(≈64s total): **the ANR did not clear at any point.**

**A genuinely new diagnostic finding:** RAM was re-measured during the
persistent ANR and held steady at 3.98 GB free — it did not degrade further,
ruling out ongoing memory exhaustion as the proximate cause of *this*
specific ANR. `qemu-system-x86_64`'s accumulated CPU time was measured at
**≈913 CPU-seconds** against roughly 100 seconds of elapsed wall time since
launch — consistent with the process pinning multiple CPU cores at or near
100% continuously. This points to a CPU-bound stall (plausibly a
virtualization-acceleration or software-rendering fallback issue, or
antivirus/real-time-scanning interference with the emulator process) as the
more likely root cause on this host, distinct from the RAM-exhaustion
pattern documented in Phases 14D/15/16. This reframes the earlier
RAM-centric diagnosis: sufficient free RAM at boot was necessary but, on
this occasion, not sufficient to avoid the same ANR symptom.

## 4. Decision

Per the standing instruction ("if the emulator again shows 'System UI isn't
responding' and cannot recover after reasonable waiting/dismissal, STOP the
live validation attempt. Do not mark the test PASS"), the attempt was
stopped. The emulator was shut down cleanly (`adb emu kill`), confirmed
fully terminated (`adb devices` empty across 5 checks), and RAM recovered
to 7.34 GB free, confirming no other process was responsible.

**The Flutter application was never installed or launched** — System UI
itself never became responsive enough to install an APK onto. No screen of
the app was observed. No screenshot was captured; a preliminary screenshot
attempt during the ANR failed for this reason (and additionally hit a local
path-creation ordering issue on the controlling machine, which is moot given
the underlying ANR made the capture meaningless regardless).

## 5. Result against Section 4/5 targets

**None of the requested validation could be attempted.** Q3–Q8, C3, C4, H1,
F1, F2, F3, L1, K1, and the Home→Security Chat FAB visual check all remain
exactly as recorded in `chatbot_final_validation.csv` before this phase —
**NOT VALIDATED**, now with this attempt's specific cause recorded. Q1, Q2,
C1, C2 remain PASS, carried forward unchanged from Phase 14B, not re-tested.

## 6. Bugs found

None — no application code was ever reached this attempt (the failure
occurred entirely at the Android System UI / emulator level, before the
Flutter app was installed). No fix was made or needed to `chatbot_logic.py`,
`decision_engine.py`, XGBoost, or any other production component.

## 7. Remaining limitation

This host cannot currently sustain either installed AVD (`Pixel_4` or
`Medium_Phone_API_36.1`) through a stable System UI boot. The Pixel_4
attempt (Phase 16) failed via RAM exhaustion (0.64 GB free post-boot); this
Medium_Phone attempt failed via a persistent ANR **despite healthy RAM**
(3.83–3.98 GB free throughout), correlated instead with sustained near-100%
CPU consumption by `qemu-system-x86_64`. Closing the remaining chatbot/
mobile validation gaps on this host likely requires investigating
virtualization acceleration (confirm Windows Hypervisor Platform/HAXM is
actually engaged and not falling back to software emulation) or antivirus
exclusions for the emulator process, rather than further RAM-headroom
management alone, which this attempt shows is not sufficient by itself.
