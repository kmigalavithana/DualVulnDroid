# Final CWE-89 Corpus — ML Feasibility Review & Experiment Plan

**Review date:** 2026-08-29
**Subject corpus:** `backend/research_eval_artifacts/new_cwe89_corpus_final/` (read-only in this review; not modified)
**Nature of this document:** A pre-registration-style feasibility assessment, produced *before* any model is trained. No model was trained, no metric was computed, and no existing dataset/source file was modified to produce this document. Every count below was independently re-derived from the corpus's own CSV/JSON files in this session, not taken from the corpus's own report narrative.

---

# Executive Verdict

The final corpus (34 samples, 18 independent projects, 3 independent vulnerable projects, project-level split verified disjoint with vulnerable-class coverage in every split) is **methodologically the strongest artifact produced across all three collection rounds**, but it remains **too small in absolute terms to support any supervised ML training or evaluation that yields a statistically defensible quantitative claim.** The bottleneck is specifically the vulnerable class: 3 independent vulnerable projects, exactly 1 per split, is enough to make the *split design* structurally sound but not enough to make any *split's metrics* statistically meaningful (n=1 positive example per split is a degenerate case for precision/recall/F1). The safe class is comparatively well-supported (31 samples, 18 projects, 4 genuinely distinct evidence mechanisms), though 52% of it (16/31 samples) falls into the least informative category (compile-time constants with no runtime variability at all).

**Recommendation: proceed with a small, explicitly-scoped feasibility/proof-of-concept experiment (Section 8), not a benchmark.** Do not train LSTM, CodeBERT, or any other high-capacity/pretrained-fine-tuning model against this corpus (Section 6). Do not reuse the old dataset's XGBoost/CodeBERT artifacts or metrics as evidence for anything about this corpus (Section 13). Before any quantitative claim beyond "this specific mechanism was demonstrated to work/fail" can be made, more independent vulnerable-class projects are required (Section 12).

---

# 1. Corpus Quality

Every count below was re-derived directly from `final_candidate_cwe89_samples.csv` and cross-checked against `final_provenance_report.json` and `final_project_split_manifest.csv` — not copied from the corpus report's prose.

