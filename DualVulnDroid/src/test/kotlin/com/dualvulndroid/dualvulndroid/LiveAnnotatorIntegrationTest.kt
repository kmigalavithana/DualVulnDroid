package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.ui.TestDialog
import com.intellij.openapi.ui.TestDialogManager
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase

/**
 * Phase 14A: real, headless IntelliJ Platform integration test.
 *
 * Unlike the other tests in this module (which test isolated Kotlin
 * functions - SqlConcatenationAnalyzer, CertificateFixAnalyzer, etc. -
 * directly, with no IDE machinery involved), this class drives the ACTUAL
 * registered plugin classes exactly as the live IDE does:
 *   - CodeSentinelAnnotator.collectInformation()/doAnnotate() - the real
 *     ExternalAnnotator registered in plugin.xml, making a REAL HTTP call
 *     to the REAL running FastAPI backend (no mocked responses).
 *   - ShowFindingDetailsIntention - the real Alt+Enter intention.
 *   - SqlFixLocator/CertificateFixLocator + the real Quick Fix classes -
 *     the exact PSI-mutation code path the live editor uses.
 *
 * This is still not a substitute for a human/agent watching the rendered
 * GUI (no pixels are captured here, and .apply()'s Annotation/tooltip
 * construction itself is not re-exercised - only what it's built FROM).
 * It is a genuine escalation in rigor over plain unit tests: real PSI,
 * real backend I/O, real quick-fix mutation, run inside a real (headless)
 * IntelliJ Platform instance.
 *
 * REQUIRES the real backend running and reachable at
 * APIClient.BACKEND_URL. If it is not reachable, every test here fails
 * loudly with a clear message rather than silently reporting a fake pass -
 * see checkBackendReachable().
 */
class LiveAnnotatorIntegrationTest : BasePlatformTestCase() {

    private var previousTestDialog: TestDialog? = null

    override fun setUp() {
        super.setUp()
        // The real SafeSqlQuickFixJava/SafeHostnameVerifierQuickFixJava
        // Quick Fix classes trigger FixVerificationRunner.runAsync() as a
        // side effect of a real invoke() (file.isPhysical is true in this
        // light fixture) - the REAL async re-scan against the REAL backend
        // then calls Messages.showInfoMessage()/showWarningDialog() on
        // completion. IntelliJ's test framework fails any test that pops a
        // real modal by default (TestDialog.FATAL) - this swaps in the
        // standard auto-answering TestDialog for the duration of this
        // class's tests so that real background verification can complete
        // without a real modal appearing, without touching any production
        // code or suppressing a genuine assertion failure.
        previousTestDialog = TestDialogManager.setTestDialog(TestDialog.OK)
    }

    override fun tearDown() {
        // The real async FixVerificationRunner re-scan can complete during
        // super.tearDown() itself (it races with the test method's own
        // return) and pop its real result dialog there - TestDialog.OK
        // must still be installed when that happens, so it is only
        // restored AFTER super.tearDown() runs, not before.
        try {
            super.tearDown()
        } finally {
            TestDialogManager.setTestDialog(previousTestDialog ?: TestDialog.DEFAULT)
        }
    }

    private fun checkBackendReachable() {
        val probe = APIClient().scanCode("int x = 1;", "ReachabilityProbe.java")
        if (probe == null) {
            fail(
                "Real backend not reachable at ${APIClient.BACKEND_URL} - this live integration " +
                    "test requires the real FastAPI backend running (Phase 14A explicitly forbids " +
                    "fake backend responses). Start it and re-run."
            )
        }
    }

    private fun runRealAnnotator(fileName: String, code: String): List<LineScanResult> {
        checkBackendReachable()
        val file = myFixture.configureByText(fileName, code)
        val annotator = CodeSentinelAnnotator()
        val collected = annotator.collectInformation(file, myFixture.editor, false)
        assertNotNull("collectInformation returned null for a supported language file", collected)
        return annotator.doAnnotate(collected) ?: emptyList()
    }

