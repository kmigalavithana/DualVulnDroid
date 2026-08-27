# Remaining Validation Items (from Phase 14B report)

Extracted directly from `phase14b_android_validation.md` Sections D, F, I, J, K, Q.
Only items whose recorded status is PARTIAL or NOT VALIDATED are listed. Every
item already recorded PASS (Login, Registration, Session restore, Logout,
Dashboard, Search-known-app, Application Details, Security assessment,
Compatibility-COMPATIBLE-case, Alternatives, History-isolation, Chatbot
mechanism/2 questions, Flutter/backend regression suites, screenshots) is
excluded and will NOT be rerun.

| # | Item | Phase 14B recorded status | Source section |
|---|---|---|---|
| 1 | Search — unknown/no-match application | PARTIAL (not separately exercised) | §D |
| 2 | Search — network-error state | PARTIAL (not separately exercised) | §D |
| 3 | Compatibility — INCOMPATIBLE device scenario | PARTIAL (not separately re-tested) | §F |
| 4 | Compatibility — NOT_AVAILABLE / missing-device-info scenario | PARTIAL (not separately re-tested) | §F |
| 5 | Chatbot — remaining required questions: "What security issues were found in this app?", "What is CWE-89?", "What should I do about this vulnerability?", "Is this app compatible with my device?", "What does this recommendation mean?", "Is this app safe?" (6 of 8; the other 2 — CWE-295 explanation and why-risky — already PASS, live-observed) | PARTIAL | §I |
| 6 | Chat history persistence (send messages, reload screen, verify behavior) | NOT VALIDATED | §J |
| 7 | APK upload | NOT VALIDATED — "by design, nothing to test" (no upload entry point exists in the Flutter UI) | §K |

Item 7 is not retestable — there is no UI to exercise. It is carried forward unchanged, not reattempted.

## Outcome of this attempt (see `phase14c_remaining_items_attempt.md` for full detail)

Items 1–6 were **attempted** on a real Android emulator (real backend, real MySQL) but could not be reached: a sustained "System UI isn't responding" condition, confirmed via measured RAM (2.79–2.87 GB free, not recovering across five dismiss attempts and a 30-second settle) and traced to a combination of the emulator plus substantial pre-existing, unrelated load already on this host, did not clear. The attempt was stopped per the standing "do not force through a genuine resource instability" rule, and the emulator was cleanly shut down (RAM recovered to 4.01 GB, confirming the emulator — not MySQL/backend/the app — was the marginal factor).

