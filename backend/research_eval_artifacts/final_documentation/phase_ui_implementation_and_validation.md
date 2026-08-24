# Phase — UI Implementation and Validation (Approved Design → DualVulnDroid Flutter App)

## 1. Scope and source of truth

No Figma file or design image was accessible in this session — no Figma MCP/API integration exists, and none was connected. The **approved design's source of truth was the detailed screen-by-screen text specification** the user supplied (dark cybersecurity theme, electric-blue/cyan accents, green/orange/red risk states, rounded modern cards, 16 named screens, bottom navigation, Settings, etc.), combined with two explicit scoping decisions the user made before implementation began:

1. Design concepts with no real backend/data support (Security Scan animation, Upload APK, dedicated CWE-89/CWE-295 screens, SHAP feature chart, "Apply Quick Fix") must **not** be skipped outright, but must **never fabricate data** — real data where it exists, honest "not available" messaging where it doesn't.
2. Build a real **Settings screen** and a real **4-tab bottom navigation** (Home/Search/History/Chat) — explicitly **not** a 5th "Installed Apps" tab and **not** a Profile tab, since neither has any real capability behind it.

This document reports exactly what changed, what stayed real, and what remains honestly unavailable.

## 2. Screens updated (visual restyle, functionality preserved)

| Screen | File | What changed | What did NOT change |
|---|---|---|---|
| Splash | `lib/screens/splash_screen.dart` | Title/subtitle now use theme type-scale slots; icon badge gets a subtle gradient ring | `restoreSession()` routing logic |
| Login/Register (single toggle screen) | `lib/screens/login_screen.dart` | Title uses `headlineSmall`; icon badge gradient ring | `_isRegisterMode` toggle, validators, real `AuthRepository.login/register` calls, error snackbars — **no 2FA/OTP added** |
| Dashboard | `lib/screens/dashboard_screen.dart` | AppBar logout icon → settings-gear icon (`AppRouter.toSettings`); welcome text restyled; single "Search for an application" button replaced with a compact 3-action row (Search Apps / Installed Apps / Upload APK); risk summary restyled into 2 real stat cards + existing chip row | `_historyFuture`/`_refresh`, FAB → `toChat` (kept), Recent Assessments cards, `toHistory` |
| Search Applications | `lib/screens/search_application_screen.dart` | Hint text aligned to design copy; result rows gained a leading app-icon avatar (real `iconUrl` when present, honest generic icon otherwise — search results never carry `iconUrl` today, so this always shows the generic icon in practice, which is correct, not fabricated) | `_search()`, `AppsRepository` calls, state views, tap → `toApplicationDetails` |
| Application Details | `lib/screens/application_details_screen.dart` | Header/status section restyled with a real-risk-color gradient wash ("large status card"); each finding gained a "View details" action | `_load()`, `getSecurity()`/`getApplication()`, "not assessed" branch, evidence/reason rendering, Android metadata, device-compatibility push, "Ask about this app", alternatives section |
| Device Compatibility | `lib/screens/device_compatibility_screen.dart` | Section-title typography aligned to theme; `runSpacing` added to both chip `Wrap`s (fixes a real overflow risk at narrow widths) | Form/auto-detect, `POST /apps/{id}/compatibility`, result widgets, RAM-not-used disclaimer |
| Security Chat | `lib/screens/security_chat_screen.dart` | Added real **date separators** ("Today"/"Yesterday"/literal date) computed from each message's real `sentAt` | `_loadHistory`/`_send`, `/ai-chat` + `/user/chat-history` calls, app-context bar |
| Assessment History | `lib/screens/assessment_history_screen.dart` | Card/typography polish only | `getHistory()`, `_formatDate` (still literal `YYYY-MM-DD` — no invented "Today/Yesterday" grouping here, since that treatment is only honest where real per-message timestamps exist, i.e. the chat screen) |

## 3. New screens/files (real functionality unless noted)