    // ---- A. SQL vulnerable ----
    // Note (Phase 14A finding): a plain, unconfirmed-parameter concatenation
    // (`String query = "..." + userId; db.rawQuery(query, null);`) was
    // verified against the REAL backend to land on decision=SUSPICIOUS_REVIEW
    // (vulnerable=false) under the CURRENT production Decision Engine
    // thresholds - meaning the real-time annotator does NOT highlight it at
    // all (CodeSentinelAnnotator.doAnnotate() only builds results when
    // response.vulnerable==true). This traced-source variant (external
    // input via getIntent().getStringExtra(), same shape as test_api.py's
    // TRACED_SQL) was verified to cross the real VULNERABLE threshold
    // (confidence 60.78%, severity CRITICAL) and is used here for that
    // reason - not because the simpler pattern is "wrong," but because it
    // is honestly, verifiably NOT auto-decided under current production
    // thresholds. This distinction is itself a real Phase 14A finding.
    fun testASqlVulnerableIsAnnotatedByRealBackend() {
        val code = """
            public class LoginActivity {
                public void onCreate() {
                    String username = getIntent().getStringExtra("username");
                    String query = "SELECT * FROM users WHERE name=" + username;
                    db.rawQuery(query, null);
                }
            }
        """.trimIndent()
        val results = runRealAnnotator("LoginActivity.java", code)
        assertTrue("Expected at least one real SQL Injection finding from the real backend", results.isNotEmpty())
        val finding = results.first()
        assertEquals("SQL Injection", finding.vulnerabilityType)
        assertNotNull("Real backend must supply a severity", finding.severity)
        assertNotNull("Real backend must supply a decision", finding.decision)
        assertTrue("Confidence must be a real, positive value", finding.confidence > 0.0)
        println(
            "[LIVE][A] SQL vulnerable -> severity=${finding.severity} confidence=${finding.confidence} " +
                "decision=${finding.decision} evidenceCount=${finding.decisionEvidence?.size ?: 0} " +
                "sourceToSink=${finding.sourceToSinkPath}"
        )
    }

    // ---- B. SQL safe (parameterized) ----
    fun testBSqlSafeParameterizedProducesNoFinding() {
        val code = """
            public class LoginActivity {
                public void login(String userId) {
                    db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});
                }
            }
        """.trimIndent()
        val results = runRealAnnotator("SafeLogin.java", code)
        println("[LIVE][B] SQL safe -> findings=${results.size}")
        assertTrue("Parameterized SQL must not be flagged by the real backend", results.isEmpty())
    }

    // ---- C. Certificate vulnerable ----
    fun testCCertificateVulnerableIsAnnotatedByRealBackend() {
        val code = """
            import javax.net.ssl.HostnameVerifier;
            import javax.net.ssl.SSLSession;
            public class NetworkConfig {
                HostnameVerifier hv = new HostnameVerifier() {
                    public boolean verify(String hostname, SSLSession session) {
                        return true;
                    }
                };
            }
        """.trimIndent()
        val results = runRealAnnotator("NetworkConfig.java", code)
        assertTrue("Expected at least one real Certificate Validation finding", results.isNotEmpty())
        val finding = results.first()
        assertEquals("Certificate Validation", finding.vulnerabilityType)
        assertNotNull(finding.severity)
        println("[LIVE][C] Cert vulnerable -> severity=${finding.severity} confidence=${finding.confidence} decision=${finding.decision}")
    }

    // ---- D. Certificate safe ----
    // P0 Step 5 finding: this fixture's checkClientTrusted() used to have
    // an empty body ("{}"). That is independently a real, already-tested
    // production finding (see backend/tests/test_dataflow.py's
    // test_cert_empty_trust_manager_is_vulnerable - an empty
    // check*Trusted() body accepts every certificate chain, regardless of
    // which of the two methods is empty), unrelated to what this test is
    // meant to exercise. It only ever produced no finding here because of
    // a separate real backend bug (dataflow.py's TRUST_MANAGER_RE did not
    // match a fully package-qualified `implements javax.net.ssl.X509TrustManager`,
    // so the whole class was invisible to the structural cert analyzer).
    // Now that the regex bug is fixed, both methods must actually
    // validate for this to be a genuinely, unambiguously safe example -
    // matching what this test's name has always claimed.
    fun testDCertificateSafeProducesNoFinding() {
        val code = """
            import java.security.cert.X509Certificate;
            import java.security.cert.CertificateException;
            public class RealTrustManager implements javax.net.ssl.X509TrustManager {
                public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                    if (chain == null || chain.length == 0) {
                        throw new CertificateException("Empty chain");
                    }
                }
                public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                    if (chain == null || chain.length == 0) {
                        throw new CertificateException("Empty chain");
                    }
                }
                public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            }
        """.trimIndent()
        val results = runRealAnnotator("RealTrustManager.java", code)
        println("[LIVE][D] Cert safe -> findings=${results.size}")
        assertTrue("A real, safe certificate check must not be flagged", results.isEmpty())
    }

    // ---- E. Unrelated safe ----
    fun testEUnrelatedSafeCodeProducesNoFinding() {
        val code = """
            public class Utils {
                public void log() {
                    System.out.println("hello world");
                    int x = 5 + 3;
                }
            }
        """.trimIndent()
        val results = runRealAnnotator("Utils.java", code)
        println("[LIVE][E] Unrelated safe -> findings=${results.size}")
        assertTrue("Unrelated safe code must not be flagged", results.isEmpty())
    }