**Final status: all of items 1–6 remain NOT VALIDATED this session** (upgraded from Phase 14B's PARTIAL/NOT VALIDATED to "attempted and blocked," not to PASS — no fabricated result). Item 7 is unchanged. One real, code-level finding was established for item 6 without needing the live device: chat history has no read-back path anywhere in the app (write-only persistence to `chat_history`), so the feature does not currently exist for a user to observe.

No previously-recorded PASS result (Login, Registration, Session restore, Logout, Search-known-app, Compatibility-COMPATIBLE, Alternatives, History isolation, chatbot mechanism, regression suites, screenshots) was rerun or altered.

## Update — chat-history read path implemented (see `phase14c_chat_history_fix.md`)

Item 6's root cause (write-only chat history, no read-back path) has been fixed: `GET /user/chat-history` added (JWT-protected, same pattern as `GET /user/history`), plus the matching Flutter load path (`chat_api_service.dart`, `chat_repository.dart`, `security_chat_screen.dart`). 7 new backend tests and 2 new Flutter tests all pass (backend regression now 323 passed/2 skipped; Flutter regression now 41 passed/0 failed). Item 6 therefore now has a genuine, tested implementation — but its **live, on-device UI validation** has explicitly not been attempted this run and remains NOT VALIDATED until the emulator is confirmed stable and the flow is actually observed.

## Current final status table

| Item | Implementation | Automated Test | Live Android Validation |
|---|---|---|---|
| 1. Search — unknown/no-match application | Pre-existing (unchanged) | Covered by existing suites | NOT VALIDATED |
| 2. Search — network-error state | Pre-existing (unchanged) | Covered by existing suites | NOT VALIDATED |
| 3. Compatibility — INCOMPATIBLE scenario | Pre-existing (unchanged) | Covered by existing suites | NOT VALIDATED |
| 4. Compatibility — NOT_AVAILABLE scenario | Pre-existing (unchanged) | Covered by existing suites | NOT VALIDATED |
| 5. Chatbot — 6 remaining required questions | Pre-existing (unchanged) | Covered by existing `test_chatbot.py` suite | NOT VALIDATED |
| 6. Chat history (read-back path) | **PASS — implemented this session** | **PASS — 7 backend + 2 Flutter tests, all passing** | **NOT VALIDATED — not attempted this run** |
| 7. APK upload | Not applicable — no UI exists | Not applicable | NOT VALIDATED — unchanged, by design |

Every row above excludes and does not alter any Phase 14B PASS result.

## Is the emulator stable enough for another attempt?

Not tested this run (per instruction, no emulator relaunch was attempted alongside the chat-history fix). As a resource-headroom check only: with the emulator stopped, free RAM is currently **4.83 GB** (of 15.75 GB), compared with the **2.79–2.87 GB** present throughout Phase 14C's failed, non-resolving ANR. This suggests a retry is more likely to succeed than last time, but it is an inference from measured headroom, not a confirmed live result.

## Phase 14D update — retry attempted, blocked pre-launch (see `phase14d_final_live_validation.md`)

The predicted retry from the section above was attempted. Pre-launch RAM was 4.35 GB (healthy). The emulator itself booted successfully in 56s and came online. But immediately after boot, free RAM measured 1.76–1.90 GB — **already below** the 2.79–2.87 GB level that caused Phase 14C's instability — before any app launch or UI interaction was attempted. Per the explicit "if resources are insufficient, STOP" instruction, the attempt was stopped at that point, proactively, rather than proceeding to rediscover the same ANR the hard way. The emulator was cleanly shut down (RAM recovered to 3.16 GB).

**All 7 items remain NOT VALIDATED.** See `final_mobile_validation.csv` for the complete, current status table. Chat-history's Implementation and Automated Tests remain PASS (unchanged, not re-touched this phase); only its Live Android UI Validation stays NOT VALIDATED.

## Phase 15 update — mobile UI polish, live validation not reattempted (see `phase15_mobile_ui_polish_and_validation.md`)

Phase 15 polished the Flutter application's visual design (theme, splash screen,
login/registration screen, chatbot message bubbles/history-loading/suggestion
chips) while preserving all existing functionality — verified by `flutter
analyze` (0 errors) and the full automated test suite (41 passed / 0 failed,
unchanged from the Phase 14C/14D baseline, no test modified).

Before attempting the emulator, a resource check found free RAM at **3.05 GB**
— within the same band that caused Phase 14C's persistent ANR (2.79–2.87 GB)
and worse than Phase 14D's pre-launch reading (4.35 GB, which itself still
collapsed to 1.76–1.90 GB post-boot and failed). Per the explicit "if RAM is
insufficient, report it and stop" instruction, the emulator was not launched
this phase.

**All 7 items remain NOT VALIDATED, unchanged from Phase 14D.** The UI polish
itself is not blocked by this — it was independently verified through static
analysis and the automated test suite — but no new live, on-device observation
was made of the polished UI or of any remaining item this phase.

## Phase 16 update — post-restart resource recheck, emulator still not launched (see `phase16_final_mobile_live_validation.md`)

Between Phase 15 and Phase 16, a Home → Security Chat FAB was added
(reusing the existing `SecurityChatScreen`/`ChatRepository` unchanged) and
verified via `flutter analyze` (0 errors) and the automated test suite
(43 passed / 0 failed, including 2 new regression tests for the FAB).

The host was then restarted with an enlarged Windows pagefile on F:, and a
fresh resource check was performed before any emulator launch, per explicit
instruction. Physical RAM free measured **2.38 GB** — below the ~4 GB gate
the instruction specified, and slightly lower than the 2.52 GB measured
immediately pre-restart. The pagefile increase enlarged *virtual* memory
headroom (~19.3 GB free) but not physical RAM, and no emulator/Java/Gradle
process was running to account for the shortage — the RAM was already
consumed by unrelated desktop applications. Per the explicit "if physical
RAM is below 4 GB, report the exact value and STOP" instruction, the
emulator was not launched.

**All items remain NOT VALIDATED, unchanged from Phase 15.** The new FAB
entry point is implementation- and automated-test-verified only; live
on-device observation of it, and of every other remaining item, is still
outstanding.

## Chatbot final validation attempt — RAM exhausted immediately post-boot (see `phase14b_chatbot_final_validation.md`, `chatbot_final_validation.csv`)

