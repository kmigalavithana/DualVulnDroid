import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';
import 'package:dualvulndroid_flutter/repositories/app_repository.dart';

AppRepository _repoWith(http.Client client) => AppRepository(client: client, baseUrl: 'http://test.invalid');

void main() {
  group('1. Search response parsing', () {
    test('parses the real normalized shape into AppInfo with isLiveData/dataSource set', () async {
      final client = MockClient((request) async {
        expect(request.url.path, '/smartapp/apps/search');
        return http.Response(
          jsonEncode({
            'apps': [
              {
                'id': 'com.example.noteflow',
                'name': 'NoteFlow',
                'packageName': 'com.example.noteflow',
                'category': 'Notes',
                'description': 'A note app.',
                'iconUrl': 'https://example.com/icon.png',
                'rating': 4.6,
                'reviewCount': 18400,
                'playStoreUrl': 'https://play.google.com/store/apps/details?id=com.example.noteflow',
                'developer': 'Example Dev',
                'realData': true,
                'source': 'google_play',
              },
            ],
            'source': 'google_play',
            'isLiveData': true,
          }),
          200,
        );
      });
      final results = await _repoWith(client).searchApps(query: 'note');

      expect(results, hasLength(1));
      final app = results.single;
      expect(app.name, 'NoteFlow');
      expect(app.packageName, 'com.example.noteflow');
      expect(app.rating, 4.6);
      expect(app.reviewCount, 18400);
      expect(app.developer, 'Example Dev');
      expect(app.isLiveData, isTrue);
      expect(app.dataSource, 'google_play');
      expect(app.isCuratedSample, isFalse);
    });

    test('passes q/category/country/language/limit through as real query parameters', () async {
      late Uri capturedUri;
      final client = MockClient((request) async {
        capturedUri = request.url;
        return http.Response(jsonEncode({'apps': []}), 200);
      });
      await _repoWith(client).searchApps(query: 'note', category: 'Notes', limit: 5);

      expect(capturedUri.queryParameters['q'], 'note');
      expect(capturedUri.queryParameters['category'], 'Notes');
      expect(capturedUri.queryParameters['limit'], '5');
    });
  });

  group('2. App details response parsing', () {
    test('parses the details shape including version/screenshots/releaseDate', () async {
      final client = MockClient((request) async {
        expect(request.url.path, '/smartapp/apps/details/com.example.noteflow');
        return http.Response(
          jsonEncode({
            'app': {
              'id': 'com.example.noteflow',
              'name': 'NoteFlow',
              'packageName': 'com.example.noteflow',
              'category': 'Notes',
              'developer': 'Example Dev',
              'version': '2.3.1',
              'releaseDate': 'Jan 1, 2020',
              'updatedOn': 'Jan 1, 2024',
              'screenshots': ['https://example.com/s1.png', 'https://example.com/s2.png'],
              'realData': true,
              'source': 'google_play',
            },
            'source': 'google_play',
            'isLiveData': true,
          }),
          200,
        );
      });
      final app = await _repoWith(client).getAppDetails('com.example.noteflow');

      expect(app, isNotNull);
      expect(app!.version, '2.3.1');
      expect(app.releaseDate, 'Jan 1, 2020');
      expect(app.updatedOn, 'Jan 1, 2024');
      expect(app.screenshots, ['https://example.com/s1.png', 'https://example.com/s2.png']);
    });
  });

  group('3. Missing rating', () {
    test('a search result with no rating parses as null, never 0 or a guess', () async {
      final client = MockClient((request) async => http.Response(
            jsonEncode({
              'apps': [
                {'id': 'a', 'name': 'A', 'packageName': 'com.example.a'},
              ],
            }),
            200,
          ));
      final results = await _repoWith(client).searchApps(query: 'a');
      expect(results.single.rating, isNull);
    });
  });

  group('4. Missing review count', () {
    test('a search result with no reviewCount parses as null, never 0', () async {
      final client = MockClient((request) async => http.Response(
            jsonEncode({
              'apps': [
                {'id': 'a', 'name': 'A', 'packageName': 'com.example.a', 'rating': 4.0},
              ],
            }),
            200,
          ));
      final results = await _repoWith(client).searchApps(query: 'a');
      expect(results.single.reviewCount, isNull);
    });
  });

  group('5. Missing privacy information', () {
    test('AppInfo.fromSmartAppJson never populates trackerCount/hasAds/isOpenSource/supportsOffline/isFree from a Play Store response', () {
      // The backend's normalized shape has no such keys at all (Part 11) -
      // this proves the Flutter-side parser doesn't invent them either.
      final app = AppInfo.fromSmartAppJson({
        'id': 'a',
        'name': 'A',
        'packageName': 'com.example.a',
        'rating': 4.5,
      });
      expect(app.trackerCount, isNull);
      expect(app.hasAds, isNull);
      expect(app.isOpenSource, isNull);
      expect(app.supportsOffline, isNull);
      expect(app.isFree, isNull);
      expect(app.resourceLevel, isNull);
      expect(app.sizeMb, isNull);
    });

    test('an app with entirely unverified attributes satisfies none of the 7 preferences', () {
      final app = AppInfo.fromSmartAppJson({'id': 'a', 'name': 'A', 'packageName': 'com.example.a'});
      for (final preference in AppPreference.values) {
        expect(app.satisfies(preference), isFalse, reason: '${preference.name} must not be assumed satisfied when unverified');
      }
    });
  });

  group('6. API error', () {
    test('a 502 from the backend (upstream provider failure) throws AppServiceUnavailableException, never an empty fake success', () async {
      final client = MockClient((request) async => http.Response(jsonEncode({'detail': 'Google Play provider error'}), 502));
      expect(() => _repoWith(client).searchApps(query: 'note'), throwsA(isA<AppServiceUnavailableException>()));
    });

    test('a network-level failure (thrown by the client) also surfaces as AppServiceUnavailableException', () async {
      final client = MockClient((request) async => throw Exception('socket closed'));
      expect(() => _repoWith(client).searchApps(query: 'note'), throwsA(isA<AppServiceUnavailableException>()));
    });

    test('a malformed JSON body throws AppRequestException rather than crashing', () async {
      final client = MockClient((request) async => http.Response('not json', 200));
      expect(() => _repoWith(client).searchApps(query: 'note'), throwsA(isA<AppRequestException>()));
    });
  });

  group('7. Empty search', () {
    test('a real empty result list from the backend returns an empty list, never a fabricated fallback', () async {
      final client = MockClient((request) async => http.Response(jsonEncode({'apps': []}), 200));
      final results = await _repoWith(client).searchApps(query: 'zzz_no_such_app_zzz');
      expect(results, isEmpty);
    });
  });

  group('8. Play Store URL handling', () {
    test('a present playStoreUrl round-trips exactly', () async {
      final client = MockClient((request) async => http.Response(
            jsonEncode({
              'apps': [
                {
                  'id': 'a',
                  'name': 'A',
                  'packageName': 'com.example.a',
                  'playStoreUrl': 'https://play.google.com/store/apps/details?id=com.example.a',
                },
              ],
            }),
            200,
          ));
      final results = await _repoWith(client).searchApps(query: 'a');
      expect(results.single.playStoreUrl, 'https://play.google.com/store/apps/details?id=com.example.a');
    });

    test('a missing playStoreUrl parses as null - never constructed from the package name', () async {
      final client = MockClient((request) async => http.Response(
            jsonEncode({
              'apps': [
                {'id': 'a', 'name': 'A', 'packageName': 'com.example.a'},
              ],
            }),
            200,
          ));
      final results = await _repoWith(client).searchApps(query: 'a');
      expect(results.single.playStoreUrl, isNull);
    });

    test('getAppDetails returns null (not a fabricated app) on a real 404', () async {
      final client = MockClient((request) async => http.Response(jsonEncode({'detail': 'not found'}), 404));
      final app = await _repoWith(client).getAppDetails('com.does.not.exist');
      expect(app, isNull);
    });
  });

  group('9. Recommendation using real AppModel data', () {
    test('the existing RecommendationEngine scores a real, fetched AppInfo using only its known fields', () async {
      final client = MockClient((request) async => http.Response(
            jsonEncode({
              'apps': [
                {
                  'id': 'a',
                  'name': 'NoteFlow',
                  'packageName': 'com.example.noteflow',
                  'category': 'Notes',
                  'rating': 4.8,
                  'reviewCount': 9100,
                },
              ],
            }),
            200,
          ));
      final results = await _repoWith(client).searchApps(query: 'note');
      const engine = RecommendationEngine();
      final result = engine.score(
        app: results.single,
        preferences: const UserPreferencesModel(),
        device: const DeviceProfileModel(),
      );

      // Real rating (4.8/5 -> 96/100) is the only verified factor here, so
      // it carries the whole (redistributed) weight - a calculated value,
      // never a hardcoded final score.
      expect(result.breakdown.available, [false, false, false, false, true]);
      expect(result.breakdown.effectiveWeights[4], closeTo(1.0, 1e-9));
      expect(result.breakdown.rating, closeTo(96, 0.01));
      // Unverified attributes are unavailable - 0 contribution, never a
      // neutral stand-in value.
      expect(result.breakdown.privacy, 0);
      expect(result.breakdown.resource, 0);
      expect(result.availableFactorCount, 1);
      expect(result.matchPercent, inInclusiveRange(0, 100));
      // Confidence is real and reduced because resourceLevel/trackerCount
      // are unavailable for this live app (Part 10).
      expect(result.confidence, lessThan(1.0));
    });
  });

  group('10. No fake fallback', () {
    test('searchApps never returns a result when the backend call fails - it throws instead', () async {
      final client = MockClient((request) async => http.Response('{}', 500));
      await expectLater(_repoWith(client).searchApps(query: 'note'), throwsA(isA<AppRepositoryException>()));
    });

    test('getAppDetails never invents a placeholder app on a non-404 failure - it throws instead', () async {
      final client = MockClient((request) async => http.Response('{}', 500));
      await expectLater(_repoWith(client).getAppDetails('com.example.a'), throwsA(isA<AppServiceUnavailableException>()));
    });
  });
}
