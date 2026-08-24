"""
Generates the ten required Chapter 5 figures using matplotlib (a real
project dependency - see backend/requirements.txt). Every box/label names
a real, verified module, class, or table from the DualVulnDroid source
code; nothing here is a generic, invented diagram.
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


def draw_flow(steps, out_path, box_width=6.8, box_height=0.62, gap=0.30, fontsize=9.3):
    n = len(steps)
    fig_height = n * (box_height + gap) + 0.6
    fig, ax = plt.subplots(figsize=(7.8, fig_height))
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


def draw_parallel_entry(entry_labels, shared_steps, out_path, box_width=3.2, shared_width=6.8,
                         box_height=0.62, gap=0.30, fontsize=8.8):
    """Two (or more) parallel entry boxes side by side, both converging
    into the first shared step, then a normal vertical chain."""
    n_shared = len(shared_steps)
    fig_height = (n_shared + 1) * (box_height + gap) + 0.9
    total_width = max(shared_width, len(entry_labels) * (box_width + 0.4)) + 1.4
    fig, ax = plt.subplots(figsize=(8.4, fig_height))
    ax.set_xlim(0, total_width)
    ax.set_ylim(0, fig_height)
    ax.axis("off")

    y = fig_height - 0.5
    entry_gap = 0.5
    total_entry_width = len(entry_labels) * box_width + (len(entry_labels) - 1) * entry_gap
    start_x = (total_width - total_entry_width) / 2
    entry_centers_x = []
    for k, label in enumerate(entry_labels):
        x = start_x + k * (box_width + entry_gap)
        box = FancyBboxPatch((x, y - box_height), box_width, box_height,
                              boxstyle="round,pad=0.02,rounding_size=0.08",
                              linewidth=1.3, edgecolor=BOX_EDGE, facecolor="#e6ecf5")
        ax.add_patch(box)
        ax.text(x + box_width / 2, y - box_height / 2, label, ha="center", va="center",
                 fontsize=fontsize, family=FONT, wrap=True)
        entry_centers_x.append(x + box_width / 2)
    entry_bottom = y - box_height
    y -= (box_height + gap)

    shared_x = (total_width - shared_width) / 2
    centers = []
    for label in shared_steps:
        box = FancyBboxPatch((shared_x, y - box_height), shared_width, box_height,
                              boxstyle="round,pad=0.02,rounding_size=0.08",
                              linewidth=1.3, edgecolor=BOX_EDGE, facecolor=BOX_FACE)
        ax.add_patch(box)
        ax.text(shared_x + shared_width / 2, y - box_height / 2, label, ha="center", va="center",
                 fontsize=fontsize + 0.3, family=FONT, wrap=True)
        centers.append(y - box_height)
        y -= (box_height + gap)

    first_shared_top = centers[0] + box_height
    for ex in entry_centers_x:
        arrow = FancyArrowPatch((ex, entry_bottom), (shared_x + shared_width / 2, first_shared_top),
                                 arrowstyle="-|>", mutation_scale=13, linewidth=1.1, color="black",
                                 connectionstyle="arc3,rad=0.0" if len(entry_labels) == 1 else
                                 ("arc3,rad=-0.15" if ex < shared_x + shared_width / 2 else "arc3,rad=0.15"))
        ax.add_patch(arrow)

    for i in range(len(centers) - 1):
        arrow = FancyArrowPatch((shared_x + shared_width / 2, centers[i]),
                                 (shared_x + shared_width / 2, centers[i + 1] + box_height),
                                 arrowstyle="-|>", mutation_scale=14, linewidth=1.2, color="black")
        ax.add_patch(arrow)

    plt.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def draw_branch_converge(branch_labels, converge_label, tail_steps, out_path,
                          branch_width=2.55, branch_height=0.85, converge_width=6.8,
                          box_height=0.62, gap=0.30, fontsize=8.3):
    """N parallel feature-branch boxes converging into one box, then a
    normal vertical chain (used for the hybrid feature pipeline)."""
    n_tail = len(tail_steps)
    fig_height = branch_height + gap + box_height + gap + n_tail * (box_height + gap) + 0.6
    branch_gap = 0.35
    total_branch_width = len(branch_labels) * branch_width + (len(branch_labels) - 1) * branch_gap
    total_width = max(total_branch_width, converge_width) + 1.4
    fig, ax = plt.subplots(figsize=(8.6, fig_height))
    ax.set_xlim(0, total_width)
    ax.set_ylim(0, fig_height)
    ax.axis("off")

    y = fig_height - 0.4
    start_x = (total_width - total_branch_width) / 2
    branch_centers_x = []
    for k, label in enumerate(branch_labels):
        x = start_x + k * (branch_width + branch_gap)
        box = FancyBboxPatch((x, y - branch_height), branch_width, branch_height,
                              boxstyle="round,pad=0.02,rounding_size=0.08",
                              linewidth=1.3, edgecolor=BOX_EDGE, facecolor="#e6ecf5")
        ax.add_patch(box)
        ax.text(x + branch_width / 2, y - branch_height / 2, label, ha="center", va="center",
                 fontsize=fontsize, family=FONT, wrap=True)
        branch_centers_x.append(x + branch_width / 2)
    branch_bottom = y - branch_height
    y -= (branch_height + gap)

    conv_x = (total_width - converge_width) / 2
    conv_box = FancyBboxPatch((conv_x, y - box_height), converge_width, box_height,
                               boxstyle="round,pad=0.02,rounding_size=0.08",
                               linewidth=1.5, edgecolor=BOX_EDGE, facecolor="#fde9c8")
    ax.add_patch(conv_box)
    ax.text(conv_x + converge_width / 2, y - box_height / 2, converge_label, ha="center", va="center",
             fontsize=fontsize + 0.7, family=FONT, weight="bold", wrap=True)
    conv_top = y
    conv_center_bottom = y - box_height
    conv_center_x = conv_x + converge_width / 2

    for bx in branch_centers_x:
        rad = 0.0 if abs(bx - conv_center_x) < 0.05 else (-0.15 if bx < conv_center_x else 0.15)
        arrow = FancyArrowPatch((bx, branch_bottom), (conv_center_x, conv_top),
                                 arrowstyle="-|>", mutation_scale=12, linewidth=1.0, color="black",
                                 connectionstyle=f"arc3,rad={rad}")
        ax.add_patch(arrow)

    y -= (box_height + gap)
    centers = [conv_center_bottom]
    for label in tail_steps:
        box = FancyBboxPatch((conv_x, y - box_height), converge_width, box_height,
                              boxstyle="round,pad=0.02,rounding_size=0.08",
                              linewidth=1.3, edgecolor=BOX_EDGE, facecolor=BOX_FACE)
        ax.add_patch(box)
        ax.text(conv_x + converge_width / 2, y - box_height / 2, label, ha="center", va="center",
                 fontsize=fontsize + 0.5, family=FONT, wrap=True)
        centers.append(y - box_height)
        y -= (box_height + gap)

    for i in range(len(centers) - 1):
        top_y = centers[i] if i > 0 else conv_center_bottom
        arrow = FancyArrowPatch((conv_center_x, top_y), (conv_center_x, centers[i + 1] + box_height),
                                 arrowstyle="-|>", mutation_scale=14, linewidth=1.2, color="black")
        ax.add_patch(arrow)

    plt.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def draw_er_diagram(out_path):
    """Manually laid out ER diagram of the real 10-table MySQL schema
    (db/models.py), including the chat_history read path added for
    GET /user/chat-history."""
    fig, ax = plt.subplots(figsize=(11, 8.6))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 11.5)
    ax.axis("off")

    def entity(x, y, w, h, title, fields, face="#f2f2f2"):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                              linewidth=1.3, edgecolor=BOX_EDGE, facecolor=face)
        ax.add_patch(box)
        ax.plot([x, x + w], [y + h - 0.42, y + h - 0.42], color="black", linewidth=1.0)
        ax.text(x + w / 2, y + h - 0.24, title, ha="center", va="center",
                 fontsize=9.5, family=FONT, weight="bold")
        ax.text(x + w / 2, y + (h - 0.42) / 2, "\n".join(fields), ha="center", va="center",
                 fontsize=7.6, family=FONT, linespacing=1.5)
        return (x, y, w, h)

    ents = {}
    ents["users"] = entity(0.3, 8.8, 2.6, 1.9, "users", ["id (PK)", "email, password_hash", "name"])
    ents["applications"] = entity(6.3, 9.3, 2.8, 1.4, "applications", ["id (PK)", "app_name, package_name"])
    ents["app_versions"] = entity(6.3, 6.6, 2.8, 1.6, "app_versions", ["id (PK)", "application_id (FK)", "min/target_sdk_version"])
    ents["scans"] = entity(3.2, 5.6, 3.0, 2.0, "scans", ["id (PK)", "user_id (FK, nullable)", "application_id (FK)", "app_version_id (FK)"])
    ents["vulnerabilities"] = entity(0.3, 3.0, 2.7, 1.4, "vulnerabilities", ["id (PK)", "scan_id (FK)", "cwe, type, severity"])
    ents["ml_predictions"] = entity(3.4, 3.0, 2.7, 1.4, "ml_predictions", ["id (PK)", "scan_id (FK)", "model, shap_summary"])
    ents["recommendations"] = entity(6.5, 3.0, 2.7, 1.4, "recommendations", ["id (PK)", "scan_id (FK)", "recommendation, reason"])
    ents["alternative_apps"] = entity(9.8, 6.6, 3.0, 1.6, "alternative_apps", ["id (PK)", "application_id (FK)", "alternative_application_id (FK)"])
    ents["chat_history"] = entity(10.5, 9.3, 3.2, 1.7, "chat_history", ["id (PK)", "user_id (FK, nullable)", "question, answer, created_at"], face="#fde9c8")
    ents["security_tips"] = entity(10.5, 0.3, 2.9, 1.4, "security_tips", ["id (PK)", "title, category", "(no FK - standalone)"])

    def connect(a, b, label=""):
        ax_, ay_, aw_, ah_ = ents[a]
        bx_, by_, bw_, bh_ = ents[b]
        ac = (ax_ + aw_ / 2, ay_ + ah_ / 2)
        bc = (bx_ + bw_ / 2, by_ + bh_ / 2)
        arrow = FancyArrowPatch(ac, bc, arrowstyle="-", linewidth=1.1, color="#555555",
                                 connectionstyle="arc3,rad=0.05", shrinkA=35, shrinkB=35)
        ax.add_patch(arrow)
        if label:
            mx, my = (ac[0] + bc[0]) / 2, (ac[1] + bc[1]) / 2
            ax.text(mx, my, label, fontsize=7, family=FONT, ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))

    connect("users", "scans", "1:N")
    connect("users", "chat_history", "1:N")
    connect("applications", "app_versions", "1:N")
    connect("applications", "scans", "1:N")
    connect("app_versions", "scans", "1:N")
    connect("scans", "vulnerabilities", "1:N")
    connect("scans", "ml_predictions", "1:N")
    connect("scans", "recommendations", "1:N")
    connect("applications", "alternative_apps", "1:N (self-ref x2)")

    ax.text(7.5, 11.1, "DualVulnDroid MySQL Schema (db/models.py) — 10 tables",
            fontsize=11, family=FONT, weight="bold", ha="center")

    plt.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def main():
    # Figure 5.1 - Overall architecture
    draw_parallel_entry(
        ["IntelliJ/Android Studio Plugin\n(Developer)", "Flutter Application\n(Application User)"],
        [
            "Backend API (FastAPI) — app.py",
            "Hybrid feature pipeline + XGBoost production model",
            "SHAP explanation + Hybrid Decision Engine",
            "MySQL database (10 tables)",
        ],
        HERE / "figure_5_1_overall_architecture.png",
    )

    # Figure 5.2 - Real-time vulnerability detection workflow
    draw_flow([
        "Developer edits Java/Kotlin code in the IDE",
        "CodeSentinelAnnotator.collectInformation() (UI thread)",
        "CodeSentinelAnnotator.doAnnotate() → APIClient → POST /predict",
        "Backend: feature construction + XGBoost + SHAP + Decision Engine",
        "Response: class, confidence, severity, decision, evidence",
        "CodeSentinelAnnotator.apply(): annotation + tooltip + Quick Fix",
        "Alt+Enter → ShowFindingDetailsIntention → MyToolWindow detail view",
    ], HERE / "figure_5_2_realtime_workflow.png", fontsize=8.8)

    # Figure 5.3 - ML detection pipeline
    draw_flow([
        "Raw code text (single file or batch)",
        "normalize_code() text normalisation (ml/feature_pipeline.py)",
        "7,610-dim hybrid feature vector construction",
        "XGBoost booster[0:103] prediction → class probabilities",
        "shap.TreeExplainer(model).shap_values() → per-feature contributions",
        "decision_engine.evaluate(ml_result, data_flow_evidence)",
        "VULNERABLE / SAFE / SUSPICIOUS_REVIEW + evidence + explanation",
    ], HERE / "figure_5_3_ml_pipeline.png", fontsize=8.8)

    # Figure 5.4 - XGBoost hybrid feature architecture
    draw_branch_converge(
        [
            "Word TF-IDF\n(max_features=5000,\nngram 1–3)",
            "Char TF-IDF\n(max_features=2000,\nngram 2–5)",
            "Count vectorizer\n(max_features=1000,\nngram 1–2)",
            "23 deterministic\nsecurity/data-flow\nfeatures",
        ],
        "hstack() → 7,610-dimensional hybrid feature vector",
        [
            "XGBoost booster (multi:softprob, 4 classes)",
            "Raw booster: 123 boosted rounds saved",
            "Sliced at load time to booster[0:103] (validated cutoff)",
            "Output: class probabilities (s0, v0, s1, v1)",
        ],
        HERE / "figure_5_4_xgboost_features.png",
    )

    # Figure 5.5 - Hybrid Decision Engine flow
    draw_flow([
        "ML prediction (signed by class, ×1.0 weight)",
        "SQL data-flow evidence (traced source→sink +2.0 /\nconcatenation +1.2 / parameterized −1.5)",
        "Certificate evidence (vulnerable +2.0 / suspicious +0.6 / safe −1.5)",
        "Static keyword-rule corroboration (+0.4)",
        "Sum → evidence_score",
        "Compare to calibrated thresholds\n(vulnerable_threshold, safe_threshold)",
        "VULNERABLE  |  SUSPICIOUS_REVIEW  |  SAFE",
    ], HERE / "figure_5_5_decision_engine.png", fontsize=8.8)

    # Figure 5.6 - IntelliJ plugin architecture
    draw_flow([
        "plugin.xml: ExternalAnnotator (Java/Kotlin), ToolWindowFactory",
        "CodeSentinelAnnotator (real-time) / ProjectFileCollector (Scan Project)",
        "APIClient.kt → POST /predict or POST /developer/scan",
        "Annotation + tooltip; ShowFindingDetailsIntention (Alt+Enter)",
        "MyToolWindow: shared findings list + detail renderer + jump-to-source",
        "SqlFixLocator / CertificateFixLocator → Safe*QuickFix classes",
        "FixVerificationRunner: real backend re-scan after a Quick Fix",
    ], HERE / "figure_5_6_plugin_architecture.png", fontsize=8.6)

    # Figure 5.7 - Flutter application architecture
    draw_flow([
        "Screens (Splash, Login, Dashboard, Search, Application Details,\nDevice Compatibility, Security Chat, Assessment History)",
        "Widgets (RiskBadge, CompatibilityBadge, DecisionCard,\nVulnerabilityTile, AlternativeAppTile, CompatibilityCheckTile)",
        "Repositories (Auth, Apps, History, Chat, DeviceProfile)",
        "API services (per-repository, one HTTP concern each)",
        "ApiClient: attaches JWT, maps HTTP errors to typed exceptions",
        "Backend API (FastAPI)",
    ], HERE / "figure_5_7_flutter_architecture.png", fontsize=8.8)

    # Figure 5.8 - Chatbot architecture
    draw_flow([
        "SecurityChatScreen (Flutter) — send message / load history",
        "ChatRepository → ChatApiService",
        "POST /ai-chat  (send)   |   GET /user/chat-history  (load)",
        "chatbot_logic.py: deterministic intent classification",
        "app_id → database.get_app_assessment_by_id() (real, stored data)",
        "database.save_chat_message() → chat_history table (MySQL)",
        "Reply rendered verbatim in the Flutter UI",
    ], HERE / "figure_5_8_chatbot_architecture.png", fontsize=8.6)

    # Figure 5.9 - Database ER diagram
    draw_er_diagram(HERE / "figure_5_9_database_er.png")

    # Figure 5.10 - End-to-end data flow
    draw_flow([
        "Developer: source code  |  APK: real Android package",
        "Plugin /predict, /developer/scan  |  Backend /upload-apk (apk_scanner.py)",
        "Shared feature pipeline + XGBoost + SHAP + Decision Engine",
        "MySQL persistence (applications, versions, scans, vulnerabilities,\nml_predictions, recommendations, chat_history)",
        "Flutter: search, security assessment, compatibility, alternatives, chatbot",
        "Developer/User result: decision, evidence, explanation, recommendation",
    ], HERE / "figure_5_10_end_to_end_flow.png", fontsize=8.8)


if __name__ == "__main__":
    main()