Inspected `phase14b_android_validation.md` Section I first to establish the
exact gap list: only 2 of 8 required chatbot questions, and 2 of 4 actual
Flutter suggestion chips, were ever directly observed live in Phase 14B; chat
history, multi-turn conversation, fallback/error handling, long-response
scrolling, keyboard/input behaviour, and overflow/crash checks were never
live-observed at all.

Pre-launch RAM was 3.29 GB free (below the ~4 GB level suggested previously,
but with no project-related process running to account for it, so a real
attempt was made rather than stopping at the reading alone). The `Pixel_4`
AVD cold-booted successfully in 36s. Immediately after boot — before any app
was installed or launched — free RAM measured **0.64 GB**, with
`qemu-system-x86_64` alone consuming 2.78 GB. This is far below every prior
instability threshold this session (2.79–2.87 GB caused Phase 14C's
persistent ANR; 1.76–1.90 GB caused Phase 14D's failure). The emulator was
shut down immediately and cleanly (`adb emu kill`, confirmed terminated); RAM
recovered to 3.78 GB, confirming the emulator itself was the cause.

**No new live validation occurred.** All items in the gap list above remain
NOT VALIDATED. The 2 previously-observed exchanges (why-risky chip, CWE-295
explanation) remain PASS, unchanged from Phase 14B — not re-tested, not
altered.

## Phase 21 update — REAL LIVE VALIDATION SUCCEEDED (see `phase21_lightweight_emulator_live_validation.md`)

`Medium_Phone_API_36.1` cold-booted and, for the first time in this
project's history, **remained stable for the entire session** (30+
minutes of continuous interaction) rather than ANR-ing. The real
DualVulnDroid app was installed and launched against the real backend,
real MySQL, real production XGBoost, and the real Decision Engine.

One genuine environment defect was found and fixed before validation
could proceed: **the backend process and MySQL were both not running**
(a leftover state from earlier in the session, unrelated to any code
change). Both were started using their existing, unmodified
configuration and verified end-to-end via direct API/DB calls before
returning to the UI. No application code was touched.

**Every chatbot/mobile item this phase targeted was executed with real,
observed evidence and passed:** Q3-Q8 (all 6 remaining required
questions), C3-C4 (suggestion chip wording), FAB1 (Home -> Security Chat
FAB), M1 (multi-turn conversation, 12 real exchanges), H1 (chat history -
genuinely reloaded correctly after navigating away and back), F1 (unknown
question), F2 (empty input), F3 (network failure - backend deliberately
stopped mid-session, real typed-exception message rendered, backend then
restarted and confirmed working), L1 (long response/scrolling), K1
(keyboard/send/multi-line growth), and U1 (no overflow/crash observed at
any point). 48 real screenshots were captured. No result was fabricated;
several responses were the app's real, correct *fallback* behaviour
(since this chat session had no `app_id` context) rather than an
app-specific answer, and are reported exactly as observed.

**No application bug was found or fixed this phase** — the one defect
(Section 3 of the phase report) was environmental only.

Search unknown-app/network-error, remaining Search sub-cases, and both
Compatibility sub-cases were outside this phase's scope and remain NOT
VALIDATED.

## Phase 22 update — Search-B/D and Compatibility-B/C attempted, emulator ANR (see `phase22_search_compatibility_live_validation.md`)

Confirmed the exact remaining test definitions directly from
`phase14b_android_validation.md` (Search-B unknown application, Search-D
network error, Compatibility-B INCOMPATIBLE, Compatibility-C
NOT_AVAILABLE — no new case invented) and pre-identified real data to
exercise them (Snaptube, `min_sdk_version=21`, plus the existing
`ZZPhase21Tester` account) before touching the emulator, so no time would
be spent guessing once inside the app.

`Medium_Phone_API_36.1` was cold-booted under the identical configuration
that completed Phase 21's entire session successfully. This time, System
UI entered a persistent ANR immediately after boot and did not clear
across a 43-second bounded wait-and-recheck. RAM was confirmed healthy
throughout (4.00 GB free, stable) — ruling out resource exhaustion; qemu
CPU time again showed the same extreme, multi-core-saturating pattern
documented in Phases 17/19 (1178 CPU-seconds in ~110s wall time). Per
explicit instruction to stop immediately rather than cycle through
configurations, the attempt was stopped and the emulator shut down
cleanly; RAM recovered to 6.99 GB. The backend and MySQL (left running
from Phase 21) were reconfirmed healthy afterward, undisturbed.

