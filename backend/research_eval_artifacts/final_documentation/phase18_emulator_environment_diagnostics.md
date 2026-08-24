# Phase 18 — Android Emulator Environment Diagnostics

**No emulator instance was booted during this phase.** The only Android-tooling
command executed was `emulator -accel-check`, which queries host acceleration
capability without starting a virtual device. All other emulator-specific
evidence below comes from **retrospective analysis of the log files already
captured during the Phase 16 (`Pixel_4`) and Phase 17 (`Medium_Phone_API_36.1`)
boot attempts** (`/tmp/emulator_boot.log`, `/tmp/emulator_boot2.log`), not from
a new session. The Flutter app was not launched. No project file was modified.

## 1. Host hardware

| Item | Value |
|---|---|
| Manufacturer / Model | LENOVO 20QES08X00 |
| CPU | Intel(R) Core(TM) i7-8665U @ 1.90GHz |
| Physical cores / logical processors | 4 cores / 8 logical (hyperthreaded) |
| Total physical RAM | 15.75 GB (16,907,448,320 bytes) |
| GPU | Intel(R) UHD Graphics 620 (integrated), driver 30.0.101.1338, dated **2022-01-20** |

## 2. Physical RAM

Not re-measured in this phase (no launch occurred); see Phases 16/17 for the
specific readings this diagnostic session is explaining (6.72 GB free
pre-launch in Phase 17, 3.83 GB post-boot, 3.98 GB during the failure — RAM
was not depleting during the ANR).

## 3. CPU virtualization status

`Win32_Processor.VirtualizationFirmwareEnabled` and
`SecondLevelAddressTranslationExtensions` both reported **False**. Taken in
isolation this would suggest VT-x/SLAT is disabled in firmware. However, this
is a well-documented WMI artifact: once a hypervisor (Hyper-V/VBS) is already
running, Windows' own root-partition OS instance reports these WMI fields
unreliably, because the query is answered by the virtualized root partition
rather than bare hardware. `systeminfo`'s dedicated, more authoritative
Hyper-V check confirms this reading is misleading here (Section 4). **This
specific WMI field is not treated as reliable evidence in this report.**

## 4. Hyper-V / WHPX status

`Get-WindowsOptionalFeature` could not be queried (requires elevation, not
available in this session). Two non-elevated, authoritative alternatives were
used instead:

- `systeminfo`: **"A hypervisor has been detected. Features required for
  Hyper-V will not be displayed."** and **"Virtualization-based security:
  Status: Running — Base Virtualization Support."** — **VERIFIED**: a
  hypervisor (Hyper-V/VBS) is active on this host.
- `emulator -accel-check`: **"WHPX(10.0.26200) is installed and usable."**
  (exit code 0) — **VERIFIED**: the Windows Hypervisor Platform API, which
  the Android Emulator requires when Hyper-V is active (HAXM cannot coexist
  with Hyper-V), is present and reports itself usable.

## 5. Emulator acceleration status (actual sessions, not just capability)

Both the Phase 16 (`Pixel_4`) and Phase 17 (`Medium_Phone_API_36.1`) boot
logs contain, identically:

```
WHPX on Windows 10.0.26200 detected.
Windows Hypervisor Platform accelerator is operational
```

**VERIFIED**: WHPX-based CPU acceleration was genuinely engaged in both of
the actual failed sessions — this is direct evidence from those sessions'
own logs, not an inference from the general capability check. **CPU
virtualization unavailability is ruled out as the cause of either failure.**

## 6. GPU / graphics / renderer status

Both logs also contain, identically:

```
Guest GLES Driver: Auto (ext controls)
library_mode host gpu mode host
...
Critical: Failed to load opengl32sw (The specified module could not be found.) (:0, )
Warning: Software OpenGL failed. Falling back to system OpenGL. (:0, )
...
Your GPU 'Intel(R) UHD Graphics 620' has driver version 1.2.203, and cannot support Vulkan properly. Please try updating your GPU Drivers.
...
Graphics Adapter: Android Emulator OpenGL ES Translator (Intel(R) UHD Graphics 620)
Graphics API Version: OpenGL ES 3.0 (4.5.0 - Build 30.0.101.1338)
```

Interpretation:

- **VERIFIED**: the emulator's own software-GL component (`opengl32sw.dll`)
  failed to load — the file could not be found — and the emulator fell back
  to sharing the host's real `opengl32.dll` (`C:\Windows\SYSTEM32\`) instead
  of an isolated software renderer for its own UI. This is a genuine, direct
  log finding, not an inference.
- **VERIFIED**: the emulator itself flags the installed Intel UHD 620 driver
  (dated January 2022) as unable to properly support Vulkan.
- **LIKELY** (strong circumstantial evidence, not directly proven by a
  process-level trace): the guest's rendering path — GPU-passthrough via
  `gfxstream`/ANGLE translation through this same aging driver, combined
  with the missing software-GL fallback for the emulator's own window —
  created a degraded, contention-prone graphics pipeline. Since
  `com.android.systemui`'s ANR specifically manifested around
  `SurfaceFlinger`/compositor responsiveness (the System UI process, whose
  main job at boot is compositing), a degraded graphics path is a plausible
  and consistent explanation for why the UI thread stalled while other
  subsystems (network, adb) remained reachable.
- Additionally observed, likely contributing: `WARNING | Please update the
  emulator to one that supports the feature(s): VulkanVirtualQueue` — the
  installed Android Emulator binary (version 36.1.9.0, build 13823996) is
  older than what this system image's feature set expects.

## 7. qemu CPU behaviour (from Phase 17's measurements)

Phase 17 measured `qemu-system-x86_64` at **≈913 CPU-seconds accumulated
over ≈100 seconds of wall-clock time**, on a host with 8 logical processors.
That ratio (≈9.1 "cores" worth of continuous work) means the process was, on
average, keeping the *entire* host CPU close to saturated throughout the
ANR window — not idling, not merely a single stuck thread.

Given Section 5's verified finding that WHPX (CPU virtualization) was
active, this saturation is **not** consistent with the classic "no
acceleration → full binary-translation (TCG) of every guest instruction"
failure mode, which would typically be flagged more explicitly in the log
and tends to make boot itself fail or take dramatically longer rather than
succeed in 33 seconds and then stall. It is more consistent with:

- **LIKELY**: heavy CPU-side work in the graphics translation layer
  (`gfxstream`, shader translation via `libshadertranslator.dll`, or
  software compositing fallback) compensating for the degraded GPU path
  identified in Section 6, spread across qemu's multiple internal worker
  threads (which is why total CPU-seconds can exceed the guest's 4 configured
  vCPUs — qemu/gfxstream use additional host-side threads for rendering,
  I/O, and device emulation beyond the vCPU count).
