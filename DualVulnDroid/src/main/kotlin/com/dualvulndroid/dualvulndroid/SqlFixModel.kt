package com.dualvulndroid.dualvulndroid

// =====================================================
// Phase 6: safe, targeted remediation models.
//
// SAFETY BY CONSTRUCTION: FixProposal only ever carries EXPRESSION-level
// replacement text (a query literal, an args array/varargs expression).
// There is no field anywhere in this file capable of holding a whole
// method/class body - the old JavaSQLQuickFix/SQLQuickFix danger (an
// entire method silently replaced with a hardcoded stub) is structurally
// impossible to reproduce through this model, not just avoided by
// convention. See tests/QuickFixSafetyTest.kt for the enforcing test.
// =====================================================

enum class FixLanguage { JAVA, KOTLIN }

/**
 * A candidate remediation for ONE specific finding. Never exposed
 * through any backend API (section 15) - this is a plugin-internal,
 * in-memory model only.
 */
data class FixProposal(
    val vulnerabilityType: String,
    val cwe: String?,
    val fileName: String,
    val originalCode: String,
    val replacementCode: String,
    val explanation: String,
    val isSafeToApply: Boolean
)

/**
 * The result of re-scanning after a fix was applied, comparing against
 * the original finding. Every field here comes from an ACTUAL re-scan -
 * this type has no way to represent "assumed fixed" without a real
 * afterDetected value.
 */
data class FixVerification(
    val vulnerabilityType: String,
    val cwe: String?,
    val beforeDetected: Boolean,
    val beforeConfidence: Double,
    val afterDetected: Boolean,
    val afterConfidence: Double,
    val resolved: Boolean,
    val message: String
) {
    fun toDisplayString(): String {
        val sb = StringBuilder()
        sb.append("Security Fix Verification\n\n")
        sb.append("Before:\n${cwe ?: vulnerabilityType} - ${"%.0f".format(beforeConfidence)}% confidence\n\n")
        sb.append("After:\n")
        sb.append(if (afterDetected) "${cwe ?: vulnerabilityType} still detected - ${"%.0f".format(afterConfidence)}% confidence\n\n"
                   else "${cwe ?: vulnerabilityType} not detected\n\n")
        sb.append(if (resolved) "Result:\n✓ Vulnerability appears resolved" else "Result:\n⚠ Vulnerability still detected")
        return sb.toString()
    }
}

/**
 * Local, metadata-only remediation log entry (section 16). Deliberately
 * excludes source code / file paths that could identify the developer's
 * project contents - only classification-level facts a research
 * evaluation needs.
 */
data class RemediationLogEntry(
    val timestampEpochMillis: Long,
    val vulnerabilityType: String,
    val cwe: String?,
    val fixAvailable: Boolean,
    val fixApplied: Boolean,
    val beforeDetected: Boolean?,
    val afterDetected: Boolean?,
    val resolved: Boolean?
)