**The Flutter app was never installed or launched this phase. All four
targets (Search-B, Search-D, Compatibility-B, Compatibility-C) remain NOT
VALIDATED**, unchanged from before this phase. No screenshot was
captured. No existing PASS result — including every genuine Phase 21
result — was touched.

This is notable as the first direct evidence that Phase 21's stability
was not attributable to a fixed configuration change: the identical setup
produced a stable 30+ minute session once and a persistent ANR the very
next attempt, pointing to session-to-session variability in whatever
Phase 18 diagnosed as the underlying graphics-pipeline issue, rather than
something resolved for good.

## Phase 17 update — lightweight AVD attempted, persistent System UI ANR unrelated to RAM (see `phase17_lightweight_emulator_validation.md`)

Compared `Pixel_4` and `Medium_Phone_API_36.1` (`config.ini`): both use
identical guest RAM (2048 MB), identical CPU cores (4), and the same system
image — `Medium_Phone_API_36.1` is not a meaningfully lighter AVD, just a
different device skin. Used it anyway per the instruction not to reattempt
`Pixel_4`. Rebuilt the debug APK first (the existing one predated the Phase
15/16 UI changes), stopped the resulting Gradle daemon once done, and
reached the healthiest pre-launch reading recorded this project (6.72 GB
free RAM, nothing else running).

The AVD cold-booted in 33s to a strong 3.83 GB free RAM — but `dumpsys
window` showed `Application Not Responding: com.android.systemui`
immediately, and it did not clear across a 64-second bounded wait-and-recheck
sequence (6/10/18/30s). Critically, RAM was re-measured during the ANR and
held steady (3.98 GB free, not degrading), while `qemu-system-x86_64` had
burned ~913 CPU-seconds in ~100s of wall time — pointing to a CPU-bound
stall (virtualization acceleration or antivirus interference, most likely),
**not RAM exhaustion**, as this specific failure's cause. This is a new
finding: it means sufficient free RAM at boot, on its own, is not sufficient
to guarantee a stable emulator session on this host.

The emulator was shut down cleanly per the standing "don't force through
instability" rule. **The Flutter app was never installed or launched** —
System UI itself never stabilised. All items remain NOT VALIDATED, unchanged
from before this phase; Q1/Q2/C1/C2 remain PASS from Phase 14B, untouched.

## Phase 18 update — root cause reframed: graphics pipeline, not RAM/CPU virtualization (see `phase18_emulator_environment_diagnostics.md`)

Pure diagnostics phase, no emulator boot. Retrospective analysis of the
Phase 16/17 boot logs found, in both: `WHPX on Windows 10.0.26200 detected.
Windows Hypervisor Platform accelerator is operational` (VERIFIED — CPU
virtualization was never the problem) alongside `Critical: Failed to load
opengl32sw... Falling back to system OpenGL` and a warning that the
installed Intel UHD 620 driver (dated January 2022) cannot properly support
Vulkan (both VERIFIED, direct log findings). Concluded LIKELY that this
degraded graphics path, not RAM or CPU-virtualization availability, drives
the sustained near-total-host CPU saturation and ANR. Recommended (not
performed): an Android Emulator package update, an explicit non-`auto` GPU
mode on the next attempt, and a driver update pending confirmation.

## Phase 19 update — reversible `-gpu swiftshader_indirect` attempted, did not fix the ANR (see `phase19_graphics_fix_and_live_validation.md`)

From the healthiest pre-launch reading yet (7.15 GB free RAM), `Medium_Phone_API_36.1`
was cold-booted with `-gpu swiftshader_indirect` (confirmed a supported mode
first). It briefly reached a genuine, responsive launcher focus — better
than any prior attempt — but degraded into a persistent ANR (now on
`com.google.android.apps.nexuslauncher`) within 10 seconds, and it did not
clear across a 40-second bounded monitoring window. RAM stayed stable
(~3.45-3.49 GB, ruling out RAM again); `qemu-system-x86_64` CPU consumption
was *higher* than the non-swiftshader Phase 17 attempt, not lower. The same
`opengl32sw` load failure recurred (confirming it's independent of guest
GPU mode), and a new error appeared — `UpdateLayeredWindowIndirect failed
... A device attached to the system is not functioning` — a host Windows
display-driver-level failure, not an Android-tooling issue. Per the
graphics diagnostic success criteria, the environment is not considered
improved; the attempt was stopped before installing the app, per
instruction. Recommendation now leans toward **B: an Intel UHD 620 driver
update** as more likely to help than an emulator package update alone,
pending explicit confirmation before either is attempted.

