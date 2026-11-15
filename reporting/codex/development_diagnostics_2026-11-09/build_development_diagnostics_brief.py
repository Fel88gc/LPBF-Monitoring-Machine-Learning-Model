"""Create a development-only findings brief and a separate pending-review packet."""
from pathlib import Path
import csv
import hashlib
import json
import sys
from collections import Counter

ROOT=Path('C:/NUS/FYP/FYP Organized')
DELIVERY_ROOT=Path('C:/Users/Felix/Documents/Codex/2026-11-08/can')
WORK=DELIVERY_ROOT/'work/development_diagnostics_2026-11-09'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'work/integrated_report'))
import build_integrated_report as layout
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Flowable, KeepTogether
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage

BASE=DELIVERY_ROOT/'outputs'
RESULT=ROOT/'results/development_diagnostics_v1_2026-11-08'
layout.BASE=BASE;layout.ASSETS=WORK/'assets'
P=layout.para;H=layout.heading;S=layout.sub;T=layout.table;F=layout.figure;PAGE=layout.page


class Brief(layout.Report):
    label='Development-only diagnostics'
    def chrome(self,canvas,doc):
        canvas.saveState();canvas.setFont('Arial',7.6);canvas.setFillColor(colors.HexColor('#617181'))
        canvas.drawString(44,A4[1]-26,'FYP | '+self.label)
        canvas.drawRightString(A4[0]-44,A4[1]-26,'Fold 0 excluded | Candidate targets provisional')
        canvas.drawString(44,22,'9 November 2026 | Prepared for Felix')
        canvas.drawRightString(A4[0]-44,22,str(doc.page));canvas.restoreState()


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def rows(path):
    with Path(path).open(newline='',encoding='utf-8') as stream:return list(csv.DictReader(stream))


class ReviewChart(Flowable):
    """Place a chart's complete panels, replacing only its clipped footer in PDF."""
    def __init__(self,path):
        super().__init__();self.path=path
        with PILImage.open(path) as image:self.full_height=507*image.height/image.width
        self.width=507;self.height=self.full_height*.92
    def draw(self):
        c=self.canv;c.saveState();clip=c.beginPath();clip.rect(0,0,self.width,self.height)
        c.clipPath(clip,stroke=0,fill=0)
        c.drawImage(str(self.path),0,self.height-self.full_height,width=self.width,height=self.full_height)
        c.restoreState()


def review_figure(name):
    path=layout.ASSETS/name
    caption=('Sensors: fixed [0,1]. XCT: fixed stored uint16 range [0,65535]. White mask pixels indicate nonzero annotations. '
             'Dark grayscale appearance alone does not establish absent flaws or missing support. Physical review remains pending.')
    number=len(layout.figures)+1
    layout.figures.append({'number':number,'file':name,'caption':caption,'pdf_layout':'Complete chart panels retained; original bottom 8% footer is clipped and re-typeset as this caption.'})
    layout.story.append(KeepTogether([ReviewChart(path),layout.p(f'<b>Figure {number}.</b> '+caption,'caption')]))
