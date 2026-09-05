K M IGLAVITHANA
DUAL-VULNERABILITY DETECTION IN ANDROID CODE: REAL-TIME SQL INJECTION AND CERTIFICATE VALIDATION DETECTION
CHAPTER 01 – INTRODUCTION AND RESEARCH PROBLEM

## 1.1 Chapter Overview

This chapter establishes the research problem addressed by DualVulnDroid, an Android security analysis system targeting two recurring weakness classes: SQL Injection (CWE-89) and Improper Certificate Validation (CWE-295). It situates the problem within Android and mobile application security, argues that existing detection approaches leave a specific, evidence-supported gap around the joint, explainable, decision-supported treatment of both classes across a developer workflow and an end-user assessment surface, and derives a research question, aim, and measurable objectives from that gap. It also states the study's significance, scope, and constraints, and outlines how later chapters build toward an evaluated answer. Implementation detail is kept to a minimum here and covered fully in Chapters 4–6.

## 1.2 Problem Context and Background

Android is the dominant mobile operating system, and its applications routinely handle authentication, payments, and personal data, making source-code-level security weaknesses a continuing concern (Android Open Source Project, n.d.). SQL Injection (CWE-89) occurs when externally influenced input reaches a SQL statement without neutralisation, letting an attacker alter the query's logic and read, modify, or delete data it was never meant to expose (MITRE, n.d.-a). Improper Certificate Validation (CWE-295) occurs when TLS/SSL certificate or hostname verification is bypassed or weakened — for example, a `HostnameVerifier` that unconditionally returns true — letting a network-positioned attacker intercept or tamper with traffic the app believes is secure (MITRE, n.d.-b). OWASP's mobile security standard treats network-communication and cryptographic weaknesses as recurring verification domains (OWASP Foundation, n.d.), and Android's network-security-configuration mechanism exists precisely because default certificate handling needs a developer to opt into stricter validation (Android Open Source Project, n.d.).

Both weaknesses follow recognisable but not always obvious coding patterns, and manual review scales poorly across large codebases. Static/data-flow analysis can trace a value from an untrusted source to a sensitive sink at the Android level (Arzt et al., 2014), but such tools address a narrow question and are not, alone, packaged for continuous in-editor use — motivating pairing this evidence with machine-learning classification, since a model can learn patterns difficult to express as fixed rules while data-flow evidence supplies justification a probability score cannot. Classical algorithms (SVM, Random Forest, XGBoost) and deep-learning/Transformer models (LSTM, CodeBERT) have each been applied to vulnerability classification, but no family consistently dominates, and deep-learning gains do not reliably transfer from benchmark to real-world conditions (Chakraborty et al., 2022). A bare label gives a developer little basis to trust a finding, motivating explanation such as SHAP (Lundberg & Lee, 2017) alongside the evidence. An equivalent need exists once an application is published: a prospective user has little accessible way to judge its risk, device compatibility, or alternatives without technical expertise. This combination — dual-CWE coverage, hybrid ML/static evidence, explainability, real-time developer support, and accessible end-user assessment — motivates the research problem below.

## 1.3 Research Problem Statement

**General problem.** Automated Android source-code security analysis remains fragmented: a given tool typically targets one vulnerability class, one form of evidence (a learned model or a static rule), and one audience (usually the developer), rather than treating detection, evidence, explanation, and audience-appropriate presentation as one evaluated system.

**Specific problem.** For CWE-89 and CWE-295, ML classification is rarely benchmarked against classical and deep-learning baselines under one protocol covering both categories, leaving unclear which modelling approach is justified. Static/data-flow evidence, where produced, is not consistently fused with a prediction into one transparent decision that reports its own coverage and reliability rather than forcing a verdict every time. Explanation, where offered, is inconsistently separated from deterministic evidence and rarely reaches the developer inside the editor rather than as a later, separate scan. Once an application exists only as a compiled artefact, consumer-facing tools rarely give a non-technical user an equivalent assessment, device-compatibility check, or safer alternative. This motivates the deficiency addressed here: limited evidence on how a hybrid ML and static/data-flow decision process for CWE-89 and CWE-295 can be integrated, and honestly evaluated, across a real-time developer workflow and a backend-mediated end-user interface within one architecture.

