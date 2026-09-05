package com.dualvulndroid.dualvulndroid

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * UI-presentation task, item 11 (tests 1-5, 10): pure, deterministic unit
 * tests for FindingModel.kt's classify()/selectRelevantDetections() - the
 * exact fix for "CodeSentinel's vulnerability finding is NOT clearly
 * highlighted/annotated" / ToolWindow "Nothing to show" even when the real
 * backend returned real evidence (ss.java: vulnerable=false, decision=
 * SUSPICIOUS_REVIEW, confidence=60%, WITH a static_rule decisionEvidence
 * entry). No backend or IntelliJ platform fixture needed - these exercise
 * the classification rule directly against constructed responses,
 * including the real ss.java response shape.
 */
class FindingClassificationTest {

    private fun scanResponse(
        vulnerable: Boolean,
        vulnerabilityType: String = "SQL Injection",
        decision: String? = "VULNERABLE",
        decisionEvidence: List<DecisionReason>? = null,
        detections: List<Detection> = emptyList()
    ) = ScanResponse(
        prediction = "s0",
        vulnerable = vulnerable,
        vulnerabilityType = vulnerabilityType,
        confidence = 60.0,
        explanation = "test",
        detections = detections,
        decision = decision,
        decisionEvidence = decisionEvidence
    )

    private fun developerResult(
        vulnerable: Boolean,
        vulnerabilityType: String = "SQL Injection",
        recommendation: String = "REVIEW",
        evidence: List<DecisionReason>? = null,
        detections: List<Detection>? = emptyList()
    ) = DeveloperScanResult(
        vulnerable = vulnerable,
        vulnerabilityType = vulnerabilityType,
        confidence = 60.0,
        severity = "MEDIUM",
        model = DeveloperModelInfo(name = "XGBoost-Hybrid", version = "production"),
        decision = DeveloperDecision(
            riskLevel = "MEDIUM", recommendation = recommendation, decisionConfidence = 0.6, evidence = evidence
        ),
        detections = detections
    )

    // ---- 1/2. DEFINITE (confirmed vulnerable=true) for both known CWEs ----
    @Test
    fun `vulnerable=true SQL Injection classifies as DEFINITE`() {
        assertEquals(FindingClassification.DEFINITE, classify(scanResponse(vulnerable = true, vulnerabilityType = "SQL Injection")))
    }

    @Test
    fun `vulnerable=true Certificate Validation classifies as DEFINITE`() {
        assertEquals(FindingClassification.DEFINITE, classify(scanResponse(vulnerable = true, vulnerabilityType = "Certificate Validation")))
    }

    // ---- 3. SAFE creates no annotation ----
    @Test
    fun `decision=SAFE with vulnerable=false classifies as NONE`() {
        assertEquals(FindingClassification.NONE, classify(scanResponse(vulnerable = false, decision = "SAFE")))
    }

    // ---- 4. SUSPICIOUS_REVIEW handled per actual backend semantics ----
    @Test
    fun `the real ss-java response shape (SUSPICIOUS_REVIEW plus a static_rule signal) classifies as REVIEW`() {
        // Exact shape of the real live /predict response captured for
        // C.../untitled16/src/ss.java: vulnerable=false, decision=
        // SUSPICIOUS_REVIEW, decisionEvidence=[ml_model 0.6, static_rule 0.4].
        val response = scanResponse(
            vulnerable = false,
            decision = "SUSPICIOUS_REVIEW",
            decisionEvidence = listOf(
                DecisionReason("ml_model", "XGBoost predicts 's0' with 60.0% confidence", 0.6),
                DecisionReason("static_rule", "Keyword-based static rule also matched a supporting line", 0.4)
            ),
            detections = listOf(
                Detection(line = 5, code = "\"SELECT ... '\" + username + \"'\";", type = "SQL Injection", risk_weight = 0.5),
                Detection(line = 7, code = "return db.rawQuery(query, null);", type = "SQL Injection", risk_weight = 0.5)
            )
        )
        assertEquals(FindingClassification.REVIEW, classify(response))
    }

    @Test
    fun `SUSPICIOUS_REVIEW with ONLY ml_model evidence (no corroborating signal) classifies as NONE`() {
        // Guards against reintroducing decision_engine.py's own documented
        // "red warning on nearly every scanned file" problem - a middling
        // ML score alone, with nothing structural backing it up, must NOT
        // be surfaced.
        val response = scanResponse(
            vulnerable = false,
            decision = "SUSPICIOUS_REVIEW",
            decisionEvidence = listOf(DecisionReason("ml_model", "XGBoost predicts 's0' with 55.0% confidence", 0.55)),
            detections = listOf(Detection(line = 3, code = "int x = 1;", type = "SQL Injection", risk_weight = 0.05))
        )
        assertEquals(FindingClassification.NONE, classify(response))
    }