**All items remain NOT VALIDATED.** No screenshot was captured. Q1/Q2/C1/C2
remain PASS from Phase 14B, untouched.

## Phase 27 update — final live UI validation of the new 59-test build attempted, delayed-onset ANR (see `phase27_final_live_ui_validation.md`)

A separate, later UI-restyle phase (not itself documented in this file, since
it predates the items above and its own outcome is tracked in
`phase_ui_implementation_and_validation.md`) added `SettingsScreen`,
`VulnerabilityDetailScreen`, `NotAvailableScreen`, and a 4-tab bottom
navigation shell, plus restyled all 8 pre-existing screens, bringing the
Flutter automated suite from 43 to 59 passing tests. That phase's own live-
validation attempt was blocked by the same class of ANR documented
throughout this file. Phase 27 is a second, independent attempt specifically
targeting this new build.

Pre-launch RAM was 6.38 GB free (healthy). The existing APK was found stale
(predated all 16 UI-restyle source files) and was rebuilt; the rebuild was
confirmed current before proceeding. `Medium_Phone_API_36.1` cold-booted in
10 seconds to a genuinely responsive System UI/launcher — the first time
since Phase 21 that System UI was *not* already in an ANR state immediately
after boot. A deliberate extra 15-second stability recheck was performed
specifically because of this improved initial signal.

**At +15s, the same `com.android.systemui` ANR appeared** — a delayed onset,
not previously observed in this project's history (every prior ANR was
present from the first post-boot check). It did not clear across a further
20-second bounded recheck. RAM remained healthy throughout (2.91-2.96 GB
free, not degrading); qemu CPU time again showed the same extreme,
multi-core-saturating pattern (997.4 CPU-seconds in ~65-70s wall time),
consistent with every prior finding and Phase 18's graphics-pipeline
diagnosis.

Per instruction, the attempt was stopped immediately: **the APK was never
installed, no screen was reached, and no screenshot was captured.** All 12
UI-restyle target screens (UI-01 through UI-12) and all 9 functional-
regression items remain **NOT VALIDATED**. No previously genuine PASS result
(Phase 14B, Phase 21) was touched. The one new finding this phase
contributes to this project's diagnostic history is that the instability's
onset timing is itself variable (immediate in most prior attempts, delayed
here), reinforcing that it is not a simple, single-cause, deterministically
timed failure.

## Phase 30 update — final live validation attempted, persistent ANR again (see `phase30_final_live_ui_validation.md`)

A third, independent live-validation attempt, specifically targeting the
final UI-redesign build (13 screens: Splash, Login, Registration,
Dashboard, Search, Application Details, Vulnerability Details, Security
Results, Security Chat, Chat History, Settings, Not Available, Bottom
Navigation).

Pre-launch RAM was 6.17 GB free (healthy); `flutter analyze` (0 errors)
and `flutter test` (59 passed / 0 failed) were re-confirmed immediately
before the attempt. The APK was rebuilt fresh and confirmed newer than
the prior build and current against all source files.
`Medium_Phone_API_36.1` cold-booted in 50 seconds. Per this phase's
instruction, an additional 20-second wait was observed after boot
completion (rather than checking immediately) before the first stability
check.

**At +20s post-boot-complete, `com.android.systemui` was already in a
persistent ANR** — confirmed unchanged at a further recheck 15 seconds
later (+35s). RAM remained healthy throughout (3.48 GB free during the
ANR); qemu CPU time again showed the same extreme, multi-core-saturating
pattern (503.8 CPU-seconds in ~85s wall time), consistent with every
prior finding and Phase 18's graphics-pipeline diagnosis.

Per instruction, the attempt was stopped immediately: **the APK was never
installed, no screen was reached, and no screenshot was captured.** All
13 UI-redesign target screens and all 12 functional-regression flows
remain **NOT VALIDATED**. No previously genuine PASS result (Phase 14B,
Phase 21) was touched.

**Summary across the first three UI-redesign live-validation attempts**
(the UI-restyle phase itself, Phase 27, and Phase 30): all three were
independently blocked by the same class of System UI ANR before the
application could be installed or launched.

## Phase 32 update — FIRST GENUINE LIVE SESSION ACHIEVED (see `phase32_final_live_ui_validation.md`)

A fourth attempt, using the same AVD and instructed to give the emulator a
longer, patient stabilization window rather than checking immediately,
succeeded: a 90-second bounded post-boot check showed **zero ANR at every
recheck** — the first sustained stable boot observed in this project's
history for the restyled build. The current APK was installed and
launched successfully.