## 1.4 Research Gap

Chapter 2 reviews this in full; the summary argument follows. Static/taint tools such as FlowDroid and TaintDroid provide checkable source-to-sink evidence but address a narrow question and are not packaged for continuous developer use (Arzt et al., 2014). CWE-89 and CWE-295 detection are, with limited exception, evaluated by separate tools and studies — SQL-Injection-focused work is not evaluated against certificate-validation cases and vice versa — so evidence of one pipeline evaluated across both together remains limited. No model family is shown to dominate consistently across datasets and representations, and deep-learning benchmark gains do not reliably transfer to real-world data (Chakraborty et al., 2022), arguing for empirical, multi-model comparison rather than assuming a technique in advance. Explainability methods such as SHAP exist but are applied inconsistently and are not typically kept explicitly separate from independently-verifiable static evidence. Real-time, IDE-integrated, ML-based Android detection has been demonstrated as achievable (Senanayake et al., 2023a), but the closest identified prior system is not documented as also combining static/data-flow evidence, separated explanation, and joint CWE-89/CWE-295 coverage, and none of the reviewed literature extends an equivalent assessment to a companion end-user interface. Support for a dual-CWE, hybrid-evidence, explainable, real-time-and-end-user-facing architecture therefore remains fragmented across separate tools rather than demonstrated as an integrated, evaluated whole — the gap DualVulnDroid addresses.

## 1.5 Research Question(s)

**Main research question.** To what extent can a hybrid approach combining machine-learning classification with static and data-flow evidence detect CWE-89 and CWE-295 in Android source code, and be delivered as explainable, decision-supported feedback through both a real-time IDE plugin and a backend-mediated end-user assessment interface?

**Sub-questions.**
RQ1 — How do classical models (Linear SVM, Random Forest, XGBoost) and supplementary deep-learning/Transformer models (LSTM, CodeBERT) compare when trained and evaluated on the same CWE-89/CWE-295 dataset under an identical protocol?
RQ2 — How can static/data-flow evidence be fused with a model's prediction into a decision process that reports its own automatic-decision coverage and reliability rather than assuming complete, error-free classification?
RQ3 — How effectively can this pipeline be surfaced as real-time, explainable feedback to a developer and as an accessible, evidence-grounded assessment to an end user, and what do automated testing and real-device validation establish about it?

## 1.6 Research Aim

The aim is to design, develop, and evaluate DualVulnDroid: an Android security analysis system that classifies CWE-89 and CWE-295 using a machine-learning pipeline compared against classical and deep-learning baselines, reinforces that classification with independent static/data-flow evidence through a Hybrid Decision Engine, and delivers the resulting explainable findings through a real-time IntelliJ/Android Studio plugin for developers and a backend-mediated Flutter application for end users.

## 1.7 Research Objectives

1. To investigate and critically compare existing static-analysis, machine-learning, and IDE-integrated approaches to CWE-89/CWE-295 detection, establishing the specific gap this research addresses (Chapter 2).
2. To prepare a leakage-checked, labelled dataset and a feature-engineered pipeline, then train and compare Linear SVM, Random Forest, and XGBoost against the supplementary deep-learning models LSTM and CodeBERT under one shared protocol (Chapters 3, 6).
3. To design and integrate a Hybrid Decision Engine fusing the production model's prediction with deterministic static/data-flow evidence and SHAP-based explanation into a single decision, measuring its automatic-decision coverage and reliability rather than assuming it (Chapters 3, 5, 6).
4. To develop a real-time IntelliJ/Android Studio plugin (in-editor annotation, project-wide scanning, narrowly-scoped, re-verified remediation) and a backend-mediated Flutter application (application search, security assessment, compatibility checking, a data-grounded security chatbot) (Chapters 5, 6).
5. To evaluate the system through the automated backend, Kotlin, and Flutter test suites and live validation on a real Android device/emulator, reporting all results — including any item that could not be validated — honestly (Chapters 7, 8).

## 1.8 Research Motivation and Significance

**1.8.1 Academic/research significance.** This research contributes an empirical, shared-protocol comparison of classical, deep-learning, and Transformer-based classifiers on CWE-89 and CWE-295 jointly, rather than assuming which family suits the task in advance, plus a documented Hybrid Decision Engine fusing an ML prediction with independent static/data-flow evidence and a measured coverage/reliability trade-off, while keeping SHAP explanation explicitly distinct from that evidence. This is a contribution in evaluation design and system integration, not in the routine features (authentication, persistence, navigation) that support them.

