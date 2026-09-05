# Dual-vulnerability Detection in Android Code: Real-time SQL Injection and Certificate Validation Detection

**Anonymous Author(s)**
*Affiliation and contact details withheld for double-blind review*

## Abstract

Android applications remain frequently exposed to SQL Injection (CWE-89) and improper certificate validation (CWE-295), two developer-introduced weaknesses that existing tooling tends to address in isolation: static/data-flow analyzers offer checkable evidence but rarely integrate a learned prediction or real-time IDE feedback, while machine-learning classifiers generalize across code patterns but seldom expose deterministic evidence or a measured automatic-decision coverage. This paper presents DualVulnDroid, a hybrid detection system that fuses a production XGBoost classifier over a 7,610-dimensional text-and-security feature representation with deterministic static/data-flow and certificate-validation evidence inside a three-state Hybrid Decision Engine (VULNERABLE / SAFE / SUSPICIOUS_REVIEW), explained per-prediction with SHAP and delivered through a real-time IntelliJ/Android Studio plugin and a backend-mediated Flutter end-user client. Five classifiers (Linear SVM, Random Forest, XGBoost, LSTM, CodeBERT) were compared under one frozen, leakage-checked, group-aware split (791/169/168 rows, seed 42) of a cleaned 1,128-row labelled dataset. XGBoost obtained the best macro-F1 (0.7874) and lowest false-positive rate (0.1467); no single model dominated every metric. The deployed Decision Engine configuration auto-decides 32.74% of test cases at a 3.03% false-negative rate and 94.12% precision, deliberately trading coverage for reliability after a higher-coverage candidate showed cross-seed instability. Live mobile validation reached 23 of 26 tracked items passing with zero failures, though two items and human-observed IDE validation remain outstanding. These results indicate that fusing learned and deterministic evidence can yield conservative, interpretable, decision-oriented vulnerability detection, while exposing open questions around generalisation, model provenance, and transport security.

**Keywords—** Android Security; Vulnerability Detection; CWE-89; CWE-295; Explainable Machine Learning

## I. Introduction

Android's per-application sandbox and permission model do not, by themselves, prevent an application from misusing the platform's own security primitives [1]. Two developer-introduced weaknesses recur across empirical studies of real Android software: SQL Injection (CWE-89), arising when untrusted input reaches a SQL command without neutralisation [2], and improper certificate validation (CWE-295), arising when TLS/SSL verification logic is overridden or disabled [3]. Large-scale studies have found vulnerable certificate-validation code across a substantial share of sampled applications [4], and standards bodies identify network-communication and platform-interaction correctness as distinct, independently verifiable risk categories rather than a single generic security property [5], [6], [7].

Existing detection approaches address these problems from largely separate directions. Static and data-flow analyzers such as FlowDroid and SSLINT provide an explicit, checkable trace from source to sink but are narrow in scope, are not integrated into a live editing workflow, and do not combine their evidence with a learned prediction [8], [9]. Classical and deep-learning classifiers generalise across code patterns without a maintained signature set, but published Android-focused studies typically report aggregate, cross-CWE accuracy rather than an isolated per-vulnerability breakdown [10], and deep-learning gains established on curated benchmarks have been shown not to transfer reliably to more realistic data [11].

The literature indicates limited integration rather than an absence of individual capability: static/data-flow analysis, machine-learning classification, explainability, IDE tooling, and end-user security communication are each independently demonstrated, but existing approaches remain fragmented across these dimensions. Only one closely related system, ACVED, reports real-time, IDE-integrated ML detection for Android, and its published description does not report a separately surfaced data-flow trace, a model-level explanation, or an extension of the same evidence to an end user [12]. No reviewed study treats CWE-89 and CWE-295 jointly, fuses learned and deterministic evidence into one measured decision, and extends an equivalent assessment to a non-technical end user.