**Genuinely live-validated this phase** (real device, real backend, real
database, 20 screenshots): real registration (`POST /register`, real
success snackbar), real login, Dashboard (real user data, settings icon,
3-action row, FAB, empty recent-assessments state), the new 4-tab bottom
navigation (real tab-switch observed), both honest Not-Available screens
(Installed Apps, Upload APK), Search (real query "Snaptube" against the
real backend, real HIGH-risk result), Application Details (real header/
version/date), and — for the first time — the new **gradient risk-status
card** rendering correctly with real data (HIGH, Score 80,
AVOID_INSTALLING), the real Findings/evidence display, and the
finding-expansion interaction revealing a real, correctly-wrapped
"Malicious URL" finding.

**Session ended partway through** (~23 minutes in, after tapping "View
details" on the real finding): the device stopped responding to input.
Diagnosis (without restarting or modifying anything) found `system_server`
stuck in kernel state `D` (uninterruptible sleep) — the InputManagerService
had genuinely disappeared from the guest's service list, and the screen
went fully black. A bounded 60-second recheck showed no recovery. Host RAM
was confirmed healthy throughout (3.62-3.73 GB free), ruling out memory
exhaustion; qemu's CPU-time-to-wall-time ratio was notably *not* in the
extreme multi-core-saturation range seen during the earlier ANR episodes —
a genuinely different failure signature from Phase 31's documented
pattern, not an exact repeat of it. Per instruction, the AVD was **not**
restarted, wiped, or reconfigured; the session was left as-is.

**Vulnerability Details (UI-07), Security Chat, Chat History, Settings,
and the remaining planned functional/edge-case tests (network-error
recovery, Compatibility NOT_AVAILABLE, unknown-app search, empty search,
keyboard/scroll edge cases) remain NOT VALIDATED** — not reached before
the session ended. This is reported honestly, not upgraded, and no
previously genuine PASS result (Phase 14B, Phase 21) was touched.

**No application-level bug was found.** The session-ending failure is a
host/environment issue, not a DualVulnDroid defect — no code was changed
this phase.

## Phase 33 update — RECOVERED, and the most comprehensive live session in this project's history (see `phase33_final_live_validation.md`)

The Phase 32 emulator was confirmed unrecoverable via read-only
diagnostics (ADB transport alive, but `system_server` still `D`, input
service gone, app process gone, screen still black). Authorized clean
recovery was performed: `adb emu kill` succeeded within 5 seconds (no
force-kill needed), and the **same, unmodified** `Medium_Phone_API_36.1`
AVD was rebooted. The +20s post-boot check showed `system_server` healthy
(state `S`) and zero ANR.

The recovered session then ran continuously and stably for **~1 hour 45
minutes of in-app time**, completing nearly the entire remaining priority
list with 44 genuine screenshots:

- **View Details → Vulnerability Details** — the exact action that hung
  Phase 32 — completed with no issue this time. Real evidence, honest SHAP
  disclaimer, correct absence of the CWE reference panel (this finding's
  `cwe` is null, not CWE-89/295) and of any Quick Fix button.
- **Security Chat** — FAB navigation, suggestion chips, a real 3-turn
  conversation (a suggestion-chip question, a typed question about
  CWE-89, and a deliberately nonsensical unknown question), all with real
  `/ai-chat` responses and a real "Today" date separator.
- **Chat history persistence** — left the chat, reopened via the
  bottom-nav Chat tab, the full 3-turn conversation reloaded correctly.
- **Settings** — real Account data, honest Notifications/Appearance (no
  fake toggles), real About section, real Logout button.
- **Search — unknown application** — real honest empty state, no
  fabricated results.
- **Compatibility — INCOMPATIBLE** — real API level 15 vs Snaptube's real
  `minSdkVersion=21` → real red INCOMPATIBLE badge.
- **Compatibility — NOT_AVAILABLE** — no Android version supplied → real
  NOT_AVAILABLE badges and a real DecisionCard "Avoid installing"
  recommendation (reflecting the app's real HIGH security risk, which
  compatibility does not override).

**Search — network-error remains NOT VALIDATED** — not attempted this
phase (would require deliberately stopping the backend mid-session; not
reached given the breadth of other tests already completed).

**No application-level bug was found or fixed across Phase 32 or Phase
33.** No previously genuine PASS result (Phase 14B, Phase 21) was
touched. See `final_mobile_validation.csv` for the complete, item-by-item
current status of every tracked case.