**1.8.2 Practical/technical significance.** For developers, real-time, explained, in-editor findings with narrowly-scoped, re-verified remediation reduce the effort and risk of manual correction. For application users and owners, a plain-language, backend-mediated assessment, honest compatibility reporting, and a grounded chatbot provide security information not otherwise accessible without specialist tooling. For software teams and researchers, the architecture — a shared detection/evidence pipeline feeding a separate decision layer and separate interfaces — is offered as a documented, evaluated pattern, not a claim that Android security is generally solved.

## 1.9 Proposed Solution / Research Artefact Overview

DualVulnDroid is one backend-centred architecture serving two interfaces. On the developer side, a Kotlin IntelliJ/Android Studio plugin annotates open Java/Kotlin files in real time and offers project-wide scanning; both call a FastAPI backend that runs a 7,610-dimensional hybrid feature pipeline (lexical TF-IDF/count features plus 23 deterministic security/data-flow features) through the production XGBoost classifier, fuses its prediction with independent static/data-flow evidence in a Hybrid Decision Engine, and attaches a live SHAP explanation before returning a finding; a matched, narrow remediation pattern is offered as a Quick Fix that rewrites only the matched expression and re-verifies it with a fresh scan. On the end-user side, a Flutter application calls the same backend to search previously-assessed applications, display their security status, evidence, and explanation, check device compatibility against manifest-derived metadata (reporting "not available" honestly rather than guessing when data is absent), suggest lower-risk alternatives, and provide a security chatbot grounded in the same stored data and rendered verbatim by the client. The Flutter application does not itself analyse source code or an uploaded APK; it is a display client over the shared backend. Its "Upload APK" and "Installed Apps" entries currently show an honest "not available" state, even though the backend separately exposes an APK metadata-ingestion capability used to build the catalogue Search draws on.

## 1.10 Project Scope, Delimitations and Boundaries

| In Scope | Out of Scope |
|---|---|
| Java/Kotlin static/data-flow analysis for CWE-89/CWE-295 via the plugin | Malware detection generally; CWEs beyond CWE-89/CWE-295 |
| SVM/Random Forest/XGBoost/LSTM/CodeBERT comparison under one protocol | LSTM/CodeBERT in production (research comparison only) |
| Production XGBoost classifier with live, per-prediction SHAP | Functioning end-user APK upload or "Installed Apps" (honest placeholders) |
| Hybrid Decision Engine with measured, reported coverage/reliability | A zero-false-negative guarantee; uncertain cases are deferred |
| Real-time annotation, project scan, narrow re-verified Quick Fix | Binary reverse engineering beyond manifest/metadata extraction |
| FastAPI/MySQL backend serving both interfaces | HTTPS/TLS transport (evaluated configuration is HTTP only) |
| Flutter app: search, assessment display, compatibility, alternatives, chatbot | Fabricated device metadata (e.g., RAM/CPU) when unavailable |
| Automated testing and live device/emulator validation | Search "network-error" branch (test-covered, not live-validated) |

As a research delimitation, the study is bounded to two CWE categories, one fixed dataset snapshot, and five compared model families, to keep evaluation feasible within an individual undergraduate project.

## 1.11 Assumptions, Constraints and Resource Requirements

Both interfaces assume network access to a reachable backend; no offline mode is evaluated. The labelled dataset (1,128 cleaned rows after excluding 559 conflicting-label rows from 1,687 raw rows; split 791/169/168) has no application-level identifier, so its split, though leakage-checked for near-duplicates, is not a true cross-application split, constraining generalisation claims. CodeBERT fine-tuning required materially more compute than the classical models, limiting experimentation depth; the project's own artefacts also contain an unreconciled discrepancy between two recorded CodeBERT evaluation runs, so its figures are treated cautiously later. The evaluated backend communicates over HTTP without TLS — a deployment-configuration constraint of the evaluated environment, not evidence about the application logic. Live validation was repeatedly interrupted by host-side Android-emulator instability, traced to a graphics-driver/virtualisation limitation of the evaluation machine rather than the application; validation was completed incrementally, and one interaction (a deliberately induced Search network failure) remains without live-device confirmation, though it is exercised by the automated test suite.

