package com.dualvulndroid.dualvulndroid

import com.intellij.lang.annotation.AnnotationHolder
import com.intellij.lang.annotation.ExternalAnnotator
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.util.TextRange
import com.intellij.psi.PsiFile

data class XmlIssue(
    val text: String,
    val message: String,
    val severity: HighlightSeverity,
    val start: Int,
    val end: Int
)

class NetworkSecurityAnnotator :
    ExternalAnnotator<PsiFile, List<XmlIssue>>() {

    override fun collectInformation(file: PsiFile): PsiFile? {

        if (file.fileType.defaultExtension != "xml")
            return null

        return file
    }

    override fun doAnnotate(file: PsiFile?): List<XmlIssue>? {

        if (file == null) return null

        val issues = mutableListOf<XmlIssue>()

        val text = file.text

        fun addIssue(keyword: String, message: String) {

            var index = text.indexOf(keyword)

            while (index >= 0) {

                issues.add(
                    XmlIssue(
                        text = keyword,
                        message = message,
                        severity = HighlightSeverity.WARNING,
                        start = index,
                        end = index + keyword.length
                    )
                )

                index = text.indexOf(
                    keyword,
                    index + keyword.length
                )
            }
        }

        addIssue(
            "android:usesCleartextTraffic=\"true\"",
            "Cleartext HTTP traffic is enabled."
        )

        addIssue(
            "cleartextTrafficPermitted=\"true\"",
            "Cleartext traffic permitted."
        )

        addIssue(
            "<debug-overrides",
            "Debug overrides detected."
        )

        addIssue(
            "src=\"user\"",
            "User certificates are trusted."
        )

        addIssue(
            "@raw/",
            "Custom CA certificate detected."
        )

        return issues
    }

    override fun apply(
        file: PsiFile,
        annotationResult: List<XmlIssue>?,
        holder: AnnotationHolder
    ) {

        if (annotationResult == null) return

        for (issue in annotationResult) {

            holder.newAnnotation(
                issue.severity,
                issue.message
            )
                .range(
                    TextRange(
                        issue.start,
                        issue.end
                    )
                )
                .tooltip(issue.message)
                .create()
        }

    }

}