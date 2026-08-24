# Phase 15 — Mobile UI Polish + Resume Remaining Live Validation

## 1. Scope of this phase

Two goals, per the phase instruction: (1) polish the existing Flutter application's
visual design to a professional, thesis/demo-ready standard while preserving all
existing functionality, and (2) resume the remaining live Android emulator
validation from exactly where Phase 14D stopped. Part 1 (inspection) and Part 2
(UI polish) were completed. Part 3 (automated verification) passed cleanly.
Part 4 (emulator resource check) found RAM below the safe threshold, so Parts 5–6
(live validation) were **not attempted this phase**, per the explicit "if RAM is
insufficient, report it and stop" instruction and the standing "do not force an
unstable emulator" rule established across Phases 14A–14D.

## 2. Part 1 — Inspection (before any change)

The following were read in full before any edit was made: `main.dart`,
`routing/app_router.dart`, `theme/app_colors.dart`, `theme/app_theme.dart`,
`widgets/risk_badge.dart`, `widgets/compatibility_badge.dart`,
`widgets/decision_card.dart`, `widgets/vulnerability_tile.dart`,
`widgets/state_views.dart`, `screens/login_screen.dart`,
`screens/dashboard_screen.dart`, `screens/security_chat_screen.dart`,
`screens/search_application_screen.dart`, `screens/application_details_screen.dart`,
`screens/device_compatibility_screen.dart`, `screens/splash_screen.dart`, and the
existing widget/screen tests that exercise these files
(`test/widgets/decision_card_test.dart`, `test/screens/search_application_screen_test.dart`,
`test/screens/application_details_screen_test.dart`).

Finding: the application was already a reasonably well-built dark cybersecurity
UI (a defined dark palette with semantic risk colours, icon+text risk/compatibility
badges — never colour alone, consistent card-based layout, dedicated
loading/empty/error state widgets, `Semantics` labels). It was not a "basic
prototype" needing a rebuild; the real, addressable gaps were: no visual
separation between the app bar and scrolled body content (both the same colour
at elevation 0), no defined chip/divider/snackbar theming (each screen that used
a `Chip`/`ActionChip`/`FilterChip` fell back to Material defaults), a bare splash
screen, an unstyled login/registration form floating directly on the background,
and a chatbot message list with no sender distinction beyond bubble colour, no
timestamps, and a plain suggestion-chip/history-loading presentation. UI polish
was scoped to these real gaps rather than a wholesale redesign.

## 3. Part 2 — UI polish: files modified

| File | Change |
|---|---|
| `lib/theme/app_colors.dart` | Added `AppColors.border` (hairline separator/card border colour) and `AppColors.accentSoft` (a muted accent tint used for icon-mark containers and selected-chip backgrounds). No existing colour constant was changed or removed. |
| `lib/theme/app_theme.dart` | App bar background changed from `background` to `surface` (gives every screen a visible boundary between the app bar and scrolled content); added a 1px `AppColors.border` side to the existing card shape (cards were elevation-0 with no depth cue); added a focused-state border to `InputDecorationTheme`; added `OutlinedButtonThemeData`, `chipTheme`, `dividerTheme`, `progressIndicatorTheme`, and `snackBarTheme` (previously undefined, so every chip/divider/snackbar in the app fell back to inconsistent Material defaults); no colour, spacing, or behavioural default was removed. |
| `lib/screens/splash_screen.dart` | Added a subtle radial-gradient background (using the existing `surface`/`background` tokens), a circular accent-tinted icon mark around the existing security icon, and a one-line tagline. The existing session-restore-then-navigate logic (`_resolve()`) is unchanged. |
| `lib/screens/login_screen.dart` | Wrapped the form fields in a `Card` with a circular icon mark above it (previously the icon, title, and bare fields floated directly on the scaffold background); changed the loading state to show a spinner inside the disabled submit button rather than swapping the whole button out for a separate centred spinner. All validators, controllers, `AuthRepository` calls, and error-message handling are unchanged. |
| `lib/screens/security_chat_screen.dart` | Added a `state_views.dart` import and replaced the bare `CircularProgressIndicator` history-loading state with the shared `LoadingView`; the "Chatting about" banner moved into the app bar's `bottom` slot with an icon and overflow handling; message bubbles now show a small user/bot avatar, use `SelectableText` (so long CWE/SHAP explanations remain copyable and always wrap within the existing 70%-width constraint rather than overflowing), and display a formatted send time; suggestion chips gained a leading icon and a one-line sub-caption; the input field now grows up to 4 lines for longer questions. `_send()`, `_loadHistory()`, `ChatRepository`/`ChatApiService` calls, and the backend intent logic are all unchanged. |

