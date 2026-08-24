package com.dualvulndroid.dualvulndroid

import com.intellij.codeInsight.intention.IntentionAction
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.psi.PsiFile
import com.intellij.util.IncorrectOperationException

/**
 * Phase 5B, section 7: the real, safe way to reach the full detail view
 * from a real-time editor annotation - an IntentionAction (Alt+Enter),
 * which is IntelliJ's standard "more info/actions for this warning"
 * mechanism. This does NOT modify any code (startInWriteAction = false,
 * invoke() only opens the tool window) and is a completely separate,
 * unrelated concern from Quick Fix, which is explicitly out of scope
 * for this phase.
 *
 * Bound to one specific finding at construction time (mirrors how
 * JavaSQLQuickFix/SQLQuickFix are bound to a specific PSI element) so it
 * never needs to re-derive anything - the finding data is already real
 * and already computed by the time CodeSentinelAnnotator attaches this.
 */
class ShowFindingDetailsIntention(
    private val fileName: String,
    private val result: LineScanResult
) : IntentionAction {

    override fun getText(): String = "DualVulnDroid: Show finding details"
    override fun getFamilyName(): String = "DualVulnDroid"
    override fun startInWriteAction(): Boolean = false

    override fun isAvailable(project: Project, editor: Editor?, file: PsiFile?): Boolean = true

    @Throws(IncorrectOperationException::class)
    override fun invoke(project: Project, editor: Editor?, file: PsiFile?) {
        MyToolWindow.showFinding(project, result.toDetailView(fileName))
    }
}