| File | Purpose | Real or honest-placeholder |
|---|---|---|
| `lib/widgets/app_shell.dart` (`AppShell`) | Bottom-nav shell (Home/Search/History/Chat), lazy-built `IndexedStack` + Material 3 `NavigationBar` | Real — wraps the 4 existing real screens unmodified internally |
| `lib/screens/settings_screen.dart` (`SettingsScreen`) | Account (real name/email), Notifications ("not available"), Appearance ("Dark, fixed"), About, real Logout | Real (Account, Logout) + honestly non-interactive (Notifications, Appearance) |
| `lib/screens/vulnerability_detail_screen.dart` (`VulnerabilityDetailScreen`) | One reusable screen for any finding — title/evidence from real `VulnerabilityModel` fields; SHAP section reuses the app's own existing real disclaimer; a static, clearly-labeled generic CWE-89/CWE-295 reference panel; **no** "Apply Quick Fix" button | Real evidence + honest SHAP disclaimer + static generic reference copy |
| `lib/screens/not_available_screen.dart` (`NotAvailableScreen`) | Thin wrapper around the existing `EmptyStateView`, used for Installed Apps and Upload APK | Honest-unavailable-state, no fabricated content |

## 4. Routing changes (`lib/routing/app_router.dart`)

- `toDashboard` now targets `AppShell` instead of bare `DashboardScreen` (same `pushAndRemoveUntil` behavior).
- `toSearch`, `toApplicationDetails`, `toApplicationDetailsById`, `toHistory`, `toChat` — unchanged, still plain pushes on top of whatever's on the stack.
- Added: `toSettings`, `toVulnerabilityDetail(context, vulnerability)`, `toInstalledApps`, `toUploadApk`.

## 5. Logout relocation

The real `AuthRepository.logout()` + `AppRouter.toLogin` call moved from Dashboard's AppBar icon into `SettingsScreen`'s "Log out" row — the call itself is byte-for-byte identical, only its location changed. Verified no existing test referenced the old logout icon before moving it.

## 6. Tests

**Baseline before this phase:** 43 passed / 0 failed.
**Final count after this phase: 59 passed / 0 failed.** (`flutter analyze`: 0 errors, 6 pre-existing style-only infos, none introduced by this phase.)

New/changed test files:
- `test/screens/security_chat_screen_test.dart` (**new**, 2 tests) — real day-separator grouping from real timestamps; empty/unauthenticated state shows no separators.
- `test/screens/vulnerability_detail_screen_test.dart` (**new**, 5 tests) — CWE-89/CWE-295/generic-fallback titles; real evidence fields render verbatim; the real SHAP disclaimer is present verbatim; a permanent regression guard asserting no "Quick Fix" text ever appears.
- `test/screens/settings_screen_test.dart` (**new**, 2 tests) — Notifications/Appearance are static text with **zero** `Switch`/`SwitchListTile` anywhere; Log out calls the real `AuthRepository.logout()` and returns to `LoginScreen`.
- `test/screens/not_available_screen_test.dart` (**new**, 2 tests) — only the honest message renders; explicit assertion that none of the original spec's example app names (WhatsApp/TikTok/Chrome/Facebook/Instagram) ever appear.
- `test/widgets/app_shell_test.dart` (**new**, 2 tests) — all 4 nav destinations present, Home FAB still present alongside the Chat tab; **lazy-build verified directly** by counting real `/user/history` requests (1 call on mount, a 2nd only after visiting the History tab, none from visiting Search/Chat).
- `test/screens/dashboard_screen_test.dart` (**changed**, 2→4 tests) — the old exact-text assertion `'Search for an application'` no longer applies (button copy legitimately changed to a compact 3-action row); replaced with an assertion that tapping "Search Apps" still opens the real `SearchApplicationScreen`. Added: Installed Apps/Upload APK show honest messaging with no fabricated app names; the new Settings entry point opens `SettingsScreen`.
- `test/screens/application_details_screen_test.dart` (**changed**, 7→8 tests) — all 7 original assertions pass unmodified; added a test that "View details" opens `VulnerabilityDetailScreen` with the same real finding.