    @Test
    fun `SUSPICIOUS_REVIEW with corroborating evidence but no detections classifies as NONE (no location to anchor)`() {
        val response = scanResponse(
            vulnerable = false,
            decision = "SUSPICIOUS_REVIEW",
            decisionEvidence = listOf(DecisionReason("static_rule", "matched", 0.4)),
            detections = emptyList()
        )
        assertEquals(FindingClassification.NONE, classify(response))
    }

    @Test
    fun `SAFE decision with static_rule evidence still classifies as NONE (decision gates it, not evidence alone)`() {
        val response = scanResponse(
            vulnerable = false,
            decision = "SAFE",
            decisionEvidence = listOf(DecisionReason("static_rule", "matched", 0.4)),
            detections = listOf(Detection(line = 3, code = "x", type = "SQL Injection", risk_weight = 0.5))
        )
        assertEquals(FindingClassification.NONE, classify(response))
    }

    // ---- Same three classifications for the /developer/scan (project-scan) shape ----
    @Test
    fun `DeveloperScanResult vulnerable=true classifies as DEFINITE`() {
        assertEquals(FindingClassification.DEFINITE, classify(developerResult(vulnerable = true)))
    }

    @Test
    fun `DeveloperScanResult MANUAL_REVIEW_RECOMMENDED with corroborating evidence classifies as REVIEW`() {
        val result = developerResult(
            vulnerable = false,
            recommendation = "MANUAL_REVIEW_RECOMMENDED",
            evidence = listOf(
                DecisionReason("ml_model", "...", 0.6),
                DecisionReason("static_rule", "matched", 0.4)
            ),
            detections = listOf(Detection(line = 7, code = "db.rawQuery(query, null);", type = "SQL Injection", risk_weight = 0.5))
        )
        assertEquals(FindingClassification.REVIEW, classify(result))
    }

    @Test
    fun `DeveloperScanResult recommendation=NONE classifies as NONE`() {
        assertEquals(FindingClassification.NONE, classify(developerResult(vulnerable = false, recommendation = "NONE")))
    }

    // ---- 5/10. selectRelevantDetections: correct location, no noise, no duplicates ----
    @Test
    fun `selectRelevantDetections for DEFINITE keeps every detection unchanged (existing behavior preserved)`() {
        val detections = listOf(
            Detection(line = 1, code = "a", type = "SQL Injection", risk_weight = 0.05),
            Detection(line = 2, code = "b", type = "SQL Injection", risk_weight = 0.5)
        )
        assertEquals(detections, selectRelevantDetections(detections, FindingClassification.DEFINITE))
    }

    @Test
    fun `selectRelevantDetections for REVIEW narrows to the strongest-evidence line, excluding low-weight noise`() {
        // The real ss.java response has 4 detections: two incidental
        // keyword-token matches (risk_weight 0.0831, on the method
        // signature and declaration lines) and two on the actual
        // concatenation/sink lines (risk_weight 0.5) - only the latter
        // should ever be highlighted for a REVIEW-level finding.
        val detections = listOf(
            Detection(line = 1, code = "public Cursor findUser(...) {", type = "SQL Injection", risk_weight = 0.0831),
            Detection(line = 4, code = "String query =", type = "SQL Injection", risk_weight = 0.0831),
            Detection(line = 5, code = "\"SELECT ... '\" + username + \"'\";", type = "SQL Injection", risk_weight = 0.5),
            Detection(line = 7, code = "return db.rawQuery(query, null);", type = "SQL Injection", risk_weight = 0.5)
        )
        val relevant = selectRelevantDetections(detections, FindingClassification.REVIEW)

        assertEquals(2, relevant.size)
        assertTrue(relevant.all { it.risk_weight == 0.5 })
        assertEquals(setOf(5, 7), relevant.map { it.line }.toSet())
    }

    @Test
    fun `selectRelevantDetections for REVIEW still includes a real traced source-to-sink detection even with zero risk_weight`() {
        val detections = listOf(
            Detection(line = 1, code = "a", type = "SQL Injection", risk_weight = 0.0),
            Detection(
                line = 3, code = "db.rawQuery(query, null);", type = "SQL Injection", risk_weight = null,
                source_to_sink_path = listOf("Intent.getStringExtra()", "query", "rawQuery()")
            )
        )
        val relevant = selectRelevantDetections(detections, FindingClassification.REVIEW)

        assertEquals(1, relevant.size)
        assertEquals(3, relevant[0].line)
    }

    @Test
    fun `selectRelevantDetections never returns empty when detections exist (safety-net fallback)`() {
        // If every detection has risk_weight=null and no dataflow evidence,
        // the "strongest evidence" filter would otherwise exclude
        // everything - falls back to showing all of them rather than
        // silently highlighting nothing for a real REVIEW-level finding.
        val detections = listOf(Detection(line = 1, code = "a", type = "SQL Injection"))
        assertEquals(detections, selectRelevantDetections(detections, FindingClassification.REVIEW))
    }