This paper presents DualVulnDroid, a hybrid Android vulnerability-detection system that fuses a machine-learning prediction with deterministic static/data-flow and certificate-validation evidence inside a Hybrid Decision Engine, explains its own decisions with SHAP, and delivers the result through a real-time IntelliJ/Android Studio plugin for developers and a backend-mediated Flutter client for end users.

This work investigates to what extent such a hybrid approach can detect CWE-89 and CWE-295 and deliver that detection as explainable, decision-supported feedback to both audiences. Its contributions are: (1) a shared-protocol, per-CWE comparison of five classifier families for this joint detection task; (2) a Hybrid Decision Engine whose automatic-decision coverage and reliability are measured, rather than assumed, as an explicit trade-off; and (3) an integrated system delivering this detection in real time to a developer and, through a backend-mediated interface, to an end user.

## II. Related Work and Research Gap

**A. Android and CWE-Specific Static/Data-Flow Analysis.** Platform and standards guidance frames Android security as a per-application, source-code-level concern rather than a purely platform-level one [1], [5], [6], [7]. For CWE-89, Halfond et al.'s classification and Livshits and Lam's points-to-based checker establish that no single technique covers the full attack surface [13], [14]; ConsiDroid pairs static analysis with concolic execution on a small Android sample [15]. For CWE-295, Fahl et al.'s large-scale study establishes real-world prevalence, and SSLINT provides scalable, signature-based static detection [4], [9]. FlowDroid provides general, technique-specific taint-flow tracking rather than a CWE-level verdict [8]. Across this theme, no study reports both a source-to-sink evidentiary trace and an isolated per-CWE false-negative rate, and none is IDE-integrated.

**B. Machine Learning, Deep Learning, and Code Representation Models.** Classical classifiers — SVM [16], Random Forest [17], XGBoost [18] — trade explicit reasoning for pattern generalisation; the Android-focused LVDAndro/ensemble line of work reports strong aggregate, cross-CWE accuracy without isolated CWE-89/CWE-295 breakdowns [10]. Graph-based deep learning (Devign, IVDetect) encodes structural information directly into the model [19], [20], but Chakraborty et al.'s empirical study found several published deep-learning detectors lose more than half their benchmark performance on more realistic, less-curated data [11] — a caution this work treats as motivation for controlled comparison rather than assumed superiority. Pretrained Transformers such as CodeBERT reduce labelled-data requirements through large-scale pretraining [21] but are evaluated on general code-understanding benchmarks, not on CWE-89/CWE-295 Android code specifically.

**C. Explainability and Decision Support.** SHAP provides a model-agnostic, per-prediction attribution framework [22]; IVDetect builds interpretability directly into one specific architecture [20]. Neither method independently verifies that a prediction is correct. Shen and Chen's survey finds automated remediation consistently validation-gated rather than autonomous [23], and no reviewed decision process reports its own automatic-decision coverage as a measured property separate from raw detection accuracy.

**D. Developer Tooling and End-User Security Communication.** ACVED is the closest identified real-time, IDE-integrated Android ML detector, but its published description does not report a separately surfaced evidence trace, an explanation mechanism, or a remediation feature [12]. Separately, usable-security studies find that most users do not attend to, or benefit from, existing permission-based security signals [24], [25], and no reviewed detection study extends a source-code-level finding to a comprehension-appropriate end-user interface.

Taken together, this literature indicates limited integration rather than an absence of individual capability. Static/data-flow analysis, ML/DL/Transformer classification, explainability, and end-user security communication are each independently demonstrated, but their combination — joint CWE-89/CWE-295 coverage, fused learned-plus-deterministic evidence, measured decision coverage, and delivery to both a developer and an end user from one pipeline — remains comparatively underexplored in the literature reviewed here. This is the gap DualVulnDroid is positioned to address.

## III. Research Methodology and Proposed Approach

This research combines Design Science Research [26] for the artefact's design, construction, and evaluation with a controlled, single-protocol experimental comparison [27] for its machine-learning component, so that a performance difference between models can be attributed to the model itself rather than to an uncontrolled difference in data or procedure.

