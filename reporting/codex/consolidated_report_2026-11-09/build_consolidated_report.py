"""Build the consolidated full-source FYP progress report from reviewed evidence."""
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
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether, Flowable

ROOT=Path('C:/NUS/FYP/FYP Organized')
WORK=Path(__file__).resolve().parent
OUTPUT=Path('C:/Users/Felix/Documents/Codex/2026-11-08/can/outputs')
BASE=WORK
ASSETS=BASE/'assets'
PDF=OUTPUT/'FYP_Consolidated_Progress_Report_2026-11-09.pdf'
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
                         title='FYP Consolidated Progress: Data Preparation, Models and Scientific Review',author='Felix',
                         subject='Snow LPBF data preparation, candidate targets, baseline results, literature and next steps')
        frame=Frame(self.leftMargin,self.bottomMargin,self.width,self.height,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='Report',frames=[frame],onPage=self.chrome))
        self.sections={}
    def chrome(self,canvas,doc):
        canvas.saveState();canvas.setFont('Arial',7.6);canvas.setFillColor(colors.HexColor('#617181'))
        canvas.drawString(44,A4[1]-26,'FYP | Consolidated progress report')
        canvas.drawRightString(A4[0]-44,A4[1]-26,'One build | Candidate targets remain provisional')
        canvas.drawString(44,22,'9 November 2026 | Prepared for Felix')
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


