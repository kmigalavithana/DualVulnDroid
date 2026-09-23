# SmartApp live-app metadata enrichment: before/after audit

Run on 2026-09-24 with `dart run tool/score_audit.dart <backend> "notes,pdf reader,music player"`.

- **Apps:** 60 unique live Google Play apps from the SmartApp backend (real SerpApi results).
- **Scoring:** the app's own `RecommendationEngine`.
- **Device profile:** the test emulator's real values (1.9 GB RAM, Android 16).
- **Preference scenarios:** all 7 preferences selected; no preferences selected; lightweight + privacy-friendly.

Metadata coverage is the share of the 7 recommendation attributes that are verified for an app:
rating, trackers, size/resource, price, ads, open source, offline. It describes how complete the data is.
It is not an accuracy or confidence figure.

## BEFORE: neutral fallbacks, Google Play search data only

| Scenario | n | min | max | mean | median | sd | unique |
|---|---|---|---|---|---|---|---|
| all 7 preferences | 60 | 40 | 42 | 41.6 | 42.0 | 0.61 | 3 |
| no preferences | 60 | 58 | 60 | 59.6 | 60.0 | 0.61 | 3 |
| lightweight + privacy | 60 | 40 | 42 | 41.6 | 42.0 | 0.61 | 3 |

Coverage was 14% for every app, because the rating was the only verified attribute.

**Why scores clustered:**
- Unverifiable preferences counted as *failed*: with 7 selected, the preference factor was 0 for every live app.
- Device, privacy and resource used fixed neutral values (60/50/50).
- Only the rating varied, and it moved the score by at most about 1 point.

## AFTER, default configuration (F-Droid on, Exodus not configured, no paid Play lookups in search)

| Scenario | n | min | max | mean | median | sd | unique |
|---|---|---|---|---|---|---|---|
| all 7 preferences | 60 | 70 | 98 | 89.8 | 92.0 | 6.16 | 15 |
| no preferences | 60 | 70 | 98 | 89.5 | 92.0 | 6.17 | 13 |
| lightweight + privacy | 60 | 70 | 98 | 89.5 | 92.0 | 6.17 | 13 |

Coverage: mean 14.5% (2 apps rose to 29%).

| Coverage | Share of apps |
|---|---|
| Google Play (rating) | 100% |
| Privacy | 0% |
| Resource | 0% |
| Price | 0% |
| Ads | 0% |
| Open source | 3% (F-Droid matches) |
| Offline | 0% |

**Reading this honestly: this spread is not caused by new evidence.**
- Almost no new data was verified.
- Availability-aware scoring removed the neutral stand-ins, so for most apps the rating is the only factor left.
- The match % therefore largely equals the rating: 4.6★ gives 92%.
- The UI says so on every card ("based on 1 of 5 verified factors").

## AFTER, with Play store facts for the top 8 results per search (`SMARTAPP_SEARCH_DETAILS_LIMIT=8`)

| Scenario | n | min | max | mean | median | sd | unique |
|---|---|---|---|---|---|---|---|
| all 7 preferences | 60 | 56 | 99 | 84.7 | 91.0 | 13.72 | 19 |
| no preferences | 60 | 70 | 98 | 89.5 | 92.0 | 6.17 | 13 |
| lightweight + privacy | 60 | 70 | 98 | 89.5 | 92.0 | 6.17 | 13 |

Coverage: mean 22.6%, max 43%.

| Coverage | Share of apps |
|---|---|
| Price | 35% |
| Ads ("Contains ads" label) | 20% |
| Open source | 3% |
| Privacy, resource, offline | 0% |

**What this configuration adds:**
- With preferences that store facts can verify (free, no ads), part of the spread is now evidence-driven.
- Apps that verifiably show ads drop below apps that don't.
- The lightweight and privacy preferences still can't be verified for live apps, so those scenarios don't change.

## Conclusion

1. The clustering came from treating unknown data as failure or as neutral. That is fixed, and unknown data now never moves a score.
2. The only real new evidence in practice:
   - price and ad labels from the Play product page (opt-in, 1 SerpApi credit per app, cached 24h);
   - F-Droid license and anti-features for the few Play apps that are also on F-Droid.
3. Privacy (trackers) stays unverified until an Exodus instance is configured (`EXODUS_BASE_URL`, `EXODUS_API_TOKEN`).
   Size and offline support have no trustworthy source in the current providers.
4. Because the rating is often the only verified factor, many live scores are rating-driven. Treat them as such.