**Dataset.** The raw labelled dataset contains 1,687 Android code rows across four labels (CWE-89 vulnerable/safe, CWE-295 vulnerable/safe). Rows whose normalised code text matched another row's template but carried a conflicting label were excluded as annotation noise (559 rows), leaving 1,128 clean rows. This clean set was split 791/169/168 (train/validation/test) using a fixed random seed of 42, grouped by normalised code template so that no template appears in more than one subset; group-key and exact-text overlap checks confirmed zero leakage [28]. The dataset carries no application/project identifier, so this is a template-level, not a true application-level, split — a limitation returned to in Section V.

**Feature representation.** A shared 7,610-dimensional feature vector combines 7,587 text-derived dimensions (word- and character-level TF-IDF plus a count vectorizer, all fitted on the training split only) with 23 deterministic security- and data-flow-derived indicators (e.g., a traced SQL source-to-sink relationship, parameterised-query use, `HostnameVerifier`/`TrustManager` patterns, and WebView SSL-error-handling behaviour).

**Models and protocol.** Three classical models (Linear SVM, Random Forest, XGBoost) were hyperparameter-tuned by cross-validation on the training split only; XGBoost used validation-based early stopping. An LSTM was trained from scratch with a code-aware tokenizer, and CodeBERT was fine-tuned from `microsoft/codebert-base`; both used the identical frozen split, consulting the test split exactly once. All five models were scored with accuracy, macro/binary F1, ROC-AUC, and per-CWE false-negative and overall false-positive rates, with FNR weighted more heavily in interpretation because a missed vulnerability is judged more consequential than a false alarm in this domain.

**Decision Engine evaluation.** The Hybrid Decision Engine combines the signed, probability-scaled XGBoost prediction with weighted static/data-flow, certificate-validation, and keyword-corroboration evidence into one score, compared against validation-calibrated thresholds to output VULNERABLE, SAFE, or SUSPICIOUS_REVIEW. Its evaluation reports coverage (the proportion of test cases resolved automatically) alongside the reliability (FNR/precision) of exactly those auto-decided cases. A second, higher-coverage threshold configuration was additionally re-evaluated across five independent data re-splits (seeds 7, 21, 42, 84, 123) to test its robustness rather than assume it.

## IV. System / Model Design and Implementation

Fig. 1 shows DualVulnDroid's overall architecture. Two client surfaces — an IntelliJ/Android Studio plugin for developers and a Flutter application for end users — submit requests to a shared FastAPI backend, which runs the hybrid feature pipeline and production XGBoost model, computes SHAP explanations and the Hybrid Decision Engine's verdict, and persists assessments in a ten-table MySQL database. Both clients consume the same detection pipeline; neither performs its own source-code vulnerability classification.

**Hybrid Decision Engine.** Fig. 2 shows how the engine fuses evidence into a single score. The ML prediction is signed by predicted class and scaled by its own probability (weight ×1.0). SQL data-flow evidence contributes +2.0 for a traced source-to-sink finding, +1.2 for unparameterised string concatenation, and −1.5 when all SQL sinks are confirmed parameterised. Certificate evidence contributes +2.0 / +0.6 / −1.5 for a vulnerable / suspicious / safe classification, and a static keyword-rule corroboration contributes +0.4. The resulting `evidence_score` is compared against two validation-calibrated thresholds to output VULNERABLE, SAFE, or SUSPICIOUS_REVIEW — deferring cases the evidence does not resolve confidently rather than forcing a verdict. This directly operationalises an "evidence, not just prediction" design principle: a genuinely traced, structural data-flow finding is weighted more heavily than an average-confidence ML score alone.

**Developer plugin.** The plugin registers a project-wide scanning tool window and two real-time external annotators (Kotlin/Java source; Android manifest and network-security-configuration XML), submitting the current file to the backend asynchronously and attaching a severity-labelled annotation carrying SHAP contributions and separately-labelled deterministic evidence for findings the Decision Engine reports vulnerable. A Quick Fix offers narrowly-scoped, re-verified remediation only for a small set of confidently-matched, safe rewrite patterns, rather than a general repair capability.

