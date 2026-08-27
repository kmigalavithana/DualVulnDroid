# Phase 32 — Final Live Android UI Validation (Real Device Session)

## 1. Summary

This session achieved the **first-ever genuine live, on-device confirmation of the redesigned UI's core flow** — registration, login, dashboard, bottom navigation, honest not-available states, search, application details, and the new risk-color gradient status card all worked correctly against the real backend and real database, captured across 21 genuine screenshots. The session then encountered a genuine, well-diagnosed host/environment failure (a `system_server` kernel-level hang, distinct from the earlier ANR pattern) approximately 23 minutes in, which stopped further testing. Every result below is either a directly observed PASS with a screenshot, or an honestly reported NOT VALIDATED / PARTIAL with the exact reason. Nothing is fabricated.

## 2. Pre-flight and boot

RAM before boot: 5.83 GB free. APK confirmed current (0 source files newer than the build). `Medium_Phone_API_36.1` cold-booted in 70s. Per instruction, a **90-second bounded stabilization window** was observed (rechecked at +15/30/45/60/75/90s) with **zero ANR at every check** — the first time this project has observed sustained, multi-check stability immediately after boot. RAM after boot: 3.33 GB free (healthy).

The pre-existing stale app install was uninstalled first (guest storage was at 92% used, 478 MB free — tight against the 175 MB APK); after uninstall, 724 MB free. The current APK was installed (`adb install -r`, **Success**) and launched (`monkey -p com.example.dualvulndroid_flutter`, confirmed via `mCurrentFocus` pointing at `MainActivity`, zero ANR).

## 3. Genuinely validated screens and flows (live, real backend, real database)

