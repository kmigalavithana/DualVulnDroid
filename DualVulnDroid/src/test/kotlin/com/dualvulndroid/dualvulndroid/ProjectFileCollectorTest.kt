package com.dualvulndroid.dualvulndroid

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * Phase 5A, section 20 (item 8: relative file path handling) and
 * section 6/7 (exclusions, empty/duplicate/oversized filtering).
 */
class ProjectFileCollectorTest {

    private lateinit var projectRoot: File
    private lateinit var sourceRoot: File

    @Before
    fun setUp() {
        projectRoot = Files.createTempDirectory("dualvulndroid-test").toFile()
        sourceRoot = File(projectRoot, "app/src/main/java")
        sourceRoot.mkdirs()
    }

    @After
    fun tearDown() {
        projectRoot.deleteRecursively()
    }

    private fun writeFile(relativeToSourceRoot: String, content: String): File {
        val f = File(sourceRoot, relativeToSourceRoot)
        f.parentFile.mkdirs()
        f.writeText(content)
        return f
    }

    @Test
    fun `produces project-relative forward-slash paths, never absolute paths`() {
        writeFile("com/example/LoginActivity.kt", "class LoginActivity")

        val result = ProjectFileCollector.collect(projectRoot.absolutePath, sourceRoot)

        assertEquals(1, result.files.size)
        val relativePath = result.files[0].relativePath
        assertEquals("app/src/main/java/com/example/LoginActivity.kt", relativePath)
        assertFalse(relativePath.startsWith("/"))
        assertFalse(relativePath.contains(":\\"))
        assertFalse(relativePath.contains(projectRoot.absolutePath))
    }

    @Test
    fun `skips build, generated, and IDE metadata directories`() {
        writeFile("com/example/Real.kt", "class Real")
        File(sourceRoot, "build/generated/Fake.kt").apply { parentFile.mkdirs(); writeText("class Fake") }
        File(sourceRoot, ".idea/Meta.kt").apply { parentFile.mkdirs(); writeText("class Meta") }

        val result = ProjectFileCollector.collect(projectRoot.absolutePath, sourceRoot)

        assertEquals(1, result.files.size)
        assertTrue(result.files[0].relativePath.endsWith("Real.kt"))
    }

    @Test
    fun `skips empty files`() {
        writeFile("Empty.kt", "")
        writeFile("Blank.kt", "   \n  \n")
        writeFile("Real.kt", "class Real")

        val result = ProjectFileCollector.collect(projectRoot.absolutePath, sourceRoot)

        assertEquals(1, result.files.size)
        assertEquals(2, result.skippedEmpty)
    }

    @Test
    fun `skips duplicate content and oversized files`() {
        writeFile("A.kt", "class Same")
        writeFile("B.kt", "class Same") // identical content -> duplicate
        writeFile("Huge.kt", "a".repeat(ProjectFileCollector.MAX_FILE_SIZE_BYTES + 1))

        val result = ProjectFileCollector.collect(projectRoot.absolutePath, sourceRoot)

        assertEquals(1, result.files.size) // only the first of the two identical files
        assertEquals(1, result.skippedDuplicate)
        assertEquals(1, result.skippedOversized)
    }

    @Test
    fun `ignores unsupported file extensions`() {
        writeFile("Readme.md", "# not source")
        writeFile("Real.kt", "class Real")

        val result = ProjectFileCollector.collect(projectRoot.absolutePath, sourceRoot)

        assertEquals(1, result.files.size)
        assertTrue(result.files[0].relativePath.endsWith("Real.kt"))
    }

    @Test
    fun `chunks files into batches no larger than the backend limit`() {
        val files = (1..450).map {
            ProjectFileCollector.CollectedFile("File$it.kt", File("File$it.kt"), "class C$it")
        }
        val batches = ProjectFileCollector.chunk(files, maxPerBatch = 200)

        assertEquals(3, batches.size)
        assertEquals(200, batches[0].size)
        assertEquals(200, batches[1].size)
        assertEquals(50, batches[2].size)
    }
}
