package com.dualvulndroid.dualvulndroid

import com.intellij.codeInspection.LocalQuickFixAndIntentionActionOnPsiElement
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiElementFactory
import com.intellij.psi.PsiExpression
import com.intellij.psi.PsiFile
import com.intellij.psi.PsiLocalVariable
import com.intellij.psi.PsiMethodCallExpression

/**
 * Phase 6: SAFE, targeted replacement of ONLY
 *   - the query-string initializer expression (if a separate
 *     `String query = "..." + x;` declaration exists), and
 *   - the rawQuery() call's arguments
 * Unlike the old (never-connected) JavaSQLQuickFix, this class never
 * touches a PsiMethod, PsiClass, or anything above expression scope -
 * see SqlFixModel.kt's FixProposal, which has no field capable of
 * representing a whole method body.
 *
 * Bound at construction to the SPECIFIC rawQuery() call this finding was
 * about (the `element` passed to the superclass) - the same "bind to a
 * real element up front" pattern the old fix used, just correctly scoped.
 */
class SafeSqlQuickFixJava(
    element: PsiMethodCallExpression,
    private val declaration: PsiLocalVariable?,
    private val match: SqlConcatenationAnalyzer.Match,
    private val fileName: String,
    private val originalFinding: LineScanResult
) : LocalQuickFixAndIntentionActionOnPsiElement(element) {

    override fun getText(): String = "DualVulnDroid: Use parameterized query (rawQuery)"
    override fun getFamilyName(): String = text
    override fun startInWriteAction(): Boolean = true

    override fun isAvailable(project: Project, file: PsiFile, startElement: PsiElement, endElement: PsiElement): Boolean {
        val call = startElement as? PsiMethodCallExpression ?: return false
        return call.isValid && revalidate(call)
    }

    override fun invoke(
        project: Project,
        file: PsiFile,
        editor: Editor?,
        startElement: PsiElement,
        endElement: PsiElement
    ) {
        val call = startElement as? PsiMethodCallExpression ?: return

        // Section 9: re-verify the exact pattern still matches THIS
        // element right now - never trust the finding that triggered
        // this fix if the source has moved on since then.
        if (!revalidate(call)) {
            Messages.showWarningDialog(project, "Source changed since analysis. Please re-scan.", "DualVulnDroid")
            return
        }

        try {
            val factory = PsiElementFactory.getInstance(project)
            val args = call.argumentList.expressions

            if (declaration != null) {
                val newInit = factory.createExpressionFromText(match.parameterizedLiteral(), declaration)
                declaration.initializer?.replace(newInit)
            } else if (args.isNotEmpty()) {
                val newQueryArg = factory.createExpressionFromText(match.parameterizedLiteral(), call)
                args[0].replace(newQueryArg)
            }

            // Re-fetch args: the declaration branch doesn't change the
            // call's own arg list, but re-reading is cheap and avoids
            // relying on a stale reference after any replace() above.
            val refreshedArgs = call.argumentList.expressions
            if (refreshedArgs.size >= 2) {
                val newArgsExpr: PsiExpression = factory.createExpressionFromText(match.argsArrayExpression(), call)
                refreshedArgs[1].replace(newArgsExpr)
            }
        } catch (e: Exception) {
            Messages.showWarningDialog(project, "Could not apply fix: ${e.message}", "DualVulnDroid")
            return
        }

        // Never fire a real backend re-scan while IntelliJ is only
        // generating a hover preview (which runs invoke() against a
        // non-physical copy of the file).
        if (file.isPhysical) {
            FixVerificationRunner.runAsync(project, file, fileName, originalFinding)
        }
    }

    private fun revalidate(call: PsiMethodCallExpression): Boolean {
        if (!SqlConcatenationAnalyzer.isSupportedSink(call.text)) return false
        val args = call.argumentList.expressions
        if (args.size < 2) return false

        val queryExprText = if (declaration != null) {
            declaration.takeIf { it.isValid }?.initializer?.text ?: return false
        } else {
            args[0].text
        }
        val currentMatch = SqlConcatenationAnalyzer.analyzeQueryExpression(queryExprText, FixLanguage.JAVA) ?: return false
        if (currentMatch.identifier != match.identifier) return false

        return SqlConcatenationAnalyzer.isSecondArgumentReplaceable(args[1].text)
    }
}
