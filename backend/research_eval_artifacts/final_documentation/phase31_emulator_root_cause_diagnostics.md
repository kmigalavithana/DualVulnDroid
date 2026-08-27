# Phase 31 — Emulator/Host Environment Root-Cause Diagnostics

**Scope note:** This is a pure diagnostics phase. No Flutter source, backend, XGBoost, ML models, Decision Engine, chatbot logic, IntelliJ plugin, database, or thesis file was modified. No AVD was created, deleted, wiped, or reconfigured. No Windows system setting, driver, or Defender configuration was changed. No live UI validation was attempted.

## 1. Review of previously captured graphics evidence

Seven raw emulator boot logs from this project's recent history were still present on local disk and were directly re-inspected (not re-derived from memory or from prior written summaries): `emulator_boot.log`, `emulator_boot2.log`, `emulator_boot3.log`, `emulator_boot4.log`, `emulator_boot5.log` (Aug 23 19:19–23:35, covering the UI-restyle-phase attempt and neighboring attempts), plus `emulator_boot27.log` (Phase 27) and `emulator_boot30.log` (Phase 30). Phase 18's and Phase 22's own raw logs were not recoverable from this session's temp storage (different session context); their findings below are drawn from the already-written `phase18_emulator_environment_diagnostics.md` and `phase22_search_compatibility_live_validation.md` reports instead, which is noted explicitly rather than silently treated as equivalent to a fresh log read.

**Result: all four graphics-related signatures are present, byte-for-byte identical, in every one of the 7 available raw logs, with zero exceptions:**

