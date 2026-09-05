# Research Phase Step 10.5 — CWE-295 SAFE Targeted Expansion Report

**Verdict: `B) STOP — fewer than 20 additional defensible samples found`** (10 confirmed, without lowering the evidence standard)

No model was trained. `dataset .csv`, `final_dataset.csv` (v1), and `final_dataset_v2.csv` were **not** modified. A new, separate `final_dataset_v3.csv` was created (524 rows).

---

## Required Summary Numbers

| Metric | Value |
|---|---|
| Previous CWE-295 safe count (start of this step) | 43 |
| New candidates collected this round | 10 |
| Rejected | **0** |
| Confirmed new safe samples | 10 |
| **Final CWE-295 safe count** | **53** |
| Repositories (new, this round) | 6 |
| Repositories (combined CWE-295-safe collection to date) | 14 |
| Java / Kotlin / XML distribution (new confirmed rows) | 7 Java / 3 Kotlin / 0 XML |
| STRONG / MODERATE / WEAK (new confirmed rows) | 10 STRONG / 0 MODERATE / 0 WEAK |
| Duplicates rejected | 0 (exact or normalized, vs. `final_dataset_v2.csv` or internally) |
| Pairs | 1 (`pair_cert4android_check_and_store`) |

## Repositories Used This Round (Conscrypt Deliberately Avoided)

| Repository | New rows | Notes |
|---|---|---|
| `bitfireAT/cert4android` | 3 | Real, independent library behind DAVx5's certificate handling |
| `signalapp/libsignal-service-java` | 2 | Real historical Signal networking code (archived repo, still real) |
| `OWASP/MASTG-Hacking-Playground` | 2 | Official OWASP mobile-security benchmark project's own reference-safe implementation |
| `ge0rg/MemorizingTrustManager` | 1 | Real, widely-used independent library (Conversations/XMPP, DAVx5) |
| `andreabenetton/pcontacts` | 1 | Real application-level (not library-internal) `CertificatePinner` usage |
| `grpc/grpc-java` | 1 | Real Google gRPC library, independent codebase from Conscrypt |

**Zero rows from Conscrypt this round**, as explicitly instructed. Combined across Step 10 + Step 10.5, Conscrypt's share of the total 42-row new-collection pool falls from 13/32 (41%, Step 10 alone) to 13/42 (31%, combined) — moving in the right direction, though still the single largest contributor overall.

## Duplicate / Near-Duplicate / Pair Analysis

Ran programmatically (`research_dataset/scripts/phase10_5b_qc_dedup.py`) against **`final_dataset_v2.csv`** (514 rows, the current base) on both exact code text and `normalize_code()`-normalized template, plus an internal check among the 10 new candidates themselves. **Zero matches on any axis.** One pair was identified and recorded: `pair_cert4android_check_and_store` links `CustomCertManager.kt`'s `checkServerTrusted` (which delegates the actual trust decision) to `CustomCertStore.kt`'s `isTrusted` implementation (which performs it) — two halves of one real control that happen to live in two files of the same library.

## Why Only 10, Not ≥20 (Explained, Not Excused)

This round investigated roughly 20 candidate repositories/sources. Six yielded usable, non-duplicate, sufficiently-evidenced, **new** (non-Conscrypt) results; the rest were investigated and abandoned for concrete, specific reasons — not because the evidence bar was relaxed to reject them, but because no usable, real, non-duplicate CWE-295-safe evidence could be found there within the time available:

