%%TITLEPAGE%%
DUAL-VULNERABILITY DETECTION IN ANDROID CODE: REAL-TIME SQL INJECTION AND CERTIFICATE VALIDATION DETECTION

Design and Evaluation of a Hybrid Vulnerability Detection Approach for CWE-89 and CWE-295 in Android Code

DualVulnDroid

K M Iglavithana

A thesis submitted in partial fulfilment of the requirements for the degree of BSc (Hons) in Software Engineering

2026
%%ENDTITLEPAGE%%

%%ABSTRACT%%
Android applications continue to ship with recurring, well-documented source-code weaknesses, of which SQL Injection (CWE-89) and Improper Certificate Validation (CWE-295) recur with particular frequency. Existing detection approaches tend to address these two categories separately, rarely fuse machine-learning prediction with deterministic static/data-flow evidence into one measured decision, integrate explainability inconsistently, and, with limited exception, do not extend a comparable, comprehension-appropriate assessment from the developer to the end user of an already-published application. This research asks to what extent a hybrid approach combining machine-learning classification with static and data-flow evidence can detect CWE-89 and CWE-295 in Android source code, and be delivered as explainable, decision-supported feedback through both a real-time IDE plugin and a backend-mediated end-user assessment interface.

Following a Design Science Research approach for artefact development, combined with a controlled experimental methodology for the machine-learning component, DualVulnDroid was designed, implemented, and evaluated. A 7,610-dimensional hybrid feature representation (TF-IDF text features plus 23 deterministic security/data-flow features) was constructed from a leakage-checked, 1,128-row cleaned dataset (split 791/169/168 under a fixed seed), and used to train and compare five models under one identical protocol: Linear SVM, Random Forest, and XGBoost as classical baselines, and LSTM and CodeBERT as supplementary deep-learning/Transformer comparisons. No model dominated every metric: XGBoost, selected as the production classifier, achieved the best macro F1 (0.7874) and lowest false-positive rate; Linear SVM achieved the best false-negative rate and ROC-AUC; CodeBERT achieved the lowest CWE-89 false-negative rate on the project's documented-authoritative evaluation artefact, a result reported alongside an unresolved provenance conflict between competing project artefacts rather than silently settled. A Hybrid Decision Engine fusing the production model's prediction with static/data-flow evidence and SHAP-based explanation was evaluated as a measured coverage/reliability trade-off: its deployed configuration auto-decides 32.74% of cases at a 3.03% false-negative rate, while a higher-coverage alternative (88.69%) was correctly not deployed on evidence of cross-split instability.

The resulting system comprises a real-time IntelliJ/Android Studio plugin, providing in-editor annotation and narrowly-scoped, re-verified remediation, and a backend-mediated Flutter application providing application search, security assessment, device-compatibility checking, and a grounded Security Chat — the Flutter client performs no source-code analysis of its own. System testing separated automated verification (323 backend, 55 Kotlin, and 59 Flutter tests) from live-device validation: 23 of 26 tracked validation items reached a genuine live PASS across a phased validation record culminating in a comprehensive session, with two items — a splash screen and a search network-error state — honestly preserved as not yet validated, alongside a plugin GUI-validation gap that likewise remains open. The evidence gathered demonstrates that a hybrid ML-and-evidence approach can be built, measured, and honestly evaluated as an integrated developer- and end-user-facing system; it does not demonstrate complete, error-free detection, and this thesis does not claim otherwise. Limitations — dataset size and composition, the absence of a true application-level split, an HTTP-only evaluated transport configuration, and the specific unresolved and not-yet-validated items above — are reported explicitly, together with concrete recommendations and a future-work roadmap.
%%ENDABSTRACT%%

%%KEYWORDS%%
Android application security; SQL Injection; CWE-89; Improper Certificate Validation; CWE-295; static and data-flow analysis; machine learning; XGBoost; explainable AI; SHAP; Hybrid Decision Engine; IntelliJ plugin; Flutter; software testing; live validation.
%%ENDKEYWORDS%%

%%ABBREVIATIONS%%
ABI — Application Binary Interface
ACVED — AI-powered Android Code Vulnerabilities Early Detection (plugin)
ANR — Application Not Responding
API — Application Programming Interface
APK — Android Package (Kit)
AVD — Android Virtual Device
CI/CD — Continuous Integration / Continuous Deployment
CRUD — Create, Read, Update, Delete
CWE — Common Weakness Enumeration
DL — Deep Learning
DSR — Design Science Research
F1 — F1-score (harmonic mean of precision and recall)
FNR — False Negative Rate
FPR — False Positive Rate
GNN — Graph Neural Network
GPU — Graphics Processing Unit
HTTP / HTTPS — HyperText Transfer Protocol (Secure)
IDE — Integrated Development Environment
JSON — JavaScript Object Notation
JWT — JSON Web Token
LSTM — Long Short-Term Memory (neural network)
MASTG — OWASP Mobile Application Security Testing Guide
MASVS — OWASP Mobile Application Security Verification Standard
ML — Machine Learning
MITRE — MITRE Corporation (maintainer of the CWE catalogue)
NFR — Non-Functional Requirement
NIST — National Institute of Standards and Technology
NLU — Natural Language Understanding
ORM — Object-Relational Mapping
OWASP — Open Worldwide Application Security Project
PSI — Program Structure Interface (IntelliJ Platform)
REST — Representational State Transfer
ROC-AUC — Receiver Operating Characteristic – Area Under the Curve
SDK — Software Development Kit
SHAP — SHapley Additive exPlanations
SLA — Service-Level Agreement
SQL — Structured Query Language
SSL/TLS — Secure Sockets Layer / Transport Layer Security
UI/UX — User Interface / User Experience
XGBoost — Extreme Gradient Boosting
%%ENDABBREVIATIONS%%
