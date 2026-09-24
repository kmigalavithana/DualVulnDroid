package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.ui.TestDialog
import com.intellij.openapi.ui.TestDialogManager
import com.intellij.psi.PsiErrorElement
import com.intellij.psi.PsiFile
import com.intellij.psi.PsiMethodCallExpression
import com.intellij.psi.PsiReturnStatement
import com.intellij.psi.util.PsiTreeUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import org.jetbrains.kotlin.psi.KtCallExpression

/**
 * P0 Step 7: end-to-end Quick-Fix validation against the REAL registered
 * plugin classes (SqlFixLocator/CertificateFixLocator - the ONLY places
 * that ever attach a Quick Fix, per their own docstrings) and the REAL
 * running backend. Complements LiveAnnotatorIntegrationTest's existing
 * testG/testH (which already cover one detect->fix->rescan cycle each)
 * with what this step specifically asks for: syntax-validity checking,
 * explicit no-fix-for-safe-code proof at the locator level, double-apply
 * corruption safety, and repeated cycles with fresh fixtures.
 *
 * REQUIRES the real backend running and reachable at APIClient.BACKEND_URL
 * - no mocked backend responses anywhere in this file.
 */
class QuickFixEndToEndTest : BasePlatformTestCase() {

    private var previousTestDialog: TestDialog? = null

    override fun setUp() {
        super.setUp()
        previousTestDialog = TestDialogManager.setTestDialog(TestDialog.OK)
    }

