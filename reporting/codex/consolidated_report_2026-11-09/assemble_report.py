"""Author one coherent report from reviewed narrative and saved evidence."""
from pathlib import Path

SOURCE=Path('C:/NUS/FYP/FYP Organized')
THREAD=Path('C:/Users/Felix/Documents/Codex/2026-11-08/can')
WORK=Path(__file__).resolve().parent
old=(SOURCE/'work/integrated_report/build_integrated_report.py').read_text(encoding='utf-8')
brief=(THREAD/'work/development_diagnostics_2026-11-09/build_development_diagnostics_brief.py').read_text(encoding='utf-8')

def replace(a,b):
    global old
    assert a in old,a[:120]
    old=old.replace(a,b)

replace('ROOT=Path.cwd().resolve()',"ROOT=Path('C:/NUS/FYP/FYP Organized')\nWORK=Path(__file__).resolve().parent\nOUTPUT=Path('C:/Users/Felix/Documents/Codex/2026-11-08/can/outputs')")
replace("BASE=ROOT/'reports/fyp_integrated_2026-11-08'","BASE=WORK")
replace("PDF=BASE/'FYP_Data_Preparation_to_Baseline_Report_2026-11-08.pdf'","PDF=OUTPUT/'FYP_Consolidated_Progress_Report_2026-11-09.pdf'")
replace('KeepTogether\n','KeepTogether, Flowable\n')
replace("title='FYP: From Sensor Data to an Exploratory Baseline'","title='FYP Consolidated Progress: Data Preparation, Models and Scientific Review'")
replace("'FYP | Data preparation to baseline'","'FYP | Consolidated progress report'")
replace("'8 November 2026 | Prepared for Felix'","'9 November 2026 | Prepared for Felix'")

# Replace the opening with a current, concise account of all completed phases.
start=old.index('    # 1\n')
end=old.index('    # 2\n',start)
cover='''    # 1
    para('FYP Progress Report <br/>From Data Preparation <br/>to Models and Scientific Review','title')
    para('A self-contained account of the research question, decisions, evidence and next steps','subtitle')
    para('Snow LPBF dataset | Consolidated 9 November 2026 | One build','small')
    sub('Executive summary')
    para('The FYP asks whether visible and near-infrared images collected during metal printing contain useful local information about internal-flaw annotations measured by XCT afterward. The completed experiments predict provisional annotation candidates. Physical pore detection and cross-build transfer remain research questions.')
    para('Selected-source preparation produced <b>329,828 traceable three-channel patches from 64 fatigue specimens and 142 layers</b>. Final Baseline v1 models fitted <b>262,369 eligible patches from 52 development specimens</b>. The 12 other specimens supplied 60,911 test patches; 6,548 unknowns were excluded from supervision. Deterministic preparation of all rows was separate from learned model fitting. [E1-E4,E7]')
    para('The selected forest achieved held-out AP <b>0.782</b>, but local performance was weak: mean within-specimen AUC <b>0.576</b>, and recall across ten specimens other than P43/P59 was <b>10.8%</b>. Follow-up used development data only. There, a layer/position forest nearly matched sensor mean-fold AP (<b>0.711 versus 0.712</b>), while sensors retained stronger within-specimen AUC (<b>0.581 versus 0.539</b>). Broad context is informative; its cause is unresolved. [E5,E8]')
    para('Feature histograms and normal-reference plots reveal tails and specimen mixtures. A Gaussian distribution was not imposed. A <b>32-case development review packet</b> and bounded crop-sensitivity check are ready; human interpretation of correspondence, measured support and target meaning is pending. [E7-E9]')
    table(['Reader question','Current answer'],[
        ['What is complete?','Selected-source preparation, Baseline v1, development diagnostics and the review materials.'],
        ['What is still provisional?','Physical target/support validity, the intended Gaussian topic, and future validation evidence.'],
        ['Why Dinh and the three tools?','The literature motivates optical/CT comparison and local validation; software is useful only for a justified operation.'],
        ['What happens next?','Record a working target policy and test the added local information in sensor images under a declared protocol.']], [144,363])
    para('Reading guide: begin with pages 1-5. Chapters 21-28 explain the new development findings; chapters 29-33 cover tools, next steps, terminology and sources. Appendix A contains all 32 review cases. PDF bookmarks provide direct navigation.','small')
    page()

'''
old=old[:start]+cover+old[end:]

replace("figure('workflow.png'","figure('workflow_current.png'")
replace("'Completed source preparation and baseline work, with scientific validation still open. Mechanical consistency and physical target validity are separate checkpoints. [E1-E6]',440)","'Current evidence chain, including development-only diagnostics and the prepared scientific review packet. Completion of computations is distinct from physical target validation. [E1-E9]',470)")
replace("15 analytical tests; 380 independent metric comparisons","15 analytical tests; 380 baseline checks and 7,481 follow-up metric comparisons")

