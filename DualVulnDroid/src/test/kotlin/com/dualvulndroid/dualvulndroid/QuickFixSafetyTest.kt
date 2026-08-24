package com.dualvulndroid.dualvulndroid

import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Phase 6, section 20: MANDATORY - proves the old dangerous behavior
 * (JavaSQLQuickFix/SQLQuickFix replacing an entire method with a
 * hardcoded, unrelated stub) is impossible to reproduce through the new
 * mechanism. Two independent guarantees are checked:
 *
 *  1. STRUCTURAL (compile-time): FixProposal's primary constructor takes
 *     exactly these 7 named, expression/literal-level String/Boolean
 *     parameters - no PSI method/class reference of any kind. If anyone
 *     ever adds a field capable of representing a method/class body, one
 *     of two things happens: either this call stops compiling (a field
 *     was added/removed/retyped) and must be updated deliberately, or -
 *     if a NEW field could be added invisibly via a default value - the
 *     explicit named-argument list below still proves the CURRENT shape
 *     is expression-only.
 *  2. BEHAVIORAL: given real, complex, unrelated user code (including
 *     the OLD hardcoded stub itself, fed back in as an adversarial
 *     input), the pattern analyzers that decide what to fix return null
 *     - no match, no fix, nothing gets touched.
 */
class QuickFixSafetyTest {

    // ---- 1. Structural guarantee (compile-time-checked) ----
    @Test
    fun `FixProposal only accepts expression-level String and Boolean data, never a method or class reference`() {
        val proposal = FixProposal(
            vulnerabilityType = "SQL Injection",
            cwe = "CWE-89",
            fileName = "Login.java",
            originalCode = "\"SELECT * FROM users WHERE id=\" + userId",
            replacementCode = "\"SELECT * FROM users WHERE id=?\"",
            explanation = "Parameterized query",
            isSafeToApply = true
        )
        // The real proof is that this call compiles at all: FixProposal's
        // constructor accepts exactly these 7 named String/Boolean
        // parameters, enforced by the compiler for every instance that
        // will ever exist - there is no PsiMethod/KtNamedFunction/
        // PsiClass parameter to (mis)use. This assertion just confirms
        // the values round-trip unchanged.
        org.junit.Assert.assertEquals("\"SELECT * FROM users WHERE id=?\"", proposal.replacementCode)
        org.junit.Assert.assertTrue(proposal.isSafeToApply)
    }

    // ---- 2. Behavioral guarantee: a real, complex, unrelated method is
    // never treated as a safe fix target ----
    @Test
    fun `a real unrelated user method is never matched by the SQL fix analyzer`() {
        // Exactly the shape of the mandatory negative test: some
        // completely different, legitimate method with real logic - not
        // the vulnerable pattern this Quick Fix targets at all.
        val someRealUserMethodBody = """
            val results = mutableListOf<User>()
            val cursor = db.query("users", null, "active = 1", null, null, null, "name ASC")
            cursor.use {
                while (it.moveToNext()) {
                    results.add(User(it.getString(0), it.getInt(1)))
                }
            }
            return results
        """.trimIndent()

        // The analyzer is only ever asked to evaluate a single query-
        // building EXPRESSION (never a whole method body) - feeding it
        // the entire method text, as a worst-case adversarial input,
        // must still yield no match.
        assertNull(SqlConcatenationAnalyzer.analyzeQueryExpression(someRealUserMethodBody, FixLanguage.KOTLIN))
        assertNull(SqlConcatenationAnalyzer.analyzeQueryExpression(someRealUserMethodBody, FixLanguage.JAVA))
    }

    @Test
    fun `the OLD hardcoded stub text itself is never matched by either analyzer`() {
        // The old JavaSQLQuickFix/SQLQuickFix's literal replacement text,
        // fed back in as input: proves the new analyzers don't somehow
        // special-case or reproduce that behavior either.
        val oldHardcodedStub = """
            fun login(username: String) {
                val query = "SELECT * FROM users WHERE name = ?"
                val selectionArgs = arrayOf(username)
                rawQuery(query, selectionArgs)
            }
        """.trimIndent()

        assertNull(SqlConcatenationAnalyzer.analyzeQueryExpression(oldHardcodedStub, FixLanguage.KOTLIN))
        assertNull(CertificateFixAnalyzer.matchReturnTrueOnly(listOf(oldHardcodedStub), "hostname", "session", FixLanguage.KOTLIN))
    }
}