def build():
    source=load(CAT/'summary.json');record=load(RUN/'run_record.json');results=load(RUN/'results_summary.json')
    verification=load(ROOT/'results/baseline_v1_2026-11-08/verification.json')
    protocol=load(ROOT/'results/baseline_v1_2026-11-08/protocol/protocol.json')
    assert source['rows']==329828 and record['status']=='complete' and verification['status']=='passed'
    selected=record['selected_primary_method'];test={r['method']:r for r in results['test']};dev={r['method']:r for r in results['development']}
    main=test[selected];spec=[r for r in rows(RUN/'test_per_specimen.csv') if r['method']==selected]
    examples=load(ASSETS/'source_example_provenance.json')['examples']

    # 1
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
    figure('workflow_current.png','Current evidence chain, including development-only diagnostics and the prepared scientific review packet. Completion of computations is distinct from physical target validation. [E1-E9]',470)
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
        ['Can the model experiment be reproduced?','Frozen split/protocol; saved models/predictions; 15 analytical tests; 380 baseline checks and 7,481 follow-up metric comparisons','The reported computations have been checked'],
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
    para('Their global-versus-local limitation makes our within-specimen diagnostics relevant. Their Gaussian filtering is an image operation; our normal-reference plots describe statistical distributions. Neither establishes that these FYP features must be Gaussian.','small')
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

    # Current follow-up sources; no new fitting or score generation.
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

    # 2
    H('21. What might Gaussian mean here?')
    P('Distribution and model checks use eligible development patches only; the review packet also includes unknown development cases. The 12 Baseline v1 test specimens remain excluded. Saved model groups and development-only logistic scaler statistics have been audited. [E7-E9]')
    P('The professor\'s intended meaning is still unknown. We therefore performed a useful descriptive feature-distribution check without changing data or assuming what was requested. A Gaussian (normal) distribution is the symmetric bell curve, described by a mean and standard deviation. [S9]')
    T(['Possible meaning','Relevance','Approach'],[
        ['Distribution of sensor values/features','Describe the population, tails and mixtures across specimens/classes','Histograms and normal-reference quantiles using development rows'],
        ['Distribution of defect size, porosity or measurement errors','A different quantity and unit of analysis','Clarify which measurement is intended; annotation-pixel counts are not physical pore sizes'],
        ['Gaussian smoothing or Laplacian-of-Gaussian','An image operation/detector, different from a normality claim','The dataset authors already use LoG in flaw detection; no new smoothing is applied'],
        ['A Gaussian statistical model or quality limit','Would introduce its own assumptions and purpose','Specify the model/measurement and justify assumptions before fitting or setting cutoffs']], [135,191,181])
    S('Does the baseline need Gaussian inputs?')
    P('The logistic classifier models a binary conditional outcome, while the forest uses decision-tree partitions. Neither requires every input feature to be normally distributed. The logistic StandardScaler centers and rescales each feature using training data; this affine operation does not turn a skewed or multimodal distribution into a Gaussian. [S10,S11]')
    P('Gaussian image smoothing weights neighboring pixels with a Gaussian kernel; it does not establish that image intensities follow a normal distribution. Its use would alter the images and needs a specific image-quality purpose. [S12]')
    P('No normality p-values, three-sigma deletions, distribution transformations or Gaussian filtering were used. Neighboring patches/layers are correlated, and the data mix specimens; a very large patch count alone does not supply independent statistical evidence.')
    PAGE()

    # 3
    H('22. Development feature distributions')
    F('distribution_channel_means_print.png','Pooled and class-conditional distributions of patch mean intensity, not individual-pixel histograms. Each displayed histogram is normalized within its population. Dashed normal references use pooled mean and population SD; they are descriptive curves, not fitted model requirements.',320)
    T(['Patch-mean feature','Mean','SD','Skew','Excess kurtosis'],[
        [label,f"{float(stats[name]['mean']):.5f}",f"{float(stats[name]['std_population']):.5f}",f"{float(stats[name]['skew_population']):.3f}",f"{float(stats[name]['excess_kurtosis_population']):.3f}"] for name,label in channels], [177,82,82,80,86])
    P('The post-melt mean has a right tail. Post-recoat means have a narrow center and important tail departures. NIR means show substantial mixture, including a high-value population enriched in candidate-positive patches. A single pooled bell curve is an incomplete description of these data.')
    P('This does not identify a physical cause. A class-separated histogram may reflect local flaws, process conditions, specimen identity encoded in appearance, support/annotation effects or a combination. All 42 descriptors also have saved pooled, class and specimen summaries. Two development endpoint-fraction features are constant zero and were retained.')
    PAGE()

    # 4
    H('23. Normal-reference quantiles')
    F('distribution_normal_qq_print.png','Normal-reference quantile plots for the same specimen-balanced display subset: 200 systematic eligible rows from each of 52 development specimens, 10,400 rows total. Original values remain unchanged. Reference moments are calculated on this display subset.',335)
    P('The horizontal axis gives quantiles of a normal reference; the vertical axis gives the ordered observed values. A distribution closely matching that reference would follow the dashed line. Curvature and tail departures show where that approximation is weak. These plots do not test the physical validity of candidate targets.')
    P('The subset is deterministic and balances the number of rows per specimen. It is not an independent random sample of 10,400 experiments. Quantile positions are (rank - 0.5)/N and the theoretical values use the subset mean and population SD. This construction is explicitly saved, rather than using a normality-test p-value.')
    S('What should we do with this result?')
    P('Describe mixtures and tails first. Consider a transform only if a specific model or scientific measurement requires it, fit any learned transformation within training folds and compare it on development data. Outlying values can contain real process information; departure from a bell curve is not a deletion rule.')
    PAGE()

    # 5
    H('24. Specimen differences are substantial')
    F('distribution_variance_components_print.png','Patch-weighted variance decomposition across 52 development specimens. Variation around specimen means and variation in those means sum to the total. This does not assign a causal explanation to material defects or process settings.',350)
    T(['Patch-mean feature','Within-specimen variance','Between-specimen mean variance'],[
        [label,f"{100*float(variance[name]['within_fraction']):.2f}%",f"{100*float(variance[name]['between_fraction']):.2f}%"] for name,label in channels], [207,150,150])
    P('For NIR patch means, 74.43% of development variance is the weighted between-specimen component. This arithmetic decomposition separates variation around each specimen mean from variation in those specimen means; it does not show that specimen conditions cause a model prediction.')
    P('It explains why interpreting a pooled intensity histogram as one homogeneous population can be misleading. The useful next question is whether local sensor patterns add information once broad location/layer structure is considered. All percentages use the current development patch population, not equal weighting of specimens.')
    PAGE()

    # 6
    H('25. Location/layer diagnostic comparators')
    F('nuisance_overview_readable.png','Four development-only comparisons on identical eligible folds. Sensor results reuse saved out-of-fold predictions; only the layer/position logistic and forest diagnostics were newly fitted. Error bars are fold SD, not confidence intervals.',305)
    T(['Method','Mean fold AP','Mean within-specimen AUC','Pooled recall'],[
        [names[name],f"{methods[name]['mean_fold_ap']:.3f}",f"{methods[name]['mean_specimen_roc_auc']:.3f}",f"{100*methods[name]['pooled_recall']:.1f}%"] for name in names], [172,100,140,95])
    P('The metadata forest uses only source layer and absolute camera Y/X. Its mean fold AP is 0.711, close to 0.712 for the sensor forest. Thus broad spatial/layer information can reproduce much of the pooled candidate separation under this fixed development experiment.')
    P('The sensor forest has higher mean within-specimen AUC: 0.581 versus 0.539 for the metadata forest. This suggests modest additional local ranking information, while leaving substantial room for improvement. These are descriptive comparisons, not proof of confounding, statistical equivalence or physical pore detection. The metadata model is a diagnostic comparator, not a replacement for the intended sensor predictor.')
    PAGE()

    # 7
    H('26. Local ranking and its limits')
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
    H('27. Inspecting spatial patterns')
    F('nuisance_spatial_maps.png','Predeclared development specimens P2, P3, P35 and P60 at layer 600. Compare candidate maps with sensor-forest and location/layer-forest scores. These are development out-of-fold predictions; no test specimen or fresh sensor fit is used.',560)
    P('Maps make it easier to see broad score fields and localized differences. They are evidence for inspection, not proof that a candidate marks a physical pore. Boundary selection and the current support proxy remain part of the experimental target convention.','small')
    PAGE()

    # 9
    H('28. The scientific review packet is ready')
    P('Appendix A contains all 32 development-only sensor/XCT review cases. It includes ordinary cases and difficult categories without selecting cases by model errors. Machine consistency checks pass; human/scientific interpretation remains pending.')
    T(['Selection category','Cases'],[
        ['Ordinary candidate-positive',6],['Ordinary candidate-zero',6],['Unknown',6],['Part-boundary selection',6],['Author-event context',4],['Constant NIR',4]], [365,142])
    P('Each record retains its source identity, fold, camera position, exact candidate XCT bounds and quality fields. Sensor images use fixed [0,1] bounds. XCT grayscale uses the common uint16 stored range [0,65535]; it can look dark and is not calibrated attenuation. A companion review template distinguishes correspondence, usable support, annotation meaning and sensor quality. The 32 purposeful cases come from 24 development specimens and have 14 positive, 12 zero and six unknown candidate statuses; selection categories and candidate statuses are different summaries.')
    T(['Crop convention on these 32 cases','Changed annotation counts','Changed candidate status'],[
        ['Rounded reference','0','0'],['Floor starts / ceil ends','4','0'],['Floor all boundaries','4','0']], [270,121,116])
    P('No candidate status changed among these 32 purposeful cases, while four annotation counts changed under each alternative. This is a bounded sensitivity check, not a full-source stability estimate or validation of the rounded convention. No policy was selected by model AP, no original target was changed and unknowns remain unknown.')
    P('The packet is ready for a focused scientific discussion. Mark cases as supported, unsupported or uncertain with evidence; do not treat the software checks as completed physical validation. The companion questions draft includes the unresolved meaning of Gaussian and the grid/support/annotation questions.')
    PAGE()

    # 22
    heading('29. Could the suggested tomography tools help?')
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
    heading('30. What to do next, and what it will produce')
    para('The completed diagnostic phase provides a clear next question: what local sensor information is added beyond layer and position? A finite review packet is ready. The next phase should record a defensible working target convention and test that incremental information, with remaining uncertainty stated explicitly.')
    table(['Next task','Why it matters','Concrete output / completion evidence'],[
        ['Review the target convention','A model learns the reference it is given; the current grid/support/annotation rules are provisional','A documented camera/XCT coordinate policy, usable-support definition and explicit positive/zero/unknown rules'],
        ['Interpret the prepared review packet','32 purposeful development cases and machine checks are ready; physical interpretation is pending','Recorded outcomes and unresolved cases with source evidence; no forced labels or population-accuracy claim'],
        ['Test added sensor information','Layer/position alone nearly matches pooled development AP, while sensor ranking is locally stronger','A declared context-only versus sensor-only versus combined comparison; assess both pooled and local results'],
        ['Declare Baseline v2','Target changes, new thresholds, features or a CNN alter the experiment','Frozen revised protocol and a defensible evaluation plan before inspecting adaptive results'],
        ['Seek broader validation when feasible','One build cannot demonstrate transfer to a different manufacturing run','A suitable independent build or externally justified evaluation design with comparable definitions']], [117,179,211])
    sub('When would a CNN make sense?')
    para('A CNN could retain spatial image structure that handcrafted summaries discard. It becomes a stronger next experiment after the target convention is defensible, nuisance controls are understood and evaluation is planned. A larger model alone cannot repair a wrong region match or an ambiguous reference.')
    sub('How to treat the inspected test set')
    para('Fold 0 has now been inspected. It remains the honest record of Baseline v1, but it cannot repeatedly guide adaptive choices while still being called untouched. With only this build, a future protocol must state that limitation and choose an appropriate new design; simply renaming the same patches is insufficient.')
    para('Expected deliverables are a justified target policy, a review pack, diagnostic evidence and a revised baseline comparison. Their success should be judged by what they establish about data validity and local prediction, rather than by a promised accuracy increase.')
    page()

    # 24
    heading('31. A short glossary for reading this work')
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
    para('We are studying whether visible and NIR printing images contain local information about XCT flaw annotations. Selected-source preparation and the first baseline are complete, with whole specimens separated during evaluation. Development diagnostics show strong specimen mixtures and substantial prediction from layer/position alone. Sensors retain modestly stronger local ranking. A 32-case review packet is prepared; the next work records a working target policy and tests the added value of local image structure.')
    page()

    # Evidence ledger and bibliography.
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

    BASE.mkdir(parents=True,exist_ok=True)
    doc=Report(PDF);doc.build(story)
    assert doc.page==42, f'Unexpected pagination: {doc.page}'
    manifest={'pdf':str(PDF),'pages':doc.page,'figures':figures,'sections':doc.sections,
              'source_rows':source['rows'],'supervised_rows':323280,'test_rows':main['n'],
              'baseline_primary':selected,'source_scope':'64 specimens; layers 519-660; one build',
              'new_training':False,'source_targets_changed':False,'pdf_sha256':sha(PDF),
              'evidence_sha256':{str(path.relative_to(ROOT)).replace('\\','/'):sha(path) for path in [CAT/'summary.json',RUN/'run_record.json',RUN/'results_summary.json',ROOT/'results/baseline_v1_2026-11-08/verification.json']},
              'asset_sha256':{f['file']:sha(ASSETS/f['file']) for f in figures}}
    (BASE/'report_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (WORK/'narrative.txt').write_text('\n\n'.join(reading_text)+'\n',encoding='utf-8')
    print(json.dumps({'pdf':str(PDF),'pages':doc.page,'figures':len(figures),'sections':doc.sections,'pdf_sha256':manifest['pdf_sha256']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--replace',action='store_true');args=parser.parse_args()
    if PDF.exists() and not args.replace:raise FileExistsError(PDF)
    build()