    // ==========================================================
    // Critical bug fix regression tests: groupDetectionsByType() - a
    // single response's `detections` can legitimately contain BOTH
    // CWE-89 and CWE-295 entries (predict_code() always runs both
    // analyzers), while the response's own top-level vulnerabilityType/
    // cwe names only ONE of them. These use the EXACT detections shape
    // captured from a real live /developer/scan response for a file
    // containing both an unsafe concatenated query (lines 6, 8) and an
    // unsafe HostnameVerifier (line 12) - see the task's final report for
    // the raw JSON.
    // ==========================================================

    private val realMixedDetections = listOf(
        Detection(line = 6, code = "\"SELECT ... '\" + username + \"'\";", type = "SQL Injection", risk_weight = 0.5),
        Detection(line = 8, code = "return db.rawQuery(query, null);", type = "SQL Injection", risk_weight = 0.5),
        Detection(
            line = 12, code = "return new HostnameVerifier() {", type = "Certificate Validation", risk_weight = 1.0,
            source_to_sink_path = listOf("Network connection", "HostnameVerifier.verify()", "Trust decision"),
            dataflow_explanation = "HostnameVerifier.verify() unconditionally returns true - hostname checking is disabled, any certificate hostname is accepted.",
            dataflow_verdict = "VULNERABLE"
        )
    )

    // ---- 1/2/3: mixed response -> exactly one group per type, each preserving its own CWE ----
    @Test
    fun `groupDetectionsByType splits a mixed-type response into one group per detection type, never crossing them`() {
        val groups = groupDetectionsByType(realMixedDetections, FindingClassification.DEFINITE)

        assertEquals("Exactly one group per distinct detection type", 2, groups.size)

        val sqlGroup = groups.first { it.vulnerabilityType == "SQL Injection" }
        assertEquals("CWE-89", sqlGroup.cwe)
        assertTrue("SQL group must anchor only on SQL-type detections (lines 6, 8)",
            sqlGroup.anchorDetections.all { it.type == "SQL Injection" })
        assertEquals(setOf(6, 8), sqlGroup.anchorDetections.map { it.line }.toSet())

        val certGroup = groups.first { it.vulnerabilityType == "Certificate Validation" }
        assertEquals("CWE-295", certGroup.cwe)
        assertTrue("Cert group must anchor only on Certificate Validation-type detections (line 12)",
            certGroup.anchorDetections.all { it.type == "Certificate Validation" })
        assertEquals(
            "The CWE-295 detection (line 12, a HostnameVerifier match) must NEVER be reclassified as CWE-89 " +
                "just because another detection in the same response is SQL-related - the exact reported bug",
            setOf(12), certGroup.anchorDetections.map { it.line }.toSet()
        )
    }

    // ---- 4/6: counts are mathematically consistent, one group per type never inflates per-detection ----
    @Test
    fun `total group count never exceeds the number of distinct detection types present`() {
        val groups = groupDetectionsByType(realMixedDetections, FindingClassification.DEFINITE)
        // 3 detections, but only 2 DISTINCT types - lines 6 and 8 are two
        // supporting detections for the SAME SQL finding, not two separate
        // findings; this is what keeps "Total findings" mathematically
        // equal to SQL count + Cert count (2 groups here), never a raw
        // per-detection count (3) that would desynchronize from it.
        assertEquals(2, groups.size)
        assertEquals(1, groups.count { it.vulnerabilityType == "SQL Injection" })
        assertEquals(1, groups.count { it.vulnerabilityType == "Certificate Validation" })
    }

    @Test
    fun `a purely SQL-only response never manufactures a phantom Certificate Validation group`() {
        val sqlOnly = realMixedDetections.filter { it.type == "SQL Injection" }
        val groups = groupDetectionsByType(sqlOnly, FindingClassification.DEFINITE)
        assertEquals(1, groups.size)
        assertEquals("SQL Injection", groups[0].vulnerabilityType)
    }

    @Test
    fun `REVIEW-level grouping only surfaces a type-group that independently carries real evidence`() {
        // A response that is SUSPICIOUS_REVIEW purely because of SQL
        // evidence must not also manufacture a Certificate Validation
        // "needs review" finding out of a detection with no real weight
        // behind it (guards the SAME "don't flag nearly everything"
        // concern classify() already applies file-wide, now scoped per type).
        val detections = listOf(
            Detection(line = 6, code = "concat", type = "SQL Injection", risk_weight = 0.5),
            Detection(line = 20, code = "unrelated cert keyword match", type = "Certificate Validation", risk_weight = 0.05)
        )
        val groups = groupDetectionsByType(detections, FindingClassification.REVIEW)
        assertEquals(1, groups.size)
        assertEquals("SQL Injection", groups[0].vulnerabilityType)
    }

