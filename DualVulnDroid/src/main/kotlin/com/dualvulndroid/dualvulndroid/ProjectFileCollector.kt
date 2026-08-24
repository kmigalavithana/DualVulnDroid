package com.dualvulndroid.dualvulndroid

import java.io.File
import java.security.MessageDigest

/**
 * Phase 5A, section 6/7: collects the .java/.kt source files that
 * "Scan Project" should upload, and nothing else - the ML/data-flow
 * analysis itself stays entirely server-side (see APIClient.scanProjectBatch).
 *
 * This class only:
 *  - walks the project's source tree
 *  - excludes build output / generated / dependency / IDE metadata paths
 *  - excludes empty, duplicate, and oversized files
 *  - produces safe, project-relative paths (never absolute local paths)
 */
object ProjectFileCollector {

    private val SUPPORTED_EXTENSIONS = setOf("kt", "java")

    // Path segments that mean "not real, developer-authored source" -
    // matches section 6's exclusion list.
    private val EXCLUDED_PATH_SEGMENTS = setOf(
        "build", ".gradle", "generated", "node_modules", ".idea",
        ".git", "out", "captures", ".cxx", "intermediates"
    )

    // Mirrors backend/app.py's MAX_CODE_SIZE_BYTES (200_000) so obviously
    // oversized files are skipped locally instead of being uploaded just
    // to get a guaranteed per-file 400 back.
    const val MAX_FILE_SIZE_BYTES = 200_000

    data class CollectedFile(
        val relativePath: String,
        val absoluteFile: File,
        val content: String
    )

    data class CollectionResult(
        val files: List<CollectedFile>,
        val skippedEmpty: Int,
        val skippedDuplicate: Int,
        val skippedOversized: Int
    )

    fun collect(projectBasePath: String, sourceRoot: File): CollectionResult {
        val basePath = File(projectBasePath).canonicalFile

        val seenContentHashes = HashSet<String>()
        val files = mutableListOf<CollectedFile>()
        var skippedEmpty = 0
        var skippedDuplicate = 0
        var skippedOversized = 0

        sourceRoot.walkTopDown()
            .onEnter { dir -> EXCLUDED_PATH_SEGMENTS.none { dir.name.equals(it, ignoreCase = true) } }
            .filter { it.isFile && it.extension.lowercase() in SUPPORTED_EXTENSIONS }
            .forEach { file ->
                if (file.length() == 0L) {
                    skippedEmpty++
                    return@forEach
                }
                if (file.length() > MAX_FILE_SIZE_BYTES) {
                    skippedOversized++
                    return@forEach
                }

                val content = try {
                    file.readText()
                } catch (e: Exception) {
                    println("[CodeSentinel] Could not read ${file.path}: ${e.message}")
                    return@forEach
                }

                if (content.isBlank()) {
                    skippedEmpty++
                    return@forEach
                }

                val hash = sha256(content)
                if (!seenContentHashes.add(hash)) {
                    skippedDuplicate++
                    return@forEach
                }

                files.add(
                    CollectedFile(
                        relativePath = relativize(basePath, file),
                        absoluteFile = file,
                        content = content
                    )
                )
            }

        return CollectionResult(files, skippedEmpty, skippedDuplicate, skippedOversized)
    }

    /** Project-relative path with forward slashes, e.g.
     *  "app/src/main/java/com/example/LoginActivity.kt" - never an
     *  absolute filesystem path, per section 6. */
    private fun relativize(basePath: File, file: File): String {
        val rel = basePath.toPath().relativize(file.canonicalFile.toPath())
        return rel.toString().replace(File.separatorChar, '/')
    }

    private fun sha256(text: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    /** Splits a file list into batches no larger than APIClient.MAX_FILES_PER_BATCH. */
    fun chunk(files: List<CollectedFile>, maxPerBatch: Int = APIClient.MAX_FILES_PER_BATCH): List<List<CollectedFile>> =
        files.chunked(maxPerBatch)
}