def save_pdf(name,title,expected_pages):
    pdf=BASE/name
    doc=Brief(pdf);doc.title=title;doc.build(layout.story)
    assert doc.page==expected_pages,(name,doc.page)
    result={'file':name,'pages':doc.page,'figures':list(layout.figures),'sections':dict(doc.sections),
            'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()}
    layout.story.clear();layout.figures.clear();layout.reading_text.clear()
    return result


def build():
    audit=load(RESULT/'split_audit.json')
    dist=load(RESULT/'distributions/summary.json')
    nuisance=load(RESULT/'nuisance/summary.json')
    checks=load(RESULT/'review/machine_checks.json')
    selection=load(RESULT/'review/selection_provenance.json')
    independent=load(RESULT/'independent_verification.json')
    assert independent['status']=='passed'
    assert audit['status']=='passed' and dist['rows']==262369 and checks['cases']==32
    assert nuisance['test_rows_fitted_or_scored']==0 and checks['test_fold_selected'] is False
    methods={r['method']:r for r in nuisance['methods']}
    stats={r['feature']:r for r in rows(RESULT/'distributions/feature_summary.csv')}
    variance={r['feature']:r for r in rows(RESULT/'distributions/variance_decomposition.csv')}
    names={'sensor_logistic':'Sensor logistic','sensor_random_forest':'Sensor forest',
           'metadata_logistic':'Layer/position logistic','metadata_random_forest':'Layer/position forest'}
    channels=[('visible_melt_mean','Visible post-melt'),('visible_recoat_mean','Visible post-recoat'),('nir_max_mean','NIR maximum')]

    # 1
    P('Training, Gaussian Distributions<br/>and the Next FYP Evidence','title')
    P('Development-only follow-up to Baseline v1','subtitle')
    S('Was the baseline trained on the whole dataset?')
    P('<b>No.</b> The five saved final models were fitted on 52 development specimens only. Twelve separate specimens were reserved for Baseline v1 testing. All specimens stayed in exactly one fold. Unknown targets did not enter supervised fitting or scores.')
    T(['Population','Patches','Specimens','Role'],[
        ['Prepared source','329,828','64','Selected layers 519-660 of 1,117; deterministic image features'],
        ['Eligible candidates','323,280','64','Provisional candidate 0/1 population'],
        ['Final model fitting','262,369','52','Development folds 1-4 only'],
        ['Reserved Baseline v1 test','60,911','12','Excluded from fitting; already evaluated for v1'],
        ['Unknown candidates','6,548','Across both partitions','Retained without supervised target assignment']], [133,81,75,218])
    P('During four development validations, each model trained on three development folds and validated on the fourth. Final refits used all four development folds. The saved logistic scalers each saw 262,369 training rows, and their means independently match those development features.')
    P('Preparing deterministic features for all rows is distinct from fitting a model or estimating learned scaling parameters. Feature extraction fitted no population statistics. The split audit checks frozen hashes, model training-specimen metadata, fit-code masks and final scaler statistics; it does not claim that tree objects independently reveal source identities.')
    S('What has happened to the test set?')
    P('The 12 test specimens were held out of fitting, but their v1 results have now been inspected. They remain excluded from this follow-up. Reusing their results to guide adaptations cannot be called fresh testing. This round analyzes development specimens only; stronger future confirmation needs appropriately unused evidence.')
    PAGE()

    # 2
    H('1. What might Gaussian mean here?')
    P('The professor\'s intended meaning is still unknown. We therefore performed a useful descriptive feature-distribution check without changing data or assuming what was requested. A Gaussian (normal) distribution is the familiar symmetric bell curve, described by a mean and standard deviation. [1]')
    T(['Possible meaning','Relevance','Approach'],[
        ['Distribution of sensor values/features','Describe the population, tails and mixtures across specimens/classes','Histograms and normal-reference quantiles using development rows'],
        ['Distribution of defect size, porosity or measurement errors','A different quantity and unit of analysis','Clarify which measurement is intended; annotation-pixel counts are not physical pore sizes'],
        ['Gaussian smoothing or Laplacian-of-Gaussian','An image operation/detector, different from a normality claim','The dataset authors already use LoG in flaw detection; no new smoothing is applied'],
        ['A Gaussian statistical model or quality limit','Would introduce its own assumptions and purpose','Specify the model/measurement and justify assumptions before fitting or setting cutoffs']], [135,191,181])
    S('Does the baseline need Gaussian inputs?')
    P('The logistic classifier models a binary conditional outcome, while the forest uses decision-tree partitions. Neither requires every input feature to be normally distributed. The logistic StandardScaler centers and rescales each feature using training data; this affine operation does not turn a skewed or multimodal distribution into a Gaussian. [2,3]')
    P('Gaussian image smoothing weights neighboring pixels with a Gaussian kernel; it does not establish that image intensities follow a normal distribution. Its use would alter the images and needs a specific image-quality purpose. [4]')
    P('No normality p-values, three-sigma deletions, distribution transformations or Gaussian filtering were used. Neighboring patches/layers are correlated, and the data mix specimens; a very large patch count alone does not supply independent statistical evidence.')
    PAGE()

    # 3
    H('2. Development feature distributions')
    F('distribution_channel_means_print.png','Pooled and class-conditional distributions of patch mean intensity, not individual-pixel histograms. Each displayed histogram is normalized within its population. Dashed normal references use pooled mean and population SD; they are descriptive curves, not fitted model requirements.',320)
    T(['Patch-mean feature','Mean','SD','Skew','Excess kurtosis'],[
        [label,f"{float(stats[name]['mean']):.5f}",f"{float(stats[name]['std_population']):.5f}",f"{float(stats[name]['skew_population']):.3f}",f"{float(stats[name]['excess_kurtosis_population']):.3f}"] for name,label in channels], [177,82,82,80,86])
    P('The post-melt mean has a right tail. Post-recoat means have a narrow center and important tail departures. NIR means show substantial mixture, including a high-value population enriched in candidate-positive patches. A single pooled bell curve is an incomplete description of these data.')
    P('This does not identify a physical cause. A class-separated histogram may reflect local flaws, process conditions, specimen identity encoded in appearance, support/annotation effects or a combination. All 42 descriptors also have saved pooled, class and specimen summaries. Two development endpoint-fraction features are constant zero and were retained.')
    PAGE()

    # 4
    H('3. Normal-reference quantiles')
    F('distribution_normal_qq_print.png','Normal-reference quantile plots for the same specimen-balanced display subset: 200 systematic eligible rows from each of 52 development specimens, 10,400 rows total. Original values remain unchanged. Reference moments are calculated on this display subset.',335)
    P('The horizontal axis gives quantiles of a normal reference; the vertical axis gives the ordered observed values. A distribution closely matching that reference would follow the dashed line. Curvature and tail departures show where that approximation is weak. These plots do not test the physical validity of candidate targets.')
    P('The subset is deterministic and balances the number of rows per specimen. It is not an independent random sample of 10,400 experiments. Quantile positions are (rank - 0.5)/N and the theoretical values use the subset mean and population SD. This construction is explicitly saved, rather than using a normality-test p-value.')
    S('What should we do with this result?')
    P('Describe mixtures and tails first. Consider a transform only if a specific model or scientific measurement requires it, fit any learned transformation within training folds and compare it on development data. Outlying values can contain real process information; departure from a bell curve is not a deletion rule.')
    PAGE()

    # 5
    H('4. Specimen differences are substantial')
    F('distribution_variance_components_print.png','Patch-weighted variance decomposition across 52 development specimens. Variation around specimen means and variation in those means sum to the total. This does not assign a causal explanation to material defects or process settings.',350)
    T(['Patch-mean feature','Within-specimen variance','Between-specimen mean variance'],[
        [label,f"{100*float(variance[name]['within_fraction']):.2f}%",f"{100*float(variance[name]['between_fraction']):.2f}%"] for name,label in channels], [207,150,150])
    P('For NIR patch means, 74.43% of development variance is the weighted between-specimen component. This arithmetic decomposition separates variation around each specimen mean from variation in those specimen means; it does not show that specimen conditions cause a model prediction.')
    P('It explains why interpreting a pooled intensity histogram as one homogeneous population can be misleading. The useful next question is whether local sensor patterns add information once broad location/layer structure is considered. All percentages use the current development patch population, not equal weighting of specimens.')
    PAGE()

    # 6
    H('5. Location/layer diagnostic comparators')
    F('nuisance_overview_readable.png','Four development-only comparisons on identical eligible folds. Sensor results reuse saved out-of-fold predictions; only the layer/position logistic and forest diagnostics were newly fitted. Error bars are fold SD, not confidence intervals.',305)
    T(['Method','Mean fold AP','Mean within-specimen AUC','Pooled recall'],[
        [names[name],f"{methods[name]['mean_fold_ap']:.3f}",f"{methods[name]['mean_specimen_roc_auc']:.3f}",f"{100*methods[name]['pooled_recall']:.1f}%"] for name in names], [172,100,140,95])
    P('The metadata forest uses only source layer and absolute camera Y/X. Its mean fold AP is 0.711, close to 0.712 for the sensor forest. Thus broad spatial/layer information can reproduce much of the pooled candidate separation under this fixed development experiment.')
    P('The sensor forest has higher mean within-specimen AUC: 0.581 versus 0.539 for the metadata forest. This suggests modest additional local ranking information, while leaving substantial room for improvement. These are descriptive comparisons, not proof of confounding, statistical equivalence or physical pore detection. The metadata model is a diagnostic comparator, not a replacement for the intended sensor predictor.')
    PAGE()

    # 7
    H('6. Local ranking and its limits')
    F('nuisance_per_specimen_difference_readable.png','Per-specimen difference between the sensor and metadata forest using saved development-only out-of-fold scores. Specimens have equal weight in the macro AUC summaries; results remain within one build.',350)
    conditional=nuisance['conditional_sensor_forest']
    T(['Within specimen/layer diagnostic','Result'],[
        ['Observed development specimen/layer blocks',f"{conditional['total_blocks']:,}"],
        ['Blocks containing both candidate classes',f"{conditional['both_class_blocks']:,} / {conditional['rows_in_both_class_blocks']:,} rows"],
        ['Single-class blocks omitted from ranking',f"{conditional['single_class_blocks_excluded_from_ranking']:,} / {conditional['rows_in_single_class_blocks']:,} rows"],
        ['Mean AUC within eligible two-class blocks',f"{conditional['mean_within_block_roc_auc']:.3f}"]], [315,192])
    P('Even after conditioning on specimen and layer, sensor ranking is modest. Single-class blocks have no meaningful positive-versus-negative AUC and are explicitly counted rather than assigned artificial scores. Nearby blocks/patches are dependent, so these summaries have no patch-independent confidence intervals. Small-block AP minus prevalence is not interpreted as a significance or chance test.')
    PAGE()

    # 8
    H('7. Inspecting spatial patterns')
    F('nuisance_spatial_maps.png','Predeclared development specimens P2, P3, P35 and P60 at layer 600. Compare candidate maps with sensor-forest and location/layer-forest scores. These are development out-of-fold predictions; no test specimen or fresh sensor fit is used.',560)
    P('Maps make it easier to see broad score fields and localized differences. They are evidence for inspection, not proof that a candidate marks a physical pore. Boundary selection and the current support proxy remain part of the experimental target convention.','small')
    PAGE()

    # 9
    H('8. The scientific review packet is ready')
    P('A separate nine-page packet contains 32 development-only sensor/XCT cases. It includes ordinary cases and difficult categories without selecting cases by model errors. Machine consistency checks pass; human/scientific interpretation remains pending.')
    T(['Selection category','Cases'],[
        ['Ordinary candidate-positive',6],['Ordinary candidate-zero',6],['Unknown',6],['Part-boundary selection',6],['Author-event context',4],['Constant NIR',4]], [365,142])
    P('Each record retains its source identity, fold, camera position, exact candidate XCT bounds and quality fields. Sensor images use fixed [0,1] bounds. XCT grayscale uses the common uint16 stored range [0,65535]; it can look dark and is not calibrated attenuation. A review template distinguishes correspondence, usable support, annotation meaning and sensor quality.')
    T(['Crop convention on these 32 cases','Changed annotation counts','Changed candidate status'],[
        ['Rounded reference','0','0'],['Floor starts / ceil ends','4','0'],['Floor all boundaries','4','0']], [270,121,116])
    P('No candidate status changed among these 32 purposeful cases, while four annotation counts changed under each alternative. This is a bounded sensitivity check, not a full-source stability estimate or validation of the rounded convention. No policy was selected by model AP, no original target was changed and unknowns remain unknown.')
    P('The packet is ready for a focused scientific discussion. Mark cases as supported, unsupported or uncertain with evidence; do not treat the software checks as completed physical validation. The companion questions draft includes the unresolved meaning of Gaussian and the grid/support/annotation questions.')
    PAGE()

    # 10
    H('9. What this changes about the next step')
    P('The new evidence narrows the FYP task: retain the current baseline, establish a defensible working reference convention, and test whether local image structure adds useful information beyond broad context. The work can progress with explicit uncertainty rather than waiting for every label to become perfect.')
    T(['Next decision','Evidence needed / proposed action'],[
        ['Meaning of Gaussian','Ask which quantity and purpose the professor meant; the descriptive distributions are available now'],
        ['Target interpretation','Review the 32-case packet and source definitions; document supported conventions and unresolved cases'],
        ['Added sensor information','Consider a declared development comparison of context-only, sensor-only and context-plus-sensor predictors'],
        ['Spatial model extension','A modest CNN could test information discarded by image summaries, once the target/evaluation convention is recorded'],
        ['Evaluation claim','Keep Baseline v1 test history intact; development CV does not create new external-build evidence']], [143,364])
    S('Evidence and reproducibility')
    P('New results: results/development_diagnostics_v1_2026-11-08/{split_audit.json,distributions,nuisance,review,independent_verification.json}. New analysis scripts are in src/diagnostics. The review CSV is human_review_template.csv. No source inputs, baseline models, test predictions or prior report files were overwritten.','small')
    P('Eight metadata diagnostic fits used four development folds; existing sensor models were not refitted. The professor\'s intended Gaussian topic remains unknown. No Gaussian image operation, distribution transform, outlier deletion, target revision or CNN was applied in this phase.','small')
    refs=[
        '[1] <link href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda3661.htm">NIST: Normal distribution</link>. Parameters and normal-reference interpretation.',
        '[2] <link href="https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html">scikit-learn: StandardScaler</link>. Training means/scales and affine standardization.',
        '[3] <link href="https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression">scikit-learn: Logistic regression</link>. Binary conditional model and regularization.',
        '[4] <link href="https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.gaussian_filter.html">SciPy: Gaussian filtering</link>. A spatial operation, separate from normality.',
        '[5] <link href="https://scikit-learn.org/stable/common_pitfalls.html#data-leakage">scikit-learn: Data leakage</link>. Training-only transformations and test separation.',
    ]
    for text in refs:P(text,'small')
    result1=save_pdf('FYP_Development_Diagnostics_2026-11-09.pdf','FYP Development Diagnostics: Training Split and Gaussian Distributions',10)

    # Separate packet: one orientation page and eight four-case sheets.
    Brief.label='Sensor/XCT scientific review'
    P('32 Development Cases<br/>for Scientific Review','title')
    P('Sensor images, candidate XCT crops and pending interpretation','subtitle')
    P('This packet contains development specimens only. Candidate annotations remain provisional. The 12 Baseline v1 test specimens are excluded from selection. No model error scores were used to choose the examples.')
    T(['Purposeful selection category','Count'],[
        ['Ordinary candidate-positive / candidate-zero','6 / 6'],['Unknown / part-boundary cases','6 / 6'],['Author-event / constant-NIR cases','4 / 4']], [365,142])
    S('How to read the case sheets')
    P('Each row has three sensor channels, the mapped reconstructed XCT grayscale and a binary display of the author flaw annotation. The case ID links to selected_catalog_records.csv and human_review_template.csv. Coordinates are source camera-grid Y/X; the exact XCT crop bounds are retained in the selected records.')
    P('Sensor display bounds are fixed at [0,1]. XCT display uses [0,65535] stored uint16 values, not a separate contrast stretch per case or calibrated attenuation. Low-contrast details may need a separately documented inspection view; darkness alone does not establish absent flaws or missing measurements.')
    S('What to record')
    P('For each case, record whether the proposed correspondence is supported, whether measured XCT support is established, how the annotation should be interpreted and whether a sensor-quality issue needs action. Keep uncertain cases explicit and cite source or review evidence. Machine agreement with the current extraction rule does not answer those physical questions.')
    P('The current rounded rule reproduces all 32 selected records. Alternative floor/ceil and floor-only crops each change four annotation counts but zero candidate statuses in this selected set. This does not justify a full-source invariance claim or select the correct physical mapping.')
    P('All human review fields are pending. This is an initial purposeful review set, not a random accuracy audit or prevalence estimate. A discussion-questions draft is saved alongside the report.','small')
    PAGE()
    for i in range(1,9):
        H(f'Case sheet {i}: R{4*i-3:02d}-R{4*i:02d}')
        review_figure(f'review_{i:02d}.png')
        if i<8:PAGE()
    result2=save_pdf('FYP_Development_Review_Packet_2026-11-09.pdf','FYP Development Sensor and XCT Review Packet',9)
    (WORK/'deliverable_manifest.json').write_text(json.dumps({'artifacts':[result1,result2],'scope':'development only; fold0 excluded','source_results':str(RESULT),'targets_changed':False},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'artifacts':[{k:r[k] for k in ['file','pages','sha256']} for r in [result1,result2]]},indent=2))


if __name__=='__main__':build()