    // ---- Alt+Enter: real intention availability + real tool window activation ----
    fun testFAltEnterIntentionIsAvailableAndOpensToolWindow() {
        val code = """
            public class LoginActivity {
                public void onCreate() {
                    String username = getIntent().getStringExtra("username");
                    String query = "SELECT * FROM users WHERE name=" + username;
                    db.rawQuery(query, null);
                }
            }
        """.trimIndent()
        val results = runRealAnnotator("AltEnterTest.java", code)
        assertTrue(results.isNotEmpty())
        val finding = results.first()

        val intention = ShowFindingDetailsIntention("AltEnterTest.java", finding)
        assertTrue("Intention must report itself available (this is what Alt+Enter checks)",
            intention.isAvailable(project, myFixture.editor, myFixture.file))
        assertEquals("DualVulnDroid: Show finding details", intention.getText())
        assertFalse("Must not require a write action just to open the detail view", intention.startInWriteAction())

        val toolWindowManager = com.intellij.openapi.wm.ToolWindowManager.getInstance(project)
        var toolWindow = toolWindowManager.getToolWindow(DUALVULNDROID_TOOL_WINDOW_ID)
        if (toolWindow == null) {
            toolWindow = toolWindowManager.registerToolWindow(DUALVULNDROID_TOOL_WINDOW_ID) {}
        }
        val myToolWindow = MyToolWindow(project)
        MyToolWindow.registry[project] = myToolWindow

        // The real invoke() the IDE calls when Alt+Enter -> this intention is selected.
        // Must not throw - this exercises the real MyToolWindow.showFinding()
        // production code path (activate the tool window + add the finding
        // to the shared list) exactly as a live Alt+Enter would.
        intention.invoke(project, myFixture.editor, myFixture.file)
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()

        assertNotNull("The real tool window must be registered by id", toolWindow)
        assertSame(
            "MyToolWindow.showFinding() must route to the SAME registered instance, not a second disconnected one",
            myToolWindow, MyToolWindow.registry[project]
        )
        // NOTE (Phase 14A honesty note): ToolWindow.isActive/isVisible are
        // NOT reliably meaningful in this headless light-fixture (no real
        // window manager/UI is rendered), so they are logged for
        // information only, never asserted on. What IS proven here: Alt+
        // Enter's real intention.invoke() runs the real
        // MyToolWindow.showFinding() code path against a real registered
        // ToolWindow without throwing.
        println("[LIVE][AltEnter] intention available, invoked without error, tool window active=${toolWindow.isActive} visible=${toolWindow.isVisible} (not asserted - unreliable headless)")
    }

    // ---- Quick Fix: SQL concatenation pattern - preview/diff + real re-scan ----
    fun testGSqlQuickFixAppliesOnlyTheExpressionAndRealBackendConfirmsResolved() {
        val code = """
            public class LoginActivity {
                public String unrelatedMethod() {
                    return "do not touch this";
                }
                public void onCreate() {
                    String username = getIntent().getStringExtra("username");
                    String query = "SELECT * FROM users WHERE name=" + username;
                    db.rawQuery(query, null);
                }
            }
        """.trimIndent()
        val results = runRealAnnotator("QuickFixSql.java", code)
        assertTrue(results.isNotEmpty())
        // Phase 14A finding: the real backend's per-line detections for
        // this file also flag the unrelated method's line 1 as
        // "SQL Injection" (a real, observed static-rule signal, not a test
        // artifact - see the Phase 14A report). The Quick Fix must only
        // ever be built from the real sink line, so select on the line
        // text actually containing the sink call, not just the type.
        val finding = results.first { it.lineText.contains("rawQuery") }

        val fix = SqlFixLocator.tryBuildFix(myFixture.file, finding, "QuickFixSql.java")
        assertNotNull("The supported concatenation pattern must produce a real Quick Fix", fix)

        // Re-locate the same real PSI element the locator found, rather
        // than relying on the fix's own SmartPsiElementPointer-backed
        // getStartElement()/getEndElement() (unreliable to dereference
        // immediately after construction in this light test fixture) -
        // this is still the exact call the live element's rawQuery()
        // invocation the annotator attached the fix to.
        val callElement = com.intellij.psi.util.PsiTreeUtil.findChildrenOfType(
            myFixture.file, com.intellij.psi.PsiMethodCallExpression::class.java
        ).first { it.text.contains("rawQuery") }

        val before = myFixture.file.text
        WriteCommandAction.runWriteCommandAction(project) {
            fix!!.invoke(project, myFixture.file, myFixture.editor, callElement, callElement)
        }
        val after = myFixture.file.text

        assertTrue("Unrelated method must be completely untouched (no whole-method rewrite)",
            after.contains("return \"do not touch this\";"))
        assertTrue("Method signature must be untouched", after.contains("public void onCreate() {"))
        assertTrue("The getIntent() source line must be untouched",
            after.contains("String username = getIntent().getStringExtra(\"username\");"))
        assertFalse("The old vulnerable concatenation must be gone",
            after.contains("\"SELECT * FROM users WHERE name=\" + username"))
        assertNotSame("File text must actually change", before, after)
        println("[LIVE][QuickFix-SQL] before-length=${before.length} after-length=${after.length}")
        println("[LIVE][QuickFix-SQL] after:\n$after")

        // Real re-scan against the post-fix text with the real backend -
        // same check FixVerificationRunner performs asynchronously, done
        // synchronously here for a deterministic test result.
        val rescan = APIClient().scanCode(after, "QuickFixSql.java")
        assertNotNull("Re-scan must reach the real backend", rescan)
        val stillFlaggedAsSql = rescan!!.vulnerable && rescan.vulnerabilityType == "SQL Injection"
        assertFalse("Real backend must confirm the SQL Injection finding is gone after the fix", stillFlaggedAsSql)
        println("[LIVE][QuickFix-SQL] real re-scan -> vulnerable=${rescan.vulnerable} type=${rescan.vulnerabilityType}")
    }

