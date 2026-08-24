package com.dualvulndroid.dualvulndroid

import com.intellij.codeInspection.LocalQuickFixAndIntentionActionOnPsiElement
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiFile
import org.jetbrains.kotlin.psi.KtExpression
import org.jetbrains.kotlin.psi.KtPsiFactory
import org.jetbrains.kotlin.psi.KtReturnExpression

/**
 * Kotlin counterpart to SafeHostnameVerifierQuickFixJava. Only supports
 * the explicit block-body `return true` shape (not the single-expression
 * `fun verify(...) = true` form) - a deliberate, documented scope limit
 * matching what the backend's own structural check already assumes.
 */
class SafeHostnameVerifierQuickFixKotlin(
    element: KtReturnExpression,
    private val match: CertificateFixAnalyzer.HostnameVerifierMatch,
    private val fileName: String,
    private val originalFinding: LineScanResult
) : LocalQuickFixAndIntentionActionOnPsiElement(element) {

    override fun getText(): String = "DualVulnDroid: Use default hostname verifier"
    override fun getFamilyName(): String = text
    override fun startInWriteAction(): Boolean = true

    override fun isAvailable(project: Project, file: PsiFile, startElement: PsiElement, endElement: PsiElement): Boolean {
        val expr = startElement as? KtReturnExpression ?: return false
        return expr.isValid && isReturnTrueLiteral(expr)
    }

    override fun invoke(
        project: Project,
        file: PsiFile,
        editor: Editor?,
        startElement: PsiElement,
        endElement: PsiElement
    ) {
        val expr = startElement as? KtReturnExpression ?: return

        if (!isReturnTrueLiteral(expr)) {
            Messages.showWarningDialog(project, "Source changed since analysis. Please re-scan.", "DualVulnDroid")
            return
        }

        try {
            val factory = KtPsiFactory(project)
            val newExpr: KtExpression = factory.createExpression(match.replacementExpression())
            expr.returnedExpression?.replace(newExpr)
        } catch (e: Exception) {
            Messages.showWarningDialog(project, "Could not apply fix: ${e.message}", "DualVulnDroid")
            return
        }

        if (file.isPhysical) {
            FixVerificationRunner.runAsync(project, file, fileName, originalFinding)
        }
    }

    private fun isReturnTrueLiteral(expr: KtReturnExpression): Boolean =
        expr.returnedExpression?.text?.trim() == "true"
}
