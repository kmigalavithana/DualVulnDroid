# Phase 19 — Safe Graphics-Path Fix Attempt + Live Validation (attempt record)

## 1. Resource check (before launch)

| Item | Value |
|---|---|
| Physical RAM free | 7.15 GB (of 15.75 GB total) — the healthiest pre-launch reading recorded this project |
| F: free disk | 167.69 GB |
| CPU usage (idle snapshot) | ≈11% |
| Selected AVD | `Medium_Phone_API_36.1` (unchanged, no new AVD created, no existing AVD data wiped) |
| Selected GPU mode | `swiftshader_indirect` (confirmed supported via `emulator -help-gpu` before use) |
| Running emulator/Java/Gradle/dart/flutter processes | None |

## 2. Launch and immediate result

`Medium_Phone_API_36.1` was cold-booted (`-no-snapshot-load -no-boot-anim
-gpu swiftshader_indirect`). Boot completed in 33 seconds.

**Immediately post-boot:** `dumpsys window` showed
`mCurrentFocus=Window{... com.google.android.apps.nexuslauncher/...
NexusLauncherActivity}` — a genuine, responsive home-screen focus, **not**
an ANR. This is a materially different (better) initial result than every
prior attempt (Phases 14C, 16, 17), which never reached a responsive
launcher at all.

RAM at this point: 3.45 GB free. `qemu-system-x86_64`: 3287.5 MB resident,
836.5 CPU-seconds already accumulated in the ≈40–50s since launch.

## 3. Bounded monitoring (Section 3/4 of this phase's instruction)

Per the instruction to wait for a bounded period and confirm stability
before installing the app, focus was re-checked every 10 seconds for 40
seconds rather than installing anything immediately:

| Elapsed | `mCurrentFocus` |
|---|---|
| +10s | `Application Not Responding: com.google.android.apps.nexuslauncher` |
| +20s | `Application Not Responding: com.google.android.apps.nexuslauncher` |
| +30s | `Application Not Responding: com.google.android.apps.nexuslauncher` |
| +40s | `Application Not Responding: com.google.android.apps.nexuslauncher` |

The initial responsive state did **not** hold — within 10 seconds it
degraded into a persistent ANR, this time on the launcher rather than
`com.android.systemui` specifically, and it did not clear across the full
40-second monitoring window.

**Final measurement before shutdown:** RAM 3.49 GB free (stable, not
degrading — consistent with Phases 16/17's finding that RAM is not the
proximate cause). `qemu-system-x86_64` CPU time had risen to 1503.25
seconds — an increase of ≈667 CPU-seconds over roughly 50 seconds of
elapsed wall time, i.e. an even higher sustained CPU-consumption rate than
Phase 17's unaccelerated-GPU-mode attempt (≈13 "cores" worth of continuous
work on an 8-logical-processor host). Software rendering shifted where the
CPU load was generated but did not reduce it — if anything, it measured
worse.

## 4. Graphics diagnostic success criteria — evaluated

| # | Criterion | Result |
|---|---|---|
| 1 | Android boots normally | Partially — reached a real launcher focus once, briefly |
| 2 | No persistent "System UI isn't responding" dialog | **Failed** — persisted across the full 40s window (on the launcher) |
| 3 | System UI remains responsive | **Failed** — lost within 10s of first reaching it |
| 4 | qemu CPU usage no longer abnormally saturated | **Failed** — measured higher than the prior (non-swiftshader) attempt |
| 5 | RAM remains reasonably stable | **Passed** — 3.45→3.49 GB, stable, not the cause |

**Overall: the environment is not considered improved.** Per the instruction
("If System UI still ANRs, stop and report the result"), the attempt was
stopped here. **The Flutter APK was not installed or launched. No live
chatbot/mobile validation (Sections 5–7 of this phase's instruction) was
performed.** No screenshot was captured — the ANR state does not constitute
genuine application evidence.

The emulator was shut down cleanly (`adb emu kill`, confirmed terminated
across 5 checks); RAM recovered to 7.3 GB, again confirming the emulator
itself — not any other process — accounts for the resource usage.

## 5. New diagnostic evidence from this attempt

Two findings from the `-gpu swiftshader_indirect` boot log refine Phase
18's LIKELY conclusion:

- **The guest's GPU rendering path genuinely switched to SwiftShader as
  requested** — the log shows `Graphics Adapter Android Emulator OpenGL ES
  Translator (Google SwiftShader)`, `Selecting Vulkan device: SwiftShader
  Device (LLVM 10.0.0)`, and `Graphics API Version OpenGL ES 3.0
  (OpenGL ES 3.0 SwiftShader 4.0.0.1)`. The `-gpu` flag worked as intended
  for guest rendering; the ANR is **not** simply "the guest GPU mode was
  wrong."
- **The same `opengl32sw` failure recurred identically**: `Critical: Failed
  to load opengl32sw (The specified module could not be found.)` /
  `Warning: Software OpenGL failed. Falling back to system OpenGL.` This
  component is used by the emulator's own Qt-based UI window (device frame,
  on-screen controls), separate from guest rendering, and is unaffected by
  the guest `-gpu` mode — confirming it is a genuinely broken/missing
  installed component, not a configuration choice.
- **A new error not seen in Phases 16/17's logs**: `Critical:
  UpdateLayeredWindowIndirect failed for ptDst=(675, -945), size=(383x32),
  dirty=(384x33 0, 0) (A device attached to the system is not
  functioning.)` — a Windows API failure specific to updating a layered
  (translucent) window, used by the emulator's own UI chrome. "A device
  attached to the system is not functioning" is a low-level Windows
  display-stack error, not an Android-tooling error. This is genuinely new,
  direct evidence implicating the **host's own graphics driver/display
  stack**, not just the emulator's configuration.

## 6. Recommendation (Section 10 of this phase's instruction)

Given the new `UpdateLayeredWindowIndirect ... device not functioning`
error is a host Windows display-driver-level failure that an Android SDK/
emulator package update would not be expected to fix (it is not an Android
tooling component), and combined with Phase 18's already-verified finding
that the installed Intel UHD 620 driver is from January 2022 and is
self-reported by the emulator as unable to properly support Vulkan, this
phase's evidence now leans more specifically toward:

**B. An Intel UHD 620 driver update is the more likely candidate fix**,
over A (an Android Emulator package update alone). The `opengl32sw`
load failure and the layered-window failure both sit below the Android
tooling layer, in the host's own graphics/display stack.

An Android Emulator package update (A) is still reasonable as a
low-risk, easy first step (it might also resolve the separate,
independently-logged `VulkanVirtualQueue` version-mismatch warning), but
this phase's evidence does not suggest it alone would fix the
`opengl32sw`/layered-window failures, which point at the driver.

**Neither was installed automatically.** Both remain proposals awaiting
explicit confirmation, per this phase's instruction.

## 7. Bugs found

None — the Flutter application was never installed or reached this
attempt, so no application-level defect could be observed. No production
code, chatbot logic, XGBoost, or Decision Engine was touched.

## 8. Status of remaining validation items

Unchanged from Phase 17/18. No item in `chatbot_final_validation.csv` was
upgraded from NOT VALIDATED. Q1/Q2/C1/C2 remain PASS, carried forward from
Phase 14B, not re-tested this phase.