# Strengthen the literature bridge while retaining the original correct comparison.
paper_end="    para('The paper does not validate this FYP\\'s dimension-ratio crop mapping, support proxy, patch size, NIR channel, feature set or model results. Its classical image-processing workflow can motivate interpretable image descriptors, but it does not prescribe the 42 features used here. Full citation includes all three authors, including Yann Quinsat.')"
replace(paper_end,paper_end+"\n    para('Their global-versus-local limitation makes our within-specimen diagnostics relevant. Their Gaussian filtering is an image operation; our normal-reference plots describe statistical distributions. Neither establishes that these FYP features must be Gaussian.','small')")

# Add new, reviewed development narrative without the duplicate cover or closing page.
diag_start=brief.index('    # 2\n')
diag_end=brief.index('    # 10\n',diag_start)
new=brief[diag_start:diag_end]
for a,b in [
 ('1. What might Gaussian mean here?','21. What might Gaussian mean here?'),
 ('2. Development feature distributions','22. Development feature distributions'),
 ('3. Normal-reference quantiles','23. Normal-reference quantiles'),
 ('4. Specimen differences are substantial','24. Specimen differences are substantial'),
 ('5. Location/layer diagnostic comparators','25. Location/layer diagnostic comparators'),
 ('6. Local ranking and its limits','26. Local ranking and its limits'),
 ('7. Inspecting spatial patterns','27. Inspecting spatial patterns'),
 ('8. The scientific review packet is ready','28. The scientific review packet is ready')]:
    assert a in new;new=new.replace(a,b)
new=new.replace('[1]','[S9]').replace('[2,3]','[S10,S11]').replace('[4]','[S12]')
new=new.replace("A separate nine-page packet contains 32 development-only sensor/XCT cases.","Appendix A contains all 32 development-only sensor/XCT review cases.")
new=new.replace("A review template distinguishes correspondence, usable support, annotation meaning and sensor quality.","A companion review template distinguishes correspondence, usable support, annotation meaning and sensor quality. The 32 purposeful cases come from 24 development specimens and have 14 positive, 12 zero and six unknown candidate statuses; selection categories and candidate statuses are different summaries.")
new=new.replace("H('21. What might Gaussian mean here?')","H('21. What might Gaussian mean here?')\n    P('Distribution and model checks use eligible development patches only; the review packet also includes unknown development cases. The 12 Baseline v1 test specimens remain excluded. Saved model groups and development-only logistic scaler statistics have been audited. [E7-E9]')")
new=new.replace("A Gaussian (normal) distribution is the familiar symmetric bell curve, described by a mean and standard deviation.","A Gaussian (normal) distribution is the symmetric bell curve, described by a mean and standard deviation.")
setup='''    # Current follow-up sources; no new fitting or score generation.
    DIAG=ROOT/'results/development_diagnostics_v1_2026-11-08'
    audit=load(DIAG/'split_audit.json')
    dist=load(DIAG/'distributions/summary.json')
    nuisance=load(DIAG/'nuisance/summary.json')
    checks=load(DIAG/'review/machine_checks.json')
    independent=load(DIAG/'independent_verification.json')
    assert audit['status']=='passed' and independent['status']=='passed'
    assert dist['rows']==262369 and nuisance['test_rows_fitted_or_scored']==0 and not checks['test_fold_selected']
    methods={r['method']:r for r in nuisance['methods']}
    stats={r['feature']:r for r in rows(DIAG/'distributions/feature_summary.csv')}
    variance={r['feature']:r for r in rows(DIAG/'distributions/variance_decomposition.csv')}
    names={'sensor_logistic':'Sensor logistic','sensor_random_forest':'Sensor forest','metadata_logistic':'Layer/position logistic','metadata_random_forest':'Layer/position forest'}
    channels=[('visible_melt_mean','Visible post-melt'),('visible_recoat_mean','Visible post-recoat'),('nir_max_mean','NIR maximum')]
    P,H,S,T,F,PAGE=para,heading,sub,table,figure,page

'''
new=new.replace('RESULT/','DIAG/')
insertion=old.index('    # 22\n')
old=old[:insertion]+setup+new+old[insertion:]

for a,b in [
 ('21. Could the suggested tomography tools help?','29. Could the suggested tomography tools help?'),
 ('22. What to do next, and what it will produce','30. What to do next, and what it will produce'),
 ('23. A short glossary for reading this work','31. A short glossary for reading this work')]:replace(a,b)

