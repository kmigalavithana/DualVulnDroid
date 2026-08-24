# Phase 14B Chatbot Final Validation — attempt record

## 1. Purpose

Continuing from the completed Phase 14B validation (login, registration,
session restore, logout, main mobile flows, real backend/MySQL integration,
the chatbot suggestion-chip bug found and fixed, 316 backend tests passed/2
skipped at that time, 39 Flutter tests passed at that time, 61 real
screenshots), this phase's goal was to close the specific chatbot/mobile
gaps Phase 14B itself documented as incomplete, without repeating already-
PASS work.

## 2. Gap analysis (from inspecting the existing Phase 14B report first)

`phase14b_android_validation.md` Section I states explicitly: of the chatbot
mechanism, only two live exchanges were directly observed on-device —
**"Why is this app high risk?"** (the suggestion chip whose wording exposed
the real intent-matching bug, found and fixed live) and a CWE-295 explanation
question. Section I's own words: *"Remaining required questions from the
Section 14 list... were not all individually re-tested live in this
session... PARTIAL for the untested subset of the required question list;
PASS for the mechanism itself."*

This gives a precise, pre-existing gap list, reproduced here as the actual
target for this phase (no test case was invented beyond what Phase 14B
itself already scoped):

- 6 of the 8 required chatbot questions never individually observed live
- 2 of the 4 actual Flutter suggestion chips ("Why can't I install this on
  my phone?", "Is there a safer alternative?") never observed live
- Consecutive multi-turn user/bot exchanges: not live-observed
- Chat-history persistence across a screen/app restart: not live-observed
  (the read path itself did not exist until Phase 14C added it)
- Unknown/unsupported question fallback behaviour: not live-observed
- Empty/invalid input handling: not live-observed
- Backend/network failure handling: not live-observed
- Long response text/scrolling behaviour: not live-observed
- Keyboard/input/send-button behaviour: not live-observed
- UI overflow/clipping/crash check: not live-observed

## 3. This attempt

**Pre-launch resource check:** physical RAM free measured 3.29 GB (of 15.75
GB total), C: free 2.48 GB, no emulator/Java/Gradle process running. This
was below the ~4 GB level suggested in the prior phase but better than the
2.38 GB and 2.52 GB readings that caused this session's two most recent
pre-emptive stops, and no project-related process was running to account for
the shortage. Given the task's intent to close these gaps and the absence of
any competing process, a real, monitored attempt was made rather than
stopping at the pre-launch reading alone — consistent with Phase 14C's
"attempt and monitor, stop cleanly if instability appears" approach rather
than Phase 14D/15/16's stricter pre-emptive gate.

**Emulator launch:** `Pixel_4` AVD, cold-booted (`-no-snapshot-load`, avoiding
the known snapshot-resume/adb-offline issue from Phase 14B). Boot completed
in 36 seconds; `adb devices` confirmed `emulator-5554  device`.

**Immediately post-boot resource check:** physical RAM free measured **0.64
GB** — `qemu-system-x86_64` alone was consuming 2.78 GB, a substantially
larger footprint than any previous successful or failed attempt this session
captured at the equivalent point. This is far below every previously
documented instability threshold (Phase 14C's persistent ANR occurred at
2.79–2.87 GB free; Phase 14D's failure occurred at 1.76–1.90 GB free). 0.64
GB free is a severe resource-exhaustion state in which even routine OS/UI
operations, let alone launching and interacting with a Flutter app inside
the guest, would be unreliable and could risk broader host instability.

**Decision:** the emulator was shut down immediately (`adb emu kill`),
confirmed fully terminated (`adb devices` empty), before any app was
installed, launched, or interacted with. No screenshot was taken. RAM
recovered to 3.78 GB free after shutdown, confirming the emulator itself —
not any other process — was the cause.

## 4. Result

**No new live validation was performed this phase.** Every gap identified in
Section 2 remains exactly as Phase 14B left it: PASS for the chatbot
mechanism and the two directly-observed exchanges (why-risky, CWE-295); NOT
VALIDATED for every other individual question, chip, and behaviour listed.
No result below is fabricated or upgraded from NOT VALIDATED to PASS.

See `chatbot_final_validation.csv` for the per-item table.

## 5. Bugs found

None — no live interaction occurred this attempt, so no live-only defect
could be observed. The previously-fixed why-risky suggestion-chip bug
(Phase 14B) was not re-broken or re-touched; no code was changed this phase.

## 6. Remaining limitation

This host's current physical RAM headroom is insufficient to run the
`Pixel_4` (API 36) emulator configuration reliably: even a 3.29 GB pre-launch
reading — itself below the ~4 GB level suggested as a safe minimum —
collapsed to 0.64 GB free immediately after boot, before any interaction was
attempted. Closing the remaining chatbot/mobile validation gaps requires
either substantially more free physical RAM at launch time (freeing the
non-project applications identified in Phase 16, and/or closing other
memory-heavy programs first) or a lighter-weight AVD configuration; the
current 3–4 GB range that has been available at launch time across recent
attempts has not been sufficient in practice.
