# Phase 20 — Intel UHD 620 Graphics Driver Remediation (diagnostics only; stopped for confirmation)

**No driver was installed. No emulator was launched. No project file was
modified.** This phase reached the mandatory confirmation checkpoint
(Section 4 of the phase instruction) and stopped there.

## A. Current driver information (Section 2 — verified locally)

| Item | Value |
|---|---|
| GPU | Intel(R) UHD Graphics 620 |
| Driver version | 30.0.101.1338 |
| Driver date | 2022-01-20 |
| Driver provider | Intel Corporation |
| INF name | `oem33.inf` |
| Signed | Yes |
| Device status (`Get-PnpDevice`) | OK — `CM_PROB_NONE`, "This device is working properly." |
| `ConfigManagerErrorCode` | 0 (no error) |
| Windows version | Windows 11 Pro, build 26200 (64-bit) |
| Host model | Lenovo 20QES08X00 — identified via search as a **ThinkPad X1 Carbon 7th Gen (Type 20QD/20QE)** |

Windows itself reports no device error for this GPU — the driver loads and
functions; the issue identified in Phases 18–19 is that it is old and the
emulator itself flags it as unable to properly support Vulkan, not that
Windows considers it broken.

## B. Proposed driver information (Section 3 — partially verified)

Two official sources were checked, per the instruction's stated preference
order:

1. **Intel's official generic driver page** — "Intel® 7th-10th Gen
   Processor Graphics - Windows*"
   (`intel.com/content/www/us/en/download/776137/...`). `WebFetch` on this
   URL returned **HTTP 403 Forbidden** (bot protection) — the page content
   could not be directly read. A `WebSearch` on the same topic returned a
   search-snippet claim of version **31.0.101.2135, dated 2025-03-28**,
   stated to support the 8th-gen family (Kaby Lake-R/Coffee Lake/Whiskey
   Lake, which includes this host's i7-8665U and UHD 620) through current
   Windows 11 builds. **This version/date is from a search snippet, not
   from directly reading Intel's page — it is not independently confirmed
   by this session.**
2. **Lenovo's official ThinkPad X1 Carbon 7th Gen (Type 20QD/20QE) support
   page**, specifically identified via the host's model number:
   `pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-carbon-7th-gen-type-20qd-20qe/downloads/ds540184`
   ("Intel HD Graphics Driver for Windows 11 (21H2+)/10 (1709+) — ThinkPad
   X1 Yoga 4th Gen, X1 Carbon 7th Gen"). `WebFetch` on this URL also
   returned **HTTP 403 Forbidden**. No version/date could be read from this
   page at all this session.

**Neither source could be directly verified by this session.** No exact
file, checksum, or direct download link was obtained from either official
page — only a landing-page URL for each, and one unverified version number
from a third-party search snippet. Attempting to install a driver based on
an unverified snippet, or by guessing a download URL, would not meet the
"verified compatible driver" bar this phase requires, and downloading from
any source other than the two official ones is explicitly out of scope.

## C–L. Everything past this point: not attempted

Per Section 4 of the phase instruction ("Do NOT install the GPU driver
without explicit user confirmation... STOP and provide: CURRENT DRIVER /
PROPOSED DRIVER / SOURCE / WHY / RESTART REQUIRED. Then wait for
confirmation"), this phase stops here. Sections 6–9 of the instruction
(install, post-install verification, emulator retest, app launch and live
validation) were **not attempted** — there is nothing to install yet
without your confirmation and, ideally, your own direct access to one of
the two official pages above (since this session could not read either).

- **Installation status:** NOT ATTEMPTED
- **Post-install verification:** NOT APPLICABLE (nothing installed)
- **Emulator retest:** NOT ATTEMPTED
- **Flutter app reached:** NOT APPLICABLE
- **Live validation results:** unchanged — all items remain exactly as
  recorded in `chatbot_final_validation.csv` after Phase 19; nothing
  upgraded from NOT VALIDATED
- **Screenshots:** none captured
- **Bugs found:** none — no application code was reached this phase

## Confirmation request (per Section 4)

```
CURRENT DRIVER:
Intel(R) UHD Graphics 620, version 30.0.101.1338, dated 2022-01-20,
Intel Corporation, currently functioning with no Windows-reported device
error.

PROPOSED DRIVER:
Unconfirmed by this session. Search evidence points to Intel's generic
"7th-10th Gen Processor Graphics" package, reported version 31.0.101.2135
(2025-03-28) — but this was not independently verified by reading Intel's
own page (blocked, HTTP 403). Lenovo's model-specific ThinkPad X1 Carbon
7th Gen (20QD/20QE) driver page was also identified but equally blocked
(HTTP 403), so its offered version is completely unknown to this session.

SOURCE:
Intel: https://www.intel.com/content/www/us/en/download/776137/intel-7th-10th-gen-processor-graphics-windows.html
Lenovo (model-specific): https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-carbon-7th-gen-type-20qd-20qe/downloads/ds540184
Both are official first-party pages; neither was readable by this
session's tools.

WHY:
Phases 18-19 verified the currently installed driver (2022-01-20) is
flagged by the Android Emulator itself as unable to properly support
Vulkan, and correlated with a graphics-pipeline failure
(opengl32sw load failure, UpdateLayeredWindowIndirect Windows API error)
that produced a persistent System UI/launcher ANR independent of CPU
virtualization (which is confirmed working) and independent of RAM
(confirmed stable throughout the failures).

RESTART REQUIRED:
Almost certainly yes for a GPU driver update on Windows, though this
cannot be confirmed without reading the actual installer's documentation
on one of the two blocked pages.
```

**This session cannot proceed past this point on its own** — it cannot
confirm the exact driver package, and even if it could, this phase
requires your explicit go-ahead before installing anything. The most
direct way to move forward: you (or I, if you can grant access to fetch
one of these pages, or if you paste the exact driver version/download link
Lenovo or Intel actually offers for this machine) confirm which package to
use, and then I proceed with Sections 6–9.