replace("The next phase should improve the scientific meaning of the result before increasing model complexity. We already have a reproducible reference baseline and a clear weakness to investigate.","The completed diagnostic phase provides a clear next question: what local sensor information is added beyond layer and position? A finite review packet is ready. The next phase should record a defensible working target convention and test that incremental information, with remaining uncertainty stated explicitly.")
replace("['Build a stratified visual audit','Inspect ordinary, uncertain, edge and acquisition-flagged cases across specimens/layers','A traceable image/XCT review pack with reviewed outcomes and unresolved cases; not only model-selected examples']","['Interpret the prepared review packet','32 purposeful development cases and machine checks are ready; physical interpretation is pending','Recorded outcomes and unresolved cases with source evidence; no forced labels or population-accuracy claim']")
replace("['Diagnose development-set nuisance structure','Strong between-specimen separation may conceal weak local information','Development-only comparisons/controls for specimen, layer and location structure; a clear account of what the baseline can distinguish']","['Test added sensor information','Layer/position alone nearly matches pooled development AP, while sensor ranking is locally stronger','A declared context-only versus sensor-only versus combined comparison; assess both pooled and local results']")
replace("We are using visible and NIR images from a metal-printing process to study whether they contain information about XCT flaw annotations. We prepared the selected source into traceable patches, retained uncertain cases explicitly and trained simple models with whole specimens held out. The first model ranks the pooled candidate population well, but detects few positives in most held-out specimens. The next work is to validate the target convention and understand that local-performance weakness.","We are studying whether visible and NIR printing images contain local information about XCT flaw annotations. Selected-source preparation and the first baseline are complete, with whole specimens separated during evaluation. Development diagnostics show strong specimen mixtures and substantial prediction from layer/position alone. Sensors retain modestly stronger local ranking. A 32-case review packet is prepared; the next work records a working target policy and tests the added value of local image structure.")