**End-user client.** The Flutter application is a backend-mediated presentation and decision-support client, not an independent detector: every risk level, finding, and explanation it displays originates from a backend response. It provides authentication, application search, a stored security assessment with risk level and evidence, a device-compatibility check comparing a device profile against extracted manifest metadata, and a data-grounded Security Chat that renders the backend's reference-text replies verbatim. Its "Upload APK" and "Installed Apps" entries deliberately present an honest "not available in this version" state rather than a non-functional flow, even though the backend separately exposes an APK metadata-ingestion endpoint used to build the searchable catalogue that Search draws on.

**Explainability.** Per-prediction SHAP values are computed with a `TreeExplainer` against the production XGBoost model at inference time and are kept structurally and terminologically distinct from the deterministic static/data-flow evidence throughout the plugin and backend, rather than merged into one undifferentiated explanation.

**Implementation notes.** The production classifier is XGBoost alone; the SVM, Random Forest, LSTM, and CodeBERT results are retained strictly as research-comparison evidence (Section V) and are not loaded in production. Measured end-to-end inference latency for the full `predict_code()` pipeline was approximately 70.03 ms on a first-run/cold session and 39.82 ms on a warm process, both on the development machine used for this research; these are development-host measurements, not a production service-level guarantee, and the two sessions are not directly comparable. The verified deployment communicates over plain HTTP rather than HTTPS/TLS between both clients and the backend, a limitation discussed in Section V.

## V. Results and Discussion

**A. Comparison with Representative Existing Approaches.** Table I positions DualVulnDroid against representative systems from Section II. No prior reviewed system combines joint CWE-89/CWE-295 coverage, fused ML-plus-static/data-flow evidence, explainability, real-time IDE delivery, and end-user support in one row.

**TABLE I. COMPARISON OF REPRESENTATIVE EXISTING APPROACHES**

| Approach | CWE-89 | CWE-295 | Evidence Type | Explainable | Real-Time IDE | End-User |
|---|---|---|---|---|---|---|
| FlowDroid [8] | No | No | Static/data-flow | No | No | No |
| SSLINT [9] | No | Yes | Static, signature-based | No | No | No |
| LVDAndro ensemble [10] | Yes (aggr.) | Yes (aggr.) | ML (classical) | No | No | No |
| ACVED plugin [12] | Yes (aggr.) | Yes (aggr.) | ML (classical) | Not reported | Yes | No |
| CodeBERT [21] | No | No | Transformer | No | No | No |
| **DualVulnDroid (this work)** | **Yes** | **Yes** | **ML + static/data-flow** | **Yes (SHAP)** | **Yes** | **Yes** |

**B. Model Comparison.** Table II reports the five compared models under the identical frozen protocol. XGBoost achieved the best macro-F1 (0.7874), the lowest overall false-positive rate (0.1467), and the best CWE-89 F1 (0.7931); Linear SVM achieved the best CWE-295 F1 (0.8525) and the best overall FNR (0.1828); the LSTM had the lowest macro-F1 of all five models and the weakest CWE-89 FNR (41.4%), consistent with the literature's caution against assuming deep-learning superiority without controlled comparison. Fig. 3 visualises macro-F1 against FNR for all five models. No model dominated every metric — the finding this comparison supports is that model selection here is a multi-criterion decision, not a single-metric one.

CodeBERT's result requires a specific provenance caveat. The project's `codebert/` artefact reports CWE-89/CWE-295 F1 of 0.7813/0.8246 and is documented as the authoritative run following an internal verification procedure; two further artefacts from an identical nominal configuration, run on different hardware, report materially different figures (CWE-89 F1 ≈ 0.6047, CWE-295 F1 ≈ 0.9120). This paper reports the authoritative-artefact figures in Table II but states explicitly that the verification procedure underlying that resolution was not independently reproduced in this study; CodeBERT is not presented here as the best model overall, only as competitive on CWE-89 recall.

