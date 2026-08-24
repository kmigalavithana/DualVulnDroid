package com.dualvulndroid.dualvulndroid

import com.intellij.codeInspection.LocalQuickFixAndIntentionActionOnPsiElement
import com.intellij.psi.PsiFile
import com.intellij.psi.PsiMethod
import com.intellij.psi.PsiReturnStatement
import com.intellij.psi.util.PsiTreeUtil
import org.jetbrains.kotlin.psi.KtClassOrObject
import org.jetbrains.kotlin.psi.KtNamedFunction
import org.jetbrains.kotlin.psi.KtReturnExpression

/**
 * Phase 6, section 14: locates the single supported certificate-fix
 * pattern (HostnameVerifier.verify() { return true }) and builds a fix
 * ONLY when the whole method body is confidently just that one
 * statement. Everything else - WebView, TrustManager, any verify() body
 * with more than the one statement - returns null, which
 * CodeSentinelAnnotator turns into the manual-remediation message.
 *
 * dataflow.py reports the finding's line at the HostnameVerifier
 * declaration, not the return statement, so this searches the whole
 * file for verify() methods inside a HostnameVerifier construct and
 * picks the one closest to the reported offset, rather than assuming
 * offset alignment.
 */
object CertificateFixLocator {

    fun tryBuildFix(file: PsiFile, result: LineScanResult, fileName: String): LocalQuickFixAndIntentionActionOnPsiElement? {
        if (result.vulnerabilityType != "Certificate Validation") return null
        val isKotlin = file.language.id.equals("kotlin", ignoreCase = true)
        return if (isKotlin) buildKotlinFix(file, result, fileName) else buildJavaFix(file, result, fileName)
    }

    private fun buildJavaFix(file: PsiFile, result: LineScanResult, fileName: String): SafeHostnameVerifierQuickFixJava? {
        val candidates = PsiTreeUtil.findChildrenOfType(file, PsiMethod::class.java)
            .filter { it.name == "verify" && isInsideHostnameVerifier(it.text, it.containingClass?.text) }
        val method = closestTo(candidates, result.startOffset) { it.textRange.startOffset } ?: return null

        val statements = method.body?.statements ?: return null
        if (statements.size != 1) return null
        val returnStmt = statements[0] as? PsiReturnStatement ?: return null
        if (returnStmt.returnValue?.text?.trim() != "true") return null

        val params = method.parameterList.parameters
        if (params.size < 2) return null
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(
            listOf("return true"), params[0].name, params[1].name, FixLanguage.JAVA
        ) ?: return null

        return SafeHostnameVerifierQuickFixJava(returnStmt, match, fileName, result)
    }

    private fun buildKotlinFix(file: PsiFile, result: LineScanResult, fileName: String): SafeHostnameVerifierQuickFixKotlin? {
        val candidates = PsiTreeUtil.findChildrenOfType(file, KtNamedFunction::class.java)
            .filter {
                val enclosing = PsiTreeUtil.getParentOfType(it, KtClassOrObject::class.java)
                it.name == "verify" && isInsideHostnameVerifier(it.text, enclosing?.text)
            }
        val function = closestTo(candidates, result.startOffset) { it.textRange.startOffset } ?: return null

        val bodyBlock = function.bodyBlockExpression ?: return null
        val statements = bodyBlock.statements
        if (statements.size != 1) return null
        val returnExpr = statements[0] as? KtReturnExpression ?: return null
        if (returnExpr.returnedExpression?.text?.trim() != "true") return null

        val params = function.valueParameters
        if (params.size < 2) return null
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(
            listOf("return true"), params[0].name, params[1].name, FixLanguage.KOTLIN
        ) ?: return null

        return SafeHostnameVerifierQuickFixKotlin(returnExpr, match, fileName, result)
    }

    private fun isInsideHostnameVerifier(methodText: String, enclosingText: String?): Boolean =
        (enclosingText ?: methodText).contains("HostnameVerifier")

    private fun <T> closestTo(candidates: List<T>, targetOffset: Int, offsetOf: (T) -> Int): T? =
        candidates.minByOrNull { kotlin.math.abs(offsetOf(it) - targetOffset) }
}