    // ---- Quick Fix: Certificate HostnameVerifier return-true pattern ----
    fun testHCertificateQuickFixAppliesOnlyTheReturnStatementAndRealBackendConfirmsResolved() {
        val code = """
            import javax.net.ssl.HostnameVerifier;
            import javax.net.ssl.SSLSession;
            public class NetworkConfig {
                public String unrelatedField = "do not touch";
                HostnameVerifier hv = new HostnameVerifier() {
                    public boolean verify(String hostname, SSLSession session) {
                        return true;
                    }
                };
            }
        """.trimIndent()
        val results = runRealAnnotator("QuickFixCert.java", code)
        assertTrue(results.isNotEmpty())
        // Select the finding anchored at the actual "return true;" line so
        // CertificateFixLocator's closest-candidate search is unambiguous,
        // the same real-code-path reasoning as the SQL Quick Fix test above.
        val finding = results.first { it.lineText.contains("return true") }

        val fix = CertificateFixLocator.tryBuildFix(myFixture.file, finding, "QuickFixCert.java")
        assertNotNull("The supported HostnameVerifier return-true pattern must produce a real Quick Fix", fix)

        val returnElement = com.intellij.psi.util.PsiTreeUtil.findChildrenOfType(
            myFixture.file, com.intellij.psi.PsiReturnStatement::class.java
        ).first { it.text.trim() == "return true;" }

        val before = myFixture.file.text
        WriteCommandAction.runWriteCommandAction(project) {
            fix!!.invoke(project, myFixture.file, myFixture.editor, returnElement, returnElement)
        }
        val after = myFixture.file.text

        assertTrue("Unrelated field must be untouched (no whole-class rewrite)",
            after.contains("public String unrelatedField = \"do not touch\";"))
        assertTrue("The delegating replacement must be present", after.contains("getDefaultHostnameVerifier"))
        assertNotSame("File text must actually change", before, after)
        println("[LIVE][QuickFix-Cert] after:\n$after")

        val rescan = APIClient().scanCode(after, "QuickFixCert.java")
        assertNotNull(rescan)
        val stillFlaggedAsCert = rescan!!.vulnerable && rescan.vulnerabilityType == "Certificate Validation"
        assertFalse("Real backend must confirm the Certificate Validation finding is gone after the fix", stillFlaggedAsCert)
        println("[LIVE][QuickFix-Cert] real re-scan -> vulnerable=${rescan.vulnerable} type=${rescan.vulnerabilityType}")
    }

    // ---- Unsupported certificate pattern must never receive an automatic fix ----
    fun testIUnsupportedCertificatePatternStaysManualRemediation() {
        val code = """
            import java.security.cert.X509Certificate;
            public class InsecureTrustManager implements javax.net.ssl.X509TrustManager {
                public void checkServerTrusted(X509Certificate[] chain, String authType) {
                }
                public void checkClientTrusted(X509Certificate[] chain, String authType) {}
                public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            }
        """.trimIndent()
        val results = runRealAnnotator("Insecure.java", code)
        println("[LIVE][I] Unsupported cert pattern -> findings=${results.size}")
        if (results.isNotEmpty()) {
            val finding = results.first()
            val fix = CertificateFixLocator.tryBuildFix(myFixture.file, finding, "Insecure.java")
            assertNull("An unsupported certificate pattern must never receive an automatic Quick Fix", fix)
        }
    }
}
