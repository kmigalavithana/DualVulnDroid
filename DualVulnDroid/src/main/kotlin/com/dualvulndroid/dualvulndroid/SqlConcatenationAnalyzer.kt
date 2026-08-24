package com.dualvulndroid.dualvulndroid

/**
 * Phase 6, sections 3-5: decides whether a SQL-injection finding matches
 * a small, deliberately narrow set of patterns confident enough to
 * auto-fix, and if so extracts exactly what's needed to build the
 * replacement - never more.
 *
 * This is a TEXT-structural analyzer (like dataflow.py's own approach),
 * kept separate from PSI so the safety-critical "is this safe" decision
 * is unit-testable without a live IDE/project fixture. PSI is used only
 * afterwards, to perform the actual replacement on the exact matched
 * expression (see SafeSqlQuickFix.kt) - never to decide what's safe.
 *
 * Deliberately conservative scope (section 4): supports ONLY
 *   "<sql literal>" + identifier
 *   "<sql literal>" + identifier + "<sql literal>"
 * and the Kotlin single-variable template equivalent. The identifier
 * must be a bare name (parameter/local/field reference) - never a method
 * call, cast, or nested expression - so the fix never risks re-ordering
 * or re-evaluating a side-effecting expression. Multi-value
 * concatenation, StringBuilder, and anything not matching this exact
 * shape are intentionally NOT supported; see MANUAL_REMEDIATION_MESSAGE.
 */
object SqlConcatenationAnalyzer {

    const val MANUAL_REMEDIATION_MESSAGE =
        "Automatic fix unavailable for this pattern. Manual remediation recommended."

    data class Match(
        val prefixLiteral: String,   // the literal SQL text before the placeholder, WITHOUT surrounding quotes
        val suffixLiteral: String?,  // optional literal SQL text after the placeholder (e.g. a closing quote), WITHOUT surrounding quotes
        val identifier: String,      // the exact bare identifier token supplying the dynamic value
        val language: FixLanguage
    ) {
        /** The fully-quoted, parameterized replacement literal, e.g. "SELECT ... WHERE id=?" */
        fun parameterizedLiteral(): String {
            val body = prefixLiteral + "?" + (suffixLiteral ?: "")
            return "\"$body\""
        }

        fun argsArrayExpression(): String = when (language) {
            FixLanguage.JAVA -> "new String[]{$identifier}"
            FixLanguage.KOTLIN -> "arrayOf($identifier)"
        }
    }

    // Written with regular (non-raw) escaping, not a triple-quoted raw
    // string - counting consecutive quote characters at the boundary of
    // a Kotlin raw string is exactly the kind of off-by-one that's easy
    // to get wrong (and did, initially - see git history/test failure
    // this fixed). This decodes to the regex: "(?:[^"\\]|\\.)*"
    private val JAVA_STRING_LITERAL = "\"(?:[^\"\\\\]|\\\\.)*\""
    private val IDENTIFIER = """[A-Za-z_][A-Za-z0-9_]*"""

    private val TWO_PART_REGEX = Regex("""^\s*($JAVA_STRING_LITERAL)\s*\+\s*($IDENTIFIER)\s*$""")
    private val THREE_PART_REGEX = Regex("""^\s*($JAVA_STRING_LITERAL)\s*\+\s*($IDENTIFIER)\s*\+\s*($JAVA_STRING_LITERAL)\s*$""")

    // Kotlin template string with exactly one substitution, either $ident or ${ident} -
    // matches a whole string literal "...${'$'}ident..." with no other templates inside.
    private val KOTLIN_SINGLE_TEMPLATE = Regex("""^\s*"([^"$]*)\$\{?($IDENTIFIER)}?([^"$]*)"\s*$""")

    private val SQL_KEYWORDS = Regex("""(?i)\b(select|insert|update|delete)\b""")

    private fun unquote(literal: String): String = literal.substring(1, literal.length - 1)

    /**
     * exprText: the source text of the expression that builds the SQL
     * query string (e.g. the initializer of `val query = ...`, or a
     * sink call's first argument).
     *
     * Returns null whenever the pattern isn't confidently safe - callers
     * MUST treat null as "no automatic fix", never as "assume the simple
     * case".
     */
    fun analyzeQueryExpression(exprText: String, language: FixLanguage): Match? {
        val trimmed = exprText.trim()
        if (trimmed.isEmpty()) return null

        val match = if (language == FixLanguage.KOTLIN) {
            matchKotlinTemplate(trimmed) ?: matchConcatenation(trimmed, language)
        } else {
            matchConcatenation(trimmed, language)
        } ?: return null

        return if (isPlausibleAndSafeSql(match)) match else null
    }

    private fun matchConcatenation(trimmed: String, language: FixLanguage): Match? {
        THREE_PART_REGEX.matchEntire(trimmed)?.let { m ->
            val (prefix, ident, suffix) = m.destructured
            return Match(unquote(prefix), unquote(suffix), ident, language)
        }
        TWO_PART_REGEX.matchEntire(trimmed)?.let { m ->
            val (prefix, ident) = m.destructured
            return Match(unquote(prefix), null, ident, language)
        }
        return null
    }

    private fun matchKotlinTemplate(trimmed: String): Match? {
        val m = KOTLIN_SINGLE_TEMPLATE.matchEntire(trimmed) ?: return null
        val (prefix, ident, suffix) = m.destructured
        if (prefix.contains('$') || suffix.contains('$')) return null // more than one substitution - too complex
        return Match(prefix, suffix.ifEmpty { null }, ident, FixLanguage.KOTLIN)
    }

    private fun isPlausibleAndSafeSql(match: Match): Boolean {
        val combined = match.prefixLiteral + (match.suffixLiteral ?: "")
        // Must look like real SQL, and must not already contain a
        // placeholder (which would mean it's already partially
        // parameterized - too ambiguous to auto-fix safely).
        return SQL_KEYWORDS.containsMatchIn(combined) && !combined.contains('?')
    }

    // ---- Sink validation (section 4.D): only rawQuery(query, null) is
    // supported in this phase - execSQL and other sinks are intentionally
    // left to manual remediation (a documented, deliberate scope limit). ----

    private val RAW_QUERY_CALL = Regex("""\brawQuery\s*\(""")

    fun isSupportedSink(sinkCallText: String): Boolean = RAW_QUERY_CALL.containsMatchIn(sinkCallText)

    /** The second argument of the sink call must currently be exactly
     * `null` - if real args are already present, the pattern is too
     * ambiguous to safely overwrite. */
    fun isSecondArgumentReplaceable(secondArgText: String): Boolean = secondArgText.trim() == "null"
}
