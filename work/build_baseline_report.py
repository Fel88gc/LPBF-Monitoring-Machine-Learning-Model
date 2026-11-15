"""Build the Baseline v1 results addendum from completed, saved artifacts."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from html import escape
from pathlib import Path
from statistics import mean, median

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path.cwd().resolve()
BASE = ROOT / "reports/baseline_v1_2026-11-08"
ASSETS = BASE / "assets"
RUN = ROOT / "results/baseline_v1_2026-11-08/training"
PDF = BASE / "FYP_Baseline_v1_Results_2026-11-08.pdf"
for name, filename in [("Arial", "arial.ttf"), ("Arial-Bold", "arialbd.ttf"), ("Arial-Italic", "ariali.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(Path("C:/Windows/Fonts") / filename)))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-Bold")
styles = {
    "title": ParagraphStyle("Title", fontName="Arial-Bold", fontSize=25, leading=29, spaceAfter=12),
    "h1": ParagraphStyle("Heading", fontName="Arial-Bold", fontSize=17, leading=21, spaceAfter=12),
    "h2": ParagraphStyle("Subheading", fontName="Arial-Bold", fontSize=11, leading=15, spaceBefore=7, spaceAfter=6),
    "body": ParagraphStyle("Body", fontName="Arial", fontSize=10, leading=14, spaceAfter=9),
    "small": ParagraphStyle("Small", fontName="Arial", fontSize=8.5, leading=11.5, spaceAfter=7),
    "cell": ParagraphStyle("Cell", fontName="Arial", fontSize=8.3, leading=11),
    "header": ParagraphStyle("Header", fontName="Arial-Bold", fontSize=8.3, leading=11),
    "caption": ParagraphStyle("Caption", fontName="Arial", fontSize=8.5, leading=11.5, spaceBefore=5, spaceAfter=9),
}
LABELS = {"dummy_prior": "Dummy prior", "logistic_combined": "Logistic: combined", "random_forest_combined": "Random forest: combined", "logistic_visible": "Logistic: visible", "logistic_nir": "Logistic: NIR"}
story, figures = [], []


class Report(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, leftMargin=44, rightMargin=44, topMargin=46, bottomMargin=40,
                         title="FYP Baseline v1 Results", author="Felix", subject="Exploratory sensor prediction of provisional XCT annotation candidates")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id="Report", frames=[frame], onPage=self.chrome))
        self.sections = {}
    def chrome(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Arial", 7.7)
        canvas.setFillColor(colors.HexColor("#59656f"))
        canvas.drawString(44, A4[1]-26, "FYP | Baseline v1 results")
        canvas.drawRightString(A4[0]-44, A4[1]-26, "Exploratory | Candidate targets unvalidated")
        canvas.drawString(44, 22, "8 November 2026 | NUS Mechanical Engineering FYP")
        canvas.drawRightString(A4[0]-44, 22, str(doc.page))
        canvas.restoreState()
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("Heading", "Title"):
            title = flowable.getPlainText()
            key = f"section_{len(self.sections)+1}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, 0, False)
            self.sections[title] = self.page


def p(text, style="body"):
    return Paragraph(text, styles[style])
def para(text, style="body"):
    story.append(p(text, style))
def heading(text):
    para(text, "h1")
def sub(text):
    para(text, "h2")
def table(headers, rows, widths):
    data = [[p(escape(str(value)), "header") for value in headers]]
    data += [[p(escape(str(value)), "cell") for value in row] for row in rows]
    item = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    item.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e7edf2")),
        ("LINEBELOW", (0,0), (-1,0), .6, colors.HexColor("#9aa7b2")),
        ("LINEBELOW", (0,1), (-1,-1), .25, colors.HexColor("#d6dce1")),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story.extend([item, Spacer(1,8)])
def figure(filename, caption, maxheight=400):
    path = ASSETS / filename
    with PILImage.open(path) as im:
        width = 507
        height = width * im.height / im.width
    if height > maxheight:
        width *= maxheight / height
        height = maxheight
    image = Image(str(path), width=width, height=height)
    image.hAlign = "CENTER"
    number = len(figures) + 1
    figures.append({"number": number, "file": filename, "caption": caption})
    story.append(KeepTogether([image, p(f"<b>Figure {number}.</b> {caption}", "caption")]))
def page():
    story.append(PageBreak())
def load(path):
    return json.loads(path.read_text(encoding="utf-8"))
def rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))
def number(value, digits=3):
    return "-" if value is None or value == "" else f"{float(value):.{digits}f}"
def percent(value):
    return "-" if value is None or value == "" else f"{100*float(value):.1f}%"


def build():
    record = load(RUN / "run_record.json")
    assert record["status"] == "complete"
    summary = load(RUN / "results_summary.json")
    protocol = load(ROOT / "results/baseline_v1_2026-11-08/protocol/protocol.json")
    split = load(ROOT / "results/baseline_v1_2026-11-08/protocol/split_summary.json")
    verification = load(ROOT / "results/baseline_v1_2026-11-08/verification.json")
    assert verification["status"] == "passed"
    selected = record["selected_primary_method"]
    test = {row["method"]: row for row in summary["test"]}
    dev = {row["method"]: row for row in summary["development"]}
    main = test[selected]
    specimens = [row for row in rows(RUN / "test_per_specimen.csv") if row["method"] == selected]
    lifts = [float(row["average_precision"]) - float(row["prevalence"]) for row in specimens]
    aps = [float(row["average_precision"]) for row in specimens]
    mean_specimen_auc = mean(float(row["roc_auc"]) for row in specimens)
    zero_recall_parts = [f"P{row['part_id']}" for row in specimens if float(row["recall"]) == 0]
    sensitivities = [row for row in rows(RUN / "sensitivity_metrics.csv") if row["phase"] == "test" and row["method"] == selected]
    method_order = record["method_order"]

    # 1 - decision and stage.
    para("FYP Baseline v1\nResults", "title")
    para("Sensor images to provisional XCT annotation candidates", "h2")
    para("Results addendum | 8 November 2026 | One LPBF build", "small")
    sub("What has been achieved")
    para(f"The first reproducible baseline experiment is complete. <b>{LABELS[selected]}</b> was selected using development folds only. On 12 reserved specimens, its average precision (AP) is <b>{number(main['average_precision'])}</b>, compared with <b>{number(test['dummy_prior']['average_precision'])}</b> for the constant-prior comparator. This establishes an image-to-annotation association under the current extraction and target convention.")
    table(["Checkpoint", "Verified result"], [
        ["Prepared source", "329,828 patches; 64 fatigue specimens; layers 519-660; one build"],
        ["Supervised experiment", "323,280 provisional 0/1 rows; 6,548 unknown rows excluded"],
        ["Development / test", "262,369 rows on 52 specimens / 60,911 rows on 12 specimens"],
        ["Model inputs", "42 deterministic image-only descriptors; no XCT or identifying metadata"],
        ["Fixed threshold", "0.5; no held-out threshold tuning or model reselection"],
        ["Saved outputs", "5 final models; frozen splits; OOF and held-out predictions; metrics and figures"]], [137,370])
    sub("How to interpret this result")
    para(f"At threshold 0.5 the selected model has precision <b>{percent(main['precision'])}</b>, recall <b>{percent(main['recall'])}</b> and balanced accuracy <b>{percent(main['balanced_accuracy'])}</b>. These measure agreement with provisional patch annotations. Registration, XCT support and annotation validity remain unresolved scientific questions. The source preparation's validation flags remain false.")
    para(f"<b>The pooled score hides a substantial weakness.</b> P43/P59 contain 61.5% of test positives and contribute 93.4% of detected positives. Recall across the other ten specimens is only 10.8%. Mean within-specimen ROC AUC is {mean_specimen_auc:.3f}; {', '.join(zero_recall_parts)} have zero recall. The next priority is target review and nuisance diagnostics before extending the model.")
    para("The stage is now baseline development and evaluation complete. The earlier 24-page preparation report remains a historical checkpoint; this report adds the first model results.", "small")
    page()

    # 2 - protocol.
    heading("Frozen experiment and data separation")
    para("One observation is a 24 x 24 patch with visible post-melt, visible post-recoat and integrated-maximum NIR channels. Existing normalized sensor shards are read without changing their pixel values or candidate targets. All 64 specimen IDs receive exactly one fold.")
    table(["Fold", "Role", "Specimens", "Eligible rows", "Candidate 1", "Unknown"], [
        [item["fold_id"], item["role"], item["specimen_count"], f"{item['eligible_rows']:,}", f"{item['candidate_one']:,}", f"{item['candidate_unknown']:,}"]
        for item in split["fold_counts"]], [40,80,70,106,106,105])
    para("<b>Reserved specimens:</b> P4, P21, P33, P37, P43, P44, P49, P50, P57, P58, P59 and P65. Folds 1-4 provide four development validations; each validation excludes its specimens from fitting. StratifiedGroupKFold uses seed 20261108 and attempts class balance subject to the group constraint. [1]")
    sub("Features and models")
    para("Each channel contributes mean, population standard deviation, minimum, maximum, p10, median, p90, p99, zero fraction, one fraction, mean absolute horizontal and vertical differences, RMS gradient and normalized 16-bin entropy. Descriptor definitions use no learned statistics. Metadata, coordinates, layer, specimen identity, quality flags and every XCT field are excluded from predictors.")
    para("The primary suite is DummyClassifier(prior), StandardScaler plus LogisticRegression(C=1, balanced weights), and a random forest with 100 trees, depth at most 12, leaf size at least 20 and balanced bootstrap weights. Visible-only and NIR-only logistic models are fixed modality comparisons. Scaling is fitted within each training partition. [2,3]")
    sub("Selection and test policy")
    para("Primary selection uses mean AP across the four development folds. Ties within 0.0001 prefer dummy, logistic, then forest. The selected name is saved and hashed before the final five-model suite is refitted on development data and scored on fold 0. Threshold 0.5 is fixed. No hyperparameter search or post-test reselection was performed.")
    para("Quality-flagged eligible rows remain in the primary analysis. Two prespecified evaluation-only summaries remove constant-NIR or author acquisition-event rows from fixed predictions; neither refits a model. Unknown rows are retained in the feature export and split manifest, with no supervised target assignment.", "small")
    page()

    # 3 - all results.
    heading("Model comparison")
    figure("model_ap_comparison.png", "Development bars show mean fold AP with fold standard deviation (descriptive variation, not a confidence interval). Held-out bars summarize the fixed test suite. Only development results select the primary model.", 335)
    table(["Method", "Dev AP", "Test AP", "Bal. acc.", "Precision", "Recall", "F1"], [
        [LABELS[name], number(dev[name]["mean_fold_ap"]), number(test[name]["average_precision"]), percent(test[name]["balanced_accuracy"]), percent(test[name]["precision"]), percent(test[name]["recall"]), number(test[name]["f1"])]
        for name in method_order], [136,58,58,65,65,65,60])
    para(f"The primary model is <b>{LABELS[selected]}</b>, selected at development mean AP {number(dev[selected]['mean_fold_ap'])}. The two single-modality logistic models assess information in the available channels using identical specimen partitions. Their held-out scores remain descriptive comparisons, not grounds to reselect the primary model.")
    para("AP summarizes the precision-recall curve using the scikit-learn definition; it is not accuracy or trapezoidal PR area. The held-out candidate-positive fraction is 25.15%, so a constant score has AP approximately 0.252. The dummy's pooled development OOF AP may differ from development prevalence because its fitted prior varies between folds. [4]", "small")
    page()

    # 4 - PR.
    heading("Ranking performance on reserved specimens")
    figure("heldout_precision_recall.png", "Precision-recall curves for the five predeclared methods on the same 60,911 held-out patches. The horizontal comparator is this test set's candidate-positive prevalence. Curves describe candidate agreement, not independently verified physical defects.", 420)
    para(f"The selected model's held-out AP is <b>{number(main['average_precision'])}</b> and ROC AUC is <b>{number(main['roc_auc'])}</b>. AP is the primary measure because the candidate classes are uneven. ROC AUC is a secondary ranking view. Neither metric states how many false alerts occur at the chosen decision threshold.")
    para("The models use class weighting and no probability-calibration procedure. Their outputs are referred to as scores. A score of 0.8 should not be described as an 80% probability of a physical pore. A future operating threshold must be chosen using development data and a declared application cost, then evaluated under a new honest test plan.")
    page()

    # 5 - threshold + sensitivity.
    heading("Errors at the fixed threshold")
    figure("selected_primary_confusion.png", f"Confusion matrix for {LABELS[selected]} at score threshold 0.5. Reference classes are the provisional candidate annotations. Row percentages describe recall and specificity within each reference class.", 335)
    para(f"Of {main['positive']:,} candidate-positive patches, {main['tp']:,} are predicted positive and {main['fn']:,} are missed. Of {main['negative']:,} candidate-zero patches, {main['fp']:,} are predicted positive and {main['tn']:,} remain negative. These disagreements are model errors against the current annotation rule; they may also expose ambiguous reference cases.")
    table(["Fixed-prediction test subset", "Removed", "AP", "Bal. acc.", "Recall"], [
        [{"all_primary_rows":"All eligible test rows", "exclude_constant_nir_evaluation_only":"Exclude constant NIR", "exclude_author_event_evaluation_only":"Exclude author-event context"}[row["subset"]], row["excluded_rows"], number(row["average_precision"]), percent(row["balanced_accuracy"]), percent(row["recall"])] for row in sensitivities], [215,65,65,87,75])
    para("These checks quantify the two prespecified subsets without altering the fitted model. Small metric differences cannot establish that acquisition flags are harmless in general. Flag categories overlap and a contextual flag does not automatically mean an image is invalid.", "small")
    page()

    # 6 - per specimen.
    heading("Variation between held-out specimens")
    figure("selected_primary_per_specimen_ap.png", "AP and candidate prevalence are shown separately for every held-out specimen. Each specimen's own prevalence is the constant-score AP comparator. The pooled score is provided as a reference and can conceal local weaknesses.", 295)
    table(["Specimen", "Rows", "Candidate 1", "AP", "AP - prevalence", "Recall"], [
        [f"P{row['part_id']}", f"{int(row['n']):,}", percent(row["prevalence"]), number(row["average_precision"]), f"{float(row['average_precision'])-float(row['prevalence']):+.3f}", percent(row["recall"])] for row in specimens], [62,75,100,75,115,80])
    para(f"Across 12 specimens, median AP is {median(aps):.3f}; AP exceeds local prevalence in {sum(value > 0 for value in lifts)} of 12, with median gain {median(lifts):+.3f}. Mean within-specimen ROC AUC is {mean_specimen_auc:.3f}. P43/P59 supply 9,001 of 9,638 detected positives (93.4%); the other ten specimens have 637/5,902 positive recall (10.8%). This descriptive breakdown identifies weak local performance; it does not prove confounding or assume patch independence.", "small")
    page()

    # 7 - concrete image diagnostics.
    heading("Examples for reviewing model disagreements")
    figure("selected_primary_error_gallery.png", "Six deterministic examples from the saved held-out predictions: TP/TN and two FP/FN cases against provisional candidates. Images use fixed [0,1] display bounds, without per-patch contrast rescaling. These examples illustrate inputs and disagreements; they do not validate annotation correctness or show a direct XCT overlay.", 625)
    page()

    # 8 - reproducibility + next research step.
    heading("Reproducibility and the next experiment")
    sub("What was preserved and verified")
    para(f"The source HDF5 was not read for model fitting. Its size and modification time agree with the original checkpoint. All {len(record['original_files_hash_verified'])} tracked original small files retain their SHA-256 checksums. Prepared source, protocol and feature hashes match before and after training; all label and coverage validation flags remain false. The fit log reports no convergence warnings.")
    para(f"The runtime is Python {record['python']}, scikit-learn {record['sklearn']} and NumPy {record['numpy']}. Feature extraction took 49.1 seconds; model development, refitting and evaluation took {record['elapsed_seconds']:.1f} seconds. Compute was bounded to two numerical threads / forest workers. Independent verification checks saved partitions, metrics, model provenance and a deterministic sample of reproduced predictions. No new fit is performed by verification.")
    sub("Recommended next work")
    para("<b>1. Review the target policy.</b> Assemble a stratified visual audit of candidate-positive, candidate-zero and unknown patches across specimens and layers, including crop-boundary-sensitive cases and acquisition flags. Confirm the physical grid convention, usable XCT support and what the algorithmic flaw raster represents. Record decisions and uncertainty with a versioned target table.")
    para("<b>2. Diagnose what the baseline learned.</b> Use development data to investigate specimen, layer and spatial structure, with nuisance controls and reviewed image/XCT examples. The primary models do not receive specimen IDs, but sensor appearance may still encode processing conditions and location. Image association alone does not establish a local physical flaw mechanism.")
    para("<b>3. Define Baseline v2 before extending the model.</b> Keep this experiment as the reference. A revised target policy, added tuning, thresholds or CNN should be evaluated under a fresh declared protocol. Fold 0 has now been inspected and cannot continue to serve as untouched evidence for an adaptive model-development sequence. With only one build, cross-build transfer remains untested.")
    sub("Saved evidence and references")
    para("Project evidence: results/baseline_v1_2026-11-08/{protocol,training}; verification.json; data/features/baseline_v1_2026-11-08; models/baseline_v1_2026-11-08; src/modeling. Tables use original float64 scores; saved float32 tensors reproduce all decision counts, with ranking differences below 0.000001. This report is an exploratory results addendum, not a target-validation certificate.", "small")
    for text in [
        '[1] <link href="https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html">scikit-learn: StratifiedGroupKFold</link>. Group-disjoint folds and approximate stratification.',
        '[2] <link href="https://scikit-learn.org/stable/common_pitfalls.html">scikit-learn: Common pitfalls</link>. Training-only preprocessing and data leakage.',
        '[3] <link href="https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html">scikit-learn: RandomForestClassifier</link>; fixed full parameters are saved in protocol.json.',
        '[4] <link href="https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html">scikit-learn: average_precision_score</link>. AP definition and interpretation.']:
        para(text, "small")
    BASE.mkdir(parents=True, exist_ok=True)
    doc = Report(PDF)
    doc.build(story)
    assert doc.page == 8, f"Unexpected report pagination: {doc.page}"
    manifest = {"pdf": str(PDF), "pages": doc.page, "figures": figures, "sections": doc.sections,
                "selected_primary_method": selected, "test_rows": main["n"],
                "protocol_sha256": record["protocol_sha256"],
                "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
                "verification_source": str(ROOT / "results/baseline_v1_2026-11-08/verification.json")}
    (BASE / "report_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if PDF.exists() and not args.replace:
        raise FileExistsError(PDF)
    build()