    @Test
    fun `empty detections or NONE classification never produce any group`() {
        assertEquals(emptyList<DetectionTypeGroup>(), groupDetectionsByType(emptyList(), FindingClassification.DEFINITE))
        assertEquals(emptyList<DetectionTypeGroup>(), groupDetectionsByType(realMixedDetections, FindingClassification.NONE))
        assertEquals(emptyList<DetectionTypeGroup>(), groupDetectionsByType(null, FindingClassification.DEFINITE))
    }

    // ---- toDetailView derives identity/evidence from the GROUP, never the response ----
    @Test
    fun `DeveloperScanResult toDetailView uses the group's own type-CWE and anchors on its own detections, not the response-level fields`() {
        val response = DeveloperScanResult(
            vulnerable = true,
            vulnerabilityType = "SQL Injection", // response-level - deliberately the OTHER type
            cwe = "CWE-89",
            confidence = 78.45,
            severity = "HIGH",
            model = DeveloperModelInfo(name = "XGBoost-Hybrid", version = "production"),
            decision = DeveloperDecision(riskLevel = "HIGH", recommendation = "REVIEW", decisionConfidence = 0.83, evidence = null),
            detections = realMixedDetections
        )
        val certGroup = groupDetectionsByType(response.detections, FindingClassification.DEFINITE)
            .first { it.vulnerabilityType == "Certificate Validation" }

        val view = response.toDetailView("ss.java", certGroup)

        assertEquals(
            "The finding's own vulnerabilityType must come from its detection group, not the response's SQL Injection",
            "Certificate Validation", view.vulnerabilityType
        )
        assertEquals("CWE-295", view.cwe)
        assertEquals(12, view.line)
        assertEquals(
            listOf("Network connection", "HostnameVerifier.verify()", "Trust decision"),
            view.sourceToSinkPath
        )
    }

    // ==========================================================
    // Zero-findings diagnostic regression test: reproduces the EXACT
    // /developer/scan response captured live for the real
    // C:/Users/User/IdeaProjects/untitled16/src/ss.java (SQL-only content,
    // no certificate code) and runs it through the full production
    // pipeline (classify -> groupDetectionsByType -> toDetailView),
    // confirming it produces exactly ONE CWE-89 finding, never zero.
    // A reported "Scan Project shows 0 findings" for this exact file was
    // traced (see the task's final report) to a stale/older installed
    // plugin build predating the SUSPICIOUS_REVIEW-surfacing fix, not a
    // defect in this pipeline - this test pins the CURRENT source code's
    // correct behavior against that exact real response shape so a
    // future regression here would be caught immediately.
    // ==========================================================
    @Test
    fun `the exact captured real ss-java developer-scan response produces exactly one CWE-89 finding, never zero`() {
        val result = DeveloperScanResult(
            vulnerable = false,
            vulnerabilityType = "SQL Injection",
            cwe = "CWE-89",
            confidence = 60.0,
            severity = "MEDIUM",
            model = DeveloperModelInfo(name = "XGBoost-Hybrid", version = "production"),
            decision = DeveloperDecision(
                riskLevel = "MEDIUM",
                recommendation = "MANUAL_REVIEW_RECOMMENDED",
                decisionConfidence = 0.6,
                evidence = listOf(
                    DecisionReason("ml_model", "XGBoost predicts 's0' with 60.0% confidence", 0.6),
                    DecisionReason("static_rule", "Keyword-based static rule also matched a supporting line", 0.4)
                )
            ),
            detections = listOf(
                Detection(line = 2, code = "public Cursor findUser(...) {", type = "SQL Injection", risk_weight = 0.0831),
                Detection(line = 5, code = "String query =", type = "SQL Injection", risk_weight = 0.0831),
                Detection(line = 6, code = "\"SELECT ... '\" + username + \"'\";", type = "SQL Injection", risk_weight = 0.5),
                Detection(line = 8, code = "return db.rawQuery(query, null);", type = "SQL Injection", risk_weight = 0.5)
            )
        )

        val classification = classify(result)
        assertEquals(FindingClassification.REVIEW, classification)

        val groups = groupDetectionsByType(result.detections, classification)
        assertEquals(1, groups.size)
        assertEquals("SQL Injection", groups[0].vulnerabilityType)
        assertEquals("CWE-89", groups[0].cwe)

        val view = result.toDetailView("src/ss.java", groups[0], classification == FindingClassification.REVIEW)
        assertEquals("CWE-89", view.cwe)
        assertEquals(8, view.line)
        assertTrue(view.reviewLevel)
    }
}