| Check | Result |
|---|---|
| Total samples | 34 (confirmed: `Counter` over the CSV's `label` column) |
| DEFINITELY_VULNERABLE | 3 |
| DEFINITELY_SAFE | 31 |
| AMBIGUOUS | 0 |
| CWE scope | 100% CWE-89 (no CWE-295 contamination) |
| Label confidence | 28 HIGH, 6 MEDIUM, 0 LOW |
| Missing critical fields (project_id, repository_id, commit_hash, file_path, label, source, sink, dataflow_path, parameterized, sanitized, license, split) across all 34 rows | **None found** |
| Independent projects | 18 (confirmed via `set(project_id)`) |
| Excluded as NOT_RELEVANT (API misidentification) | 2 (`ot-EXCLUDED-001`: `Uri.getRawQuery()` false positive; `dv-EXCLUDED-001`: `DnsResolver.rawQuery()` false positive) |
| Excluded as VULNERABLE_PATTERN_UNREACHABLE (dead code) | 2 (`os-EXCLUDED-001`, `os-EXCLUDED-002` — vulnerable-shaped code in openintents/safe with no live caller anywhere in the app) |
| Entire project excluded (clone/duplicate risk) | 1 (FossifyOrg/Notes, a near-verbatim fork of the Phase-1 Simple-Notes sample) |
| Sample-to-project split consistency | Verified: every sample's `split` field matches its project's entry in `final_project_split_manifest.csv`, with zero mismatches |
| Vulnerable projects entirely within one split | Verified: `andstatus-andstatus` (train only), `tasks-tasks` (validation only), `openintents-safe` (test only) — no vulnerable project's samples are split across boundaries |

**Only DEFINITELY_VULNERABLE and DEFINITELY_SAFE samples exist in this corpus** — there is no AMBIGUOUS or NOT_RELEVANT contamination to filter before any supervised experiment, because those categories were already excluded at corpus-construction time (documented in `final_excluded_candidates.csv`) rather than left in the main sample file for a downstream consumer to filter. This is a genuine quality strength: the corpus requires no further label-quality triage before use.

**Verdict on this axis: the corpus is clean and internally consistent.** Its limitation is scale, not label quality or documentation quality.

---

# 2. Vulnerable-Project Independence

Full comparison table in `vulnerable_project_analysis.csv`. Summary:

| | `as-001` (andstatus) | `ts-001` (tasks) | `os-001` (openintents-safe) |
|---|---|---|---|
| **Source type** | In-app user content (note/status text) | External IPC caller (ContentProvider parameter) | External file import (XML backup) |
| **Sink API** | `execSQL(String)`, single-arg | Custom `rawQuery(String)` wrapper via a discarded query-builder | `query()`'s `selection` parameter |
| **Propagation** | 2 files (concat + a buggy escaping helper) | 2 files (builder pattern misuse) | 5 files (SAX parser → data object → restore loop → DB helper) |
| **Android component** | None (internal utility) | ContentProvider, `exported="true"` | None (local file-import feature) |
| **Sanitization failure** | Attempted but flawed (bypassable edge case in a real escaping function) | Absent entirely | Absent entirely |
| **Reachability** | Internal, no IPC needed | **External** — reachable from another installed app holding a custom permission | Local/social-engineering — requires the user to import a malicious file |

**Determination: A. Independent vulnerability mechanisms**, with one honest caveat: `ts-001` and `os-001` both ultimately fail at "use the `selection`/WHERE-clause channel of a SQLite API safely" — that surface-level commonality is close to *definitional* for CWE-89 (nearly every instance of this CWE involves an unparameterized clause somewhere), so it should not be read as evidence these are the same bug. What distinguishes them as independent flaws, by the task's own stated criteria, is genuinely different: the entry vector (external IPC call vs. local file import) is different, the exact API misused is different (a discarded query-builder's bind mechanism vs. a structured `query()` call's unused `selectionArgs`), the reachability precondition is different (no user action required vs. requiring the user to actively import a file), and the propagation depth is different (2 files vs. 5 files, with `os-001` additionally passing through a completely different subsystem — an XML parser — that neither of the other two touches at all). `as-001` is the clearest independent case: it is the only one of the three with an *attempted* defense that fails, rather than *no* defense, and it is not IPC/file-reachable at all.

**Practical consequence:** 3 independent vulnerable projects is enough to assert "this corpus demonstrates at least 3 genuinely different ways CWE-89 manifests in real Android code" as a qualitative claim. It is not enough to assert anything about how *representative* these 3 mechanisms are of CWE-89 in general — 3 data points cannot support a claim about the distribution of vulnerability mechanisms in the wild, only that these specific 3 exist and were independently verified.

---

# 3. Safe-Class Diversity

Full per-sample categorization in `safe_evidence_analysis.csv`. Categories and counts, independently tallied from the corpus's own `dataflow_path`/`parameterized`/`sanitized` text (not from the corpus report's prose):

| Category | Samples | Projects | % of safe class |
|---|---|---|---|
| Compile-time constants / fully literal | 16 | 13 | **52%** |
| Framework- or type-system-constrained input | 6 | 4 | 19% |
| Parameterized query / bind arguments | 6 | 6 | 19% |
| Explicit runtime allowlist / validation logic | 3 | 2 | 10% |