## 1.12 Thesis Organization

The remainder of this thesis comprises seven further chapters. Chapter 2 (Critical Literature Review and Research Gap) reviews Android security, static/data-flow analysis, ML/DL vulnerability detection, and explainability literature to substantiate the gap above. Chapter 3 (Methodology) describes the end-to-end method, from dataset preparation through feature engineering, model comparison, and Decision Engine design, to production integration. Chapter 4 (System Analysis and Requirements) derives requirements for each component from the stated problem. Chapter 5 (System Design and Architecture) presents the resulting system, database, and pipeline architecture. Chapter 6 (System Implementation) describes how the plugin, backend, and Flutter application were built. Chapter 7 (Testing and Evaluation) reports the automated test suites and ML/Decision-Engine evaluation. Chapter 8 (Results and Discussion) synthesises these against the research questions, discusses the production model decision and limitations, and closes the thesis.

## 1.13 Chapter Summary

This chapter has situated DualVulnDroid within the recurring problem of fragmented, single-audience, single-evidence-source approaches to Android CWE-89 and CWE-295 detection, and derived a research gap concerning the joint, explainable, decision-supported treatment of both classes across a developer workflow and an end-user interface. It has stated one main research question with three sub-questions, an overarching aim, and five measurable objectives moving from investigation through comparison and integration to honest evaluation. It has outlined DualVulnDroid's conceptual architecture, the study's scope and explicit boundaries — including capabilities not implemented or not live-validated — and the constraints under which the research was conducted. Chapter 2 now examines the underlying literature in full to substantiate the research gap stated here through a critical, comparative review.

## References (APA 7)

Android Open Source Project. (n.d.). *Network security configuration*. Android Developers. Retrieved 2026, from https://developer.android.com/privacy-and-security/security-config

Arzt, S., Rasthofer, S., Fritz, C., Bodden, E., Bartel, A., Klein, J., Le Traon, Y., Octeau, D., & McDaniel, P. (2014). FlowDroid: Precise context, flow, field, object-sensitive and lifecycle-aware taint analysis for Android apps. In *Proceedings of the 35th ACM SIGPLAN Conference on Programming Language Design and Implementation* (pp. 259–269). ACM. https://doi.org/10.1145/2594291.2594299

Chakraborty, S., Krishna, R., Ding, Y., & Ray, B. (2022). Deep learning based vulnerability detection: Are we there yet? *IEEE Transactions on Software Engineering*, 48(9), 3280–3296. https://doi.org/10.1109/TSE.2021.3087402

Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. In *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (pp. 785–794). ACM. https://doi.org/10.1145/2939672.2939785

Feng, Z., Guo, D., Tang, D., Duan, N., Feng, X., Gong, M., Shou, L., Qin, B., Liu, T., Jiang, D., & Zhou, M. (2020). CodeBERT: A pre-trained model for programming and natural languages. In *Findings of the Association for Computational Linguistics: EMNLP 2020* (pp. 1536–1547). Association for Computational Linguistics.

Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. In *Advances in Neural Information Processing Systems 30* (pp. 4765–4774). Curran Associates.

MITRE. (n.d.-a). *CWE-89: Improper neutralization of special elements used in an SQL command ('SQL Injection')*. Common Weakness Enumeration. Retrieved 2026, from https://cwe.mitre.org/data/definitions/89.html

MITRE. (n.d.-b). *CWE-295: Improper certificate validation*. Common Weakness Enumeration. Retrieved 2026, from https://cwe.mitre.org/data/definitions/295.html

OWASP Foundation. (n.d.). *OWASP Mobile Application Security Verification Standard (MASVS)*. Retrieved 2026, from https://mas.owasp.org/MASVS/

Senanayake, J., Kalutarage, H., Al-Kadri, M. O., Petrovski, A., & Piras, L. (2023a). Android code vulnerabilities early detection using AI-powered ACVED plugin. In *Data and Applications Security and Privacy XXXVII (DBSec 2023)* (pp. 339–357). Springer. https://doi.org/10.1007/978-3-031-37586-6_20