    override fun tearDown() {
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
                "Real backend not reachable at ${APIClient.BACKEND_URL} - this test requires " +
                    "the real backend running. Start it and re-run."
            )
        }
    }

    private fun assertNoSyntaxErrors(file: PsiFile) {
        val error = PsiTreeUtil.findChildOfType(file, PsiErrorElement::class.java)
        assertNull("Resulting source must be syntactically valid - found a PSI error: ${error?.errorDescription}", error)
    }

    private fun scanRealFile(fileName: String, code: String): Pair<PsiFile, List<LineScanResult>> {
        val file = myFixture.configureByText(fileName, code)
        val annotator = CodeSentinelAnnotator()
        val collected = annotator.collectInformation(file, myFixture.editor, false)
        assertNotNull(collected)
        val results = annotator.doAnnotate(collected) ?: emptyList()
        return file to results
    }

    private fun sqlVulnerableFixture(tag: String) = """
        public class LoginActivity$tag {
            public String unrelatedMethod$tag() {
                return "do not touch $tag";
            }
            public void onCreate() {
                String username = getIntent().getStringExtra("username");
                String query = "SELECT * FROM users WHERE name=" + username;
                db.rawQuery(query, null);
            }
        }
    """.trimIndent()

    private fun certVulnerableFixture(tag: String) = """
        import javax.net.ssl.HostnameVerifier;
        import javax.net.ssl.SSLSession;
        public class NetworkConfig$tag {
            public String unrelatedField$tag = "do not touch $tag";
            HostnameVerifier hv = new HostnameVerifier() {
                public boolean verify(String hostname, SSLSession session) {
                    return true;
                }
            };
        }
    """.trimIndent()

    // ---- SQL: detect -> fix -> syntax valid -> real rescan -> resolved,
    // repeated twice with a FRESH fixture each time (item 8) ----
    fun testSqlQuickFixEndToEndRepeatedWithFreshFixtures() {
        checkBackendReachable()
        repeat(2) { i ->
            val fileName = "FreshSql$i.java"
            val code = sqlVulnerableFixture("$i")
            val (file, results) = scanRealFile(fileName, code)
            assertTrue("Cycle $i: expected a real SQL Injection finding", results.isNotEmpty())
            val finding = results.first { it.lineText.contains("rawQuery") }

            val fix = SqlFixLocator.tryBuildFix(file, finding, fileName)
            assertNotNull("Cycle $i: expected a real Quick Fix", fix)

            val callElement = PsiTreeUtil.findChildrenOfType(file, PsiMethodCallExpression::class.java)
                .first { it.text.contains("rawQuery") }

            val before = file.text
            WriteCommandAction.runWriteCommandAction(project) {
                fix!!.invoke(project, file, myFixture.editor, callElement, callElement)
            }
            val after = file.text

            assertNotSame("Cycle $i: file text must actually change", before, after)
            assertTrue("Cycle $i: unrelated method must be untouched", after.contains("return \"do not touch $i\";"))
            assertTrue("Cycle $i: method signature must be untouched", after.contains("public void onCreate() {"))
            assertFalse(
                "Cycle $i: old vulnerable concatenation must be gone",
                after.contains("\"SELECT * FROM users WHERE name=\" + username")
            )
            assertNoSyntaxErrors(file)

            val rescan = APIClient().scanCode(after, fileName)
            assertNotNull("Cycle $i: real re-scan must succeed", rescan)
            val stillVulnerable = rescan!!.vulnerable && rescan.vulnerabilityType == "SQL Injection"
            assertFalse("Cycle $i: real backend must confirm the SQL Injection finding is gone", stillVulnerable)
        }
    }

    // ---- SQL with the value inside SQL quotes: the fix must drop the quotes
    // (name=?), never produce name='?' (a literal "?", not a parameter) ----
    fun testQuotedSqlValueQuickFixProducesARealParameter() {
        checkBackendReachable()
        val fileName = "QuotedSql.java"
        val code = """
            public class QuotedSql {
                public void onCreate() {
                    String username = getIntent().getStringExtra("username");
                    String query = "SELECT * FROM users WHERE name='" + username + "'";
                    db.rawQuery(query, null);
                }
            }
        """.trimIndent()
        val (file, results) = scanRealFile(fileName, code)
        val finding = results.first { it.lineText.contains("rawQuery") }
        val fix = SqlFixLocator.tryBuildFix(file, finding, fileName)
        assertNotNull("expected a real Quick Fix for the quoted value", fix)

        val callElement = PsiTreeUtil.findChildrenOfType(file, PsiMethodCallExpression::class.java)
            .first { it.text.contains("rawQuery") }
        WriteCommandAction.runWriteCommandAction(project) {
            fix!!.invoke(project, file, myFixture.editor, callElement, callElement)
        }
        val after = file.text

        assertTrue("placeholder must be a real parameter: $after", after.contains("\"SELECT * FROM users WHERE name=?\""))
        assertFalse("must never produce a quoted placeholder", after.contains("'?'"))
        assertTrue("the value must be bound as an argument", after.contains("new String[]{username}"))
        assertNoSyntaxErrors(file)

        val rescan = APIClient().scanCode(after, fileName)
        assertNotNull(rescan)
        assertFalse(
            "real backend must confirm the SQL Injection finding is gone",
            rescan!!.vulnerable && rescan.vulnerabilityType == "SQL Injection"
        )
    }

    // ---- Certificate: detect -> fix -> syntax valid -> real rescan ->
    // resolved, repeated twice with a FRESH fixture each time (item 8) ----
    fun testCertificateQuickFixEndToEndRepeatedWithFreshFixtures() {
        checkBackendReachable()
        repeat(2) { i ->
            val fileName = "FreshCert$i.java"
            val code = certVulnerableFixture("$i")
            val (file, results) = scanRealFile(fileName, code)
            assertTrue("Cycle $i: expected a real Certificate Validation finding", results.isNotEmpty())
            val finding = results.first { it.lineText.contains("return true") }

            val fix = CertificateFixLocator.tryBuildFix(file, finding, fileName)
            assertNotNull("Cycle $i: expected a real Quick Fix", fix)

            val returnElement = PsiTreeUtil.findChildrenOfType(file, PsiReturnStatement::class.java)
                .first { it.text.trim() == "return true;" }

            val before = file.text
            WriteCommandAction.runWriteCommandAction(project) {
                fix!!.invoke(project, file, myFixture.editor, returnElement, returnElement)
            }
            val after = file.text

            assertNotSame("Cycle $i: file text must actually change", before, after)
            assertTrue("Cycle $i: unrelated field must be untouched", after.contains("unrelatedField$i = \"do not touch $i\";"))
            assertTrue("Cycle $i: delegating replacement must be present", after.contains("getDefaultHostnameVerifier"))
            assertNoSyntaxErrors(file)

            val rescan = APIClient().scanCode(after, fileName)
            assertNotNull("Cycle $i: real re-scan must succeed", rescan)
            val stillVulnerable = rescan!!.vulnerable && rescan.vulnerabilityType == "Certificate Validation"
            assertFalse("Cycle $i: real backend must confirm the Certificate Validation finding is gone", stillVulnerable)
        }
    }

    // ---- Safe code: no Quick-Fix is ever offered, proven at the locator
    // level (not merely inferred from "no finding") ----
    fun testNoQuickFixOfferedForSafeSqlCode() {
        checkBackendReachable()
        val fileName = "SafeSqlNoFix.java"
        val code = """
            public class LoginActivity {
                public void login(String userId) {
                    db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});
                }
            }
        """.trimIndent()
        val (file, results) = scanRealFile(fileName, code)
        assertTrue("Safe parameterized SQL must produce no finding", results.isEmpty())

        val call = PsiTreeUtil.findChildrenOfType(file, PsiMethodCallExpression::class.java)
            .first { it.text.contains("rawQuery") }
        val syntheticResult = LineScanResult(
            lineText = call.text,
            vulnerabilityType = "SQL Injection",
            confidence = 0.0,
            startOffset = call.textRange.startOffset,
            endOffset = call.textRange.endOffset
        )
        assertNull(
            "SqlFixLocator must refuse to build a fix for an already-parameterized query, even if asked directly",
            SqlFixLocator.tryBuildFix(file, syntheticResult, fileName)
        )
    }

    fun testNoQuickFixOfferedForSafeCertificateCode() {
        checkBackendReachable()
        val fileName = "SafeCertNoFix.java"
        val code = """
            import javax.net.ssl.HostnameVerifier;
            import javax.net.ssl.HttpsURLConnection;
            import javax.net.ssl.SSLSession;
            public class NetworkConfig {
                HostnameVerifier verifier = new HostnameVerifier() {
                    public boolean verify(String hostname, SSLSession session) {
                        return HttpsURLConnection.getDefaultHostnameVerifier().verify(hostname, session);
                    }
                };
            }
        """.trimIndent()
        val (file, results) = scanRealFile(fileName, code)
        assertTrue("A HostnameVerifier delegating to the real default check must produce no finding", results.isEmpty())

        val method = PsiTreeUtil.findChildrenOfType(file, com.intellij.psi.PsiMethod::class.java).first { it.name == "verify" }
        val syntheticResult = LineScanResult(
            lineText = method.text,
            vulnerabilityType = "Certificate Validation",
            confidence = 0.0,
            startOffset = method.textRange.startOffset,
            endOffset = method.textRange.endOffset
        )
        assertNull(
            "CertificateFixLocator must refuse to build a fix for a delegating HostnameVerifier, even if asked directly",
            CertificateFixLocator.tryBuildFix(file, syntheticResult, fileName)
        )
    }

    // ---- Applying the same Quick Fix twice must not corrupt the source ----
    fun testApplyingSqlQuickFixTwiceDoesNotCorruptSource() {
        checkBackendReachable()
        val fileName = "DoubleApplySql.java"
        val (file, results) = scanRealFile(fileName, sqlVulnerableFixture("DoubleApply"))
        val finding = results.first { it.lineText.contains("rawQuery") }
        val fix = SqlFixLocator.tryBuildFix(file, finding, fileName)
        assertNotNull(fix)
        val callElement = PsiTreeUtil.findChildrenOfType(file, PsiMethodCallExpression::class.java)
            .first { it.text.contains("rawQuery") }

        WriteCommandAction.runWriteCommandAction(project) {
            fix!!.invoke(project, file, myFixture.editor, callElement, callElement)
        }
        val afterFirstApply = file.text
        assertNoSyntaxErrors(file)

        assertFalse(
            "The same fix instance must report itself unavailable once its target pattern is gone",
            fix!!.isAvailable(project, file, callElement, callElement)
        )

        WriteCommandAction.runWriteCommandAction(project) {
            fix.invoke(project, file, myFixture.editor, callElement, callElement)
        }
        val afterSecondApply = file.text
        assertEquals(
            "A second invoke() on the same already-applied fix must be a no-op, not corrupt the source",
            afterFirstApply, afterSecondApply
        )
        assertNoSyntaxErrors(file)
    }

    fun testApplyingCertificateQuickFixTwiceDoesNotCorruptSource() {
        checkBackendReachable()
        val fileName = "DoubleApplyCert.java"
        val (file, results) = scanRealFile(fileName, certVulnerableFixture("DoubleApply"))
        val finding = results.first { it.lineText.contains("return true") }
        val fix = CertificateFixLocator.tryBuildFix(file, finding, fileName)
        assertNotNull(fix)
        val returnElement = PsiTreeUtil.findChildrenOfType(file, PsiReturnStatement::class.java)
            .first { it.text.trim() == "return true;" }

        WriteCommandAction.runWriteCommandAction(project) {
            fix!!.invoke(project, file, myFixture.editor, returnElement, returnElement)
        }
        val afterFirstApply = file.text
        assertNoSyntaxErrors(file)

        assertFalse(
            "The same fix instance must report itself unavailable once its target pattern is gone",
            fix!!.isAvailable(project, file, returnElement, returnElement)
        )

        WriteCommandAction.runWriteCommandAction(project) {
            fix.invoke(project, file, myFixture.editor, returnElement, returnElement)
        }
        val afterSecondApply = file.text
        assertEquals(
            "A second invoke() on the same already-applied fix must be a no-op, not corrupt the source",
            afterFirstApply, afterSecondApply
        )
        assertNoSyntaxErrors(file)
    }

    // ---- Duplicate-finding / missing-Quick-Fix regression (live sandbox
    // bug report): a Kotlin sink whose query is built on an EARLIER `val`
    // line (not inline) used to produce TWO separate real-time annotations
    // for the exact same vulnerability - one on the `val query = ...`
    // declaration line (an incidental rule/SHAP keyword hit on "select ",
    // carrying no Quick Fix since SqlFixLocator's sink search never finds
    // a rawQuery(...) call on that line) and one on the actual
    // `db.rawQuery(...)` sink line. Alt+Enter on the declaration line's
    // annotation offered only "Show finding details", never the Quick Fix,
    // exactly as reported. This reproduces the EXACT live file content of
    // SqlInjectionQuickFixCandidate.kt's vulnerable BEFORE state. ----
    fun testKotlinVariableIndirectedSqlProducesOneAnnotationWithAWorkingQuickFix() {
        checkBackendReachable()
        val code = """
            package com.example.securitytest

            import android.database.Cursor
            import android.database.sqlite.SQLiteDatabase

            class UserDatabase {

                fun findUser(db: SQLiteDatabase, userId: String): Cursor {

                    val query = "SELECT * FROM users WHERE id=" + userId

                    return db.rawQuery(query, null)
                }
            }
        """.trimIndent()
        val (file, results) = scanRealFile("SqlInjectionQuickFixCandidate.kt", code)

        val sqlResults = results.filter { it.vulnerabilityType == "SQL Injection" }
        println("[QUICKFIX][dedup] SQL Injection annotation count = ${sqlResults.size}, lines = ${sqlResults.map { it.lineNumber }}")
        assertEquals(
            "The same rawQuery/concatenation vulnerability must be surfaced as exactly ONE real-time " +
                "annotation, not one per incidental keyword/dataflow detection sharing the same finding",
            1, sqlResults.size
        )

        val finding = sqlResults.single()
        assertTrue(
            "The single consolidated annotation must be anchored on the actual sink line - not the " +
                "`val query = ...` declaration line - so SqlFixLocator's sink search can find it",
            finding.lineText.contains("rawQuery")
        )

        val fix = SqlFixLocator.tryBuildFix(file, finding, "SqlInjectionQuickFixCandidate.kt")
        assertNotNull(
            "DualVulnDroid: Use parameterized query (rawQuery) must be available on this finding - " +
                "this is the exact fix that was reported missing",
            fix
        )

        val callElement = PsiTreeUtil.findChildrenOfType(file, KtCallExpression::class.java)
            .first { it.text.contains("rawQuery") }
        val before = file.text
        WriteCommandAction.runWriteCommandAction(project) {
            fix!!.invoke(project, file, myFixture.editor, callElement, callElement)
        }
        val after = file.text
        assertNotSame("The fix must actually change the file", before, after)
        assertFalse(
            "The old vulnerable concatenation must be gone",
            after.contains("\"SELECT * FROM users WHERE id=\" + userId")
        )
        assertNoSyntaxErrors(file)

        val rescan = APIClient().scanCode(after, "SqlInjectionQuickFixCandidate.kt")
        assertNotNull("Real re-scan must succeed", rescan)
        assertFalse(
            "The real backend must confirm the SQL Injection finding is gone after the fix",
            rescan!!.vulnerable && rescan.vulnerabilityType == "SQL Injection"
        )
    }

    // ---- execSQL(sql): the fix adds the bind-args argument ----
    fun testKotlinExecSqlQuickFixAddsBindArgs() {
        checkBackendReachable()
        val fileName = "NotesDao.kt"
        val code = """
            import android.database.sqlite.SQLiteDatabase

            class NotesDao(private val db: SQLiteDatabase) {
                fun deleteNote(noteId: String) {
                    db.execSQL("DELETE FROM notes WHERE id=" + noteId)
                }
            }
        """.trimIndent()
        val (file, results) = scanRealFile(fileName, code)
        val finding = results.first { it.vulnerabilityType == "SQL Injection" }
        val fix = SqlFixLocator.tryBuildFix(file, finding, fileName)
        assertNotNull("expected a Quick Fix for execSQL", fix)
        assertEquals("DualVulnDroid: Use parameterized query (execSQL)", fix!!.text)

        val call = PsiTreeUtil.findChildrenOfType(file, KtCallExpression::class.java).first { it.text.startsWith("execSQL") }
        WriteCommandAction.runWriteCommandAction(project) { fix.invoke(project, file, myFixture.editor, call, call) }
        val after = file.text

        assertTrue(after, after.contains("db.execSQL(\"DELETE FROM notes WHERE id=?\", arrayOf(noteId))"))
        assertNoSyntaxErrors(file)
        assertFalse("applied fix must no longer be offered", fix.isAvailable(project, file, call, call))

        val rescan = APIClient().scanCode(after, fileName)
        assertNotNull(rescan)
        assertFalse("real backend must confirm the SQL Injection finding is gone", rescan!!.vulnerable)
    }

    fun testJavaExecSqlQuickFixAddsObjectBindArgs() {
        checkBackendReachable()
        val fileName = "NotesActivity.java"
        val code = """
            public class NotesActivity {
                public void onCreate() {
                    String noteId = getIntent().getStringExtra("noteId");
                    db.execSQL("DELETE FROM notes WHERE id=" + noteId);
                }
            }
        """.trimIndent()
        val (file, results) = scanRealFile(fileName, code)
        val finding = results.first { it.vulnerabilityType == "SQL Injection" && it.lineText.contains("execSQL") }
        val fix = SqlFixLocator.tryBuildFix(file, finding, fileName)
        assertNotNull("expected a Quick Fix for execSQL", fix)

        val call = PsiTreeUtil.findChildrenOfType(file, PsiMethodCallExpression::class.java).first { it.text.contains("execSQL") }
        WriteCommandAction.runWriteCommandAction(project) { fix!!.invoke(project, file, myFixture.editor, call, call) }
        val after = file.text

        assertTrue(after, after.contains("db.execSQL(\"DELETE FROM notes WHERE id=?\", new Object[]{noteId});"))
        assertNoSyntaxErrors(file)

        val rescan = APIClient().scanCode(after, fileName)
        assertNotNull(rescan)
        assertFalse("real backend must confirm the SQL Injection finding is gone", rescan!!.vulnerable)
    }

    // ---- Trust-all X509TrustManager: init() gets null (platform default
    // trust managers) and the unused trust-all local is removed ----
    private val kotlinTrustAllCode = """
        import java.security.cert.X509Certificate
        import javax.net.ssl.SSLContext
        import javax.net.ssl.TrustManager
        import javax.net.ssl.X509TrustManager

        class TrustAllManager {
            fun unrelated() = "do not touch"

            fun insecureContext(): SSLContext {
                val trustAllCerts = arrayOf<TrustManager>(
                    object : X509TrustManager {
                        override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
                        override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
                        override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
                    }
                )
                val context = SSLContext.getInstance("TLS")
                context.init(null, trustAllCerts, null)
                return context
            }
        }
    """.trimIndent()

    fun testKotlinTrustAllQuickFixUsesDefaultTrustManagers() {
        checkBackendReachable()
        val fileName = "TrustAllManager.kt"
        val (file, results) = scanRealFile(fileName, kotlinTrustAllCode)
        val finding = results.first { it.vulnerabilityType == "Certificate Validation" }
        val fix = CertificateFixLocator.tryBuildFix(file, finding, fileName)
        assertNotNull("expected a Quick Fix for the trust-all TrustManager", fix)
        assertEquals("DualVulnDroid: Use default certificate validation", fix!!.text)

        val call = PsiTreeUtil.findChildrenOfType(file, KtCallExpression::class.java).first { it.text.startsWith("init(") }
        WriteCommandAction.runWriteCommandAction(project) { fix.invoke(project, file, myFixture.editor, call, call) }
        val after = file.text

        assertTrue(after, after.contains("context.init(null, null, null)"))
        assertFalse("the trust-all local must be removed", after.contains("trustAllCerts"))
        assertFalse(after.contains("checkServerTrusted"))
        assertTrue("unrelated code must be untouched", after.contains("fun unrelated() = \"do not touch\""))
        assertNoSyntaxErrors(file)
        assertFalse("applied fix must no longer be offered", fix.isAvailable(project, file, call, call))

        val rescan = APIClient().scanCode(after, fileName)
        assertNotNull(rescan)
        assertFalse("real backend must no longer confirm a Certificate Validation vulnerability", rescan!!.vulnerable)
    }

    fun testJavaInlineTrustAllQuickFixUsesDefaultTrustManagers() {
        checkBackendReachable()
        val fileName = "ApiClient.java"
        val code = """
            import java.security.cert.X509Certificate;
            import javax.net.ssl.SSLContext;
            import javax.net.ssl.TrustManager;
            import javax.net.ssl.X509TrustManager;

            public class ApiClient {
                public SSLContext context() throws Exception {
                    SSLContext ctx = SSLContext.getInstance("TLS");
                    ctx.init(null, new TrustManager[]{
                        new X509TrustManager() {
                            public void checkClientTrusted(X509Certificate[] chain, String authType) {}
                            public void checkServerTrusted(X509Certificate[] chain, String authType) {}
                            public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
                        }
                    }, null);
                    return ctx;
                }
            }
        """.trimIndent()
        val (file, results) = scanRealFile(fileName, code)
        val finding = results.first { it.vulnerabilityType == "Certificate Validation" }
        val fix = CertificateFixLocator.tryBuildFix(file, finding, fileName)
        assertNotNull("expected a Quick Fix for the inline trust-all array", fix)

        val call = PsiTreeUtil.findChildrenOfType(file, PsiMethodCallExpression::class.java).first { it.methodExpression.referenceName == "init" }
        WriteCommandAction.runWriteCommandAction(project) { fix!!.invoke(project, file, myFixture.editor, call, call) }
        val after = file.text

        assertTrue(after, after.contains("ctx.init(null, null, null);"))
        assertFalse(after.contains("checkServerTrusted"))
        assertNoSyntaxErrors(file)

        val rescan = APIClient().scanCode(after, fileName)
        assertNotNull(rescan)
        assertFalse("real backend must no longer confirm a Certificate Validation vulnerability", rescan!!.vulnerable)
    }

    fun testNoTrustManagerFixWhenTheArrayIsUsedElsewhere() {
        val code = kotlinTrustAllCode.replace("return context", "println(trustAllCerts.size)\n        return context")
        val file = myFixture.configureByText("SharedTrustAll.kt", code)
        val call = PsiTreeUtil.findChildrenOfType(file, KtCallExpression::class.java).first { it.text.startsWith("init(") }
        val syntheticResult = LineScanResult(
            lineText = call.text,
            vulnerabilityType = "Certificate Validation",
            confidence = 0.0,
            startOffset = call.textRange.startOffset,
            endOffset = call.textRange.endOffset
        )
        assertNull(
            "Deleting a trust-all local that other code still uses would break it - no automatic fix",
            CertificateFixLocator.tryBuildFix(file, syntheticResult, "SharedTrustAll.kt")
        )
    }
}