No existing assertion was weakened or removed — the one existing assertion that changed (`dashboard_screen_test.dart`'s button-text check) changed because the underlying UI copy legitimately changed as part of this restyle, and the replacement test still verifies the same real navigation behavior.

## 7. Live validation

**Attempted, not completed — reported honestly rather than fabricated.**

- Pre-flight: 6.47 GB RAM free (of 15.75 GB), no emulator/gradle/java processes running, healthy baseline consistent with this project's prior successful Phase 21 session.
- `Medium_Phone_API_36.1` (the same AVD that completed Phase 21 successfully) was cold-booted with the identical default/auto-GPU configuration. Boot completed in ~70 seconds.
- **Immediately after boot**, `dumpsys window` showed `Application Not Responding: com.android.systemui` — the same failure signature recorded in Phase 22.
- RAM was re-measured during the ANR: **3.97 GB free — healthy**, ruling out memory exhaustion as the cause, consistent with every prior finding in this project once RAM itself was no longer the limiting factor.
- Following the bounded wait-and-recheck protocol established in prior phases, the ANR was rechecked at +8s, +15s, and +20s: **it did not clear at any point.**
- Per this project's standing instruction ("if the emulator becomes unstable, STOP immediately... do not fabricate screenshots"), the attempt was stopped. The emulator was shut down cleanly (`adb emu kill`, confirmed terminated), and RAM recovered to 6.86 GB, confirming the emulator itself — not the host — was the resource sink.
- **The Flutter application was never installed, launched, or interacted with.** No screenshot was captured. This is consistent with this project's own established finding (first documented in Phase 18, reconfirmed in Phase 22, and reconfirmed again here) that this host's emulator instability is genuinely intermittent and not resolved by any configuration tried so far — it is *not* attributable to RAM, which was measured healthy in every one of these episodes including this one.

**No claim of visual PASS is made for any screen in this phase.** Every visual change described in sections 2–3 above is verified only by source-code review and the automated widget-test suite (section 6), exactly as this project's standing documentation discipline requires when live validation is blocked.

## 8. Gap table — final disposition of every named design element

| Design element | Disposition |
|---|---|
| Splash / Login / Register | Restyled-only |
| Dashboard header/welcome/Search | Restyled + Real |
| Dashboard "3-stat summary" | Scoped to 2 real stats (Apps analysed, Safe applications) — "Vulnerabilities Found" dropped; `HistoryItem` has no per-app vulnerability count field, so showing one would require either an expensive N+1 fetch per history row or a fabricated number |
| Dashboard Recent Assessments / FAB | Real, restyled, FAB kept alongside the new Chat tab |
| Installed Applications (bottom-nav tab) | **Omitted** — no on-device enumeration capability exists anywhere in this app |
| Installed Applications (Dashboard button) | Honest-unavailable-state via `NotAvailableScreen`, no fabricated app list |
| Upload APK | Honest-unavailable-state — no upload endpoint is wired in this Flutter app |
| Application Details | Restyled + real "View details" navigation added |
| Vulnerability Details (CWE-89/CWE-295) | Real — one reusable `VulnerabilityDetailScreen`, not two hardcoded screens; evidence real; SHAP section restyled-only (reuses the real existing disclaimer); reference panel is static, clearly-labeled generic copy |
| "Apply Quick Fix" | **Omitted entirely** — no such capability exists anywhere in this app; a stub button would be actively misleading |
| Security Chatbot | Restyled-only |
| Chat History "Today/Yesterday" | Restyled, merged into the one real chat screen via real per-message timestamps — the backend has no separate "conversations" concept to group by |
| Security Scan animated step-checklist | **Not built as an animation** — restyled the existing loading state only; no streaming/progress API exists, so an animated multi-step tracker would fabricate the appearance of a live process |
| SAFE/WARNING/CRITICAL states | Real, restyled — built from the real `riskLevel`/`confidence` already in Application Details |
| Settings | Real, new — Notifications/Appearance explicitly non-interactive, no fake toggle |
| Bottom navigation | Real, new — 4 tabs (Home/Search/History/Chat), reduced from the design's original 5 |
| Profile screen/tab | **Omitted** — no distinct capability beyond Settings' Account section |

## 9. Genuine bugs found

None. No production code defect was discovered during this phase; every change was a planned restyle or a planned new honestly-scoped screen. No XGBoost, Decision Engine, chatbot intent logic, or backend API contract was touched.

## 10. Limitations

- No visible-GUI live validation exists for any screen in this phase (section 7) — every visual claim rests on source review + the automated widget-test suite, not on-device observation.
- The Dashboard's 3-stat summary is intentionally scoped down (section 8) rather than matching the design's exact 3 tiles.
- Four Flutter live-validation gaps predating this phase (Search-B/D, Compatibility-B/C from Phase 22) remain unresolved and unrelated to this phase's changes.
- This host's emulator instability remains unresolved and appears genuinely session-dependent, not fixed by any configuration tried across this project's history to date.