No backend file, no `chatbot_logic.py` intent logic, no API contract, and no other
Dart file were modified. No new package dependency was added (the message
timestamp is formatted manually from the existing non-nullable `ChatMessage.sentAt`
field — no `intl` dependency was introduced).

## 4. Part 3 — Automated verification

```
flutter analyze
```
Result: **0 errors.** 6 pre-existing informational lints remain (in
`auth_repository.dart`, `application_details_screen.dart`, `chat_api_service.dart`,
and one test file) — none in a file touched this phase, none new.

```
flutter test
```
Result: **41 passed / 0 failed** — the exact baseline required by this phase's
success criteria. No test needed modification; the UI changes did not alter any
text string, widget type, or structural element any existing test asserts on.

## 5. Part 4 — Real Android emulator resource check

Per the phase instruction ("Before launching: 1. Check available RAM. 2. Check
disk. 3. Check existing Java/Gradle/emulator processes... If RAM is insufficient,
report it and stop. Do not force an unstable emulator."):

| Check | Result |
|---|---|
| Free RAM | **3.05 GB** of 15.75 GB total |
| Free disk (C:) | 4.51 GB |
| Running emulator/qemu/java/gradle/Android Studio processes | None found |
| Running `adb` process | One (`adb.exe`, ~14 MB — the idle daemon, not a running emulator) |

**Decision: did not launch the emulator.** 3.05 GB free RAM falls inside the same
band already documented as unstable on this host: Phase 14C's persistent,
non-recovering "System UI isn't responding" condition occurred with free RAM
measured flat at 2.79–2.87 GB throughout the attempt, and Phase 14D — which
started from a materially healthier 4.35 GB pre-launch reading — still saw free
RAM collapse to 1.76–1.90 GB immediately after boot, below that same failure
band, before any UI interaction was possible. A 3.05 GB starting point is worse
than Phase 14D's starting point and only slightly above Phase 14C's failure
band; launching from here would be expected, based on this host's own
documented pattern across two prior attempts, to reproduce the same instability
rather than to succeed. No unrelated user application was identified as the
cause (no emulator, Java, Gradle, or Android Studio process was already
running), so there was nothing safe to close on this host's own account. Per the
explicit instruction, this is reported and the attempt stops here rather than
being forced.

## 6. Parts 5–6 — Live validation (not attempted this phase)

Because Part 4 did not clear, the polished-UI regression check (Part 5) and the
resumed remaining-item validation (Part 6) — the six chatbot questions, chat
history live UI, the two remaining search sub-cases, and the two compatibility
sub-cases — were **not attempted this phase**. No screenshot, pass/fail result,
or on-device observation is claimed for any of these items beyond what Phase 14B
already established as PASS. This is a resource-availability limitation on this
development host at the time of this phase, not a defect in the UI changes made
in Part 2 (which were independently verified through `flutter analyze` and the
full automated test suite) or in any previously-validated functionality.

## 7. Bug policy

No genuine application bug was discovered during this phase — the UI changes
were additive/cosmetic (theming, layout wrapping, avatar/timestamp presentation)
and did not touch any request, response-parsing, or state-management logic, so
no regression test was needed and none of the existing 41 tests required
modification.

## 8. Screenshots

No screenshots were captured this phase, since no live emulator session was run.
Capturing polished-UI screenshots without an actual on-device session would not
constitute real validation evidence and was not done.

## 9. Remaining limitations (unchanged from Phase 14D)

All seven previously-remaining items are unchanged:

1. Search — unknown-app/network-error: NOT VALIDATED
2. Search — remaining sub-case B: NOT VALIDATED
3. Search — remaining sub-case D: NOT VALIDATED
4. Compatibility — INCOMPATIBLE: NOT VALIDATED
5. Compatibility — NOT_AVAILABLE: NOT VALIDATED
6. Six remaining chatbot questions: NOT VALIDATED
7. Chat-history UI persistence: NOT VALIDATED (implementation and automated
   tests remain PASS, unchanged from Phase 14C)

APK upload remains NOT APPLICABLE / NOT IMPLEMENTED — the current Flutter
client has no upload entry point, unchanged from prior phases and not
re-verified live this phase (no code change was made to this area).