**The safe class is heavily dominated by one template: "compile-time constants / fully literal," at 52%.** This is the least informative category for a supervised classifier to learn from, because it requires no discrimination ability at all — a trivial rule ("no runtime variable reaches the sink") would classify all 16 of these correctly, and that rule teaches nothing about the actually-hard cases (a variable *does* reach the sink, and the question is whether it's safely handled). The three categories that *do* require discriminating a defended-but-risky-looking pattern from an undefended one — parameterized/bind (6), framework-constrained (6), and allowlist (3) — total 15 samples, 44% of the safe class, spread across 12 of the 18 projects.

This has a direct consequence for Section 8's fusion design: **the ML component's usefulness will be dominated by how well it does on the 15 "hard" safe samples and the 3 vulnerable samples, not the 16 "easy" ones**, and any reported aggregate accuracy that blends all 31 safe samples together will overstate the model's actual discriminative ability by diluting it with easy negatives.

---

# 4. Project-Level Split

Disjointness re-verified in this review (not merely re-stated from the corpus's own report): built `train`/`validation`/`test` as Python sets keyed by `project_id` from `final_project_split_manifest.csv`, checked all three pairwise intersections and the union against the full 18-project set. Result: `train&val=∅`, `train&test=∅`, `val&test=∅`, `union=all 18 projects`. Cross-checked against every sample's own `split` field in `final_candidate_cwe89_samples.csv`: **zero mismatches.**

| Split | Projects | Vulnerable projects | Safe-only projects | Samples | Vulnerable samples | Safe samples |
|---|---|---|---|---|---|---|
| **TRAIN** | 7 | 1 (andstatus-andstatus) | 6 | 15 | 1 (`as-001`) | 14 |
| **VALIDATION** | 5 | 1 (tasks-tasks) | 4 | 11 | 1 (`ts-001`) | 10 |
| **TEST** | 6 | 1 (openintents-safe) | 5 | 8 | 1 (`os-001`) | 7 |

Full detail: `final_split_analysis.csv`.

**Mathematically disjoint is confirmed. Statistically usable is a separate question, and the answer is no for any quantitative purpose.** With exactly 1 vulnerable sample in each split, every split's vulnerable-class recall is either 0% or 100% depending on the outcome of a single prediction — there is no distribution to estimate, only a coin-flip-scale outcome. The split is well-designed *given* the data available (it correctly avoids the alternative failure modes of putting 0 vulnerable projects in a split, or splitting a single project's samples across boundaries to artificially pad a split's vulnerable count), but no split design can manufacture statistical power that 3 total vulnerable projects do not contain.

---

# 5. Test-Set Adequacy

**Exact test-set composition** (re-derived from the CSV, not assumed):
- Vulnerable test projects: 1 (`openintents-safe`)
- Vulnerable test samples: 1 (`os-001`)
- Safe test projects: 5 (`owntracks-android`, `tuskyapp-tusky`, `commons-app-apps-android-commons`, `fossifyorg-calendar`, `nextcloud-android`)
- Safe test samples: 7

**Why n=1 vulnerable cannot support the requested metrics:**

- **Precision** on the vulnerable class requires multiple positive predictions to average over; with 1 true positive available, precision is only defined/meaningful if the model happens to predict "vulnerable" for exactly this one case among however many predictions it makes — a single data point, not a rate.
- **Recall** on the vulnerable class is binary at n=1: either `os-001` is caught (100%) or missed (0%). There is no way to distinguish "this model reliably catches ~80% of CWE-89 instances" from "this model got lucky/unlucky once" — the sample size cannot separate signal from chance.
- **F1** inherits both of the above problems, since it is a function of precision and recall.
- **False Negative Rate (FNR)** is likewise 0% or 100% — no intermediate value is observable.
- **False Positive Rate** is somewhat better-supported (7 safe test samples give slightly more room), but still far too few for a stable rate estimate — a single misclassified safe example swings the FPR by ~14 percentage points.
- **Confidence intervals**: any interval computed from n=1 (e.g., a Wilson or Clopper-Pearson interval for a binomial proportion) will be so wide as to be uninformative (spanning nearly 0% to 100%), and reporting a narrow interval would be a fabricated/overstated claim the task explicitly prohibits.
- **Generalization claims**: none are supportable. A model's behavior on 1 held-out vulnerable example says nothing about its behavior on CWE-89 instances of a different mechanism, in a different Android component, or in a different app — precisely because Section 2 established that even the corpus's own 3 vulnerable examples are mechanistically distinct from each other. There is no basis to assume a 4th, unseen instance would resemble any of the 3 already seen.

**No statistical significance is invented anywhere in this document**, consistent with the task's strict rules. The correct characterization of this test set is: it can demonstrate whether a specific model correctly classifies *this specific, well-documented example* — a case-study-level demonstration — and nothing beyond that.

---

# 6. ML Feasibility

Full per-model reasoning in `model_feasibility_analysis.csv`. Summary:

| Model | Feasible at n=34 (3 vulnerable)? | Recommended for the focused paper? |
|---|---|---|
| SVM (linear/RBF, hand-crafted or TF-IDF features) | Partial — fits without error, but test-split metrics are not meaningful (Section 5) | Yes, as a baseline only |
| Random Forest | Partial — same caveat, additionally unstable feature-importance rankings | Yes, as a comparison baseline, explicitly to illustrate overfitting risk |
| XGBoost | No, for a genuine performance claim — will fit but memorizes 1–3 positive examples rather than learning a boundary | Only as an explicitly-labeled "known-limitation" baseline, never as the headline result |
| Generic feed-forward neural network | No | No |
| Transformer (trained from scratch) | No, categorically | No |
| **CodeBERT (fine-tuned)** | **No** — insufficient examples to move a pretrained model meaningfully, AND any existing project checkpoint was fit on the old, invalidated dataset | **No — explicitly exclude from the focused paper** |
| **LSTM** | **No** — parameter count vastly exceeds example count, and long-range dependency learning needs many examples per sequence-length bucket, which 3 vulnerable examples of differing shapes cannot provide | **No — explicitly exclude from the focused paper** |

**Why specifically LSTM and CodeBERT must be excluded, not just "small dataset":**

- **LSTM**: a recurrent architecture's useful capacity comes from learning long-range token/sequence dependencies, which requires many examples *of comparable sequence length and structure* to generalize a dependency pattern rather than memorize one sequence. With 3 vulnerable examples of three different code shapes (a single-file concatenation, a two-file builder-pattern misuse, a five-file XML-to-SQL chain), there is no shared sequence structure across even 2 of the 3 positive examples for an LSTM to generalize from — each one is effectively its own "class of one."
- **CodeBERT**: two independent, compounding problems rather than one. First, the general fine-tuning sample-size problem (a pretrained transformer's classification head still needs enough task-specific examples to reliably move away from its pretraining prior — typically low hundreds at minimum for a binary head, not single digits). Second, and specific to this project: `research_eval_artifacts/codebert/` already contains a fine-tuned checkpoint, but it was trained against the dataset `DATASET_VALIDITY_VERDICT.md` found methodologically invalid (100% boilerplate explanations for the entire negative/safe class, undocumented provenance). Reusing that checkpoint's weights as a "warm start" for the new corpus would silently reintroduce exactly the contamination this three-round corpus-construction effort exists to eliminate, even if the fine-tuning data itself were the new, clean corpus.

**SVM and Random Forest are recommended specifically because their failure mode at this scale is legible and diagnosable** (an inspectable linear coefficient vector; a small number of trees whose individual splits can be read) — not because they are expected to "work" in any generalizable sense. This distinction — a model chosen because its limitations are visible, versus a model chosen because it appears to perform well — is the correct basis for model selection at n=34.

---

# 7. Double-Counting Risks

Per the task's explicit constraint: **the ML feature pipeline must not contain the same deterministic evidence the independent static/data-flow analyzer (or a later fusion layer) also uses.**

This project's own prior forensic work already identified this exact failure mode in the *existing, pre-corpus* DualVulnDroid pipeline: `backend/security_features.py`'s 23 handcrafted features and `backend/decision_engine.py`'s weighted-evidence combiner were found (during the earlier `DATASET_VALIDITY_VERDICT.md`-era audit) to encode overlapping deterministic signals — e.g. a "source reaches sink" boolean appearing both as an ML input feature *and* as a separately-weighted term in the decision engine's evidence sum, meaning the same fact influenced the final decision twice under two different names.

**For any experiment built on this new corpus, the same discipline must be applied from the start:**

1. If `backend/dataflow.py` (the deterministic source→sink tracer already used throughout this corpus's own construction as an oracle) is used as the "independent static/data-flow detector" baseline (Section 8), then any ML-side feature that is a direct restatement of its output (e.g. "was a traced source-to-sink path found," "is the value parameterized," "is the sink `execSQL`/`rawQuery`/`query`") must be **excluded from the ML feature pipeline** — those are exactly the deterministic facts the independent detector already contributes, and including them in both places would make the "late fusion" step (Section 8) circular: the ML model would just be re-deriving the static analyzer's own verdict, and the fusion layer would then double-weight it.
2. Legitimate ML-side features are the ones the deterministic analyzer does *not* already compute: e.g. surface lexical/statistical text features (token n-grams, string-literal density, identifier-naming patterns), structural features not already part of `dataflow.py`'s traced-evidence output, or code-context features unrelated to the specific source/sink/parameterization facts.
3. Given the corpus's own composition (Section 3: 52% of the safe class is "no variable reaches the sink at all," a fact the deterministic analyzer already captures perfectly), a feature pipeline that leans heavily on deterministic dataflow facts would trivially separate most of this corpus's safe examples from its vulnerable ones **without learning anything ML-specific** — which would make an "ML detector" that appears to work well on this corpus largely a restatement of the static analyzer, not independent corroborating evidence. This is precisely the scenario the fusion design in Section 8 must avoid.

---

# 8. Recommended Experimental Design

Given Sections 1–7, the smallest experiment that is honestly defensible on this corpus:

**BASELINE A — Text-only classifier.** A linear model (SVM, per Section 6) or simple bag-of-tokens classifier trained purely on surface code text (identifiers, literals, token sequences), with no access to `dataflow.py`'s traced source/sink/parameterization facts. Tests: can lexical surface features alone separate the 3 vulnerable examples from the 31 safe ones? Given each vulnerable example has a distinct code shape (Section 2), a plausible and honestly-reportable outcome is "no, or only trivially" — that is itself a useful, reportable finding about this corpus, not a failure of the experiment design.

**BASELINE B — Independent static/data-flow detector.** `backend/dataflow.py`, used exactly as it was used as an oracle throughout this corpus's own construction (Phase D/E audits, and every SAFE/VULNERABLE label in this corpus was itself produced by a human applying the same source→sink→parameterization reasoning `dataflow.py` automates). Run, unmodified, against all 34 samples and report its agreement with the corpus's human labels. **Important framing note:** because the corpus's own labels were produced using the same reasoning this tool automates, a high agreement rate here demonstrates *consistency of method*, not independent validation — this must be stated explicitly if reported, not presented as an accuracy claim.

**PROPOSED — Late fusion (ML probability + independent static/data-flow evidence).** Combine Baseline A's output with Baseline B's output at decision time (not at feature-engineering time — see Section 7's double-counting constraint). A simple, interpretable fusion rule (e.g. "flag as vulnerable if either signal fires strongly, abstain if they disagree") is more appropriate than a learned fusion weight at this scale, since a learned combiner would itself need training data the corpus cannot spare without contaminating the already-tiny test set.

**RISK-AWARE — VULNERABLE / SAFE / ABSTAIN.** Given n=1 vulnerable test example, a binary forced-choice evaluation cannot distinguish "confidently correct" from "correct by chance." A three-way output with an explicit ABSTAIN option (triggered when Baseline A and Baseline B disagree, or when either signal's confidence is low) is the only evaluation mode that lets the experiment report something more informative than a single binary hit/miss on the one test-set vulnerable example — e.g. "the fused system abstained rather than guessed wrong on the harder safe examples" is a reportable, non-overstated finding.

**What this design explicitly does NOT attempt:** a leaderboard-style comparison of multiple high-capacity models (Section 6), a precision/recall table treated as a generalization claim (Section 5), or any claim that the fusion system's behavior on this test set predicts its behavior on CWE-89 instances outside this corpus.

---

# 9. Minimal Ablation Study

Design only — **not run** in this session, per the task's strict rules.

| Ablation | Tests |
|---|---|
| **A. ML only** (Baseline A alone) | Whether surface lexical/textual signal, with zero access to traced dataflow facts, carries any separating information at all on this corpus. A near-chance result here is expected and informative, not a failure. |
| **B. Static/data-flow only** (Baseline B alone) | Whether the deterministic analyzer's own traced verdict matches the human-assigned corpus labels — a consistency check (see Section 8's framing note), not an independent-validity check, since both were produced by the same underlying reasoning. |
| **C. ML + static/data-flow** (naive fusion, forced binary choice) | Whether combining the two signals changes the outcome relative to either alone — and specifically whether the combination ever *disagrees* with both individual baselines in a way that reveals a genuine third source of information, versus the fused output simply tracking whichever baseline is more confident. |
| **D. ML + static/data-flow + abstention** | Whether adding a "disagreement → abstain" rule reduces the rate of confident-but-wrong predictions on the corpus's hardest cases (the 15 "hard" safe samples identified in Section 3, plus all 3 vulnerable samples) relative to Ablation C's forced binary choice. This is the ablation most likely to produce a genuinely useful, honestly-scoped finding at this sample size, because it asks a qualitative question ("does abstention help here") rather than a quantitative one ("what is the F1").|

Each ablation should be reported per-split (train/validation/test) and per-sample where feasible (given only 8 test samples, per-sample reporting is itself tractable and more honest than an aggregate rate at this scale), consistent with Section 5's finding that aggregate rates are not meaningful here.

---

# 10. Selective Prediction / Abstention

Selective prediction (Section 8/9's ABSTAIN option) is **the single most valuable methodological addition available at this corpus's scale**, for a specific reason grounded in Sections 3 and 5: the corpus's safe class is dominated (52%) by trivially-easy negatives, and its vulnerable class is dominated by mechanistically-distinct singletons. A forced binary classifier evaluated in aggregate will look artificially strong (dragged up by the easy negatives) or artificially weak (dragged down by a single hard positive miss) depending on which failure mode dominates a given run — neither outcome is informative. An abstention mechanism lets the experiment separate "the system is confidently and correctly discriminating" from "the system doesn't have enough basis to decide," which is the honest state of affairs for most of this corpus's harder cases. Reporting *how often and on which specific samples* the system abstains is itself a legitimate, non-overstated experimental finding at n=34, in a way that a bare accuracy number is not.

---

# 11. Claims Supported

- **Feasibility**: that a source-to-sink CWE-89 corpus with real, independently-verified provenance (not fabricated, not keyword-derived) can be constructed from public Android repositories using a documented, repeatable methodology.
- **Proof-of-concept**: that a deterministic static analyzer (`dataflow.py`) and/or a simple text-based classifier can be exercised end-to-end against real, labeled CWE-89 examples.
- **Qualitative source-level detection**: specific, well-documented demonstrations that particular code patterns (a flawed escaping helper, a query-builder API misuse, a structured-API misuse via file import) constitute genuine CWE-89 flaws, and that particular contrasting patterns (constant-only concatenation, `?`-bound parameterization, a tokenizer-based allowlist) do not.
- **Comparison of evidence mechanisms**: a documented comparison of *how* different Android apps get CWE-89 right or wrong across at least 4 genuinely distinct safe-evidence categories (Section 3) and 3 genuinely distinct vulnerable mechanisms (Section 2).
- **Selective-decision methodology**: a demonstration of an abstention-capable evaluation design, and a reportable account of when/why it abstains on this specific corpus.

# 12. Claims NOT Supported

- **Broad Android generalization**: 18 projects, however carefully chosen, is not a representative sample of the Android app ecosystem, and 3 vulnerable projects cannot support any claim about how common or rare any particular CWE-89 mechanism is in the wild.
- **Production accuracy**: no metric computed on this corpus (Section 5, 6) reflects what any model would do on unseen, real-world code at deployment scale.
- **Statistically strong model ranking**: Section 6 established that any model comparison at this scale is not statistically separable from noise; a table ranking SVM vs. Random Forest vs. XGBoost by a point-estimate metric would misrepresent what the numbers can support.
- **"Best model" claims**: for the same reason — "best" implies a statistically meaningful comparison, which n=3 vulnerable/34 total cannot provide.
- **Large-scale benchmark superiority**: this corpus is not a benchmark, and no claim of outperforming another tool/model/dataset on it would be defensible.
- **Universal CWE-89 detection capability**: nothing in this corpus supports a claim that any resulting system detects CWE-89 in general, as opposed to demonstrating specific, documented instances.

---

# 13. Additional Data Requirements

**Dataset size decision (per the task's required categories A–E): A, qualified.**

**A. Proceed with a carefully labelled feasibility experiment** is the correct immediate choice — the corpus's label quality (Section 1), mechanism diversity (Sections 2–3), and split integrity (Section 4) are all sound enough to support the Section 8 design *as an explicitly-scoped feasibility/proof-of-concept study*. Stopping and redesigning (E) is not warranted — nothing in this review found a methodological defect requiring a restart, only a scale limitation, which is a different problem with a different, additive remedy.

**B. Collect more vulnerable projects is the necessary next step before any quantitative claim becomes possible** — not a "nice to have," but a hard precondition, because Section 5 established that no split's current vulnerable-class metric is statistically meaningful at n=1. This is a stronger and more specific need than C (more safe projects): the safe class is already reasonably diverse (Section 3, 4 categories, 15 "hard" examples across 12 projects) relative to its role in the experiment, while the vulnerable class has exactly the minimum viable count (3) for the *split design* to work at all and nowhere near enough for the *split's metrics* to mean anything.

**Recommended minimum, expressed in independent projects, not row count** (per the task's explicit instruction — and explicitly not a guarantee of statistical validity, only an operational threshold below which the specific degenerate problems in Section 5 are certain to recur):

- **Minimum vulnerable projects**: roughly 5–8 *independent* vulnerable projects per split (15–24 total) to move from a single degenerate data point per split to a small-but-non-degenerate sample — still not enough for a narrow confidence interval, but enough that a single hit or miss no longer swings the split's apparent recall by 100 percentage points.
- **Minimum safe projects**: maintain a ratio no more imbalanced than roughly 2:1 to 3:1 safe:vulnerable projects (consistent with the corpus's current ~5:1 ratio at 15 safe-only vs. 3 vulnerable, which is already within a defensible range) — the priority is not adding more safe projects for their own sake, but ensuring the safe class doesn't become *more* dominated by the easy "constants" category as it grows (Section 3's finding should inform *which* new safe projects are prioritized, favoring ones likely to add parameterized/framework-constrained/allowlist-style evidence over more literal-DDL boilerplate).
- **Minimum total independent projects**: on the above ratios, roughly 30–50 total independent projects would put the corpus in a range where a genuinely modest quantitative claim (not a benchmark, but a real confidence interval wider than "0% to 100%") becomes possible.

No specific number above is claimed to guarantee statistical validity — these are operational targets for escaping the specific degenerate cases identified in Section 5, not thresholds with any formal statistical grounding.

# 14. Final Recommendation

1. **Proceed** with the Section 8 feasibility experiment on the current 34-sample corpus, scoped explicitly as a proof-of-concept / methodology demonstration.
2. **Exclude** LSTM and CodeBERT from the focused paper's experimental section (Section 6); include SVM and Random Forest only as baselines with explicit small-sample caveats; include XGBoost only as a labeled known-limitation baseline, never as the headline result.
3. **Enforce** the no-double-counting constraint (Section 7) when designing the ML feature pipeline — exclude any feature that restates `dataflow.py`'s own traced-evidence output.
4. **Report per-sample, not aggregate**, wherever the sample count makes aggregate rates misleading (Sections 5, 9) — with only 8 test samples (1 vulnerable), per-sample reporting is tractable and more honest.
5. **Do not** reuse the old dataset's XGBoost/CodeBERT trained artifacts, metrics, or hand-tuned decision-engine weights as evidence for anything about this new corpus (Section 13) — the existing implementations are reusable as scaffolding, not as pre-validated results.
6. **In parallel with, not instead of, Step 1**: begin a further corpus-expansion effort targeting additional independent vulnerable-class projects (Section 12's operational minimum) before attempting any experiment whose conclusions depend on a quantitative claim rather than a qualitative/case-study one.
7. **Do not write the conference paper yet.** The claim boundaries in Sections 11–12 should directly shape the paper's scope once written — a paper describing this as a "feasibility study with selective prediction on a documented, provenance-verified corpus" is fully supportable; a paper claiming a validated CWE-89 detector is not.
