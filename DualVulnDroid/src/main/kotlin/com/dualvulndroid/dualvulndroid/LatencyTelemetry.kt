package com.dualvulndroid.dualvulndroid

import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Opt-in latency telemetry for the real-time annotation pipeline
 * (latency-measurement experiment task). DISABLED BY DEFAULT
 * ([enabled] starts false) - every call site in CodeSentinelAnnotator is
 * guarded by a single `if (LatencyTelemetry.enabled)` check first, so
 * when disabled, none of this class's code runs at all: no
 * System.nanoTime() call, no map write, no allocation. This is exactly
 * how "if telemetry is disabled, current behaviour must remain
 * unchanged" is satisfied - not just "produces the same result" but
 * "executes none of this code."
 *
 * Timestamps use System.nanoTime() - the JVM's monotonic high-resolution
 * clock - never System.currentTimeMillis() (wall clock, not monotonic,
 * can jump backwards on clock sync).
 *
 * Keyed by the SAME cache key CodeSentinelAnnotator already uses for its
 * staleness guard (path + file-text hash - see cacheKey() in that file).
 * A completed [LatencyEvent] only exists once every one of
 * T0/T1/T2/T6/T7/T8 has been recorded for the EXACT same key. A pass that
 * gets superseded partway through - the staleness guard's normal, correct
 * behavior - simply never finishes its set of marks and is never turned
 * into an event, rather than fabricating a partial/incorrect row.
 */
object LatencyTelemetry {
    @Volatile
    var enabled: Boolean = false

    data class LatencyEvent(
        val key: String,
        val t0: Long, val t1: Long, val t2: Long,
        val t6: Long, val t7: Long, val t8: Long,
    ) {
        // All durations in nanoseconds - the harness converts to
        // milliseconds for the CSV/JSON/report, keeping the raw,
        // unrounded value here.
        val debounceNanos get() = t1 - t0
        val requestNanos get() = t6 - t2
        val pluginResponseProcessingNanos get() = t7 - t6
        val annotationNanos get() = t8 - t7
        val endToEndNanos get() = t8 - t0
        val pipelineNanos get() = t8 - t1
    }

    private class InProgress {
        @Volatile var t0: Long? = null
        @Volatile var t1: Long? = null
        @Volatile var t2: Long? = null
        @Volatile var t6: Long? = null
        @Volatile var t7: Long? = null
        @Volatile var t8: Long? = null
    }

    private val inProgress = ConcurrentHashMap<String, InProgress>()
    private val completed = CopyOnWriteArrayList<LatencyEvent>()

    /** Clears all recorded/in-progress state - called by the harness
     * between the warm-up phase and the measured phase, and at the start
     * of a fresh experiment run, so stale entries from a previous run can
     * never leak into new results. */
    fun reset() {
        inProgress.clear()
        completed.clear()
    }

    /** A snapshot (defensive copy) of every event completed so far. */
    fun snapshot(): List<LatencyEvent> = completed.toList()

    private fun entry(key: String): InProgress = inProgress.getOrPut(key) { InProgress() }

    fun markT0(key: String) { if (enabled) entry(key).t0 = System.nanoTime() }
    fun markT1(key: String) { if (enabled) entry(key).t1 = System.nanoTime() }
    fun markT2(key: String) { if (enabled) entry(key).t2 = System.nanoTime() }
    fun markT6(key: String) { if (enabled) entry(key).t6 = System.nanoTime() }
    fun markT7(key: String) { if (enabled) entry(key).t7 = System.nanoTime() }

    fun markT8(key: String) {
        if (!enabled) return
        val e = inProgress[key] ?: return
        val t8 = System.nanoTime()
        val t0 = e.t0; val t1 = e.t1; val t2 = e.t2; val t6 = e.t6; val t7 = e.t7
        if (t0 != null && t1 != null && t2 != null && t6 != null && t7 != null) {
            completed.add(LatencyEvent(key, t0, t1, t2, t6, t7, t8))
            inProgress.remove(key)
        }
        // If any earlier mark is missing (e.g. this pass was superseded
        // between T6 and T7 in a way that still let apply() run once more
        // for old data), the in-progress entry is deliberately left as-is
        // rather than emitting a partial event - it will simply never
        // complete, and is cleared by the next reset().
    }
}