- **POSSIBLE**: some additional retry/backoff loop specific to the failed
  `opengl32sw` load or the Vulkan feature-mismatch warning, though no direct
  log evidence of a repeating retry was captured (this would require a
  live, verbose trace of a fresh session to confirm — not done, per this
  phase's "no live validation" constraint).

No evidence of a hung or spinning single thread was found; the behaviour
observed is broad, multi-thread CPU consumption, not a classic livelock
signature.

## 8. Antivirus / security observations

Windows Defender: `AntivirusEnabled: True`, `RealTimeProtectionEnabled:
True`, `AMServiceEnabled: True`, `AntispywareEnabled: True` — real-time
protection is active. Existing exclusion paths could not be read
(`Get-MpPreference` requires administrator rights, not available in this
session), so **no evidence either way** on whether the Android SDK, AVD
directory, or `qemu-system-x86_64` are already excluded. No process-level
evidence (e.g., `MsMpEng.exe` CPU spikes correlated with the emulator's
CPU usage) was gathered, since doing so would have required either
elevated access or a fresh live session, both outside this phase's scope.
**Classification: POSSIBLE contributing factor, unconfirmed.** If a future
session can run as administrator, checking `Get-MpPreference` exclusions
and `Get-MpComputerStatus`/`Get-WinEvent` for Defender scan activity
concurrent with a boot attempt would let RAM this be upgraded to VERIFIED
or ruled out.

## 9–10. AVD configuration comparison

| Setting | `Pixel_4` | `Medium_Phone_API_36.1` |
|---|---|---|
| `hw.ramSize` | 2048 MB | 2048 MB |
| `hw.cpu.ncore` | 4 | 4 |
| `hw.gpu.enabled` / `hw.gpu.mode` | yes / auto | yes / auto |
| `disk.dataPartition.size` | 6G | 6G |
| `vm.heapSize` | 256 MB | 336 MB |
| `fastboot.forceColdBoot` (config default) | no (overridden to cold via `-no-snapshot-load` CLI flag both times) | no (same override) |
| `image.sysdir` (system image) | `android-36.1/google_apis_playstore/x86_64` | same image |
| Resolution @ density | 1080x2280 @440dpi | 1080x2400 @420dpi |
| **Secondary display** | **`hw.display1` configured: 720x1280 @213dpi** | none configured |
| Skin | `pixel_4` (device-specific skin path) | `1080x2400` (generic resizable skin) |

**Finding, restated from Phase 17 and confirmed here at the full-config
level:** the two AVDs are equivalent in every resource dimension that
matters for this failure (RAM, cores, image, GPU mode). The one real
difference — `Pixel_4`'s extra configured secondary display — adds
compositing overhead specific to `Pixel_4` but cannot explain
`Medium_Phone`'s identical ANR, since that AVD has no secondary display at
all. This rules out the secondary display as the (sole) cause.

## 11. Most likely cause

- **VERIFIED**: CPU virtualization (WHPX) was active and operational in
  both failed sessions. Not the cause.
- **VERIFIED**: the emulator's software-GL fallback component
  (`opengl32sw.dll`) is missing/fails to load on this host, forcing a
  shared-context fallback to the system OpenGL driver.
- **VERIFIED**: the host's GPU driver (Intel UHD 620, dated January 2022)
  is flagged by the emulator itself as unable to properly support Vulkan.
- **LIKELY**: the combination of these two verified graphics-path issues —
  not RAM, not CPU virtualization availability, not AVD device-profile
  weight — is the primary driver of the sustained, near-total-host CPU
  saturation and the resulting `com.android.systemui` ANR. The degraded
  GPU/rendering path is the most evidence-backed candidate; it is labelled
  LIKELY rather than VERIFIED because no live, process/thread-level trace
  isolating exactly which subsystem burned the 913 CPU-seconds was
  captured (that would require a fresh, instrumented session, which this
  phase's "no live validation" constraint rules out).
- **POSSIBLE**: outdated Android Emulator binary (36.1.9.0, missing
  `VulkanVirtualQueue` support relative to what the system image expects)
  compounding the above.
- **POSSIBLE, unconfirmed**: Windows Defender real-time scanning
  contention — real-time protection is active, but no direct evidence of
  interference was gathered (would need administrator access).

## 12. Recommended next action

None of the following were performed this phase — they are proposed for
explicit confirmation before any is attempted, per this phase's "no
destructive changes without asking" instruction:

1. **Update the Intel UHD 620 graphics driver** (currently January 2022).
   This is a real system-level change with genuine risk (a bad driver
   install can affect display output); explicit confirmation should be
   sought before attempting it, and it should be done through Windows
   Update or Intel's official driver tool, not an arbitrary download.
2. **Update the Android Emulator package** via Android Studio's SDK Manager
   or `sdkmanager --update` — safe and non-destructive (does not touch
   project files), directly addresses the logged `VulkanVirtualQueue`
   version-mismatch warning.
3. **Try an explicit, non-`auto` GPU mode** on the next attempt (e.g.
   `-gpu angle_indirect` or `-gpu swiftshader_indirect` instead of the
   default `auto`) to see whether forcing a specific renderer avoids the
   `opengl32sw` load failure. This is a launch-flag change only, not a
   project or AVD file change, and is reversible immediately.
4. If administrator access becomes available: check `Get-MpPreference`
   exclusions and Defender scan history for evidence of interference
   (Section 8), and re-run `Get-WindowsOptionalFeature` for a direct,
   authoritative Hyper-V/WHPX/VMP feature-state reading rather than the
   indirect `systeminfo`/`accel-check` evidence used here.

No AVD was deleted, no system image was downloaded, no driver was
installed, and no configuration file was changed during this phase.

## 13. Whether another live validation attempt is advisable

**Not yet, without first trying recommendation 3 (an explicit GPU mode
flag) or recommendation 2 (an emulator update) — both low-risk and
directly targeted at the two VERIFIED graphics-path findings above.**
Simply retrying either AVD again under the current configuration would be
expected, based on this diagnostic evidence, to reproduce the same ANR
regardless of available RAM — Phase 17 already demonstrated that healthy
RAM (3.83–3.98 GB free) does not prevent it. A future attempt should change
at least one of the two verified graphics-path variables before spending
another boot cycle on this host.