# Replace the prior compact reference page with a fuller evidence ledger and bibliography.
ref_start=old.index('    # 25\n')
ref_end=old.index('    BASE.mkdir',ref_start)
refs='''    # Evidence ledger and bibliography.
    heading('32. Evidence and reproducibility')
    para('All numerical results come from saved, versioned source preparation, Baseline v1 or development-only diagnostics. Creating this report introduces no new training, target revision or tomography processing. Code, tables, selected case identities and checksums remain inspectable.')
    table(['Evidence ID','Source and scope'],[
        ['E1: selected source','data/cleaned/snow_source_preparation_v1: source_config.json, production_summary.json and catalog summaries; 329,828 rows / 64 specimens / layers 519-660'],
        ['E2: patch trace','Canonical catalog/manifest.csv, per-layer features.npz shards and report source-example provenance; exact camera/XCT bounds retained'],
        ['E3: descriptors','data/features/baseline_v1_2026-11-08: 42-feature arrays, dictionary, metadata and source hashes'],
        ['E4: frozen v1 protocol','results/baseline_v1_2026-11-08/protocol: specimen partitions, eligibility, model settings and hashes'],
        ['E5: v1 results','Baseline training outputs, model artifacts and held-out/per-specimen metrics; five final development-only refits'],
        ['E6: v1 verification','Baseline verification.json; feature/metric tests and 380 independent metric comparisons'],
        ['E7: follow-up scope/distributions','development_diagnostics_v1_2026-11-08: split_audit.json and distributions; 262,369 eligible development rows only'],
        ['E8: context diagnostics','nuisance: fixed layer/Y/X protocol, eight development fits, saved OOF scores and local metrics; independent_verification.json reproduces 7,481 comparisons'],
        ['E9: review material','review: 32 selected records, selection provenance, machine checks, crop-policy tables and pending human-review template']], [111,396])
    para('Paths above are relative to the FYP project root; follow-up result folders are under results. The master report and its output copies are delivered in Documents/Codex. Original project inputs, model files and earlier reports are preserved. Appendix panels retain source IDs and use documented display bounds. The PDF removes only an already clipped chart footer and re-typesets the same display/validation caveats; all case image panels remain visible.','small')
    sub('Computation is checked; scientific interpretation is separate')
    para('Baseline v1 uses Python 3.11.4, NumPy 2.4.6 and scikit-learn 1.9.1. Feature extraction took 49.112 seconds; baseline fitting/refitting/evaluation 182.094 seconds. The metadata diagnostic fits took 79.813 seconds. New diagnostic statistics and fits exclude fold 0. Independent follow-up checks reproduce AP/AUC at machine precision and exact decision counts. These checks do not establish physical target truth.','small')
    para('Stored v1 predictions are float32 while some original metric tables use float64 estimator scores; reproduced ranking differences are below 0.000001. New context-control scores are float64. No patch-independent confidence intervals or formal normality tests are claimed. The Q-Q subset uses saved (rank-0.5)/N normal quantiles, not a different software plotting-position convention.','small')
    page()

    heading('33. Literature and software references')
    references=[
        ('S1','Z. Snow et al. (2025). In situ Visible Light and Thermal Imaging Data from a Laser Powder Bed Fusion Additive Manufacturing Process Co-Registered to X-ray Computed Tomography and Fatigue Data. ORNL. Supplied README.','https://doi.org/10.13139/ORNLNCCS/2524534'),
        ('S2','Snow dataset Methods, supplied Snow_Methods.docx. Build design, imaging calibration, XCT reconstruction/registration, annotation detector and fatigue context.',None),
        ('S3','D. M. Dinh, N. Muller and Y. Quinsat (2021). Layering Defects Detection in Laser Powder Bed Fusion using Embedded Vision System. Computer-Aided Design & Applications 18(5), 1111-1118. Supplied eight-page paper.','https://doi.org/10.14733/cadaps.2021.1111-1118'),
        ('S4','scikit-learn: specimen/group-separated cross-validation.','https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data'),
        ('S5','scikit-learn: average_precision_score. AP definition and ranking interpretation.','https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html'),
        ('S6','TomoPy: reconstruction API. Projection data, projection angles and reconstruction conventions.','https://tomopy.readthedocs.io/en/stable/api/tomopy.recon.algorithm.html'),
        ('S7','Algotom: postprocessing of reconstructed datasets, including statistics and reslicing.','https://algotom.readthedocs.io/en/latest/toc/api/algotom.post.postprocessing.html'),
        ('S8','ASTRA Toolbox: explicit 3D volume and projection geometries.','https://astra-toolbox.com/docs/geom3d.html'),
        ('S9','NIST Engineering Statistics Handbook: normal distribution.','https://www.itl.nist.gov/div898/handbook/eda/section3/eda3661.htm'),
        ('S10','scikit-learn: StandardScaler. Training means/scales and affine standardization.','https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html'),
        ('S11','scikit-learn: logistic regression. Binary conditional model.','https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression'),
        ('S12','SciPy: Gaussian filtering. A spatial image operation, distinct from statistical normality.','https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.gaussian_filter.html'),
        ('S13','scikit-learn: common pitfalls and data leakage. Training-only learned preprocessing and test separation.','https://scikit-learn.org/stable/common_pitfalls.html#data-leakage'),
    ]
    for ident,text,url in references:
        text=f'[{ident}] {escape(text)}'
        if url:text+=f' <link href="{url}" color="#2464A1">Source link</link>.'
        overview={'S6':'https://tomopy.readthedocs.io/en/stable/','S7':'https://algotom.readthedocs.io/en/latest/','S8':'https://astra-toolbox.com/'}.get(ident)
        if overview:text+=f' <link href="{overview}" color="#2464A1">Tool overview</link>.'
        para(text,'small')
    para('Official documentation and supplied-paper claims were checked for this consolidation on 9 November 2026. Tool relevance is a project-specific inference from current inputs and documented capabilities. No publisher figure is presented as original FYP evidence. The supplied Dinh paper is the primary reading source when its DOI is inaccessible.','small')
    page()

    # Appendix A: the complete, machine-checked development review set.
    for i in range(1,9):
        heading(f'Appendix A{i}. Development cases R{4*i-3:02d}-R{4*i:02d}')
        review_figure(f'review_{i:02d}.png')
        if i<8:page()

'''
old=old[:ref_start]+refs+old[ref_end:]
replace("assert doc.page==25, f'Unexpected pagination: {doc.page}'","assert doc.page==42, f'Unexpected pagination: {doc.page}'")
replace("(ROOT/'work/integrated_report/narrative.txt')","(WORK/'narrative.txt')")

# Preserve all panels in the review charts and typeset their footer in PDF.
helpers='''
class ReviewChart(Flowable):
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
    caption=('Sensors: fixed [0,1]. XCT: fixed stored uint16 range [0,65535]. White mask pixels indicate nonzero annotations. '
             'Dark grayscale appearance alone does not establish absent flaws or missing support. Human scientific review remains pending. [E9]')
    number=len(figures)+1;figures.append({'number':number,'file':name,'caption':caption})
    story.append(KeepTogether([ReviewChart(ASSETS/name),p(f'<b>Figure {number}.</b> '+caption,'caption')]))
    reading_text.append(f'Figure {number}. '+caption)


'''
idx=old.index('def build():')
old=old[:idx]+helpers+old[idx:]
replace('"""Build the source-preparation-to-baseline FYP narrative, without the pilot."""','"""Build the consolidated full-source FYP progress report from reviewed evidence."""')
(WORK/'build_consolidated_report.py').write_text(old,encoding='utf-8')
print(WORK/'build_consolidated_report.py')
