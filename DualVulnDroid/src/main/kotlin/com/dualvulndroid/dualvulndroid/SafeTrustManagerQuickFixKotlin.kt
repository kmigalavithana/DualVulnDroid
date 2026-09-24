package com.dualvulndroid.dualvulndroid

import com.intellij.codeInspection.LocalQuickFixAndIntentionActionOnPsiElement
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiFile
import com.intellij.psi.util.PsiTreeUtil
import org.jetbrains.kotlin.psi.KtBlockExpression
import org.jetbrains.kotlin.psi.KtCallExpression
import org.jetbrains.kotlin.psi.KtNameReferenceExpression
import org.jetbrains.kotlin.psi.KtProperty
import org.jetbrains.kotlin.psi.KtPsiFactory

/**
 * Replaces the trust-all array passed to SSLContext.init() with `null`
 * (the platform's default trust managers) and removes the now-unused
 * trust-all local, if the array came from one. Scope: the init() call's
 * second argument and that one local declaration - never the enclosing
 * function or class.
 */
class SafeTrustManagerQuickFixKotlin(
    element: KtCallExpression,
    private val declaration: KtProperty?,
    private val fileName: String,
    private val originalFinding: LineScanResult
) : LocalQuickFixAndIntentionActionOnPsiElement(element) {

    override fun getText(): String = "DualVulnDroid: Use default certificate validation"
    override fun getFamilyName(): String = text
    override fun startInWriteAction(): Boolean = true

    override fun isAvailable(project: Project, file: PsiFile, startElement: PsiElement, endElement: PsiElement): Boolean {
        val call = startElement as? KtCallExpression ?: return false
        return call.isValid && isStillTrustAll(call, declaration)
    }

    override fun invoke(project: Project, file: PsiFile, editor: Editor?, startElement: PsiElement, endElement: PsiElement) {
        val call = startElement as? KtCallExpression ?: return

        if (!isStillTrustAll(call, declaration)) {
            Messages.showWarningDialog(project, "Source changed since analysis. Please re-scan.", "DualVulnDroid")
            return
        }

        try {
            val factory = KtPsiFactory(project)
            call.valueArguments[1].getArgumentExpression()
                ?.replace(factory.createExpression(CertificateFixAnalyzer.DEFAULT_TRUST_MANAGERS_ARGUMENT))
            declaration?.delete()
        } catch (e: Exception) {
            Messages.showWarningDialog(project, "Could not apply fix: ${e.message}", "DualVulnDroid")
            return
        }

        if (file.isPhysical) {
            FixVerificationRunner.runAsync(project, file, fileName, originalFinding)
        }
    }

    companion object {
        /**
         * The exact shape the fix rewrites: `x.init(a, b, c)` whose second
         * argument is a trust-all array literal, or a bare name for a local
         * declared in the same block with such an initializer and used
         * nowhere else. Anything else - no fix.
         */
        fun isStillTrustAll(call: KtCallExpression, declaration: KtProperty?): Boolean {
            if (call.calleeExpression?.text != "init") return false
            val args = call.valueArguments
            if (args.size != 3) return false
            val trustArg = args[1].getArgumentExpression() ?: return false
            if (declaration == null) {
                return CertificateFixAnalyzer.isTrustAllArray(trustArg.text, FixLanguage.KOTLIN)
            }
            if (!declaration.isValid || trustArg.text.trim() != declaration.name) return false
            val initializer = declaration.initializer ?: return false
            if (!CertificateFixAnalyzer.isTrustAllArray(initializer.text, FixLanguage.KOTLIN)) return false
            return onlyUse(declaration, call)
        }

        fun findTrustAllDeclaration(call: KtCallExpression): KtProperty? {
            val name = call.valueArguments.getOrNull(1)?.getArgumentExpression()?.text?.trim() ?: return null
            val block = PsiTreeUtil.getParentOfType(call, KtBlockExpression::class.java) ?: return null
            val callIndex = block.statements.indexOfFirst { PsiTreeUtil.isAncestor(it, call, false) }
            if (callIndex <= 0) return null
            return block.statements.subList(0, callIndex).filterIsInstance<KtProperty>().lastOrNull { it.name == name && it.isLocal }
        }

        /** The declared local is referenced exactly once - by this init() call. */
        private fun onlyUse(declaration: KtProperty, call: KtCallExpression): Boolean {
            val block = PsiTreeUtil.getParentOfType(declaration, KtBlockExpression::class.java) ?: return false
            val uses = PsiTreeUtil.findChildrenOfType(block, KtNameReferenceExpression::class.java)
                .filter { it.getReferencedName() == declaration.name }
            return uses.size == 1 && PsiTreeUtil.isAncestor(call, uses[0], false)
        }
    }
}
