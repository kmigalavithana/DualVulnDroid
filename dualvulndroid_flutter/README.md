# SmartApp

Context-aware Android application discovery and recommendation.

Instead of surfacing only popular apps, SmartApp ranks candidate apps by how
well they actually fit **this user** and **this device** - combining the
user's selected preferences, the device's real hardware/OS profile, each
app's privacy characteristics, its resource efficiency, and its rating.

SmartApp is a **standalone** mobile app: no login, no backend, no APK
upload/scan. Every recommendation is computed on-device by an explainable,
weighted scoring engine (`lib/services/recommendation_engine.dart`), and
every score comes with a transparent "Why this app?" breakdown rather than a
single opaque percentage.

## Scoring model

| Signal | Weight |
|---|---|
| Preference match | 30% |
| Device suitability | 25% |
| Privacy | 20% |
| Resource efficiency | 15% |
| Rating | 10% |

The five weighted contributions always sum to the final 0-100 match score -
nothing is hardcoded. See `RecommendationEngine` for the full, unit-tested
implementation, and `test/services/recommendation_engine_test.dart` for its
test coverage.

## Data

The bundled app catalog (`lib/data/sample_apps_data.dart`) is a clearly
marked curated/demo dataset (`AppInfo.isCuratedSample`), not verified
real-world Play Store metadata. It exists to demonstrate the recommendation
engine end-to-end; a future real data source would only need to populate the
same `AppInfo` model.

## Architecture

```
lib/
  models/        Pure data types (AppInfo, DeviceProfileModel, ...)
  data/           The curated demo app catalog
  services/       RecommendationEngine (pure, testable) + platform wrappers
  repositories/   App-lifetime state (preferences, history, device profile)
  screens/        UI
  widgets/        Reusable UI pieces
  routing/        Centralized navigation
  theme/          App-wide colors/theme
```

Recommendation logic lives entirely in `RecommendationEngine`, never in a
screen - screens only ever call it and render the result.

## Getting started

```
flutter pub get
flutter analyze
flutter test
flutter build apk
```
