package com.dualvulndroid.dualvulndroid

import com.intellij.codeInspection.LocalQuickFixAndIntentionActionOnPsiElement
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiElementFactory
import com.intellij.psi.PsiFile
import com.intellij.psi.PsiReturnStatement

/**
 * Phase 6, section 7: the ONLY certificate-validation auto-fix in this
 * phase. Bound to the SPECIFIC `return true;` statement inside
 * HostnameVerifier.verify() - replaces just the returned expression with
 * a delegation to the platform default verifier. Never touches the
 * enclosing method, class, or anything else.
 */
class SafeHostnameVerifierQuickFixJava(
    element: PsiReturnStatement,
    private val match: CertificateFixAnalyzer.HostnameVerifierMatch,
    private val fileName: String,
    private val originalFinding: LineScanResult
) : LocalQuickFixAndIntentionActionOnPsiElement(element) {

    override fun getText(): String = "DualVulnDroid: Use default hostname verifier"
    override fun getFamilyName(): String = text
    override fun startInWriteAction(): Boolean = true

    override fun isAvailable(project: Project, file: PsiFile, startElement: PsiElement, endElement: PsiElement): Boolean {
        val stmt = startElement as? PsiReturnStatement ?: return false
        return stmt.isValid && isReturnTrueLiteral(stmt)
    }

    override fun invoke(
        project: Project,
        file: PsiFile,
        editor: Editor?,
        startElement: PsiElement,
        endElement: PsiElement
    ) {
        val stmt = startElement as? PsiReturnStatement ?: return

        if (!isReturnTrueLiteral(stmt)) {
            Messages.showWarningDialog(project, "Source changed since analysis. Please re-scan.", "DualVulnDroid")
            return
        }

        try {
            val factory = PsiElementFactory.getInstance(project)
            val newExpr = factory.createExpressionFromText(match.replacementExpression(), stmt)
            stmt.returnValue?.replace(newExpr)
        } catch (e: Exception) {
            Messages.showWarningDialog(project, "Could not apply fix: ${e.message}", "DualVulnDroid")
            return
        }

        if (file.isPhysical) {
            FixVerificationRunner.runAsync(project, file, fileName, originalFinding)
        }
    }

    private fun isReturnTrueLiteral(stmt: PsiReturnStatement): Boolean =
        stmt.returnValue?.text?.trim() == "true"
}
