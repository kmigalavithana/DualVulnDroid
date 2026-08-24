"""
Generates the seven required Chapter 6 implementation figures using
matplotlib. These are deliberately more granular than the Chapter 5
architecture diagrams - each box names an actual function, class, or
API call from the current source, not an architectural layer.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

HERE = Path(__file__).parent
FONT = "DejaVu Sans"
BOX_FACE = "#f2f2f2"
BOX_EDGE = "black"


def draw_flow(steps, out_path, box_width=7.2, box_height=0.62, gap=0.26, fontsize=8.6):
    n = len(steps)
    fig_height = n * (box_height + gap) + 0.6
    fig, ax = plt.subplots(figsize=(8.2, fig_height))
    ax.set_xlim(0, box_width + 1.4)
    ax.set_ylim(0, fig_height)
    ax.axis("off")

    y = fig_height - 0.5
    centers = []
    for label in steps:
        box = FancyBboxPatch(
            (0.7, y - box_height), box_width, box_height,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.3, edgecolor=BOX_EDGE, facecolor=BOX_FACE,
        )
        ax.add_patch(box)
        ax.text(0.7 + box_width / 2, y - box_height / 2, label,
                 ha="center", va="center", fontsize=fontsize, family=FONT, wrap=True)
        centers.append(y - box_height)
        y -= (box_height + gap)

    for i in range(len(centers) - 1):
        arrow = FancyArrowPatch(
            (0.7 + box_width / 2, centers[i]), (0.7 + box_width / 2, centers[i + 1] + box_height),
            arrowstyle="-|>", mutation_scale=14, linewidth=1.2, color="black",
        )
        ax.add_patch(arrow)

    plt.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def main():
    # Figure 6.1 - Backend Prediction Implementation Flow
    draw_flow([
        "predict_code(code, fileName) called (predictor.py)",
        "Guard: empty/whitespace-only code -> early SAFE/none response",
        "If fileName ends .xml -> rule-based XML branch\n(AndroidManifest.xml / network_security_config.xml)",
        "Else: build_feature_matrix() (ml/feature_pipeline.py)",
        "xgb.DMatrix(features); model.predict(dmatrix)",
        "np.argmax(probabilities) -> label via reverse_mapping; LABEL_INFO lookup",
        "explainer.shap_values(dmatrix) -> shapTopFeatures",
        "Rule/SHAP line-localisation loop -> detections[]",
        "analyze_sql_dataflow() / analyze_cert_dataflow() (dataflow.py)",
        "decision_engine.evaluate(label, confidence, sql_flow, cert_flow,\nsink_safety, rule_keyword_hit)",
        "Return dict: prediction, decision, decisionEvidence,\nsecurityFeatures, severity, shapTopFeatures",
    ], HERE / "figure_6_1_backend_prediction_flow.png", fontsize=8.0)

    # Figure 6.2 - XGBoost Feature-to-Prediction Flow
    draw_flow([
        "Raw code string",
        "normalize_code(): lowercase, strip comments, mask\nstring/char/number literals (ml/feature_pipeline.py)",
        "word_vectorizer.transform() / char_vectorizer.transform() /\ncount_vectorizer.transform() (pre-fitted joblib artifacts)",
        "extract_security_feature_vector() -> 23 columns (security_features.py)",
        "hstack() -> 7,610-column scipy sparse feature matrix",
        "xgb.DMatrix(features)",
        "_raw_booster[0:103] sliced model.predict(dmatrix)",
        "probabilities[4] -> argmax = label, max = confidence",
    ], HERE / "figure_6_2_xgboost_feature_to_prediction.png", fontsize=8.4)

    # Figure 6.3 - SHAP + Decision Engine Implementation Flow
    draw_flow([
        "shap.TreeExplainer(model) instantiated once at module load (predictor.py)",
        "explainer.shap_values(dmatrix) computed per request",
        "Top-8 |SHAP value| features -> shapTopFeatures (predicted class)",
        "Per class >5% probability: top-10 positive SHAP features\nmatched against source lines -> detections[]",
        "analyze_sql_dataflow() / analyze_cert_dataflow() /\nsql_sink_safety_summary() (dataflow.py)",
        "decision_engine.compute_evidence(label, confidence, sql_flow,\ncert_flow, sink_safety, rule_keyword_hit) -> evidence_score, reasons",
        "decision_engine.decide(evidence_score,\nVULNERABLE_THRESHOLD, SAFE_THRESHOLD)",
        "VULNERABLE / SAFE / SUSPICIOUS_REVIEW + reasons[]",
    ], HERE / "figure_6_3_shap_decision_engine_flow.png", fontsize=8.3)

    # Figure 6.4 - Plugin-to-Backend Communication
    draw_flow([
        "CodeSentinelAnnotator.collectInformation() (UI thread) -> FileScanData",
        "doAnnotate() (background thread): APIClient builds ScanRequest(code, fileName)",
        "OkHttpClient POST /predict (JSON body)",
        "Backend predict_code() executes (Figure 6.1)",
        "Gson-parsed ScanResponse -> List<LineScanResult>",
        "apply() (UI thread): AnnotationHolder.newAnnotation() for vulnerable == true findings only",
        "Alt+Enter -> ShowFindingDetailsIntention.invoke() -> MyToolWindow.showFinding()",
    ], HERE / "figure_6_4_plugin_backend_communication.png", fontsize=8.4)

    # Figure 6.5 - Flutter-to-Backend Communication
    draw_flow([
        "Screen widget calls a Repository method",
        "Repository calls its API service (e.g. ChatApiService, AppsApiService)",
        "API service calls ApiClient.get()/post()",
        "ApiClient attaches Authorization: Bearer <JWT> via tokenProvider (if available)",
        "http.Client request to the backend route, with ApiConfig.requestTimeout",
        "ApiClient._send(): status 200/201 -> decoded JSON;\nelse throws a typed exception (Unauthorized/NotFound/Validation/Server/Network)",
        "Repository maps JSON to a model object",
        "Screen renders the result or the caught typed exception's message",
    ], HERE / "figure_6_5_flutter_backend_communication.png", fontsize=8.2)

    # Figure 6.6 - Chatbot Request and Response Flow
    draw_flow([
        "SecurityChatScreen sends a message",
        "ChatRepository -> ChatApiService -> POST /ai-chat\n{message, app_id, user_id}",
        "_strip_legacy_context_prefix() -> _classify_intent() (chatbot_logic.py)",
        "explain_cwe_89 / explain_cwe_295 -> fixed CWE reference text",
        "why_risky / what_to_do / explain_recommendation / compatibility\n(needs app_id) -> database.get_app_assessment_by_id()",
        "app_lookup fallback: _extract_app_name() -> analyze_user_query()",
        "Reply string returned; database.save_chat_message() if user_id present",
        "Flutter renders the reply bubble in SecurityChatScreen",
    ], HERE / "figure_6_6_chatbot_request_response_flow.png", fontsize=8.0)

    # Figure 6.7 - Chat History Retrieval Flow
    draw_flow([
        "SecurityChatScreen.initState(): checks AuthRepository.currentUser?.id != null",
        "ChatRepository.getHistory() -> ChatApiService.getHistory()",
        "GET /user/chat-history, Authorization: Bearer <JWT>",
        "get_current_user() dependency verifies the token -> current_user.id",
        "crud.get_user_chat_history(db, current_user.id),\nORDER BY created_at ASC",
        "{\"history\": [...]}",
        "Flutter expands each row into two ChatMessage objects\n(question=fromUser, answer=fromBot)",
        "ListView renders the transcript; silent fallback if unauthenticated or the request fails",
    ], HERE / "figure_6_7_chat_history_retrieval_flow.png", fontsize=8.2)


if __name__ == "__main__":
    main()
