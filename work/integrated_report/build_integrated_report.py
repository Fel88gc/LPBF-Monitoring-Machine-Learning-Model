"""Build the source-preparation-to-baseline FYP narrative, without the pilot."""
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

ROOT=Path.cwd().resolve()
BASE=ROOT/'reports/fyp_integrated_2026-11-08'
ASSETS=BASE/'assets'
PDF=BASE/'FYP_Data_Preparation_to_Baseline_Report_2026-11-08.pdf'
CAT=ROOT/'data/cleaned/snow_source_preparation_v1/catalog'
RUN=ROOT/'results/baseline_v1_2026-11-08/training'
for name,filename in [('Arial','arial.ttf'),('Arial-Bold','arialbd.ttf'),('Arial-Italic','ariali.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/filename)))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial-Italic',boldItalic='Arial-Bold')
STYLES={
 'title':ParagraphStyle('Title',fontName='Arial-Bold',fontSize=25,leading=29,spaceAfter=13,textColor=colors.HexColor('#18334b')),
 'subtitle':ParagraphStyle('Subtitle',fontName='Arial',fontSize=12.5,leading=17,spaceAfter=12),
 'h1':ParagraphStyle('Heading',fontName='Arial-Bold',fontSize=17,leading=21,spaceAfter=12,textColor=colors.HexColor('#18334b')),
 'h2':ParagraphStyle('Subheading',fontName='Arial-Bold',fontSize=11.2,leading=15,spaceBefore=8,spaceAfter=6),
 'body':ParagraphStyle('Body',fontName='Arial',fontSize=10.1,leading=14.3,spaceAfter=9),
 'small':ParagraphStyle('Small',fontName='Arial',fontSize=8.6,leading=11.6,spaceAfter=6),
 'cell':ParagraphStyle('Cell',fontName='Arial',fontSize=8.8,leading=11.8),
 'header':ParagraphStyle('Header',fontName='Arial-Bold',fontSize=8.8,leading=11.8),
 'caption':ParagraphStyle('Caption',fontName='Arial',fontSize=8.5,leading=11.4,spaceBefore=5,spaceAfter=10),
}
LABELS={'dummy_prior':'Dummy prior','logistic_combined':'Logistic: combined','random_forest_combined':'Random forest: combined','logistic_visible':'Logistic: visible','logistic_nir':'Logistic: NIR'}
story=[]
figures=[]
reading_text=[]


class Report(BaseDocTemplate):
    def __init__(self,path):
        super().__init__(str(path),pagesize=A4,leftMargin=44,rightMargin=44,topMargin=46,bottomMargin=40,
                         title='FYP: From Sensor Data to an Exploratory Baseline',author='Felix',
                         subject='Snow LPBF data preparation, candidate targets, baseline results, literature and next steps')
        frame=Frame(self.leftMargin,self.bottomMargin,self.width,self.height,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='Report',frames=[frame],onPage=self.chrome))
        self.sections={}
    def chrome(self,canvas,doc):
        canvas.saveState();canvas.setFont('Arial',7.6);canvas.setFillColor(colors.HexColor('#617181'))
        canvas.drawString(44,A4[1]-26,'FYP | Data preparation to baseline')
        canvas.drawRightString(A4[0]-44,A4[1]-26,'One build | Candidate targets remain provisional')
        canvas.drawString(44,22,'8 November 2026 | Prepared for Felix')
        canvas.drawRightString(A4[0]-44,22,str(doc.page));canvas.restoreState()
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name in ('Heading','Title'):
            title=flowable.getPlainText();key=f'section_{len(self.sections)+1}'
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(title,key,0,False);self.sections[title]=self.page


def p(text,style='body'):
    return Paragraph(text,STYLES[style])
def para(text,style='body'):
    story.append(p(text,style));reading_text.append(text)