**TABLE II. MODEL COMPARISON RESULTS (FROZEN 168-ROW TEST SET)**

| Model | Macro F1 | CWE-89 F1 | CWE-295 F1 | FNR | FPR |
|---|---|---|---|---|---|
| Linear SVM | 0.7789 | 0.7742 | **0.8525** | **0.1828** | 0.2000 |
| Random Forest | 0.7519 | 0.7541 | 0.8205 | 0.2366 | 0.2133 |
| **XGBoost** | **0.7874** | **0.7931** | 0.8000 | 0.2581 | **0.1467** |
| LSTM | 0.7448 | 0.6415 | 0.8500 | 0.2688 | 0.1600 |
| CodeBERT † | 0.7780 | 0.7813 | 0.8246 | 0.2258 | 0.1733 |

† Authoritative project artefact; a documented, unresolved provenance conflict with two other artefacts is discussed in the text.

**C. Hybrid Decision Engine.** Table III summarises the deployed and alternative Decision Engine configurations. The deployed configuration auto-decides 32.74% of test cases at a 3.03% false-negative rate and 94.12% precision among auto-decided cases, deferring the remaining 67.26% to manual review. A higher-coverage "Balanced" candidate raised coverage to 88.69% but at a substantially higher 20.24% FNR; re-evaluating its threshold-selection procedure across five independent re-splits (seeds 7, 21, 42, 84, 123) produced coverage ranging from 88.69% to 99.42% and FNR from approximately 5.7% to 21.8%, with the selected safe threshold changing sign between seeds — direct evidence of instability, and the specific reason the Balanced candidate was not deployed. Threshold selection is therefore treated as a coverage/reliability policy trade-off rather than a single optimisation target: the deployed configuration deliberately favours reliability over automatic throughput.

**TABLE III. HYBRID DECISION ENGINE CONFIGURATIONS**

| Configuration | Coverage | Auto-Decided FNR | Precision |
|---|---|---|---|
| Deployed (production) | 32.74% | 3.03% | 94.12% |
| Balanced (research candidate, not deployed) | 88.69% | 20.24% | 88.16% |

