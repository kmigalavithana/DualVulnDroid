package com.dualvulndroid.dualvulndroid

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Phase 6, section 17: the SQL Quick Fix's safety-critical decision
 * logic, tested offline (no IntelliJ platform fixture needed - this is
 * the same design principle as dataflow.py's own text-structural
 * approach).
 */
class SqlConcatenationAnalyzerTest {

    // ---- 1. Simple vulnerable concatenation ----
    @Test
    fun `simple concatenation is matched and produces a correct parameterized replacement`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE id=\" + userId", FixLanguage.JAVA
        )
        assertNotNull(match)
        assertEquals("userId", match!!.identifier)
        assertEquals("\"SELECT * FROM users WHERE id=?\"", match.parameterizedLiteral())
        assertEquals("new String[]{userId}", match.argsArrayExpression())
    }

    @Test
    fun `a quoted value loses its SQL quotes so the placeholder is a real parameter`() {
        // name='?' would compare against the literal text "?" - the quotes
        // must go when the value becomes a bound argument.
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE name='\" + username + \"'\"", FixLanguage.JAVA
        )
        assertNotNull(match)
        assertEquals("username", match!!.identifier)
        assertEquals("\"SELECT * FROM users WHERE name=?\"", match.parameterizedLiteral())
        assertEquals("new String[]{username}", match.argsArrayExpression())
    }

    @Test
    fun `a quoted value followed by more SQL keeps the rest of the statement`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE name='\" + username + \"' AND active=1\"", FixLanguage.JAVA
        )
        assertEquals("\"SELECT * FROM users WHERE name=? AND active=1\"", match!!.parameterizedLiteral())
    }

    @Test
    fun `kotlin template inside SQL quotes is parameterized without the quotes`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE name='\$username'\"", FixLanguage.KOTLIN
        )
        assertEquals("\"SELECT * FROM users WHERE name=?\"", match!!.parameterizedLiteral())
        assertEquals("arrayOf(username)", match.argsArrayExpression())
    }

    @Test
    fun `unbalanced quote around the value gets no automatic fix`() {
        assertNull(
            SqlConcatenationAnalyzer.analyzeQueryExpression(
                "\"SELECT * FROM users WHERE name='\" + username", FixLanguage.JAVA
            )
        )
    }

    @Test
    fun `LIKE wildcard inside the quotes gets no automatic fix`() {
        // Parameterizing '%x%' needs the bound VALUE changed to "%x%", which
        // a text-only rewrite of the SQL can't do safely.
        assertNull(
            SqlConcatenationAnalyzer.analyzeQueryExpression(
                "\"SELECT * FROM notes WHERE title LIKE '%\" + term + \"%'\"", FixLanguage.JAVA
            )
        )
    }

    @Test
    fun `escaped quote next to the value gets no automatic fix`() {
        assertNull(
            SqlConcatenationAnalyzer.analyzeQueryExpression(
                "\"SELECT * FROM users WHERE name=''\" + username + \"''\"", FixLanguage.JAVA
            )
        )
    }

    // ---- 2. Kotlin interpolation ----
    @Test
    fun `kotlin single-variable template interpolation is matched`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE id=\$userId\"", FixLanguage.KOTLIN
        )
        assertNotNull(match)
        assertEquals("userId", match!!.identifier)
        assertEquals("arrayOf(userId)", match.argsArrayExpression())
    }

    @Test
    fun `kotlin braced template interpolation is matched`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE id=\${userId}\"", FixLanguage.KOTLIN
        )
        assertNotNull(match)
        assertEquals("userId", match!!.identifier)
    }

    // ---- 3. Safe parameterized query - no concatenation present at all ----
    @Test
    fun `already parameterized literal is not matched (nothing to fix)`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE id=?\"", FixLanguage.JAVA
        )
        assertNull(match)
    }

    // ---- 4. Multiple query parameters - too complex, must not auto-fix ----
    @Test
    fun `multiple concatenated dynamic values are rejected`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM t WHERE a=\" + x + \" AND b=\" + y", FixLanguage.JAVA
        )
        assertNull(match)
    }

    // ---- 5. Complex SQL (method calls, nested expressions) - manual remediation ----
    @Test
    fun `concatenation involving a method call is rejected, not blindly transformed`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE id=\" + getUserId()", FixLanguage.JAVA
        )
        assertNull(match)
    }

    @Test
    fun `concatenation involving field access is rejected`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE id=\" + request.userId", FixLanguage.JAVA
        )
        assertNull(match)
    }

    // ---- 6. StringBuilder construction - not safely reconstructable, manual remediation ----
    @Test
    fun `StringBuilder-built queries are never matched`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "sb.append(\"SELECT * FROM users WHERE id=\").append(userId).toString()", FixLanguage.JAVA
        )
        assertNull(match)
    }

    // ---- 7. Already-fixed / non-SQL text ----
    @Test
    fun `non-SQL text is rejected even if structurally concatenation-shaped`() {
        val match = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"hello \" + name", FixLanguage.JAVA
        )
        assertNull(match)
    }

    // ---- Sink / argument validation ----
    @Test
    fun `only rawQuery is treated as a supported sink`() {
        assertTrue(SqlConcatenationAnalyzer.isSupportedSink("db.rawQuery(query, null)"))
        assertFalse(SqlConcatenationAnalyzer.isSupportedSink("db.execSQL(query)"))
        assertFalse(SqlConcatenationAnalyzer.isSupportedSink("db.query(table, null, null, null, null, null, null)"))
    }

    @Test
    fun `second argument must be exactly null to be safely replaceable`() {
        assertTrue(SqlConcatenationAnalyzer.isSecondArgumentReplaceable("null"))
        assertFalse(SqlConcatenationAnalyzer.isSecondArgumentReplaceable("existingArgs"))
        assertFalse(SqlConcatenationAnalyzer.isSecondArgumentReplaceable("new String[]{x}"))
    }

    // ---- 8. "Source changed since analysis" - the identifier-equality
    // check the real fix's revalidate() relies on (full PSI-level
    // re-validation needs a live IntelliJ platform fixture, out of scope
    // for this project's existing offline test convention - this proves
    // the underlying comparison the fix depends on behaves correctly). ----
    @Test
    fun `re-analyzing changed source yields a different identifier, which the fix treats as invalidated`() {
        val original = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE id=\" + userId", FixLanguage.JAVA
        )
        val afterEdit = SqlConcatenationAnalyzer.analyzeQueryExpression(
            "\"SELECT * FROM users WHERE id=\" + accountId", FixLanguage.JAVA
        )
        assertNotNull(original)
        assertNotNull(afterEdit)
        assertTrue("a real fix must detect this identifier change and refuse to apply", original!!.identifier != afterEdit!!.identifier)
    }
}
