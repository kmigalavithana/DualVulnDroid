package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.project.Project
import com.google.gson.Gson
import java.io.File

/**
 * Phase 6, section 16: local-only remediation log for later research
 * evaluation. Deliberately metadata-only (see RemediationLogEntry) -
 * never writes source code, file paths, or anything sent externally.
 * Appended as JSON Lines to a file inside the project so it survives
 * IDE restarts but never leaves the developer's machine.
 */
object RemediationLog {

    private val gson = Gson()

    private fun logFile(project: Project): File? {
        val basePath = project.basePath ?: return null
        val dir = File(basePath, ".dualvulndroid")
        if (!dir.exists() && !dir.mkdirs()) return null
        return File(dir, "remediation_log.jsonl")
    }

    fun record(project: Project, entry: RemediationLogEntry) {
        try {
            val file = logFile(project) ?: return
            file.appendText(gson.toJson(entry) + "\n")
        } catch (e: Exception) {
            println("[DualVulnDroid] Could not write remediation log: ${e.message}")
        }
    }
}
