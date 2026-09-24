package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.fileChooser.FileChooser
import com.intellij.openapi.fileChooser.FileChooserDescriptor
import com.intellij.openapi.project.Project
import com.intellij.openapi.project.guessProjectDir
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.ui.JBColor
import com.intellij.ui.components.JBLabel
import com.intellij.util.ui.JBUI
import java.awt.Font
import java.awt.event.ActionEvent
import javax.swing.Action
import javax.swing.BoxLayout
import javax.swing.JComponent
import javax.swing.JPanel

/** Only these source types are ever sent to the backend by "Scan File". */
fun isScannableSourceFile(file: VirtualFile): Boolean {
    val extension = file.extension?.lowercase()
    return !file.isDirectory && (extension == "kt" || extension == "java")
}

enum class CurrentFileStatus { NONE, SUPPORTED, UNSUPPORTED }

enum class ScanFileChoice { SCAN_CURRENT_FILE, CHOOSE_FILE, CANCEL }

/**
 * What the "Scan File" dialog shows about the currently open editor file,
 * and which actions it offers. Kept free of Swing so the button rules are
 * unit-testable without opening a modal:
 *  - supported .kt/.java  -> [Scan Current File] [Choose Another File] [Cancel]
 *  - unsupported file     -> [Choose Another File] [Cancel]
 *  - no file open         -> [Choose File] [Cancel]
 */
data class ScanFilePromptInfo(
    val fileName: String?,
    val relativePath: String?,
    val status: CurrentFileStatus
) {
    val canScanCurrentFile: Boolean get() = status == CurrentFileStatus.SUPPORTED
    val chooseButtonLabel: String
        get() = if (status == CurrentFileStatus.NONE) ScanFileDialog.CHOOSE_FILE_LABEL else ScanFileDialog.CHOOSE_ANOTHER_FILE_LABEL
}

/** Asked every time "Scan File" is clicked, before any scan starts. */
internal class ScanFileDialog(project: Project, private val info: ScanFilePromptInfo) : DialogWrapper(project, true) {

    companion object {
        const val SCAN_CURRENT_EXIT_CODE = NEXT_USER_EXIT_CODE
        const val CHOOSE_FILE_EXIT_CODE = NEXT_USER_EXIT_CODE + 1
        const val SCAN_CURRENT_FILE_LABEL = "Scan Current File"
        const val CHOOSE_FILE_LABEL = "Choose File"
        const val CHOOSE_ANOTHER_FILE_LABEL = "Choose Another File"
        const val WHAT_TO_SCAN_PROMPT = "What do you want to scan?"
    }

    init {
        title = "Scan File"
        init()
    }

    override fun createCenterPanel(): JComponent {
        val secondary = JBColor.namedColor("Label.infoForeground", JBColor.GRAY)
        return JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            border = JBUI.Borders.empty(4, 4, 8, 4)
            if (info.status == CurrentFileStatus.NONE) {
                add(JBLabel(MyToolWindow.NO_FILE_OPEN_MESSAGE))
            } else {
                add(JBLabel("Current open file:"))
                add(JBLabel(info.fileName ?: "").apply { font = font.deriveFont(Font.BOLD) })
                if (!info.relativePath.isNullOrEmpty()) add(JBLabel(info.relativePath).apply { foreground = secondary })
                add(JBLabel(" "))
                add(JBLabel(if (info.canScanCurrentFile) WHAT_TO_SCAN_PROMPT else MyToolWindow.UNSUPPORTED_FILE_MESSAGE))
            }
        }
    }

    override fun createActions(): Array<Action> {
        val actions = mutableListOf<Action>()
        if (info.canScanCurrentFile) {
            actions += object : DialogWrapperAction(SCAN_CURRENT_FILE_LABEL) {
                init { putValue(DEFAULT_ACTION, true) }
                override fun doAction(e: ActionEvent?) = close(SCAN_CURRENT_EXIT_CODE)
            }
        }
        actions += object : DialogWrapperAction(info.chooseButtonLabel) {
            init { if (!info.canScanCurrentFile) putValue(DEFAULT_ACTION, true) }
            override fun doAction(e: ActionEvent?) = close(CHOOSE_FILE_EXIT_CODE)
        }
        actions += cancelAction
        return actions.toTypedArray()
    }

    fun choice(): ScanFileChoice = when (exitCode) {
        SCAN_CURRENT_EXIT_CODE -> ScanFileChoice.SCAN_CURRENT_FILE
        CHOOSE_FILE_EXIT_CODE -> ScanFileChoice.CHOOSE_FILE
        else -> ScanFileChoice.CANCEL
    }
}

internal fun showScanFileDialog(project: Project, info: ScanFilePromptInfo): ScanFileChoice {
    val dialog = ScanFileDialog(project, info)
    dialog.show()
    return dialog.choice()
}

/** IntelliJ's native file chooser, limited to .kt/.java files, starting at the project root. */
internal fun chooseSourceFileToScan(project: Project): VirtualFile? {
    val descriptor = FileChooserDescriptor(true, false, false, false, false, false)
        .withTitle("Choose a File to Scan")
        .withDescription("Select a Kotlin (.kt) or Java (.java) file.")
        .withFileFilter { isScannableSourceFile(it) }
    val projectDir = project.guessProjectDir()
    return FileChooser.chooseFile(descriptor, project, projectDir)
}