**D. Live System Validation.** Of 26 tracked mobile validation rows, 23 reached a genuine live PASS, zero FAIL, zero PARTIAL; two remain NOT VALIDATED (the Splash screen, covered only by automated tests, and Search's network-error state, blocked once by an unrelated emulator failure and not re-attempted); one item — APK upload from the Flutter UI — is Not Applicable by design, since the mobile interface intentionally presents a "not available" state rather than an upload flow. Phase 33, the most comprehensive live session, ran stably for approximately 1h45m and produced 20 new current live-PASS items across 44 screenshots with zero failures, recovering from a Phase 32 session-ending `system_server` uninterruptible-kernel-state failure attributed to host graphics-driver instability rather than an application defect, on the basis of consistently healthy RAM/CPU during the failure and fully stable sessions on the identical AVD configuration. Human-observed, on-screen validation of the IDE plugin's real-time annotation, Quick Fix, and project scan remains outstanding; only headless integration-test coverage exists for these components.

**E. Discussion.** These results support the claim that fusing an ML prediction with deterministic evidence produces a measurably more conservative, higher-precision automatic decision (94.12% precision at 3.03% FNR) than the raw classifier's own aggregate figures on the cases it resolves, at the cost of resolving only about a third of cases automatically. They do not support a claim of complete or generalisable detection: false-negative rates across models and CWE categories range from roughly 14% to 41%, the dataset's split is template- rather than application-level, and the CodeBERT provenance conflict and Decision Engine threshold instability remain open. Measured inference latency stayed under 100 ms in both sessions measured, but these are development-machine figures, not a production service-level guarantee, and the deployed system currently communicates over HTTP rather than HTTPS.

## VI. Conclusion and Future Work

This paper presented DualVulnDroid, a hybrid Android vulnerability-detection system that fuses a production XGBoost classifier with deterministic static/data-flow and certificate-validation evidence inside a three-state Hybrid Decision Engine, explains its decisions per-prediction with SHAP, and delivers findings through a real-time IDE plugin and a backend-mediated end-user client. Under one frozen, leakage-checked protocol, five classifiers were compared with no universal winner; XGBoost achieved the best macro-F1 (0.7874) and lowest FPR (0.1467). The deployed Decision Engine auto-decides 32.74% of cases at 3.03% FNR and 94.12% precision, deliberately favouring reliability over coverage after a higher-coverage candidate showed cross-seed instability, and live mobile validation reached 23 of 26 tracked items with zero failures. These results support the claim that hybrid, evidence-fused detection can provide conservative, interpretable, decision-oriented feedback for CWE-89 and CWE-295, but not that detection is complete: dataset generalisation, an unresolved CodeBERT provenance conflict, Decision Engine threshold instability, absent human-observed IDE validation, two unvalidated mobile items, and HTTP-only transport all remain open limitations. Future work should pursue a genuine application-level dataset split, independently reproduce the CodeBERT verification procedure, recalibrate Decision Engine thresholds on a larger validation set, conduct a human-observed IDE validation session, and migrate the deployment to HTTPS/TLS.

## References

[1] Android Developers, "Security checklist," Android Open Source Project. [Online]. Available: https://developer.android.com/topic/security/best-practices

[2] MITRE, "CWE-89: Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')," Common Weakness Enumeration. [Online]. Available: https://cwe.mitre.org/data/definitions/89.html

[3] MITRE, "CWE-295: Improper Certificate Validation," Common Weakness Enumeration. [Online]. Available: https://cwe.mitre.org/data/definitions/295.html

[4] S. Fahl, M. Harbach, T. Muders, L. Baumgärtner, B. Freisleben, and M. Smith, "Why Eve and Mallory love Android: An analysis of Android SSL (in)security," in *Proc. 2012 ACM Conf. Computer and Communications Security*, Raleigh, NC, USA, 2012, pp. 50–61.

[5] OWASP Foundation, "OWASP Mobile Application Security Verification Standard (MASVS)." [Online]. Available: https://mas.owasp.org/MASVS/

[6] OWASP Foundation, "OWASP Mobile Application Security Testing Guide (MASTG)." [Online]. Available: https://mas.owasp.org/MASTG/

[7] M. Ogata, J. Franklin, J. Voas, V. Sritapan, and S. Quirolgico, "Vetting the Security of Mobile Applications," National Institute of Standards and Technology, Gaithersburg, MD, USA, NIST Special Publication 800-163 Rev. 1, 2019.

[8] S. Arzt, S. Rasthofer, C. Fritz, E. Bodden, A. Bartel, J. Klein, Y. Le Traon, D. Octeau, and P. McDaniel, "FlowDroid: Precise context, flow, field, object-sensitive and lifecycle-aware taint analysis for Android apps," in *Proc. 35th ACM SIGPLAN Conf. Programming Language Design and Implementation*, Edinburgh, UK, 2014, pp. 259–269.

[9] Y. He, V. Rastogi, V. N. Venkatakrishnan, C. Xiong, R. Yang, and Z. Zhang, "Vetting SSL usage in applications with SSLINT," in *Proc. 2015 IEEE Symp. Security and Privacy*, San Jose, CA, USA, 2015, pp. 519–534.

[10] J. Senanayake, H. Kalutarage, M. O. Al-Kadri, L. Piras, and A. Petrovski, "Labelled vulnerability dataset on Android source code (LVDAndro) to develop AI-based code vulnerability detection models," in *Proc. 20th Int. Conf. Security and Cryptography (SECRYPT 2023)*, 2023, pp. 659–666.

[11] S. Chakraborty, R. Krishna, Y. Ding, and B. Ray, "Deep learning based vulnerability detection: Are we there yet?," *IEEE Trans. Softw. Eng.*, vol. 48, no. 9, pp. 3280–3296, 2022.

[12] J. Senanayake, H. Kalutarage, M. O. Al-Kadri, A. Petrovski, and L. Piras, "Android code vulnerabilities early detection using AI-powered ACVED plugin," in *Data and Applications Security and Privacy XXXVII (DBSec 2023)*, 2023, pp. 339–357.

[13] W. G. J. Halfond, J. Viegas, and A. Orso, "A classification of SQL-injection attacks and countermeasures," in *Proc. IEEE Int. Symp. Secure Software Engineering*, 2006.

[14] V. B. Livshits and M. S. Lam, "Finding security vulnerabilities in Java applications with static analysis," in *Proc. 14th USENIX Security Symp.*, 2005.

[15] M. Ermuth, S. Pape, and U. Rauf, "ConsiDroid: A concolic-based tool for detecting SQL injection vulnerability in Android apps," *arXiv:1811.10448*, 2018.

[16] C. Cortes and V. Vapnik, "Support-vector networks," *Mach. Learn.*, vol. 20, no. 3, pp. 273–297, 1995.

[17] L. Breiman, "Random forests," *Mach. Learn.*, vol. 45, no. 1, pp. 5–32, 2001.

[18] T. Chen and C. Guestrin, "XGBoost: A scalable tree boosting system," in *Proc. 22nd ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining*, 2016, pp. 785–794.

[19] Y. Zhou, S. Liu, J. Siow, X. Du, and Y. Liu, "Devign: Effective vulnerability identification by learning comprehensive program semantics via graph neural networks," in *Advances in Neural Information Processing Systems 32*, 2019.

[20] Y. Li, S. Wang, and T. N. Nguyen, "Vulnerability detection with fine-grained interpretations," in *Proc. 29th ACM Joint Meeting European Software Engineering Conf. and Symp. Foundations of Software Engineering*, 2021, pp. 292–303.

[21] Z. Feng, D. Guo, D. Tang, N. Duan, X. Feng, M. Gong, L. Shou, B. Qin, T. Liu, D. Jiang, and M. Zhou, "CodeBERT: A pre-trained model for programming and natural languages," in *Findings of the Association for Computational Linguistics: EMNLP 2020*, 2020, pp. 1536–1547.

[22] S. M. Lundberg and S.-I. Lee, "A unified approach to interpreting model predictions," in *Advances in Neural Information Processing Systems 30*, 2017, pp. 4765–4774.

[23] Z. Shen and S. Chen, "A survey of automatic software vulnerability detection, program repair, and defect prediction techniques," *Secur. Commun. Netw.*, vol. 2020, Art. no. 8858010, 2020.

[24] A. P. Felt, E. Ha, S. Egelman, A. Haney, E. Chin, and D. Wagner, "Android permissions: User attention, comprehension, and behavior," in *Proc. 8th Symp. Usable Privacy and Security*, 2012, Art. no. 3.

[25] E. Chin, A. P. Felt, V. Sekar, and D. Wagner, "Measuring user confidence in smartphone security and privacy," in *Proc. 8th Symp. Usable Privacy and Security*, 2012, Art. no. 1.

[26] A. R. Hevner, S. T. March, J. Park, and S. Ram, "Design science in information systems research," *MIS Q.*, vol. 28, no. 1, pp. 75–105, 2004.

[27] C. Wohlin, P. Runeson, M. Höst, M. C. Ohlsson, B. Regnell, and A. Wesslén, *Experimentation in Software Engineering*. Berlin, Germany: Springer, 2012.

[28] S. Kaufman, S. Rosset, C. Perlich, and O. Stitelman, "Leakage in data mining: Formulation, detection, and avoidance," *ACM Trans. Knowl. Discov. Data*, vol. 6, no. 4, Art. no. 15, 2012.