- **`ACRA/acra`** — a repository-tree fetch failed/timed out (as it did in Step 10); the specific fix commit for its own reported unsafe-TrustManager issue was not tracked down by other means.
- **`braintree/braintree_android`** — the PR referenced by its cross-reference timeline (#208) resolved to HTTP 404.
- **`guardianproject/NetCipher`** — its `StrongSSLSocketFactory` classes take a caller-supplied `TrustManager[]` and wire it into an `SSLContext`; they contain no independent validation logic of their own to serve as positive evidence.
- **`signalapp/Signal-Android`** — the main app repository is ~2.5 GB, too large for a full tree search in this environment; the smaller, tractable `libsignal-service-java` companion repository was used instead and did yield real results.
- **`ProtonMail/protoncore_android`** — a repository-tree fetch was attempted but the response was truncated (very large monorepo); the same real Proton certificate-pinning pattern was instead found via the smaller `andreabenetton/pcontacts` repository, which explicitly reimplements Proton's API client.
- **`tutao/tutanota`**, **`F-Droid/fdroidclient`**, **`satishpatnayak/AndroGoat`**, **`optiv/InsecureShop`**, **`rewanthtammana/Damn-Vulnerable-Bank`** — repository trees were successfully searched; none contained a file matching TLS/certificate/trust-manager/hostname-verifier naming patterns at all (these apps' security focus, or lack of custom TLS handling, lies elsewhere).
- **`square/retrofit` issue #4226`** — a stale automated-scanner (Checkmarx) false positive about a transitively-bundled old OkHttp version; the current, already-fixed OkHttp code was already collected in Step 10.
- **`element-hq/element-android`, `wireapp/wire-android`, F-Droid/fdroidclient tree, and several other apps** — searched via web search for specific file names/classes; no verifiable, specific real file path was surfaced with sufficient confidence to justify a repository-tree fetch (which, per the above, is itself a scarce, rate-limited, and often slow operation in this environment).

Reaching 20+ (let alone the 100–150 target) would require either substantially more collection cycles at this same pace, or bulk tooling not available here (see Step 10's report for the same underlying constraint: no authenticated GitHub code search, no practical full-repository cloning for large real apps).

## Remaining Limitations

1. **53 total CWE-295 safe samples remains well short of the 100–150 preferred target**, and still likely too small for a fully confident held-out test split for 5 model families, though meaningfully better than the 11 this project started with two steps ago.
2. **Conscrypt remains the single largest repository contributor** across the full CWE-295-safe collection (13/42 new rows, 31%) — this round deliberately added zero more from it, but did not retroactively reduce its share of Step 10's rows.
3. **Provenance tier mismatch persists**: the 465 pre-existing `final_dataset.csv` (v1) rows still carry no provenance at all, while all new rows across Steps 10 and 10.5 carry full, individually-verified provenance. This remains true of `final_dataset_v3.csv`.
4. **Library/platform code still outweighs pure application code** among the new rows, though this round's `andreabenetton/pcontacts` and `bitfireAT/cert4android`-via-DAVx5 rows partially offset that (real application-level usage), continuing the trend started in Step 10 with `silkimen/cordova-plugin-advanced-http`, `mendhak/gpslogger`, and `GrapheneOS/Auditor`.
5. **CWE-89 is untouched by this step**, as instructed — its evidence-strength profile (138/140 MODERATE) is unchanged.
6. **No split has been frozen for `final_dataset_v3.csv`.**

## Is a Common CWE-89 + CWE-295 Experiment Now Defensible?

**Not yet, but closer.** 53 confirmed CWE-295 safe samples is roughly 5x the starting count from before Step 10 (11), and nearly 5x better than the absolute floor that made a split indefensible. A rough illustrative 70/15/15 split would now leave roughly 8 CWE-295 safe samples in a held-out test set — still thin (a single misclassification swings that class's test recall by ~12.5 percentage points), but a materially less fragile basis than the ~6-sample test slice implied by the 43-sample count reported after Step 10. **This is still not recommended as a basis for a defensible 5-model comparison** without either (a) further collection to comfortably clear 100+, or (b) an explicit, separately-approved decision to accept wider confidence intervals for the CWE-295 half of the experiment. The CWE-89-only subset remains the nearest-to-ready part of the overall research objective, unaffected by this step.