def heading(text):para(text,'h1')
def sub(text):para(text,'h2')
def table(headers,rows,widths):
    data=[[p(escape(str(v)),'header') for v in headers]]+[[p(escape(str(v)),'cell') for v in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eff5')),
        ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#9daab6')),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#d5dde4')),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.extend([t,Spacer(1,8)]);reading_text.append(' | '.join(map(str,headers)))
    reading_text.extend(' | '.join(map(str,row)) for row in rows)
def figure(name,caption,maxheight=390):
    path=ASSETS/name
    with PILImage.open(path) as im:
        w=507;h=w*im.height/im.width
    if h>maxheight:w*=maxheight/h;h=maxheight
    image=Image(str(path),width=w,height=h);image.hAlign='CENTER'
    n=len(figures)+1;figures.append({'number':n,'file':name,'caption':caption})
    story.append(KeepTogether([image,p(f'<b>Figure {n}.</b> '+caption,'caption')]))
    reading_text.append(f'Figure {n}. {caption}')
def page():story.append(PageBreak())
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def rows(path):
    with path.open(newline='',encoding='utf-8') as stream:return list(csv.DictReader(stream))
def num(v,d=3):return '-' if v is None or v=='' else f'{float(v):.{d}f}'
def pct(v):return '-' if v is None or v=='' else f'{100*float(v):.1f}%'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    source=load(CAT/'summary.json');record=load(RUN/'run_record.json');results=load(RUN/'results_summary.json')
    verification=load(ROOT/'results/baseline_v1_2026-11-08/verification.json')
    protocol=load(ROOT/'results/baseline_v1_2026-11-08/protocol/protocol.json')
    assert source['rows']==329828 and record['status']=='complete' and verification['status']=='passed'
    selected=record['selected_primary_method'];test={r['method']:r for r in results['test']};dev={r['method']:r for r in results['development']}
    main=test[selected];spec=[r for r in rows(RUN/'test_per_specimen.csv') if r['method']==selected]
    examples=load(ASSETS/'source_example_provenance.json')['examples']

    # 1
    para('From Sensor Data to an <br/>Exploratory Baseline','title')
    para('FYP progress report: the question, data preparation, reasoning, results and next research steps','subtitle')
    para('Snow LPBF dataset | Evidence through 8 November 2026','small')
    sub('Executive summary')
    para('The FYP asks whether images collected while metal parts are printed contain information about internal-flaw annotations measured by X-ray computed tomography (XCT) after printing. The current task is local patch classification: use the sensor images to estimate whether a corresponding XCT region contains a dataset-detected flaw annotation. This is a step toward process-based quality assessment; it is not yet an independently validated pore detector.')
    para('We converted a roughly 128 GB source file into a traceable, manageable dataset: <b>329.8k three-channel patches from 64 fatigue specimens and 142 selected layers</b>. Preparation preserved the source, screened structural problems, recorded quality flags and kept uncertain reference cases separate. Of these patches, 323.3k have provisional binary candidates and 6.5k remain unknown. [E1-E3]')
    para('The first baseline experiment is complete. A development-selected random forest achieved pooled test average precision (AP) of <b>0.782</b>, compared with <b>0.252</b> for a constant comparator. However, two high-prevalence specimens contribute 93.4% of detected positives. Recall across the other ten test specimens is only <b>10.8%</b>. The next scientific priority is checking the target definition and understanding specimen-level effects. [E4-E6]')
    table(['Question','Current answer'],[
        ['Have we cleaned the data?','The selected sensor inputs are prepared and checked. Their physical reference labels remain provisional.'],
        ['Have we developed a model?','Yes: five fixed baseline methods, with specimen-separated development and testing.'],
        ['How is Dinh et al. relevant?','It motivates linking process images to CT and highlights the difficulty of local correspondence; it does not validate our labels.'],
        ['Do we need new tomography software?','No reconstruction step is currently justified. Algotom may help with a specific reconstructed-volume diagnostic.'],
        ['What should happen next?','Review image/XCT correspondence and uncertain targets, then investigate local versus specimen-level model information.']], [148,359])
    para('Reading guide: pages 2-13 explain the data and preparation; page 14 connects the literature; pages 15-21 explain the baseline; pages 22-25 cover tomography tools, next steps, terminology and evidence. PDF bookmarks provide section navigation.','small')
    page()

    # 2
    heading('1. What we want to find out')
    para('Laser powder bed fusion (LPBF) builds metal parts layer by layer. A camera can observe powder spreading and the surface after melting. NIR imaging records near-infrared emission during the process. XCT subsequently gives a view of the solid part interior. The research opportunity is to learn whether the earlier process observations contain useful information about later internal-flaw evidence. [S1,S2]')
    figure('research_connection.png','The research connection. Sensor patches are the model inputs; XCT-derived candidates provide the research reference. The arrow between modalities represents a correspondence that must be justified. This conceptual diagram describes the present workflow, not a deployed inspection system. [E1-E4]',330)
    sub('A precise current question')
    para('<b>For a small region of a previously unseen specimen from this build, can its visible and NIR image features rank whether the currently mapped XCT region has a nonzero flaw annotation?</b> This formulation separates a testable computational experiment from the stronger future claim that a method detects real internal pores reliably.')
    para('The current output is a patch score and a binary decision at a declared threshold. Fatigue-life prediction, pore counting, quantitative porosity estimation and transfer to another build are outside the completed model experiment. Their source data or scientific relevance do not make them completed FYP results.')
    page()

    # 3
    heading('2. What data we actually have')
    para('The source is the Snow et al. release, a single LPBF build of stainless-steel 316H fatigue cylinders, manufactured on a Colibrium Additive M2. The authors describe 56 nominal cylinders and eight made with high volumetric-energy-density parameters, plus auxiliary geometries. Sixty of the 64 cylinders were fatigue tested. The source is one build, not 64 independent builds. [S1,S2]')
    table(['Data item','What it means','Use in this experiment'],[
        ['Visible post-melt','Surface image after laser melting','Selected sensor input'],
        ['Visible post-recoat','Surface image after powder spreading','Selected sensor input'],
        ['NIR integrated maximum','Largest stored NIR response over frames assigned to a layer','Selected sensor input; not calibrated temperature'],
        ['Part and sample templates','Integer-valued images identifying geometry/sample regions','Part selection, provenance and diagnostics'],
        ['Registered XCT grayscale','Already reconstructed interior-intensity data placed in build coordinates','Reference-region inspection and current support proxy'],
        ['Registered XCT flaw raster','Author algorithm-detected flaw annotation values','Source of provisional patch targets'],
        ['Other released data','NIR sum/argmax, scan paths, process settings, fatigue results and partial thermal simulations','Available context; not predictors in the completed baseline']], [115,224,168])
    sub('Size and storage')
    para('The unchanged HDF5 source is 127,808,960,296 bytes, approximately 128 GB. The selected camera channels and ID templates have shape <b>1,117 x 2,844 x 2,844</b>; registered XCT arrays have shape <b>1,117 x 13,752 x 13,752</b>. Storage axes are layer, Y, X. A larger XCT grid does not alone establish its exact physical extent or pixel-center convention. [E1]')
    para('HDF5 is a container for named arrays and metadata. Here, the project folder called data/raw means the preserved source release. Its XCT array already contains reconstructed slices; the folder name does not turn those slices into raw radiographic projections.')
    page()

    # 4
    heading('3. What one model observation looks like')
    para('One observation is a <b>24 x 24 camera-grid patch at one specimen, layer and location</b>. The three sensor channels cover the same selected camera-grid region. Keeping them together lets the model use information from different stages of the printing process.')
    figure('one_sensor_patch.png','An example taken from the full prepared source catalog: specimen P4, layer 600. Each channel has 576 pixels. Values are displayed on the stored normalized [0,1] scale; the NIR color map shows image intensity, not temperature. This image was not selected as representative of a physical defect. [E1,E2]',330)
    table(['Record component','Purpose'],[
        ['Three-channel pixel array','The observed sensor information. Shape per patch: 3 x 24 x 24.'],
        ['Sample identity and coordinates','Trace the patch to the source specimen, layer, Y/X location and saved shard.'],
        ['Candidate target','Provisional 1, 0 or unknown; generated from the candidate XCT region.'],
        ['Quality and validation fields','Retain review context and make uncertainty explicit.'],
        ['42 descriptor values','Compact image summaries used by the baseline; stored separately from metadata.']], [151,356])
    para('The patch size is a working resolution and compute choice. It provides a manageable local observation and a reproducible starting point; its optimal size and exact physical footprint have not been established. Adjacent patches and neighboring layers can remain strongly related even when their pixel windows do not overlap.')
    page()

    # 5
    heading('4. What the authors had already processed')
    para('The released data were not untouched camera photographs and unreconstructed scan measurements. Understanding the author processing prevents us from repeating transformations or claiming work that was already done. [S2]')
    table(['Stage','Dataset authors','Work performed here'],[
        ['Visible images','Illumination compensation, lens correction and homography to build coordinates','Use supplied arrays; extract patches and apply a fixed numeric scale'],
        ['NIR images','Noise suppression, per-layer sum/max/argmax, lens and perspective correction','Use the supplied integrated-maximum channel'],
        ['XCT','Reconstruction/preprocessing, then registration to build coordinates using point-to-plane ICP with RANSAC','Inspect supplied grids; record an explicit candidate index mapping for patch targets'],
        ['Flaw annotations','Laplacian-of-Gaussian response, thresholding and clustering in XCT data','Count nonzero annotation pixels in a candidate crop; do not rerun their detector'],
        ['Experimental design','Material, machine, process settings, spatter arrangement and fatigue measurements','Select the research scope and record source context']], [80,216,211])
    sub('Why this distinction matters')
    para('A second uncalibrated homography could move images away from their supplied coordinate system. Filtering an official flaw raster could change which pixels count as positive. Reconstructing CT again without projection data and scanner geometry would be a different problem from preparing the supplied registered slices.')
    para('The authors report XCT scanning around the fatigue-coupon gauge section with a nominal voxel size of 17.8 micrometres. This helps describe the acquisition, but it does not independently settle the released slice grid extent, exact camera/XCT crop mapping or usable support at every location. Those need dataset-specific evidence. [S2]')
    para('Accordingly, the completed preparation focuses on safe extraction, consistent numeric representation, structural screening and traceability. Scientific target validation is recorded separately.')
    page()

    # 6
    heading('5. Why preparation was needed')
    para('A large file can be readable yet unsuitable for direct modeling. A model needs aligned observations, explicit targets and a way to separate specimens during evaluation. Preparation turns the source into such records while retaining enough information to audit every choice.')
    figure('workflow.png','Completed source preparation and baseline work, with scientific validation still open. Mechanical consistency and physical target validity are separate checkpoints. [E1-E6]',440)
    para('Layer-wise compressed shards keep memory use bounded and allow failed or interrupted jobs to be checked and resumed. A canonical catalog joins the shard row to its source identity, quality flags and candidate annotation. Checksums help detect unintended changes or mismatched files.')
    para('This is why cleaning did not mean making every image look smoother. Preserving the released pixel information and recording uncertainty was more defensible than deleting difficult cases or applying image enhancement without a demonstrated need.')
    page()

    # 7
    heading('6. The cleaning choices and their reasoning')
    table(['Choice made','Reason','What remains a working assumption'],[
        ['64 fatigue-bar geometries','Align extraction with the research specimens and omit auxiliary spatter/default-tensile geometries','The release contains other useful context; omitted geometry is not corrupt data'],
        ['Layers 519-660 inclusive','Focus preparation on the nominal XCT gauge-section range','This scope is not a verified measured-support mask; 975 other source layers were not prepared'],
        ['24 x 24 patches, step 24','Make a manageable local dataset with a repeatable within-part grid','Patch scale and within-patch aggregation are not proven optimal'],
        ['At least 75% of patch pixels belong to the selected part','Reduce patches dominated by background or another geometry','A retained heuristic; up to 25% can be off-part and remain in the image'],
        ['Visible /255; NIR /65535; float32','Represent integer channel values on a common numeric range without fitting to the whole dataset','This is numeric scaling, not radiometric calibration or temperature conversion'],
        ['Finite/shape/empty-input screening','Catch mechanically unusable records before training','Passing these checks cannot establish correct scientific labels'],
        ['Retain quality flags','Avoid an unsupported assumption that every unusual value or contextual event is a bad sample','Flags require interpretation; additional exclusions need evidence'],
        ['Preserve IDs, bounds and hashes','Make the dataset reproducible and errors traceable','Traceability enables checks; it does not replace physical validation']], [114,191,202])
    para('The 75% rule is based on the part-ID template. The whole retained patch is used; off-part pixels are not independently masked out of the baseline. Such background or edge information may help encode location, so its effect belongs in later nuisance diagnostics. [E1,E2]')
    para('No further per-patch contrast normalization, arbitrary denoising or forced removal of all stored-maximum values was applied. The first experiment holds a declared preparation convention fixed so later changes can be compared honestly.')
    page()

    # 8
    heading('7. How a provisional target is created')
    para('The sensor and XCT arrays have different sampling grids. The current candidate conversion uses the dimension ratio <b>13,752 / 2,844 = 4.835443</b> and rounds each scaled crop boundary. Exact bounds are saved. This defines a reproducible convention; it is not independent proof that the physical regions coincide.')
    figure('candidate_grid_mapping.png','The current crop convention. A camera patch usually corresponds to approximately 116 x 116 XCT-grid pixels, depending on boundary rounding. Array-size agreement alone cannot resolve origin, extent or pixel-center assumptions. [E1,E2]',255)
    table(['Candidate value','Exact current rule','Plain-language meaning'],[
        ['Unknown: -1','Crop bounds invalid, or fewer than 50% of mapped grayscale pixels are >0','Insufficient evidence under the current proxy; do not force a negative'],
        ['1','Bounds valid, proxy at least 50%, and any nonzero flaw-raster pixel','The current candidate region contains a dataset annotation'],
        ['0','Bounds valid, proxy at least 50%, and no nonzero flaw-raster pixel','No annotation in this candidate crop under the current rule']], [80,231,196])
    para('The fraction of grayscale XCT pixels above zero is a <b>support proxy</b>, not validated observed coverage. Zero values may have several meanings, including padding or background; the rule cannot certify measured material. The 50% cutoff and any-nonzero annotation rule are working heuristics, not calibrated physical thresholds.')
    para('A nonzero annotation count is a number of raster pixels in one mapped slice region. It is not a count of pores or a 3D porosity fraction. The final label_validated and coverage_validated flags remain false for every record.')
    page()

    # 9
    heading('8. What the source and candidates look like')
    figure('source_xct_examples.png','Three new examples traced directly from the full source catalog. Rows show a candidate-positive patch, a nearby candidate-zero patch, and an unknown patch with low positive-intensity proxy. The XCT crops are displayed with shared grayscale bounds. Sensor images remain fixed to [0,1]. These are illustrations of the rule, not manually confirmed physical defect cases. [E2]',435)
    para('For the first row, the current mapped crop has seven nonzero flaw pixels and proxy 1.000, producing candidate 1. The nearby second row has zero annotation pixels and proxy 1.000, producing candidate 0. The third row has zero annotation pixels but proxy about 0.171, so it stays unknown. Treating that last case as an ordinary negative would hide uncertainty in the reference region.')
    para('The example sample IDs, crop bounds, source shard checksums and display settings are saved with the report figures. Only three bounded XCT crops were read to make this illustration; the source was opened read-only.')
    page()

    # 10
    heading('9. What cleaning produced')
    figure('source_candidate_composition.png','Composition of all 329,828 prepared patches. These are candidate patch labels, not physical-pore counts or volumetric porosity. The candidate-positive proportion among eligible 0/1 rows is 22.78%. [E1]',265)
    table(['Result','Count','Interpretation'],[
        ['Prepared sensor patches','329,828','All 64 selected specimens and 142 layers'],
        ['Candidate 1 / candidate 0','73,649 / 249,631','323,280 provisional supervised rows'],
        ['Unknown candidates','6,548','Retained; excluded from supervised fitting/scoring'],
        ['Structurally quarantined','0','No retained extraction failed the declared structural screen'],
        ['Exact three-channel duplicates','0','No identical raw three-channel patch content found globally'],
        ['Geometry-scope positions excluded','115,484','Outside the 75% part-fraction selection; not confirmed corrupt images']], [177,105,225])
    para('Zero structural failures or exact duplicates is a useful engineering result. It does not mean every record is scientifically correct or statistically independent. Very similar patches from related layers and neighboring locations can remain correlated without being byte-identical.')
    page()

    # 11
    heading('10. What is present across layers')
    figure('source_candidates_by_layer.png','Prepared patch counts and provisional candidates over the 142 selected layers. Counts reflect the stated extraction scope and current annotation/support rules. They do not prove valid measured XCT support throughout the range. [E1]',380)
    table(['Review context','Occurrences','Treatment'],[
        ['Author acquisition-event context','2,119','Retain and flag; no automatic whole-layer deletion'],
        ['Constant NIR channel','11','Retain and flag; inspect separately'],
        ['Any stored-maximum endpoint','65,712 rows','Record endpoint values; do not equate them with proven saturation'],
        ['Any recorded quality flag','72,754 rows','Flags overlap; not a count of unusable images']], [187,100,220])
    para('The author-event context arises around source layer 602. The preparation records relevant source notes and review flags rather than inferring that every image in that layer failed. A maximum digital value can have multiple causes; physical saturation needs acquisition-specific evidence. [E1,S1,S2]')
    para('Quality flags are therefore available for inspection and sensitivity summaries. They are not hidden feature inputs, and their occurrences should not be added together as if each referred to a different bad patch.')
    page()

    # 12
    heading('11. The candidate population varies by specimen')
    figure('specimen_prevalence_grid.png','All 64 fatigue specimens, ordered by numerical ID. Each cell shows candidate-positive prevalence among that specimen\'s known 0/1 rows. This arrangement is a display grid, not the physical build layout. Unknown rows are excluded from each percentage denominator. [E1]',420)
    para('Large differences in candidate prevalence are present before training. They may reflect process conditions, physical defect populations, annotation behavior, registration/support effects or several of these together. These counts alone cannot identify their cause.')
    para('A sensor model can obtain a strong pooled score partly by distinguishing specimens or their conditions, even when specimen IDs are excluded from its inputs. This is why the evaluation keeps specimens separate and why later results are also reported within each held-out specimen.')
    page()

    # 13
    heading('12. What is trustworthy now, and what is open')
    table(['Question','Evidence obtained','Meaning'],[
        ['Are records mechanically consistent?','Source and shard hashes; finite-value/range checks; ID, target and coordinate alignment; unique sample identities','Prepared records can be traced and loaded reproducibly'],
        ['Was the source preserved?','Read-only HDF5 use; unchanged source size/mtime; unchanged SHA-256 for 28 tracked original small files','The new workflow did not overwrite the original inputs and scripts'],
        ['Can the model experiment be reproduced?','Frozen split/protocol; saved models/predictions; 15 analytical tests; 380 independent metric comparisons','The reported computations have been checked'],
        ['Are the targets physically validated?','No independent final support mask or fully justified physical index convention yet','All candidate/coverage validation flags remain false'],
        ['Does performance transfer to another build?','Only one build evaluated','Cross-build transfer remains untested']], [128,235,144])
    sub('Why a baseline was still useful')
    para('A carefully labeled exploratory experiment can reveal whether the current representation contains annotation-associated information and expose where it fails. It does not need to wait for perfect calibration to provide that engineering evidence. The experiment must keep its target limitations visible, preserve a fixed reference convention and avoid presenting computational success as physical validation.')
    sub('What final target validation needs')
    para('The remaining questions are specific: what physical extent and origin do the released grids use; what marks actually observed XCT support; what do flaw-raster values and zeros represent; and how should an uncertain or boundary case enter the research target? A defensible policy can retain uncertainty rather than claim every location is perfectly known.')
    para('The original source-preparation readiness flags remain unchanged. The later model run is explicitly identified as exploratory prediction of provisional candidates, rather than a silent promotion of those candidates into verified ground truth. [E1-E6]')
    page()

    # 14
    heading('13. How Dinh, Muller and Quinsat is relevant')
    para('Dinh, Muller and Quinsat (2021) investigated an embedded visible-vision approach to layering defects in LPBF. Their demonstration used four Inconel 718 parts on an AddUp FormUp 350, with a 5 MP camera producing post-layering and post-melting images over 463 layers (926 images). [S3, pp. 1111-1116]')
    table(['Aspect','Their study','This FYP'],[
        ['Image evidence','Visible images after powder spreading and melting','Visible post-recoat/post-melt plus integrated-maximum NIR'],
        ['Method','Reference-point homography; classical filtering, thresholding and edge-based regions; stacked voxel maps','Supplied corrected images; patch descriptors; supervised baseline classifiers'],
        ['Image-derived target concept','Potential missing-powder/defect-risk regions','Provisional presence of a mapped author XCT flaw annotation'],
        ['CT comparison','Global image-derived potential-defect and CT porosity volume fractions across four parts','Patch candidate agreement with whole-specimen holdout and local diagnostics'],
        ['Shared challenge','Local image-to-material correspondence and CT limitations','Exact mapping, usable support and physical target interpretation']], [95,206,206])
    para('Their image-derived potential-defect ratio was about <b>0.77%</b>, while CT-derived porosity ratios were <b>0.11%-0.13%</b>, with 20-micrometre CT voxels. These are different volume-fraction results. They are not accuracy, AP or proof of matched local pore detection. The paper explicitly calls for more local comparison and larger studies. [S3, pp. 1116-1117]')
    sub('What the paper contributes to our reasoning')
    para('It supports the motivation for combining process-stage observations with CT and reinforces the importance of geometry and region selection. It also provides a useful warning: a visible powder anomaly, a potential-defect region and a confirmed internal pore are different observations. Our model labels should preserve that distinction.')
    para('The paper does not validate this FYP\'s dimension-ratio crop mapping, support proxy, patch size, NIR channel, feature set or model results. Its classical image-processing workflow can motivate interpretable image descriptors, but it does not prescribe the 42 features used here. Full citation includes all three authors, including Yann Quinsat.')
    page()

    # 15
    heading('14. How the baseline experiment was separated')
    para('A baseline is a deliberately modest reference experiment. It asks what a simple reproducible model can achieve before spending effort on a larger architecture. The test must also expose failures that an apparently strong overall score can hide.')
    figure('baseline_split.png','Frozen five-fold specimen partition, seed 20261108. The reserved test fold never enters development fitting or validation. Four development runs use one development fold for validation and the other three for training. Learned scaling is fitted only on those training rows. [E4,E5]',340)
    table(['Partition','Specimens','Eligible patches','Role'],[
        ['Development folds 1-4','52','262,369','Choose the primary model using mean fold AP'],
        ['Reserved fold 0','12','60,911','Evaluate the fixed five-method suite after selection'],
        ['Unknown targets','Assigned to their specimen fold','6,548','No supervised fitting or scoring']], [126,72,100,209])
    para('Keeping whole specimens together prevents nearly related patches from the same specimen appearing in both fit and test sets. It does not remove all correlations or create an external build. Test specimens are P4, P21, P33, P37, P43, P44, P49, P50, P57, P58, P59 and P65. [E4; S4]')
    para('The decision threshold was fixed at 0.5. Hyperparameters and modality comparisons were predeclared. After development selection, all five fixed methods were refitted on the 52 development specimens and scored on the reserved specimens. There was no test-based retuning.')
    page()

    # 16
    heading('15. What the models learned from')
    para('The baseline converts each image patch into compact descriptions of brightness, variation and simple texture. Fourteen descriptors per channel give 42 combined features. They summarize the sensor arrays; they do not contain XCT measurements or externally calibrated physical properties. [E3,E4]')
    table(['Feature family','Descriptors per channel','Why include it'],[
        ['Brightness and spread','Mean; population standard deviation; minimum; maximum','Summarize overall response and variation'],
        ['Intensity distribution','10th percentile; median; 90th and 99th percentiles','Describe dark, typical and bright portions without retaining every pixel'],
        ['Stored endpoints','Fraction exactly zero; fraction exactly one','Record endpoint patterns without declaring their physical cause'],
        ['Local variation','Mean absolute horizontal and vertical differences; RMS gradient','Summarize local changes and edge-like texture'],
        ['Histogram texture','16-bin entropy divided by 4','Summarize diversity of stored intensities on a 0-1 scale']], [104,223,180])
    table(['Method','Plain-language role','Fixed initial settings'],[
        ['Dummy prior','Ignores images and supplies a reference score','Training positive fraction; threshold 0.5 predicts all zeros here'],
        ['Logistic regression','Combines standardized image descriptors in a regularized linear rule','C=1; balanced class weights; train-only StandardScaler'],
        ['Random forest','Combines 100 bounded decision trees to allow nonlinear relationships','Maximum depth 12; leaf size at least 20; balanced bootstrap weights'],
        ['Modality comparisons','Repeat logistic regression with visible-only or NIR-only features','Same partitions and fitting settings; 28 visible / 14 NIR features']], [104,223,180])
    para('Primary selection uses the highest mean AP over four development folds among dummy, combined logistic and combined random forest. A tie within 0.0001 prefers the simpler method. All metadata and reference fields remain outside the predictors. No CNN, feature-search sweep, probability calibration or operating-threshold optimization was part of Baseline v1.')
    page()

    # 17
    heading('16. The first model comparison')
    figure('model_ap_comparison.png','Development comparison and the reserved-specimen result. Fold error bars show standard deviation, a description of variation rather than a confidence interval. The blue diamond identifies the primary model selected before the holdout was scored. [E5]',330)
    table(['Method','Dev AP','Test AP','Precision','Recall','F1'],[
        [LABELS[name],num(dev[name]['mean_fold_ap']),num(test[name]['average_precision']),pct(test[name]['precision']),pct(test[name]['recall']),num(test[name]['f1'])]
        for name in record['method_order']], [151,64,64,80,80,68])
    para('The combined random forest had development mean AP 0.712 and was selected. Its test AP is 0.782. The combined logistic model has test AP 0.763; fixed visible-only and NIR-only logistic results are 0.628 and 0.711. Both modalities contain annotation-associated information in this experiment, with the combined logistic representation performing better here.')
    para('These comparisons do not establish universal modality superiority or a statistically confirmed improvement. Models are compared on the same source policy and partitions. An undefined dummy precision occurs because it predicts no positives at threshold 0.5.','small')
    page()

    # 18
    heading('17. What average precision tells us')
    figure('heldout_precision_recall.png','Precision-recall curves on the fixed 60,911-patch test cohort. The horizontal level of about 0.252 is the test candidate-positive prevalence. All curves measure agreement with provisional candidate annotations. [E5; S5]',400)
    para('<b>Precision</b> asks: among patches called positive, how many have a positive candidate annotation? <b>Recall</b> asks: among candidate-positive patches, how many does the model detect? Changing the score threshold changes this trade-off. <b>Average precision</b> summarizes ranking across the precision-recall curve; it is not the percentage of all patches classified correctly.')
    para('At test prevalence 25.15%, a constant score has AP about 0.252. The selected forest reaches AP 0.782 and pooled ROC AUC 0.863. Those results show separation in the pooled candidate population. They do not tell us whether separation occurs locally within each specimen; that diagnostic follows.')
    para('The class-weighted model outputs are uncalibrated scores. A value of 0.8 is not established as an 80% physical-pore probability. The current threshold is a fixed experimental convention, not an optimized industrial acceptance criterion.')
    page()

    # 19
    heading('18. The errors at threshold 0.5')
    figure('selected_primary_confusion.png','Selected random forest confusion counts. Candidate 0 and 1 are the experimental reference classes. Row percentages show specificity and recall; they do not certify physical flaws or flaw-free material. [E5]',330)
    para('The model detects <b>9,638 of 15,322</b> candidate-positive test patches, giving recall <b>62.9%</b>. It calls 1,810 candidate-zero patches positive. Precision is <b>84.2%</b>, F1 is <b>0.720</b>, balanced accuracy is <b>79.5%</b>, and overall accuracy is <b>87.7%</b>. A fixed-negative rule has 74.85% test accuracy and zero positive recall, illustrating why accuracy alone is insufficient.')
    table(['Prespecified evaluation subset','Rows removed','AP','Balanced accuracy','Recall'],[
        ['All eligible test patches','0','0.782','79.5%','62.9%'],
        ['Exclude constant-NIR cases','7','0.782','79.5%','62.9%'],
        ['Exclude author-event context','396','0.782','79.5%','62.9%']], [218,68,58,91,72])
    para('The sensitivities reuse fixed predictions and do not refit or select a model. Differences are small at this display precision. They do not prove that these flags are harmless in all settings. False-positive/false-negative names refer to disagreement with current candidates; a separate image/XCT review is needed to interpret the physical situation.','small')
    page()

    # 20
    heading('19. Why the pooled score needs caution')
    figure('selected_primary_per_specimen_ap.png','Within-specimen AP compared with each specimen\'s own candidate prevalence. A high AP in a specimen with more than 93% positive candidates needs a different interpretation from the same AP in a mostly negative specimen. [E5]',290)
    table(['Specimen','Candidate 1','AP','ROC AUC','Recall'],[
        [f"P{r['part_id']}",pct(r['prevalence']),num(r['average_precision']),num(r['roc_auc']),pct(r['recall'])] for r in spec], [85,115,100,107,100])
    para('P43/P59 contain 61.5% of test positives and supply 9,001 of the 9,638 detected positives (93.4%). The remaining ten specimens have only 637/5,902 recall, or 10.8%, at threshold 0.5. Mean within-specimen ROC AUC is 0.576; P57 and P65 have zero recall. This is a substantial local-performance weakness, although its cause is not yet established.','small')
    page()

    # 21
    heading('20. Looking at agreements and disagreements')
    figure('selected_primary_error_gallery.png','Six deterministic extreme-score test examples from the saved forest predictions. TP/TN denote agreement with positive/zero candidates; FP/FN denote disagreement. Images have fixed display bounds and are not contrast-stretched separately. The cases illustrate model behavior, not independently verified pores. [E5]',625)
    page()

    # 22
    heading('21. Could the suggested tomography tools help?')
    para('The three links are relevant background, but their role depends on the task. Our working XCT arrays are already reconstructed and registered. Usable angular projections, their angles, scanner geometry and calibration inputs have not been demonstrated as reconstruction inputs in the current audit. That does not assert that no other acquisition files exist elsewhere.')
    table(['Tool','Documented capability','Practical relevance here'],[
        ['TomoPy','Tomographic processing, reconstruction, filtering and ring-related tools. Reconstruction takes projection data and projection angles.','Low immediate reconstruction priority. Consider a defined CT-processing question only after the appropriate measurements and acquisition conventions are established. [S6]'],
        ['Algotom','Preprocessing and reconstruction, plus statistics, downsampling and reslicing of reconstructed datasets. Some tools address reconstructed-image artifacts.','Closest optional fit now: inspect a bounded specimen volume in another orientation, or investigate a demonstrated artifact. Existing NumPy/h5py already support the basic inspection needed. [S7]'],
        ['ASTRA Toolbox','2D/3D reconstruction and forward/backprojection using explicit projection and volume geometries; many GPU operations.','Useful for a separately justified reconstruction/forward-model study with suitable projection data and geometry. Unnecessary for the completed camera-to-candidate baseline. [S8]']], [80,221,206])
    sub('What these packages cannot decide for us')
    para('A package cannot infer the physical meaning of zeros in Snow\'s release or certify the current camera-to-XCT crop convention. Entering an assumed extent into a reconstruction geometry encodes the assumption; it does not verify it. Cross-modal image correlation may support a constrained diagnostic, but cannot alone prove that visible-surface and XCT-intensity structures should align.')
    sub('Recommendation')
    para('Continue using the supplied reconstructed reference for the current FYP. Keep Algotom as an optional diagnostic tool if a concrete need emerges. Introduce new tomography processing only when its purpose, inputs and validation are clear. Any filtering/resampling of the flaw raster could change targets and must be a separate documented version. This recommendation is a project-specific inference from the documented capabilities and current inputs.')
    page()

    # 23
    heading('22. What to do next, and what it will produce')
    para('The next phase should improve the scientific meaning of the result before increasing model complexity. We already have a reproducible reference baseline and a clear weakness to investigate.')
    table(['Next task','Why it matters','Concrete output / completion evidence'],[
        ['Review the target convention','A model learns the reference it is given; the current grid/support/annotation rules are provisional','A documented camera/XCT coordinate policy, usable-support definition and explicit positive/zero/unknown rules'],
        ['Build a stratified visual audit','Inspect ordinary, uncertain, edge and acquisition-flagged cases across specimens/layers','A traceable image/XCT review pack with reviewed outcomes and unresolved cases; not only model-selected examples'],
        ['Diagnose development-set nuisance structure','Strong between-specimen separation may conceal weak local information','Development-only comparisons/controls for specimen, layer and location structure; a clear account of what the baseline can distinguish'],
        ['Declare Baseline v2','Target changes, new thresholds, features or a CNN alter the experiment','Frozen revised protocol and a defensible evaluation plan before inspecting adaptive results'],
        ['Seek broader validation when feasible','One build cannot demonstrate transfer to a different manufacturing run','A suitable independent build or externally justified evaluation design with comparable definitions']], [117,179,211])
    sub('When would a CNN make sense?')
    para('A CNN could retain spatial image structure that handcrafted summaries discard. It becomes a stronger next experiment after the target convention is defensible, nuisance controls are understood and evaluation is planned. A larger model alone cannot repair a wrong region match or an ambiguous reference.')
    sub('How to treat the inspected test set')
    para('Fold 0 has now been inspected. It remains the honest record of Baseline v1, but it cannot repeatedly guide adaptive choices while still being called untouched. With only this build, a future protocol must state that limitation and choose an appropriate new design; simply renaming the same patches is insufficient.')
    para('Expected deliverables are a justified target policy, a review pack, diagnostic evidence and a revised baseline comparison. Their success should be judged by what they establish about data validity and local prediction, rather than by a promised accuracy increase.')
    page()

    # 24
    heading('23. A short glossary for reading this work')
    table(['Term','Meaning in this project'],[
        ['LPBF','Laser powder bed fusion: metal powder is spread and selectively melted layer by layer.'],
        ['In situ / post-build','Measured during printing / measured after printing.'],
        ['XCT','X-ray computed tomography: a reconstructed representation of the part interior.'],
        ['Reconstruction','Recovering a volume from radiographic projections taken at different angles.'],
        ['Registration','Establishing corresponding physical positions across images or volumes.'],
        ['Patch / channel','A local 24 x 24 image window / one type or process-stage image at that window.'],
        ['Annotation / candidate target','A released detector-marked reference / the provisional patch rule derived from it.'],
        ['Support proxy','An indirect indicator used to flag uncertain reference regions; not verified coverage.'],
        ['Feature / descriptor','A numeric summary of an input image, such as brightness or local variation.'],
        ['Prevalence','The fraction of eligible candidate labels that are positive in the stated population.'],
        ['Development / holdout','Data used to make model choices / a reserved group scored after those choices.'],
        ['Leakage','Information from evaluation data improperly influencing fitting or model choices.'],
        ['Precision / recall','Positive-call agreement / the fraction of candidate positives detected.'],
        ['AP / ROC AUC','Ranking summaries; neither establishes physical validity or operating-threshold performance.'],
        ['Nuisance structure','Information about specimen, layer, location or conditions that may predict labels without useful local flaw discrimination.'],
        ['Provenance / checksum','The trace of a record back to its source / a digest used to detect changed content.']], [128,379])
    sub('How to explain the project in a few sentences')
    para('We are using visible and NIR images from a metal-printing process to study whether they contain information about XCT flaw annotations. We prepared the selected source into traceable patches, retained uncertain cases explicitly and trained simple models with whole specimens held out. The first model ranks the pooled candidate population well, but detects few positives in most held-out specimens. The next work is to validate the target convention and understand that local-performance weakness.')
    page()

    # 25
    heading('24. Evidence, reproducibility and references')
    para('This report uses the completed source catalog and saved Baseline v1 outputs as its numerical sources. The report does not introduce new training or change targets. Report illustrations derived from bounded source crops retain their sample IDs, bounds, display settings and checksums in the assets directory.','small')
    table(['Evidence ID','Project-relative source'],[
        ['E1: source scope/counts','data/cleaned/snow_source_preparation_v1/{source_config.json,production_summary.json,catalog/summary.json,catalog/per_specimen.csv,catalog/per_layer.csv}'],
        ['E2: patch trace and examples','Canonical catalog/manifest.csv; layer features.npz shards; this report\'s assets/source_example_provenance.json'],
        ['E3: model features','data/features/baseline_v1_2026-11-08/{summary.json,feature_dictionary.json,metadata.csv,features.npy}'],
        ['E4: frozen experiment','results/baseline_v1_2026-11-08/protocol/{protocol.json,splits.npz,split_manifest.csv}'],
        ['E5: model results','results/baseline_v1_2026-11-08/training/{run_record.json,results_summary.json,test_metrics.csv,test_per_specimen.csv,sensitivity_metrics.csv}; models/baseline_v1_2026-11-08'],
        ['E6: verification','results/baseline_v1_2026-11-08/verification.json; src/modeling/test_features.py and test_evaluation.py']], [105,402])
    para('Environment: Python 3.11.4, NumPy 2.4.6, scikit-learn 1.9.1. Source feature extraction: 49.112 seconds; baseline fitting/refitting/evaluation: 182.094 seconds with two numerical threads / forest workers. Independent verification matched all decision counts; float32 stored scores versus float64 metric-table scores differ in ranking metrics by less than 0.000001. All 15 analytical tests passed.','small')
    refs=[
        ('S1','Z. Snow et al. (2025). In situ Visible Light and Thermal Imaging Data from a Laser Powder Bed Fusion Additive Manufacturing Process Co-Registered to X-ray Computed Tomography and Fatigue Data. ORNL. Supplied README.','https://doi.org/10.13139/ORNLNCCS/2524534'),
        ('S2','Snow dataset Methods, supplied Snow_Methods.docx. Build design, camera processing, XCT reconstruction/registration, flaw detector and fatigue-test context.',None),
        ('S3','D. M. Dinh, N. Muller and Y. Quinsat (2021). Layering Defects Detection in Laser Powder Bed Fusion using Embedded Vision System. Computer-Aided Design & Applications 18(5), 1111-1118. Supplied eight-page paper.','https://doi.org/10.14733/cadaps.2021.1111-1118'),
        ('S4','scikit-learn: StratifiedGroupKFold and training-only preprocessing.','https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html'),
        ('S5','scikit-learn: average_precision_score.','https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html'),
        ('S6','TomoPy official features and reconstruction API.','https://tomopy.readthedocs.io/en/stable/api/tomopy.recon.algorithm.html'),
        ('S7','Algotom official documentation and reconstructed-data postprocessing API.','https://algotom.readthedocs.io/en/latest/toc/api/algotom.post.postprocessing.html'),
        ('S8','ASTRA Toolbox official overview and 3D geometry definitions.','https://astra-toolbox.com/docs/geom3d.html'),
    ]
    for ident,text,url in refs:
        label=f'[{ident}] {escape(text)}'
        if url:label+=f' <link href="{url}" color="#2464A1">Source link</link>.'
        if ident=='S4':label+=' <link href="https://scikit-learn.org/stable/common_pitfalls.html" color="#2464A1">Preprocessing guide</link>.'
        overview={'S6':'https://tomopy.readthedocs.io/en/stable/','S7':'https://algotom.readthedocs.io/en/latest/','S8':'https://astra-toolbox.com/'}.get(ident)
        if overview:label+=f' <link href="{overview}" color="#2464A1">Tool overview</link>.'
        para(label,'small')
    para('Official tool documentation was reviewed on 8 November 2026. Tool-use recommendations are project-specific judgments, not claims that these packages were installed or applied. The Dinh paper informs motivation and limitations; no publisher figure has been reproduced as FYP evidence.','small')

    BASE.mkdir(parents=True,exist_ok=True)
    doc=Report(PDF);doc.build(story)
    assert doc.page==25, f'Unexpected pagination: {doc.page}'
    manifest={'pdf':str(PDF),'pages':doc.page,'figures':figures,'sections':doc.sections,
              'source_rows':source['rows'],'supervised_rows':323280,'test_rows':main['n'],
              'baseline_primary':selected,'source_scope':'64 specimens; layers 519-660; one build',
              'new_training':False,'source_targets_changed':False,'pdf_sha256':sha(PDF),
              'evidence_sha256':{str(path.relative_to(ROOT)).replace('\\','/'):sha(path) for path in [CAT/'summary.json',RUN/'run_record.json',RUN/'results_summary.json',ROOT/'results/baseline_v1_2026-11-08/verification.json']},
              'asset_sha256':{f['file']:sha(ASSETS/f['file']) for f in figures}}
    (BASE/'report_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (ROOT/'work/integrated_report/narrative.txt').write_text('\n\n'.join(reading_text)+'\n',encoding='utf-8')
    print(json.dumps({'pdf':str(PDF),'pages':doc.page,'figures':len(figures),'sections':doc.sections,'pdf_sha256':manifest['pdf_sha256']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--replace',action='store_true');args=parser.parse_args()
    if PDF.exists() and not args.replace:raise FileExistsError(PDF)
    build()
