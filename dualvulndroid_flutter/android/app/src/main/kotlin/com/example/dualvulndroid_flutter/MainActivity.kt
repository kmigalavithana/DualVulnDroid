package com.example.dualvulndroid_flutter

import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * SmartApp's one custom platform channel: "smartapp/installed_apps".
 *
 * Enumerates only the apps that are actually launchable from the home
 * screen (i.e. have a MAIN/LAUNCHER intent filter) - the same category of
 * information any Android launcher legitimately sees, and nothing about
 * another app's private data, source, or protected files. On Android 11+
 * this legitimately relies on the `<queries>` declaration in
 * AndroidManifest.xml (package-visibility filtering) rather than the
 * restricted QUERY_ALL_PACKAGES permission - if that declaration is ever
 * removed, or a future Android version restricts this further, the
 * result list simply comes back empty/partial rather than crashing, and
 * the Dart side (InstalledAppsService) already treats a failure/empty
 * platform-channel response as "unavailable" and falls back gracefully.
 */
class MainActivity : FlutterActivity() {
    private val channelName = "smartapp/installed_apps"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName).setMethodCallHandler { call, result ->
            if (call.method == "getInstalledApps") {
                try {
                    result.success(getLauncherApps())
                } catch (e: Exception) {
                    result.error("INSTALLED_APPS_ERROR", e.message, null)
                }
            } else {
                result.notImplemented()
            }
        }
    }

    private fun getLauncherApps(): List<Map<String, String>> {
        val pm = packageManager
        val mainIntent = Intent(Intent.ACTION_MAIN, null).apply { addCategory(Intent.CATEGORY_LAUNCHER) }
        val resolved = pm.queryIntentActivities(mainIntent, PackageManager.MATCH_ALL)

        val seen = HashSet<String>()
        val apps = mutableListOf<Map<String, String>>()
        for (info in resolved) {
            val packageName = info.activityInfo?.packageName ?: continue
            if (!seen.add(packageName)) continue

            // Exclude this app itself from its own "installed apps" list -
            // recommending alternatives to yourself is meaningless.
            if (packageName == this.packageName) continue

            val appInfo: ApplicationInfo? = try {
                pm.getApplicationInfo(packageName, 0)
            } catch (e: PackageManager.NameNotFoundException) {
                null
            }
            // Skip system components with no user-facing label rather than
            // showing a confusing blank/placeholder entry.
            val label = try {
                (appInfo?.let { pm.getApplicationLabel(it) } ?: info.loadLabel(pm)).toString()
            } catch (e: Exception) {
                packageName
            }

            apps.add(mapOf("appName" to label, "packageName" to packageName))
        }
        return apps
    }
}