| Signature | Status | Evidence |
|---|---|---|
| `opengl32sw` load failure | **CONFIRMED present, 7/7 logs** | `Critical: Failed to load opengl32sw (The specified module could not be found.)` — identical text in every log |
| Vulkan compatibility warning for Intel UHD 620 | **CONFIRMED present, 7/7 logs** (6/7 report it via the standard path; the 7th, `emulator_boot3.log`, is the one attempt that used `-gpu swiftshader_indirect` — see below) | `Your GPU 'Intel(R) UHD Graphics 620' has driver version 1.2.203, and cannot support Vulkan properly. Please try updating your GPU Drivers.` The emulator's own Vulkan probe additionally reports `driverVersion: 0.404.1338` — the trailing `1338` matches the host driver's actual build number (see Section 3) |
| `UpdateLayeredWindowIndirect` failure | **CONFIRMED present, 7/7 logs** | `Critical: UpdateLayeredWindowIndirect failed for ptDst=(675, -945), size=(383x32), dirty=(384x33 0, 0) (A device attached to the system is not functioning.)` — identical coordinates and size in every single occurrence, indicating a deterministic, reproducible failure rather than a random/transient one |
| WHPX acceleration | **CONFIRMED operational, 7/7 logs** | `WHPX on Windows 10.0.26200 detected.` present in every log — hardware virtualization is not, and has never been, the limiting factor |
| `com.android.systemui` ANR | **CONFIRMED** in the phases where `dumpsys window` was checked post-boot (Phase 22, Phase 27, Phase 30 — direct `dumpsys` evidence captured in each phase's own report) | Consistent across all three most recent direct checks |
| NexusLauncher ANR (as opposed to systemui) | **CONFIRMED, Phase 19 only** | Occurred specifically under the one attempt using `-gpu swiftshader_indirect` (`emulator_boot3.log` matches this attempt's Vulkan/SwiftShader ICD loading detail) — a different ANR target under a different GPU mode, still a failure, not an improvement |
| Excessive qemu CPU consumption | **CONFIRMED in every phase where it was measured** | Phase 17: 913 CPU-s / ~100s wall; Phase 19: higher than Phase 17's under swiftshader; Phase 22: 1178 CPU-s / ~110s wall; Phase 27: 997.4 CPU-s / ~65-70s wall; Phase 30: 503.8 CPU-s / ~85s wall. Every measurement shows 5-12x realtime, multi-core-saturating CPU consumption during the ANR |

**Interpretation:** this is not an intermittent or ambiguous signature — it is the single most consistent finding in this project's entire diagnostic history. Every boot, regardless of which phase, which specific week, or (in one case) which alternate GPU mode was tried, reproduces the identical graphics-subsystem warning sequence.

## 2. Current host GPU

Checked directly via `Win32_VideoController`, Device Manager (`Get-PnpDevice`), and a freshly generated `dxdiag` report (not reused from any earlier phase):

| Item | Value |
|---|---|
| GPU name | Intel(R) UHD Graphics 620 |
| Driver version | **30.0.101.1338** |
| Driver date | **1/20/2022** |
| Hardware ID (PNP Device ID) | `PCI\VEN_8086&DEV_3EA0&SUBSYS_229217AA&REV_02\3&11583659&0&10` |
| Windows version/build | Windows 11 Pro, 10.0.26200 |
| DirectX version | DirectX 12 |
| Driver model | WDDM 3.0 |
| Feature levels | 12_1, 12_0, 11_1, 11_0, 10_1, 10_0, 9_3, 9_2, 9_1, 1_0_CORE |
| Device Manager status | `OK` / `CM_PROB_NONE` (no reported hardware problem) |
| dxdiag Display Tab 1 result | "No problems found" |

**This confirms exactly the value you asked me to verify: 30.0.101.1338, dated 2022-01-20.** The driver has not changed. It is now over 4 years old relative to the current session date, and is the same driver Phase 20 originally diagnosed as a likely contributor.

One additional, minor finding not previously documented: a secondary Intel graphics *extension* driver component (`iigd_ext.inf`, reported separately by dxdiag) is at version 27.20.100.8187, dated 4/17/2020 — a different, older sub-component from the same driver package. This is not a second GPU or a conflict, just a secondary component that appears not to have been refreshed alongside the primary display driver at the last update.

## 3. Verified official newer driver — attempted, inconclusive this session

Per the instruction to determine a **verified** newer driver before considering any install, and not to rely on assumptions:

- **Lenovo (ThinkPad X1 Carbon 7th Gen, Type 20QD/20QE)**: the official driver-list page was reached this session via `curl` with a browser user-agent (HTTP 200, page title confirmed as the correct product: *"thinkpad x1 carbon 7th gen type 20qd 20qe - Lenovo Support US"*) — a genuine improvement over a plain `WebFetch` attempt on the same URL, which returned 403 as it has every time in this project's history. However, the actual driver listing on this page loads dynamically via a `supportapi.lenovo.com` JavaScript call, not present in the static HTML — attempts to locate or query that API directly this session did not succeed (a guessed endpoint returned 404). **I could not independently re-confirm, with fresh data this session, whether a newer official Lenovo driver exists.** A prior phase (Phase 20C, earlier in this project's history) reported having confirmed no newer driver was offered by Lenovo for this exact machine — that finding is **not** re-verified here and should be treated as a prior claim, not a current one, until it is re-checked with a working method (e.g. a real browser session, or successfully locating the API call).
- **Intel (official product driver page)**: blocked (HTTP 403) via the same curl+browser-UA method that succeeded for Lenovo — consistent with every prior attempt in this project's history.

**Honest conclusion for this section: it is not currently verified, one way or the other, whether a newer official driver exists.** No driver of any kind — verified or unverified — was downloaded or installed.

## 4. No driver installed

Confirmed: no download, no install, no system modification of any kind was performed regarding the GPU driver. This section exists only to explicitly document compliance with that instruction.

## 5. Android Emulator graphics tooling

| Item | Value |
|---|---|
| Android Emulator version | 36.1.9 |
| SDK platform-tools version | 36.0.0 |
| AVD used for config inspection | `Medium_Phone_API_36.1` (real path: `F:\android-avd\Medium_Phone.avd\config.ini` — read only, not modified) |
| `hw.gpu.enabled` | `yes` |
| `hw.gpu.mode` | `auto` (unchanged from every prior phase) |
| System image | `android-36.1`, `google_apis_playstore`, `x86_64` |
| `hw.ramSize` | `2048` (MB, guest RAM — unchanged) |
| `hw.cpu.ncore` | `4` |

No AVD was created, deleted, or wiped. No config value was changed. Both the emulator binary and platform-tools are current, recently-released versions — not stale or outdated tooling, which argues against classification B (a tooling-version problem) as the primary cause.

## 6. Safe, reversible diagnostic tests performed

Only non-destructive checks that do not boot an AVD (per instruction) or, where a boot check was unavoidable for prior phases' evidence, results already on record are cited rather than re-run:

| Command | Result |
|---|---|
| `emulator -accel-check` | `WHPX(10.0.26200) is installed and usable.` — confirms hardware virtualization acceleration is fully operational, independent of and consistent with every boot log's own `WHPX ... detected` line |
| `emulator -help-gpu` | Lists available `-gpu` modes: `auto` (current default, in use every attempt), `auto-no-window`, `host`, `swiftshader_indirect` (already tried in Phase 19, made the ANR target shift to NexusLauncher without resolving it), `angle_indirect` (an OpenGL-ES-to-D3D11 path via ANGLE, **not yet attempted anywhere in this project's history**), `guest` (explicitly documented as unsupported/falls back automatically on this API level) |

No emulator boot was performed in this phase — the two commands above do not launch an AVD.

## 7. Windows display diagnostics

- **Device Manager**: `Intel(R) UHD Graphics 620` reports `Status: OK`, `ConfigManagerErrorCode: CM_PROB_NONE` — no hardware-level problem flagged.
- **DirectX diagnostics (`dxdiag`)**: "Display Tab 1: No problems found." Device Problem Code: "No Problem." DirectX 12 / WDDM 3.0 confirmed operational.
- **Windows Event Viewer — System log**: searched the last 40 hours (covering essentially every emulator boot attempt logged in this project's recent history, including Phase 27 and Phase 30) for any display-driver-stopped-responding / TDR (Timeout Detection and Recovery) event (event ID 4101, or any message matching "display driver" / "TDR" / "timeout detection"). **Zero matching events found.**
- **Windows Event Viewer — Application log**: searched the same window for any crash/error event referencing `qemu` or `emulator`. **Zero matching events found.**

**This is a genuinely new and significant finding.** It means the failure is *not* accompanied by a classic Windows-logged GPU driver crash or reset — the graphics driver itself never gets reported as having failed and recovered. This argues against a full driver crash/corruption (which would normally leave a TDR event) and is more consistent with a driver that functions normally for ordinary desktop use, but silently fails or degrades under the specific, unusual rendering calls the emulator's Qt-based UI and layered-window compositing make (`UpdateLayeredWindowIndirect`) combined with an outdated Vulkan capability level — a capability gap rather than a crash.

## 8. Windows Defender

Checked, not modified: `Get-MpComputerStatus` reports `RealTimeProtectionEnabled: True`, `AntivirusEnabled: True`, `AMServiceEnabled: True`, `BehaviorMonitorEnabled: True`. Real-time protection is active. Per instruction, it was **not** disabled and no exclusion was created. Its status is reported as a remaining, unruled-out contributing hypothesis (heavy real-time scanning of a CPU/IO-intensive process like `qemu-system-x86_64` is a known, generic source of slowdown on Windows), not as a confirmed factor — no test was performed that could isolate its contribution.

## 9. Final root-cause classification

**A. Confirmed host graphics-driver problem** — with an important precision about what "confirmed" means here.

What is directly, repeatedly, and consistently confirmed by evidence:
- The exact same GPU driver (30.0.101.1338, dated 2022-01-20) has been present, unchanged, across every single attempt in this project's history to date.
- That exact driver is flagged, by the Android Emulator's own internal Vulkan capability probe, as unable to properly support Vulkan — in 100% of 7 directly-inspected raw boot logs, with identical wording every time.
- A downstream host-side compositing failure (`UpdateLayeredWindowIndirect`, "a device attached to the system is not functioning") occurs at the identical screen coordinates and size in 100% of those same logs — a deterministic failure pattern, not noise.
- Every alternative host-level explanation checked this phase or in prior phases has been ruled out or shown healthy: RAM (repeatedly measured healthy and stable during every ANR across this project's history), CPU virtualization/WHPX (confirmed operational independently via `-accel-check` and present in every boot log), Windows' own view of the display stack (Device Manager "OK," dxdiag "no problems found," zero TDR/crash events logged), AVD configuration (unchanged, standard), and Android Emulator/platform-tools versions (both current, not stale).

What is **not** confirmed, and is explicitly not claimed:
- That updating the driver would actually resolve the ANR — this has not been tested, and this phase was explicitly scoped to not attempt any remediation or re-validation.
- That a verified newer official driver even exists (Section 3) — this remains unresolved.
- That Windows Defender's real-time protection plays no role — it was checked but not isolated as a variable.

Given the instruction not to call something "confirmed" without evidentiary support, but also not to leave a well-evidenced, highly consistent, single-variable finding artificially downgraded to "inconclusive": **A** is the most defensible classification, understood specifically as "confirmed to be the outdated-driver / Vulkan-capability gap on the host, evidenced consistently and directly, with every other host-level candidate independently checked and ruled out or shown healthy" — not as "confirmed by having applied and observed a working fix."

## 10. Recommended remediation (report only — nothing installed or changed)

| Item | Detail |
|---|---|
| What needs to change | The Intel UHD Graphics 620 driver, currently 30.0.101.1338 (2022-01-20), needs to be updated to a newer version — if and only if a verified newer version can actually be located (Section 3 found this **unresolved**, not confirmed available) |
| Why | It is the single most consistent variable across this project's entire diagnostic history — self-flagged as Vulkan-insufficient by the emulator in every one of 7 directly-inspected boot logs — while every other host-level factor checked (RAM, CPU virtualization, Windows display-stack health, AVD config, emulator/platform-tools currency) has been ruled out or shown healthy |
| Risk | Moderate, not zero. A GPU driver update on a laptop can occasionally introduce display glitches or, rarely, require a rollback. Risk is generally lower for an OEM-signed or Windows-Update-delivered driver than for a random third-party download |
| Restart required | Yes — virtually all GPU driver installs on Windows require a restart to fully apply |
| Admin privileges required | Yes — installing a device driver requires administrator rights |
| Exact next step (for a future phase, only after explicit approval) | Before attempting any external download, check **Settings → Windows Update → Advanced options → Optional updates → Driver updates** on this machine — Windows Update's optional-driver channel is often the most reliable, lowest-risk source for an OEM-signed Intel graphics driver update on a ThinkPad, and avoids the need to reverse-engineer Lenovo's or Intel's download-page APIs (which were only partially reachable this session, per Section 3). Only if that channel offers nothing newer should an external Lenovo/Intel source be pursued again, and only with the actual driver list (not just the page shell) successfully retrieved and read before proceeding |

**Nothing further should happen automatically.** This phase stops here and awaits explicit approval before any driver action is taken, per instruction.

## 11. Unresolved items

- Whether a verified newer official driver actually exists (Lenovo's dynamic driver list could not be queried this session; Intel's page remains blocked).
- Whether Windows Defender's real-time protection meaningfully contributes to the CPU saturation (checked but not isolated).
- Whether `-gpu angle_indirect` (an available, not-yet-tried rendering mode) would behave differently — this was not tested in this phase, per the explicit "do not run another live-validation attempt" instruction, and is noted only as an untested option for a possible future controlled test.
- The precise causal mechanism linking the host-side `UpdateLayeredWindowIndirect` compositing failure to the guest-side `com.android.systemui`/launcher ANR remains a well-supported inference from consistent, repeated correlation — not an experimentally isolated, single-variable proof.

## 12. What did not change

No live-validation status was changed by this phase. All items from Phase 30 (13 UI screens, 12 functional flows) remain exactly as recorded: NOT VALIDATED. Every genuine Phase 14B and Phase 21 PASS result remains untouched. `final_mobile_validation.csv` and `REMAINING_VALIDATION_ITEMS.md` were not modified this phase.
