package com.dualvulndroid.dualvulndroid

import junit.framework.TestCase

/**
 * Fast, no-IDE-fixture, no-backend-needed unit tests for LatencyTelemetry
 * itself (latency-measurement experiment task, Part 10 items 1-4). Plain
 * JUnit - LatencyTelemetry has no IntelliJ Platform dependency, so these
 * don't need BasePlatformTestCase or a running backend.
 */
class LatencyTelemetryTest : TestCase() {

    override fun setUp() {
        super.setUp()
        LatencyTelemetry.enabled = true
        LatencyTelemetry.reset()
    }

    override fun tearDown() {
        LatencyTelemetry.reset()
        LatencyTelemetry.enabled = false
        super.tearDown()
    }

    // ---- 3. Telemetry disabled behaviour ----
    fun testDisabledTelemetryRecordsNothing() {
        LatencyTelemetry.enabled = false
        val key = "disabled-key"
        LatencyTelemetry.markT0(key)
        LatencyTelemetry.markT1(key)
        LatencyTelemetry.markT2(key)
        LatencyTelemetry.markT6(key)
        LatencyTelemetry.markT7(key)
        LatencyTelemetry.markT8(key)
        assertTrue("No event may be recorded while disabled", LatencyTelemetry.snapshot().isEmpty())
    }

    // ---- 4. Telemetry enabled behaviour ----
    fun testEnabledTelemetryRecordsOneCompleteEventForASingleKey() {
        val key = "enabled-key"
        LatencyTelemetry.markT0(key)
        LatencyTelemetry.markT1(key)
        LatencyTelemetry.markT2(key)
        LatencyTelemetry.markT6(key)
        LatencyTelemetry.markT7(key)
        LatencyTelemetry.markT8(key)

        val events = LatencyTelemetry.snapshot()
        assertEquals(1, events.size)
        assertEquals(key, events[0].key)
    }

    // ---- 1. Timestamp ordering ----
    fun testMarksRecordedInOrderProduceNonDecreasingTimestamps() {
        val key = "ordering-key"
        LatencyTelemetry.markT0(key)
        Thread.sleep(1)
        LatencyTelemetry.markT1(key)
        Thread.sleep(1)
        LatencyTelemetry.markT2(key)
        Thread.sleep(1)
        LatencyTelemetry.markT6(key)
        Thread.sleep(1)
        LatencyTelemetry.markT7(key)
        Thread.sleep(1)
        LatencyTelemetry.markT8(key)

        val e = LatencyTelemetry.snapshot().single()
        assertTrue(e.t0 <= e.t1)
        assertTrue(e.t1 <= e.t2)
        assertTrue(e.t2 <= e.t6)
        assertTrue(e.t6 <= e.t7)
        assertTrue(e.t7 <= e.t8)
    }

    // ---- 2. Duration calculation ----
    fun testDurationsAreComputedCorrectlyAndNeverNegative() {
        val key = "duration-key"
        LatencyTelemetry.markT0(key)
        Thread.sleep(2)
        LatencyTelemetry.markT1(key)
        Thread.sleep(2)
        LatencyTelemetry.markT2(key)
        Thread.sleep(2)
        LatencyTelemetry.markT6(key)
        Thread.sleep(2)
        LatencyTelemetry.markT7(key)
        Thread.sleep(2)
        LatencyTelemetry.markT8(key)

        val e = LatencyTelemetry.snapshot().single()
        assertTrue(e.debounceNanos > 0)
        assertTrue(e.requestNanos > 0)
        assertTrue(e.pluginResponseProcessingNanos > 0)
        assertTrue(e.annotationNanos > 0)
        assertTrue(e.endToEndNanos > 0)
        assertTrue(e.pipelineNanos > 0)

        // end-to-end must be the largest span, pipeline the second-largest
        // (it excludes only the debounce) - a structural sanity check on
        // the formulas themselves, not on any specific measured value.
        assertTrue(e.endToEndNanos >= e.pipelineNanos)
        assertTrue(e.pipelineNanos >= e.requestNanos)
    }

    // An event must never complete on a partial set of marks (e.g. a pass
    // that was superseded between T6 and T7, or a cache-hit pass that
    // skips T1/T2/T6 entirely) - this is the mechanism that makes
    // "record every successful measurement individually" actually true.
    fun testIncompleteMarkSequenceNeverProducesAnEvent() {
        val key = "incomplete-key"
        LatencyTelemetry.markT0(key)
        LatencyTelemetry.markT1(key)
        LatencyTelemetry.markT2(key)
        LatencyTelemetry.markT6(key)
        // T7 never marked (e.g. doAnnotate() returned null and apply()
        // was never reached with a non-null result) - markT8 alone must
        // not fabricate a completed event.
        LatencyTelemetry.markT8(key)
        assertTrue(LatencyTelemetry.snapshot().isEmpty())
    }

    fun testDifferentKeysDoNotInterfereWithEachOther() {
        val keyA = "key-a"
        val keyB = "key-b"
        for (k in listOf(keyA, keyB)) {
            LatencyTelemetry.markT0(k)
            LatencyTelemetry.markT1(k)
            LatencyTelemetry.markT2(k)
            LatencyTelemetry.markT6(k)
            LatencyTelemetry.markT7(k)
            LatencyTelemetry.markT8(k)
        }
        val events = LatencyTelemetry.snapshot()
        assertEquals(2, events.size)
        assertEquals(setOf(keyA, keyB), events.map { it.key }.toSet())
    }

    fun testResetClearsBothCompletedAndInProgressState() {
        val key = "reset-key"
        LatencyTelemetry.markT0(key)
        LatencyTelemetry.markT1(key)
        LatencyTelemetry.markT2(key)
        LatencyTelemetry.markT6(key)
        LatencyTelemetry.markT7(key)
        LatencyTelemetry.markT8(key)
        assertEquals(1, LatencyTelemetry.snapshot().size)

        LatencyTelemetry.reset()
        assertTrue(LatencyTelemetry.snapshot().isEmpty())

        // A fresh mark sequence for the SAME key after reset must produce
        // a fresh event, not silently reuse old state.
        LatencyTelemetry.markT0(key)
        LatencyTelemetry.markT1(key)
        LatencyTelemetry.markT2(key)
        LatencyTelemetry.markT6(key)
        LatencyTelemetry.markT7(key)
        LatencyTelemetry.markT8(key)
        assertEquals(1, LatencyTelemetry.snapshot().size)
    }
}
