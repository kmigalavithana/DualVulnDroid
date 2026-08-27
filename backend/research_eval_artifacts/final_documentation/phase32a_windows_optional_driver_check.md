# Phase 32A — Windows Optional Driver Updates Check (Read-Only)

**Scope note:** This phase was read-only throughout. No update was downloaded or installed, no restart was performed, no Windows setting/registry/Defender configuration was changed, no emulator/AVD file was touched, and no project file was modified. The emulator was not launched.

## Method

Windows Update's own Optional Updates → Driver Updates list (the UI path `Settings → Windows Update → Advanced options → Optional updates → Driver updates`) is backed by the Windows Update Agent, which is also directly queryable via the built-in `Microsoft.Update.Session` COM API without installing any additional tooling (no `PSWindowsUpdate` module was installed — checked first, confirmed absent, and not added). This was queried directly:

1. A targeted search for `IsInstalled=0 and Type='Driver'` — mirrors exactly what the "Driver updates" section of the Optional Updates UI shows.
2. A second, broader search for `IsInstalled=0` across all update types, then keyword-matched every title against `graphic|display|UHD|video|intel.*gpu` — a redundant check to make sure no graphics-relevant update was miscategorized or missed by the first query.

Both queries returned the identical, consistent result.

## Current driver (unchanged, re-confirmed)

Intel(R) UHD Graphics 620 — **30.0.101.1338**, dated **2022-01-20**.

## Windows Optional Driver Updates — exact result

**3 driver updates are currently offered**, none of them graphics-related:

| # | Title | Provider | Date | Version | Size | Category |
|---|---|---|---|---|---|---|
| 1 | Intel - System - 4/12/2017 12:00:00 AM - 14.28.47.630 | Intel | 4/12/2017 | 14.28.47.630 | ~1.51 MB | Drivers |
| 2 | Intel - System - 9/19/2017 12:00:00 AM - 11.7.0.1000 | Intel | 9/19/2017 | 11.7.0.1000 | ~0.045 MB | Drivers |
| 3 | Lenovo Ltd. - Firmware - 1.0.0.0 | Lenovo | December 2019 | 1.0.0.0 | ~0.42 MB | Drivers |

None of these three are named or categorized as Intel Graphics, Intel Display, Intel UHD Graphics, a display adapter, or a Lenovo graphics/display driver. All three predate the current graphics driver (2022-01-20) by 2-5 years, are labeled "System"/"Firmware" rather than "Display"/"Graphics," and are unrelated to the diagnosed graphics/Vulkan-capability problem from Phase 31. Per instruction, **none of these unrelated updates were installed.**

The broader, all-types keyword search independently confirmed the same 3 total updates, with zero titles matching `graphic|display|UHD|video|intel.*gpu` — ruling out the possibility that a relevant update was present but miscategorized outside the "Driver" type filter.

## Answer to Section 3's exact question

**"No Intel/graphics driver update is currently offered through Windows Optional Updates."**

## Final report

| Item | Value |
|---|---|
| Current driver | 30.0.101.1338 / 2022-01-20 (unchanged) |
| Windows Optional Driver Updates | 3 offered — Intel System (x2, 2017), Lenovo Firmware (2019) — none graphics-related |
| Graphics driver update available | **NO** |
| Exact proposed update | N/A — none applicable to graphics; the 3 available updates are unrelated to the diagnosed problem and were not installed |
| Installation performed | **NO** |
| Restart performed | **NO** |
| Recommended next action | Windows Update's own optional-driver channel — the lowest-risk source identified in Phase 31 — has nothing to offer for this specific problem. The next step, if pursued, would need to go back to an external official source (Lenovo's or Intel's own site), which Phase 31 already found only partially reachable this session (Lenovo's page loaded but its actual driver list is served by a dynamic API that could not be queried; Intel's page remained blocked). Any such attempt should be a distinct, explicitly-approved future step — this phase does not recommend or take one itself. Alternatively, since no driver update is available through any currently-working verification path, it may be worth considering the emulator-side graphics options already identified in Phase 31 (e.g. the untested `-gpu angle_indirect` mode) as an alternative avenue not dependent on obtaining a new driver at all — noting this is a suggestion for a future phase's consideration, not an action taken here. |

**No emulator launch. No live validation. No project file touched.** Stopping here, awaiting approval before any further action.