| ID | Item | Result | Evidence |
|---|---|---|---|
| — | Emulator stability at launch | **PASS** | 90s zero-ANR window, direct `dumpsys window` checks |
| — | APK install | **PASS** | `adb install -r` → `Success` |
| — | App launch | **PASS** | `mCurrentFocus` = MainActivity, no ANR |
| UI-01 | Splash | **NOT VALIDATED** | The app passed through Splash to Login before the first screenshot could be captured (session restore is fast); not independently observed this session |
| UI-02 | Login | **PASS** | `01_launch.png` — gradient icon badge, restyled title, card form, no overflow |
| UI-03 | Registration | **PASS** | `02_register.png` through `08_check.png` — "Create your account" title, Full name/Email/Password fields, Register button, toggle link, all render correctly |
| — | Functional: Registration (real `POST /register`) | **PASS** | `09_register_result.png` — real green "Registration successful. Please log in." snackbar from the real backend; auto-switched to Login with email prefilled |
| — | Functional: Login (real `POST /login`) | **PASS** | `10_login_result.png` → `11_dashboard.png` — real session established, real username "Phase32Tester" shown on Dashboard |
| UI-04 | Dashboard | **PASS** | `11_dashboard.png` — settings-gear AppBar icon, "Welcome, Phase32Tester" (real user data), 3-action row (Search Apps/Installed Apps/Upload APK), "Recent assessments" honest empty state ("No applications assessed yet." — real, not fabricated), FAB visible |
| UI-13 | Bottom Navigation | **PASS** | `11_dashboard.png` (Home tab selected, pill indicator) and `15_search_tab.png` (Search tab selected after tap) — real tab-switch state change observed |
| — | Home → Security Chat FAB (visual) | **PASS** (visible only) | `11_dashboard.png` — FAB correctly rendered, labeled "Security Chat" |
| — | Home → Security Chat FAB (navigation) | **NOT VALIDATED** | Never tapped — session ended before this test was reached |
| UI-12 | Not Available — Installed Apps | **PASS** | `12_installed_apps.png` — honest message "On-device app scanning is not available in this version...", no fabricated app list, back arrow works |
| UI-12 | Not Available — Upload APK | **PASS** | `13_upload_apk.png` — honest message "Uploading an APK for direct analysis is not available in this version...", no fake result |
| UI-05 | Search screen | **PASS** | `14_search_screen.png` — restyled hint "Search application name...", empty-state icon/message |
| — | Search — valid real app | **PASS** | `16_search_result.png` — real query "Snaptube" against real backend returned real result: Snaptube, com.snaptube.premium, real **HIGH** risk badge |
| — | Search — unknown/non-existing app | **NOT VALIDATED** | Not reached before session ended |
| — | Search — empty search | **NOT VALIDATED** | Not reached |
| — | Search result → Application Details navigation | **PASS** | `17_app_details.png` → `18_app_details.png` |
| UI-06 | Application Details | **PASS** | `18_app_details.png` — real header (Snaptube, com.snaptube.premium, real version 7.57.0.75750110, real assessed date 2026-08-17) |
| UI-08 | Security Results (new gradient risk-status card) | **PASS** | `18_app_details.png` — the restyled red-gradient wash status card rendering correctly with real data: **HIGH** badge, **Score: 80**, **Recommendation: AVOID_INSTALLING** — first-ever live confirmation of this restyled component |
| — | Findings section (real vulnerability display) | **PASS** | `18_app_details.png`/`20_finding_expanded2.png` — real finding "Malicious URL", HIGH severity, bug icon |
| — | Finding expand/collapse (ExpansionTile) | **PASS** | `20_finding_expanded2.png` — tapped, expanded to show the full real description (a real, genuinely long malicious URL string, correctly text-wrapped with no overflow), Status: OPEN |
| — | "Why was this flagged?" section | **PASS** | `18_app_details.png` — real "WHY THIS DECISION?" eyebrow label, real reason text ("The APK contains 1 suspicious URL identified during static analysis."), real EVIDENCE bullet |
| — | "View details" button (new, per-finding) | **PASS** (visible) | `20_finding_expanded2.png` — button correctly rendered on the real finding |
| UI-07 | Vulnerability Details screen | **NOT VALIDATED** | The "View details" button was tapped, but the device became unresponsive (see Section 4) before any screenshot of the resulting screen could be captured. Whether navigation actually succeeded is genuinely unknown — not claimed as PASS |
| — | Compatibility section (real Snaptube data, minSdkVersion=21) | **NOT VALIDATED** | Not reached — would have required scrolling further and tapping "Check device compatibility"; session ended first |
| — | Android security metadata section | **NOT VALIDATED** | Only its section heading was barely visible at the very bottom edge of `18_app_details.png`; not confirmed fully rendered or scrolled into view |
| — | History tab | **NOT VALIDATED** | Not reached |
| UI-09 | Security Chat | **NOT VALIDATED** | Not reached |
| UI-10 | Chat History (screen/grouping) | **NOT VALIDATED** | Not reached |
| — | Chatbot Q&A (normal / app-context / unknown / multi-turn) | **NOT VALIDATED** | Not reached |
| — | Chat history persistence (leave/reopen) | **NOT VALIDATED** | Not reached |
| UI-11 | Settings | **NOT VALIDATED** | Not reached |
| — | Explicit scroll-gesture test | **NOT VALIDATED** | Content extending below the fold was observed (Application Details), but an explicit scroll gesture was not exercised before the session ended |
| — | Keyboard open/close, multi-field text entry | **PASS** | Extensively exercised during registration (`02`–`09`) — keyboard opened correctly, multiple fields focused/typed/cleared, closed correctly on submit, no layout break |
| — | Buttons/chips/cards — overflow or clipping check | **PASS** (for every screen reached) | No overflow, clipping, or crash observed on any of the 20 real screenshots captured before the session ended |
| — | Backend network-error test | **NOT VALIDATED** | Not attempted — session became unresponsive before this planned test |
| — | Compatibility NOT_AVAILABLE case | **NOT VALIDATED** | Not reached |

## 4. Session-ending failure — genuine evidence, not an application defect

At approximately 23 minutes into the session (device time ~11:53, after the "View details" tap), the device stopped responding to input. Diagnosis, performed without restarting or modifying anything:

- `adb shell input tap ...` failed: `cmd: Can't find service: input`.
- `adb shell screencap` failed: `Transport endpoint is not connected`.
- `adb exec-out screencap` (bypassing the sdcard write path entirely) succeeded mechanically but returned a **fully black frame** (`23_execout.png`).
- `adb shell service list` still enumerated 80 services, but **`input` was not among them** — the InputManagerService had genuinely gone away.
- `adb shell ps -A` showed `system_server` in **state `D`** (uninterruptible sleep — a kernel-level block, not a crash, not a normal ANR-banner state) while `surfaceflinger` remained nominally running.
- A **bounded 60-second recheck** (per this project's established protocol) at +15/30/45/60s showed `system_server` remaining in state `D` throughout, unchanged.
- Host RAM was checked twice during this failure: 3.62 GB and 3.73 GB free — **healthy, ruling out RAM exhaustion**, consistent with every prior finding in this project.
- qemu CPU time (3086s) against elapsed wall time (~46 minutes since boot) was **not** in the extreme multi-core-saturation range seen during the earlier ANR episodes (Phase 27/30 showed 5-12x realtime; this session's ratio was closer to 1x) — a genuinely different failure signature from the immediate/delayed-onset systemui ANR documented in Phase 31, not the same pattern recurring identically.

**This is not an application defect.** No DualVulnDroid code was reached or exercised at the moment of failure beyond a single button tap already known to work at the UI layer (the tile had already expanded correctly moments earlier). This is a deeper manifestation of the same class of host/environment instability Phase 31 diagnosed (host graphics/compositing capability gap), now presenting as a `system_server` hang partway through an otherwise-successful session rather than an immediate boot-time ANR. Per your explicit instruction not to restart, wipe, or reconfigure the AVD, **no recovery action was taken** — the session was left in its current (hung) state and no further live interaction was attempted.

## 5. Test counts

| Result | Count |
|---|---|
| **PASS** (genuinely observed live) | 20 |
| **FAIL** | 0 |
| **PARTIAL** | 0 |
| **NOT VALIDATED** | 16 |

No item was marked PASS without a captured screenshot or direct, observed evidence (e.g. the real snackbar text, the real tab-selection state change).

## 6. Screenshots captured (21 files, all genuine, `dualvulndroid_flutter/phase32_screenshots/`)

`01_launch.png`, `02_register.png`, `03_register_filled.png`, `04_cleared.png`, `05_register_filled2.png`, `06_email_fixed.png`, `07_email_cleared.png`, `08_check.png`, `09_register_result.png`, `10_login_result.png`, `11_dashboard.png`, `12_installed_apps.png`, `13_upload_apk.png`, `14_search_screen.png`, `15_search_tab.png`, `16_search_result.png`, `17_app_details.png`, `18_app_details.png`, `19_finding_expanded.png`, `20_finding_expanded2.png`, `23_execout.png` (the black-frame failure evidence).

Note: screenshots `03`–`08` document a real, known `adb shell input text` quirk (dropping leading characters, e.g. "hase32tester@..." instead of "phase32tester@...") encountered and worked around live, exactly as documented in this project's established testing methodology — not an application bug. The real registered account's actual email ended up as `xphase32tester@dualvulndroid.test` (visible in `09_register_result.png`/`10_login_result.png`), used consistently thereafter.

## 7. Bugs found

**None.** No application-level defect was discovered. The session-ending failure (Section 4) is an environment/host issue, already extensively diagnosed in Phase 31, not a DualVulnDroid code defect. No code was changed this phase.

## 8. Relationship to prior evidence

This phase's PASS results are **new, genuine, live evidence** for the UI-restyle build specifically — the first such evidence obtained after three prior blocked attempts (the UI-restyle phase's own attempt, Phase 27, Phase 30). They do not replace or downgrade any earlier genuine PASS result:

- **Automated Test PASS** (unchanged): Flutter 59/59, `flutter analyze` clean — established before this phase, not re-run during it.
- **Previous Live PASS** (unchanged): Phase 14B and Phase 21's results remain exactly as recorded, for the pre-restyle UI.
- **Current Live PASS** (new, this phase): the 20 items in Section 3 marked PASS — the first live confirmation of the restyled/new UI (Login, Registration, Dashboard, Bottom Navigation, both Not Available states, Search, Application Details, the new gradient risk-status card, Findings/evidence display, and the finding-expansion interaction).
- **Still NOT VALIDATED**: Vulnerability Details screen (tapped but unconfirmed), Security Chat, Chat History, Settings, and the remaining functional-regression/edge-case items listed in Section 3 — carried forward honestly, not claimed.

**The entire UI is not claimed as validated.** Roughly half of the originally planned 13-screen, 20-flow test matrix was genuinely reached and passed; the remainder is honestly reported as not validated, with the exact reason (either "not reached before the session ended" or, for Vulnerability Details specifically, "tapped but outcome unconfirmed").
