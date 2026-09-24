package com.example.securitydemo

// DualVulnDroid screenshot demo.
//
// sql/   - SQL Injection (CWE-89):           UserRepository.kt, LoginActivity.java, NotesDao.kt
// cert/  - Certificate Validation (CWE-295): InsecureHttpsClient.kt, ApiConnection.java, TrustAllManager.kt
// safe/  - the fixed versions, which should show no findings
//
// See README.md for the screenshot checklist.
fun main() {
    println("DualVulnDroid screenshot demo - open the files under sql/, cert/ and safe/.")
}
