package com.dualvulndroid.dualvulndroid

import com.intellij.codeInspection.LocalQuickFixAndIntentionActionOnPsiElement
import com.intellij.psi.PsiDeclarationStatement
import com.intellij.psi.PsiFile
import com.intellij.psi.PsiLocalVariable
import com.intellij.psi.PsiMethodCallExpression
import com.intellij.psi.PsiStatement
import com.intellij.psi.util.PsiTreeUtil
import org.jetbrains.kotlin.psi.KtBlockExpression
import org.jetbrains.kotlin.psi.KtCallExpression
import org.jetbrains.kotlin.psi.KtProperty

/**
 * Phase 6, section 14: the ONLY place that decides whether a SQL finding
 * gets an automatic Quick Fix. Registration happens if and only if this
 * returns non-null - CodeSentinelAnnotator never attaches a fix "just in
 * case". Everything unmatched here falls back to
 * SqlConcatenationAnalyzer.MANUAL_REMEDIATION_MESSAGE in the tooltip.
 */
object SqlFixLocator {

    fun tryBuildFix(file: PsiFile, result: LineScanResult, fileName: String): LocalQuickFixAndIntentionActionOnPsiElement? {
        if (result.vulnerabilityType != "SQL Injection") return null
        val isKotlin = file.language.id.equals("kotlin", ignoreCase = true)
        val language = if (isKotlin) FixLanguage.KOTLIN else FixLanguage.JAVA

        return if (isKotlin) {
            buildKotlinFix(file, result, fileName, language)
        } else {
            buildJavaFix(file, result, fileName, language)
        }
    }

    // ---- Java ----

    private fun buildJavaFix(file: PsiFile, result: LineScanResult, fileName: String, language: FixLanguage): SafeSqlQuickFixJava? {
        val call = findJavaRawQueryCallInRange(file, result.startOffset, result.endOffset) ?: return null
        if (!SqlConcatenationAnalyzer.isSupportedSink(call.text)) return null

        val args = call.argumentList.expressions
        if (args.size < 2 || !SqlConcatenationAnalyzer.isSecondArgumentReplaceable(args[1].text)) return null

        SqlConcatenationAnalyzer.analyzeQueryExpression(args[0].text, language)?.let { inlineMatch ->
            return SafeSqlQuickFixJava(call, null, inlineMatch, fileName, result)
        }

        val varName = args[0].text.trim()
        if (!varName.matches(BARE_IDENTIFIER)) return null
        val decl = findPrecedingJavaDeclaration(call, varName) ?: return null
        val declText = decl.initializer?.text ?: return null
        val declMatch = SqlConcatenationAnalyzer.analyzeQueryExpression(declText, language) ?: return null

        return SafeSqlQuickFixJava(call, decl, declMatch, fileName, result)
    }

    private fun findJavaRawQueryCallInRange(file: PsiFile, start: Int, end: Int): PsiMethodCallExpression? {
        return PsiTreeUtil.findChildrenOfType(file, PsiMethodCallExpression::class.java)
            .firstOrNull { it.textRange.startOffset in start until end && it.text.contains("rawQuery") }
    }

    private fun findPrecedingJavaDeclaration(call: PsiMethodCallExpression, varName: String): PsiLocalVariable? {
        var statement = PsiTreeUtil.getParentOfType(call, PsiStatement::class.java) ?: return null
        var prev = statement.prevSibling
        while (prev != null) {
            if (prev is PsiDeclarationStatement) {
                for (declared in prev.declaredElements) {
                    if (declared is PsiLocalVariable && declared.name == varName) return declared
                }
            }
            prev = prev.prevSibling
        }
        return null
    }

    // ---- Kotlin ----

    private fun buildKotlinFix(file: PsiFile, result: LineScanResult, fileName: String, language: FixLanguage): SafeSqlQuickFixKotlin? {
        val call = findKotlinRawQueryCallInRange(file, result.startOffset, result.endOffset) ?: return null
        if (!SqlConcatenationAnalyzer.isSupportedSink(call.text)) return null

        val arguments = call.valueArgumentList?.arguments ?: return null
        if (arguments.size < 2) return null
        val secondArgText = arguments[1].getArgumentExpression()?.text ?: return null
        if (!SqlConcatenationAnalyzer.isSecondArgumentReplaceable(secondArgText)) return null

        val firstArgText = arguments[0].getArgumentExpression()?.text ?: return null
        SqlConcatenationAnalyzer.analyzeQueryExpression(firstArgText, language)?.let { inlineMatch ->
            return SafeSqlQuickFixKotlin(call, null, inlineMatch, fileName, result)
        }

        val varName = firstArgText.trim()
        if (!varName.matches(BARE_IDENTIFIER)) return null
        val decl = findPrecedingKotlinDeclaration(call, varName) ?: return null
        val declText = decl.initializer?.text ?: return null
        val declMatch = SqlConcatenationAnalyzer.analyzeQueryExpression(declText, language) ?: return null

        return SafeSqlQuickFixKotlin(call, decl, declMatch, fileName, result)
    }

    private fun findKotlinRawQueryCallInRange(file: PsiFile, start: Int, end: Int): KtCallExpression? {
        return PsiTreeUtil.findChildrenOfType(file, KtCallExpression::class.java)
            .firstOrNull { it.textRange.startOffset in start until end && it.text.contains("rawQuery") }
    }

    private fun findPrecedingKotlinDeclaration(call: KtCallExpression, varName: String): KtProperty? {
        val block = PsiTreeUtil.getParentOfType(call, KtBlockExpression::class.java) ?: return null
        val statements = block.statements
        val callStatementIndex = statements.indexOfFirst { PsiTreeUtil.isAncestor(it, call, false) }
        if (callStatementIndex <= 0) return null
        for (i in callStatementIndex - 1 downTo 0) {
            val stmt = statements[i]
            if (stmt is KtProperty && stmt.name == varName) return stmt
        }
        return null
    }

    private val BARE_IDENTIFIER = Regex("[A-Za-z_][A-Za-z0-9_]*")
}
