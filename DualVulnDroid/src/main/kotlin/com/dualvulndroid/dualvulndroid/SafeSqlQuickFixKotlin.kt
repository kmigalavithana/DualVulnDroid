package com.dualvulndroid.dualvulndroid

import com.intellij.codeInspection.LocalQuickFixAndIntentionActionOnPsiElement
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiFile
import org.jetbrains.kotlin.psi.KtCallExpression
import org.jetbrains.kotlin.psi.KtExpression
import org.jetbrains.kotlin.psi.KtProperty
import org.jetbrains.kotlin.psi.KtPsiFactory
import org.jetbrains.kotlin.psi.KtValueArgument

/**
 * Phase 6: Kotlin counterpart to SafeSqlQuickFixJava - same scope
 * discipline (query-literal expression + args expression only, never a
 * whole function/class), same re-validation before applying.
 */
class SafeSqlQuickFixKotlin(
    element: KtCallExpression,
    private val sink: SqlConcatenationAnalyzer.SqlSink,
    private val declaration: KtProperty?,
    private val match: SqlConcatenationAnalyzer.Match,
    private val fileName: String,
    private val originalFinding: LineScanResult
) : LocalQuickFixAndIntentionActionOnPsiElement(element) {

    override fun getText(): String = "DualVulnDroid: Use parameterized query (${sink.methodName})"
    override fun getFamilyName(): String = text
    override fun startInWriteAction(): Boolean = true

    override fun isAvailable(project: Project, file: PsiFile, startElement: PsiElement, endElement: PsiElement): Boolean {
        val call = startElement as? KtCallExpression ?: return false
        return call.isValid && revalidate(call)
    }

    override fun invoke(
        project: Project,
        file: PsiFile,
        editor: Editor?,
        startElement: PsiElement,
        endElement: PsiElement
    ) {
        val call = startElement as? KtCallExpression ?: return

        if (!revalidate(call)) {
            Messages.showWarningDialog(project, "Source changed since analysis. Please re-scan.", "DualVulnDroid")
            return
        }

        try {
            val factory = KtPsiFactory(project)
            val arguments = call.valueArgumentList?.arguments ?: emptyList()

            if (declaration != null) {
                val newInit: KtExpression = factory.createExpression(match.parameterizedLiteral())
                declaration.initializer?.replace(newInit)
            } else if (arguments.isNotEmpty()) {
                val newQueryArg: KtExpression = factory.createExpression(match.parameterizedLiteral())
                arguments[0].getArgumentExpression()?.replace(newQueryArg)
            }

            val refreshedArgs = call.valueArgumentList?.arguments ?: emptyList()
            val newArgsExpr: KtExpression = factory.createExpression(match.argsArrayExpression(sink))
            when (sink) {
                SqlConcatenationAnalyzer.SqlSink.RAW_QUERY ->
                    if (refreshedArgs.size >= 2) refreshedArgs[1].getArgumentExpression()?.replace(newArgsExpr)
                SqlConcatenationAnalyzer.SqlSink.EXEC_SQL ->
                    call.valueArgumentList?.addArgument(factory.createArgument(newArgsExpr))
            }
        } catch (e: Exception) {
            Messages.showWarningDialog(project, "Could not apply fix: ${e.message}", "DualVulnDroid")
            return
        }

        if (file.isPhysical) {
            FixVerificationRunner.runAsync(project, file, fileName, originalFinding)
        }
    }

    private fun revalidate(call: KtCallExpression): Boolean {
        if (SqlConcatenationAnalyzer.sinkNamed(call.calleeExpression?.text) != sink) return false
        val arguments: List<KtValueArgument> = call.valueArgumentList?.arguments ?: return false
        val argTexts = arguments.map { it.getArgumentExpression()?.text ?: return false }
        if (!SqlConcatenationAnalyzer.argumentsFitSink(sink, argTexts)) return false

        val queryExprText = if (declaration != null) {
            declaration.takeIf { it.isValid }?.initializer?.text ?: return false
        } else {
            argTexts[0]
        }
        val currentMatch = SqlConcatenationAnalyzer.analyzeQueryExpression(queryExprText, FixLanguage.KOTLIN) ?: return false
        return currentMatch.identifier == match.identifier
    }
}
