package com.dualvulndroid.dualvulndroid

import com.intellij.codeInspection.LocalQuickFixAndIntentionActionOnPsiElement
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.psi.PsiCodeBlock
import com.intellij.psi.PsiDeclarationStatement
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiElementFactory
import com.intellij.psi.PsiFile
import com.intellij.psi.PsiLocalVariable
import com.intellij.psi.PsiMethodCallExpression
import com.intellij.psi.PsiReferenceExpression
import com.intellij.psi.PsiStatement
import com.intellij.psi.util.PsiTreeUtil

/**
 * Java counterpart to SafeTrustManagerQuickFixKotlin - same scope: the
 * init() call's second argument and, when the array came from a local,
 * that single-variable declaration statement.
 */
class SafeTrustManagerQuickFixJava(
    element: PsiMethodCallExpression,
    private val declaration: PsiLocalVariable?,
    private val fileName: String,
    private val originalFinding: LineScanResult
) : LocalQuickFixAndIntentionActionOnPsiElement(element) {

    override fun getText(): String = "DualVulnDroid: Use default certificate validation"
    override fun getFamilyName(): String = text
    override fun startInWriteAction(): Boolean = true

    override fun isAvailable(project: Project, file: PsiFile, startElement: PsiElement, endElement: PsiElement): Boolean {
        val call = startElement as? PsiMethodCallExpression ?: return false
        return call.isValid && isStillTrustAll(call, declaration)
    }

    override fun invoke(project: Project, file: PsiFile, editor: Editor?, startElement: PsiElement, endElement: PsiElement) {
        val call = startElement as? PsiMethodCallExpression ?: return

        if (!isStillTrustAll(call, declaration)) {
            Messages.showWarningDialog(project, "Source changed since analysis. Please re-scan.", "DualVulnDroid")
            return
        }

        try {
            val factory = PsiElementFactory.getInstance(project)
            call.argumentList.expressions[1]
                .replace(factory.createExpressionFromText(CertificateFixAnalyzer.DEFAULT_TRUST_MANAGERS_ARGUMENT, call))
            declaration?.parent?.delete() // the PsiDeclarationStatement, which declares only this variable
        } catch (e: Exception) {
            Messages.showWarningDialog(project, "Could not apply fix: ${e.message}", "DualVulnDroid")
            return
        }

        if (file.isPhysical) {
            FixVerificationRunner.runAsync(project, file, fileName, originalFinding)
        }
    }

    companion object {
        fun isStillTrustAll(call: PsiMethodCallExpression, declaration: PsiLocalVariable?): Boolean {
            if (call.methodExpression.referenceName != "init") return false
            val args = call.argumentList.expressions
            if (args.size != 3) return false
            if (declaration == null) {
                return CertificateFixAnalyzer.isTrustAllArray(args[1].text, FixLanguage.JAVA)
            }
            if (!declaration.isValid || args[1].text.trim() != declaration.name) return false
            val statement = declaration.parent as? PsiDeclarationStatement ?: return false
            if (statement.declaredElements.size != 1) return false
            val initializer = declaration.initializer ?: return false
            if (!CertificateFixAnalyzer.isTrustAllArray(initializer.text, FixLanguage.JAVA)) return false
            return onlyUse(declaration, call)
        }

        fun findTrustAllDeclaration(call: PsiMethodCallExpression): PsiLocalVariable? {
            val name = call.argumentList.expressions.getOrNull(1)?.text?.trim() ?: return null
            var prev = PsiTreeUtil.getParentOfType(call, PsiStatement::class.java)?.prevSibling
            while (prev != null) {
                if (prev is PsiDeclarationStatement) {
                    prev.declaredElements.firstOrNull { it is PsiLocalVariable && it.name == name }?.let { return it as PsiLocalVariable }
                }
                prev = prev.prevSibling
            }
            return null
        }

        /** The declared local is referenced exactly once - by this init() call. */
        private fun onlyUse(declaration: PsiLocalVariable, call: PsiMethodCallExpression): Boolean {
            val block = PsiTreeUtil.getParentOfType(declaration, PsiCodeBlock::class.java) ?: return false
            val uses = PsiTreeUtil.findChildrenOfType(block, PsiReferenceExpression::class.java)
                .filter { it.qualifierExpression == null && it.referenceName == declaration.name }
            return uses.size == 1 && PsiTreeUtil.isAncestor(call, uses[0], false)
        }
    }
}
