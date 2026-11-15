"""Build the consolidated FYP progress PDF from verified local evidence."""
from __future__ import annotations
import argparse
import csv
import json
from html import escape
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether, ListFlowable, ListItem
from PIL import Image as PILImage

ROOT=Path.cwd().resolve()
BASE=ROOT/'reports/fyp_progress_2026-11-08'
ASSETS=BASE/'assets'
SOURCE=ROOT/'data/cleaned/snow_source_preparation_v1'
AUDIT=ROOT/'results/data_quality/2026-11-08_run01'
PDF=BASE/'FYP_Progress_Report_2026-11-08.pdf'
FONT=Path('C:/Windows/Fonts')
for name,filename in [('Arial','arial.ttf'),('Arial-Bold','arialbd.ttf'),('Arial-Italic','ariali.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/filename)))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial-Italic',boldItalic='Arial-Bold')

STYLES={
 'title':ParagraphStyle('ReportTitle',fontName='Arial-Bold',fontSize=25,leading=29,spaceAfter=12,textColor=colors.black),
 'subtitle':ParagraphStyle('Subtitle',fontName='Arial',fontSize=13,leading=18,spaceAfter=9,textColor=colors.black),
 'h1':ParagraphStyle('SectionHeading',fontName='Arial-Bold',fontSize=17,leading=21,spaceAfter=12,textColor=colors.black,keepWithNext=True),
 'h2':ParagraphStyle('Subheading',fontName='Arial-Bold',fontSize=11.2,leading=15,spaceBefore=7,spaceAfter=6,textColor=colors.black,keepWithNext=True),
 'body':ParagraphStyle('Body',fontName='Arial',fontSize=10.1,leading=14.3,spaceAfter=8),
 'small':ParagraphStyle('Small',fontName='Arial',fontSize=8.6,leading=11.5,spaceAfter=5),
 'caption':ParagraphStyle('Caption',fontName='Arial',fontSize=8.5,leading=11.2,spaceBefore=5,spaceAfter=10),
 'cell':ParagraphStyle('Cell',fontName='Arial',fontSize=9,leading=12),
 'header':ParagraphStyle('TableHeader',fontName='Arial-Bold',fontSize=9,leading=12),
}


class Report(BaseDocTemplate):
    def __init__(self,path):
        super().__init__(str(path),pagesize=A4,leftMargin=44,rightMargin=44,topMargin=46,bottomMargin=40,
                         title='FYP Data Preparation Progress Report',author='Felix',subject='Snow LPBF sensor preparation and provisional XCT-derived targets')
        frame=Frame(self.leftMargin,self.bottomMargin,self.width,self.height,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='Report',frames=[frame],onPage=self.page_chrome))
        self.section_pages={}
    def page_chrome(self,canvas,doc):
        canvas.saveState()
        canvas.setFont('Arial',7.7);canvas.setFillColor(colors.HexColor('#5a6268'))
        if doc.page>1:
            canvas.drawString(self.leftMargin,A4[1]-26,'FYP data preparation progress')
            canvas.drawRightString(A4[0]-self.rightMargin,A4[1]-26,'Sensor inputs prepared | Targets provisional')
        canvas.drawString(self.leftMargin,22,'8 November 2026 | NUS Mechanical Engineering FYP')
        canvas.drawRightString(A4[0]-self.rightMargin,22,str(doc.page))
        canvas.restoreState()
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=='SectionHeading':
            title=flowable.getPlainText()
            key='section_'+str(len(self.section_pages)+1)
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(title,key,0,False)
            self.section_pages[title]=self.page


story=[]
figures=[]
def p(text,style='body'):
    return Paragraph(text,STYLES[style])
def para(text,style='body'):
    story.append(p(text,style))
def heading(text):
    story.append(p(text,'h1'))
def sub(text):
    story.append(p(text,'h2'))
def bullets(items):
    story.append(ListFlowable([ListItem(p(item),leftIndent=0) for item in items],bulletType='bullet',leftIndent=13,bulletFontName='Arial',bulletFontSize=7,spaceAfter=6))
def table(headers,rows,widths=None,font='cell'):
    data=[[p(escape(str(v)),'header') for v in headers]]+[[p(escape(str(v)),font) for v in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9edf1')),
        ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#9aa4ad')),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#d5d9dd')),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.extend([t,Spacer(1,9)])
def figure(name,caption,width=6.5*inch,maxheight=None):
    path=ASSETS/name
    with PILImage.open(path) as image:
        h=width*image.height/image.width
    if maxheight and h>maxheight:
        width*=maxheight/h;h=maxheight
    image=Image(str(path),width=width,height=h)
    image.hAlign='CENTER'
    number=len(figures)+1
    figures.append({'number':number,'file':name,'caption':caption})
    story.append(KeepTogether([image,p(f'<b>Figure {number}.</b> '+caption,'caption')]))
def page():
    story.append(PageBreak())
def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def build():
    catalog=load(SOURCE/'catalog/summary.json')
    production=load(SOURCE/'production_summary.json')
    pilot=load(AUDIT/'pilot/final/pilot_audit.json')
    spatial=load(AUDIT/'spatial/summary.json')
    preservation=load(AUDIT/'verification/source_preparation_preservation.json')
    total=catalog['rows']
    # 1 Executive progress statement
    para('FYP Data Preparation Progress Report','title')
    para('Snow LPBF sensor images and XCT annotations','subtitle')
    para('Prepared for Felix | 8 November 2026','small')
    sub('Current conclusion')
    para('The source-data preparation and quality-screening workflow is complete for <b>329,828 three-channel sensor patches across 64 fatigue specimens and 142 selected layers</b>. The inputs are traceable and manageable for later experiments. Their XCT-derived candidate targets remain scientifically provisional; no final target vector or ML model has been produced.')
    para('This report consolidates the research objective, original pilot, reproducibility audit, spatial and label-sensitivity findings, expanded source preparation, relevant images, preservation checks and proposed next steps. The selected layers are 519-660 inclusive, a nominal XCT gauge-section scope within a 1,117-layer source file.')
    table(['Progress measure','Verified result'],[
        ['Prepared sensor patches','329,828'],['Specimens and layers','64 fatigue specimens; 142 layers; one build'],
        ['Candidate target counts','73,649 annotation-positive; 249,631 annotation-zero; 6,548 unknown'],
        ['Structural quarantine and exact duplicates','0 quarantined; 0 exact duplicate three-channel images'],
        ['Preservation','28 original small files SHA-256 unchanged; raw HDF5 read-only with unchanged size and modification time'],
        ['Current readiness','Prepared inputs available; final target interpretation and grouped ML evaluation pending']], [151,356])
    sub('What the next phase should produce')
    para('Use the prepared catalog to establish a defensible working target policy: the grid conversion, usable XCT support, annotation meaning and treatment of uncertain cases. Then generate a versioned target table and conduct a baseline evaluated on held-out specimens. The aim is a justified convention with stated uncertainty, rather than perfect calibration or an accuracy promise.')
    para('Navigation: research context and workflow; pilot evidence and images; expanded cleaning results; limitations and next steps; references; alignment and specimen appendices. PDF bookmarks provide section navigation.','small')
    page()

    # 2 Research context
    heading('Research objective and experimental source')
    para('Laser powder bed fusion (LPBF) builds a metal part layer by layer. Monitoring images describe the process and surface appearance while printing. X-ray computed tomography (XCT), measured after printing, provides information about the specimen interior. The FYP asks whether the monitoring images contain useful information about a corresponding dataset-detected internal flaw annotation.')
    para('The working observation is one <b>24 x 24 camera-grid patch</b> at a specimen, layer and location. It has three channels: visible post-melt, visible post-recoat and integrated-maximum near-infrared (NIR). Its candidate target is generated by this project from nonzero values in a mapped XCT flaw raster; the dataset did not supply these ready-made binary patch labels.')
    table(['Source feature','Meaning'],[
        ['Snow dataset [1]','One LPBF build containing 64 stainless-steel 316H fatigue cylinders; 60 were fatigue tested. These are not 60 separate builds.'],
        ['Local experimental file','2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5; 127,808,960,296 bytes, approximately 128 GB.'],
        ['Camera and ID grids','1,117 x 2,844 x 2,844; axes in storage are layer, Y and X.'],
        ['Registered XCT grids','1,117 x 13,752 x 13,752 for grayscale XCT and flaw annotations.'],
        ['Prepared source scope','64 named AMMTO Fatigue Bar geometries; layers 519-660 inclusive. Auxiliary spatter generators and the default tensile bar are outside this scope.'],
        ['Other source content','975 source layers remain outside this preparation pass. Their presence was indexed, not screened as prepared inputs.']], [136,371])
    sub('Processing already performed by the dataset authors')
    para('The author Methods describes illumination correction for visible images, lens calibration and homographic correction for the cameras, NIR aggregation, and XCT registration to build coordinates using point-to-plane ICP with RANSAC [2]. The released arrays already incorporate author processing. The present workflow does not blindly repeat homography correction or introduce a new tomography reconstruction.')
    para('The XCT flaws were detected algorithmically using a Laplacian-of-Gaussian response, thresholding and clustering [2]. A target should therefore be described as presence of a <b>dataset-detected XCT annotation</b>, not an independently verified count of physical pores.','small')
    page()

    # 3 Workflow
    heading('Workflow and the role of the pilot')
    para('The pilot was an engineering test of extraction, normalization, record alignment and candidate targets before processing a larger region. It now serves as a regression reference. Routine source preparation did not have to wait for every scientific target question to be resolved.')
    figure('fyp_workflow_checkpoint.png','Completed and pending stages. Source preparation is complete for the declared scope; final target validation and ML remain future work. The workflow separates mechanical preparation from scientific interpretation. [E1-E6]',maxheight=7.15*inch)
    page()

    # 4 Pilot
    heading('Pilot extraction and reproducibility audit')
    para('The original pilot selected specimens P2, P9, P16, P24, P35, P43, P52 and P60 at layer indices 540, 560, 580, 600, 620, 638 and 640. It contains 2,024 patches: 948 provisional positives and 1,076 provisional negatives. Each specimen contributes 253 patches. [E1]')
    table(['Audit result','Evidence'],[
        ['Internal checks','18 passed; 0 failed. Shapes, row order, labels, specimen IDs and layer IDs agree across NPZ and CSV.'],
        ['Finite and nonempty inputs','No NaN/Inf, wholly zero three-channel patches or wholly constant three-channel images.'],
        ['Uniqueness','No duplicate coordinate keys or exact duplicate three-channel image content in the pilot.'],
        ['Raw sensor reproduction','All 2,024 saved sensor patches reproduced exactly; maximum absolute feature difference 0.0.'],
        ['Original annotation counts','All 2,024 stored flaw-pixel counts reproduced under pilot_round; 0 mismatches.']], [135,372])
    figure('pilot_specimen_balance.png','Pilot class composition by selected specimen. Numbers above bars are provisional positive counts. P2, P35 and P43 contribute 730 of the 948 positives (77.0%). This selected pilot is not a build-wide defect-prevalence sample. [E1]',maxheight=3.2*inch)
    para('These results demonstrate internal consistency and reproducibility under the existing rules. They do not independently establish physical registration, usable XCT support or correctness of every target.','small')
    page()

    # 5 Positive negative trace
    heading('Traced sensor and XCT examples')
    para('The following two P16 examples are from layer 600. All displays use the original pilot_round crop convention. Visible values are shown on 0-255 and NIR on 0-65,535; XCT grayscale uses percentile contrast for viewing. Binary annotation displays indicate nonzero values, not pore counts. [E2]')
    figure('p16_positive_trace.png','Provisional positive example. Camera start (Y=1997, X=1994), patch 24 x 24; XCT crop Y=9656:9772, X=9642:9758. The original crop contains 308 nonzero annotation pixels. Cross-modality physical correspondence remains a candidate interpretation.',maxheight=3.3*inch)
    figure('p16_negative_trace.png','Provisional annotation-zero example. Camera start (Y=2021, X=1994); XCT crop Y=9772:9888, X=9642:9758. The crop contains zero nonzero annotation pixels. A zero annotation mask alone does not certify experimentally observed flaw-free material.',maxheight=3.3*inch)
    page()

    # 6 Rounding known example
    heading('Explaining the 308 versus 317 discrepancy')
    para('The earlier scripts selected slightly different XCT windows. They all used the same candidate scale, 13,752 / 2,844 = 4.835443037975, but differed in rounding each crop boundary. Python slices use half-open intervals: the stop index is not included. A one-pixel boundary difference can include or exclude a small annotation. [E2]')
    table(['Policy','Y bounds','X bounds','Nonzero pixels'],[
        ['Pilot round','9656:9772','9642:9758','308'],
        ['Floor start / ceil end','9656:9773','9641:9758','317'],
        ['Floor / floor','9656:9772','9641:9757','317']], [158,116,116,117])
    figure('known_positive_crop_rounding.png','The known positive annotation under the three candidate windows. All three give a positive target for this example, while selecting different pixels. This explains the count discrepancy without proving that any particular physical conversion is correct.',maxheight=3.3*inch)
    para('The original 308-pixel count is retained as the reproduction reference. It was not altered to match a slide. New report figures reproduce that reference and clearly retain provisional captions. The other methods are sensitivity alternatives, not accepted corrections.')
    sub('Why this matters beyond one figure')
    para('The known positive and adjacent zero example do not expose every boundary-sensitive case. Rechecking the full pilot showed that some small annotations do cross the current binary target boundary when a different window convention is used. That finding is quantified on the following page.')
    page()

    # 7 six flips
    heading('Six pilot targets depend on the crop convention')
    table(['Method','Positive targets','Labels changed','Counts changed'],[
        ['pilot_round','948','0','0'],['audit_floor_ceil','951','3','328'],['export_floor','948','6','347']], [185,105,108,109])
    para('The floor/floor method preserves the total of 948 positives but exchanges three negatives to positive and three positives to negative. Aggregate counts alone would miss those changes. The union is six pilot rows, 0.296% of the pilot. [E2]')
    figure('pilot_crop_sensitive_cases.png','Nonzero annotation pixels in the six pilot records whose current greater-than-zero target changes. These are small boundary-adjacent annotations. This is a pilot sensitivity result, not a complete count of boundary-sensitive cases in the expanded source set.',maxheight=3.3*inch)
    table(['Pilot row','Specimen / layer','Camera Y / X','Round / floor-ceil / floor'],[
        ['352','P9 / 560','2249 / 2097','0 / 3 / 3'],['803','P52 / 580','578 / 769','2 / 2 / 0'],
        ['956','P16 / 600','2021 / 1874','4 / 4 / 0'],['1017','P35 / 600','1188 / 381','0 / 3 / 3'],
        ['1153','P2 / 620','2306 / 381','3 / 3 / 0'],['1538','P16 / 638','2043 / 1969','0 / 4 / 4']], [66,117,131,193])
    page()

    # 8 threshold and constant NIR
    heading('Target threshold and sensor channel observations')
    para('The existing target rule is any nonzero annotation pixel in the candidate crop. This project-defined rule is provisional. Raising the minimum changes the target population substantially; thresholds must be justified from measurement meaning, not selected to improve a later model score. [E1]')
    figure('pilot_threshold_sensitivity.png','Pilot sensitivity to minimum annotation-pixel count. Positive counts for thresholds 1, 5, 10, 25, 50 and 100 are 948, 932, 909, 840, 727 and 545. No new threshold was selected.',maxheight=2.7*inch)
    figure('constant_nir_example.png','Pilot row 585: P2, layer 580, camera Y=2279, X=357. All 576 NIR values equal 65,535, while the visible channels vary. The condition reproduces from raw data. It is retained with a review flag; the stored maximum is not proof of physical saturation.',maxheight=2.2*inch)
    para('The expanded source set contains 11 constant NIR-channel patches. Neither those cases nor the six pilot crop-sensitive cases were silently deleted. More subtle image-quality decisions remain explicit policy choices.','small')
    page()

    # 9 production method
    heading('Expanded source preparation and cleaning rules')
    para('The tested extraction was expanded to all 64 named fatigue bars in the nominal gauge-section range, layers 519-660 inclusive. The source file remains immutable. Each layer is a separate compressed feature shard, avoiding a giant in-memory feature array. [E3]')
    table(['Step','Applied rule'],[
        ['Research scope','Select names containing AMMTO Fatigue Bar. Exclude background, auxiliary spatter generators and the default tensile bar from this declared experiment.'],
        ['Geometry scope','Use the original 24 x 24 grid and minimum part fraction 0.75. This is an inherited project heuristic, not an author-validated inclusion criterion.'],
        ['Standardized inputs','Float32 channels with existing divisors 255, 255 and 65,535. No learned scaling, imputation or new image filtering.'],
        ['Structural screening','Quarantine invalid shape, nonfinite values or all-three-channel-zero patches, retaining provenance.'],
        ['Quality observations','Retain constant/zero channel, stored-maximum and duplicate-content flags. Preserve source acquisition-event context.'],
        ['Candidate annotation','Reuse dimension-ratio mapping and rounded bounds. If the raw-positive intensity proxy is below 0.50 or bounds are invalid, export candidate -1. Otherwise use the provisional nonzero-annotation rule.'],
        ['Preservation and catalog','Exclusive new outputs, worker-version checks, per-shard hashes, stable sample IDs, resumable checkpoints and a canonical manifest.']], [118,389])
    sub('Why routine preparation could proceed')
    para('Mechanical image preparation and final target interpretation are related but distinct. Consistent inputs, provenance and uncertainty flags can be produced while mapping and annotation questions are investigated. Candidate targets stay separate from validation status, and no final y vector is exported.')
    para('Nominal layer bounds and sample templates describe processing scope or geometry. They are not independent experimental-support masks. Unknowns remain separate from candidate negatives.','small')
    page()

    # 10 Source results
    heading('Prepared source cohort and candidate composition')
    table(['Measure','Result'],[
        ['Prepared inputs','329,828 patches; 64 specimens; 142 layers; one build'],
        ['Candidate 1','73,649 (22.3295%): nonzero annotation under the candidate rule'],
        ['Candidate 0','249,631 (75.6852%): no nonzero annotation under the candidate rule'],
        ['Candidate -1','6,548 (1.9853%): unknown intensity-proxy or crop-bounds status'],
        ['Unique identities and raw image hashes','329,828 each; no exact duplicate three-channel content found'],
        ['Structural quarantine','0 extracted patches met the structural quarantine rules'],
        ['Geometry-scope positions excluded','115,484 candidate grid positions outside the inherited part-fraction selection']], [168,339])
    figure('source_candidate_composition.png','Candidate composition among all 329,828 prepared inputs. These are project-derived annotation candidates, not validated physical defect classes or porosity percentages. Unknowns are retained as a separate category. [E4]',maxheight=3.3*inch)
    para('All label and coverage validation flags remain false. This records unresolved evidence; it does not assert that all rows are physically wrong. The prepared source folder and catalog occupied about 1.55 GB at final QA, without copying or rewriting the approximately 128 GB experimental file.','small')
    page()

    # 11 layers
    heading('Layer coverage and unknown candidates')
    figure('source_candidates_by_layer.png','Prepared inputs and provisional candidates by layer. Unknown candidates increase near the nominal range end; layer 660 has 1,147 unknowns among 2,368 prepared patches. This is an intensity-proxy-derived observation, not independent proof of measured XCT support. [E4]',maxheight=4.65*inch)
    para('The author notes identify approximately layer 519 as the start of gauge-section XCT and layer 660 as its approximate end. Those notes guided the preparation scope, but they do not prove that every nominally included camera region has usable reconstructed XCT. The rise in unknowns is a reason to make support explicit rather than convert every empty annotation crop to class 0.')
    para('The other 975 source layers are indexed but were not prepared in this pass. They may support later sensor-only work or an expanded study; they should not be silently mixed into the current supervised-target population.')
    para('Per-layer and per-specimen tables are included in the catalog. The two specimen-composition appendices show all 64 groups. Patches within a specimen and nearby layers are related observations; a large patch count does not create the same number of independent experiments.','small')
    page()

    # 12 quality
    heading('Quality observations and how they were handled')
    table(['Observation','Rows','Treatment and interpretation'],[
        ['Any quality flag','72,754','Retained. Includes informational endpoints and acquisition context; not a count of unusable samples.'],
        ['Any channel has a stored-maximum pixel','65,712','Retained and recorded. An endpoint value alone does not establish physical saturation.'],
        ['Constant NIR channel','11','Retained for review. No automatic missing-channel treatment or exclusion was chosen.'],
        ['Author acquisition-event context','2,119','Retained. Layer 602 notes a subsequent-layer laser spot in the post-spreading image. The affected spatial region is not inferred from the note alone.'],
        ['Insufficient raw-XCT positive proxy','6,548','Retained inputs with candidate target -1. The proxy itself is not validated measured support.'],
        ['Exact duplicate image content','0','Global raw three-channel content hashes checked across the declared extraction.'],
        ['Structural quarantine','0','No extracted patch met invalid-shape, nonfinite or wholly empty-image rules.']], [179,58,270])
    para('These flag categories overlap and must not be summed to estimate bad rows. Zero structural quarantines does not mean every sensor measurement or target is scientifically valid. It means the extracted inputs passed these explicit mechanical conditions. [E3-E4]')
    sub('No unjustified pixel repair or exclusion')
    para('The workflow does not smooth images, replace bright pixels, relabel edge cases or drop an entire layer merely because it has a source note. Such changes could remove useful process signal or alter the experiment. Any additional action should have a documented reason, preserve the original data and be tested as a declared policy.')
    page()

    # 13 Scientific interpretation
    heading('What remains uncertain about the targets')
    sub('Exact registered-grid conversion')
    para('The authors registered both modalities to build coordinates [1-2]. The present code assumes the camera and XCT rasters share an extent and origin, then maps boundaries by their dimension ratio. The inspected material does not specify the exact registered XCT outer extent, center/boundary convention, numeric affine transform or registration-error estimate needed to independently confirm that index conversion.')
    para('The root describes a nominal 245 mm camera field. A 13,752-pixel grid spanning exactly 245 mm would have 17.81559046 micrometre spacing. The Methods quotes a nominal 17.8 micrometre acquisition voxel size, which spans 244.7856 mm across that dimension. This 0.2144 mm difference may reflect rounding or registered resampling; it is not a demonstrated spatial error or justification to switch transforms automatically.')
    sub('Measured support and the meaning of a zero')
    para('Raw XCT greater than zero is only a proxy. The sample-ID raster describes nominal gauge geometry, and all logical XCT chunks are allocated; neither template membership nor allocation independently proves usable measurements at each pixel. Candidate 0 means no annotation in the candidate crop under the current rule, not certified flaw-free material.')
    sub('Detector semantics and uncertainty')
    para('The flaw raster is algorithmically generated and sampled values are not only 0/1. The exact value encoding, detector limits and minimum-size interpretation should be clarified. Nonzero-pixel counts do not count distinct pores. Tiny boundary annotations should be handled with an explicit convention and uncertainty policy. The six demonstrated crop-sensitive labels belong to the pilot; the full production boundary-sensitive population has not been exhaustively re-quantified.')
    sub('Methodological context from the supplied paper')
    para('Dinh, Muller and Quinsat [3] describe perspective correction and conventional optical processing, with a CT comparison, for four Inconel 718 parts. It supports making local correspondence and interpretation explicit. It concerns a different experiment and does not validate the Snow transform or require this FYP to implement a new 3D reconstruction pipeline.')
    page()

    # 14 Next steps
    heading('Recommended next phase and expected deliverables')
    para('Build on the completed prepared-source catalog. The next scientific deliverable should be a working target and uncertainty policy that applies to the 64-specimen cohort, rather than another small pilot or a repeated broad audit.')
    table(['Next milestone','Concrete output and acceptance point'],[
        ['1 Justify the target policy','Document the grid convention and evidence or explicit assumptions; define usable support and annotation-positive, annotation-zero and unknown cases. State residual uncertainty.'],
        ['2 Apply the policy to the catalog','Create a new target table linked by stable sample_id. Preserve current inputs and original candidates; record changes, exclusions and uncertainty flags with reasons.'],
        ['3 Prepare grouped evaluation','Use whole-specimen holdouts or grouped cross-validation across the 64 available groups. Record class composition in each split. Fit learned preprocessing on training groups only.'],
        ['4 Evaluate a simple baseline','Compare a small, predeclared set of simple features/models and visible-only, NIR-only and combined inputs. Include a trivial comparator, class-sensitive metrics and error analysis.'],
        ['5 Write the FYP results','Explain the preparation, policy, evaluation and limitations with reproducible figures. A useful signal, limited signal or lack of support for the chosen target are all possible experimental outcomes.']], [139,368])
    sub('Questions for the supervisors or dataset authors')
    bullets(['Can an author conversion example or registered-grid definition establish the camera-to-XCT convention and layer correspondence?',
             'What denotes usable reconstructed XCT support, distinct from nominal geometry or nonzero intensity?',
             'What do stored flaw values encode, and what detection or registration limits should inform tiny boundary annotations?',
             'Which treatment of uncertain targets and questionable channels best matches the agreed feasibility-study claim?'])
    para('The goal is a defensible experiment with stated uncertainty. Perfect calibration is not an automatic prerequisite for every preparatory task, but approval of a convenient policy cannot substitute for missing physical evidence. No ML accuracy, cross-build generalisation or final academic outcome can be promised.')
    page()

    # 15 QA preservation
    heading('Preservation and verification evidence')
    table(['Check','Scope and result'],[
        ['Original files','28 pre-existing scripts, pilot files, old results and small records retain their original SHA-256 hashes.'],
        ['Raw HDF5','Read-only opens; size and modification time unchanged. No full 128 GB checksum was computed.'],
        ['Coordinate regression','Four unit tests cover recorded bounds, adjacent half-open boundaries, separate X/Y scales and unknown-policy rejection.'],
        ['Independent crop verification','All 2,024 pilot bounds independently recomputed using rational arithmetic; two opposite target flips directly reread from raw data.'],
        ['Production regression','All 264 overlapping layer-600 pilot records match feature bytes and candidate counts in the 64-specimen batch.'],
        ['Independent new-source QA','12 records, four layers and four previously unpiloted specimens directly reread. Included unknown, positive and zero candidates. Sensor bytes, hashes, counts and status fields agreed.'],
        ['Complete catalog','All feature/manifest shard hashes and NPY headers verified; globally unique IDs; exact-content index; SQLite integrity; complete count reconciliation.'],
        ['Overwrite and resume guards','Completed outputs refused reuse; checked files unchanged. A concurrent duplicate attempt was stopped by exclusive creation and resumed using the completed shard after provenance checks.']], [141,366])
    para('The independent production spot check covers 12 records, not a second raw reread of all 329,828 patches. Catalog verification checks complete hashes and array headers; it does not independently recompute every source feature value. The producer performs the per-patch mechanical checks. These distinctions keep the strength of the evidence proportionate. [E5-E6]')
    para('No original scripts were bulk-run. New code and new output folders separate reproducibility references from generated results. No package installation, final split assignment, learned preprocessing, model fitting, tuning or evaluation was performed.')
    page()

    # 16 references
    heading('References and evidence map')
    para('<b>[1]</b> Z. Snow, L. Scime, C. Joslin, W. Halsey, A. Marquez Rossy, A. Ziabari, V. Paquit and R. Dehoff. <i>In situ Visible Light and Thermal Imaging Data from a Laser Powder Bed Fusion Additive Manufacturing Process Co-Registered to X-ray Computed Tomography and Fatigue Data.</i> Oak Ridge National Laboratory, 2025. Dataset DOI: <link href="https://doi.org/10.13139/ORNLNCCS/2524534" color="#1864ab">10.13139/ORNLNCCS/2524534</link>. The accompanying README identifies Zackary Snow and 19 March 2025 as its author/date.')
    para('<b>[2]</b> Author-supplied <i>Methods.docx</i> and README accompanying the Snow dataset. Local verified copies: <font name="Arial-Italic">references/Snow_Methods.docx</font> and <font name="Arial-Italic">references/Snow_README.txt</font>. These supplements were read locally; no separate companion journal publication is asserted.')
    para('<b>[3]</b> D. M. Dinh, N. Muller and Y. Quinsat. <i>Layering Defects Detection in Laser Powder Bed Fusion using Embedded Vision System.</i> Computer-Aided Design &amp; Applications 18(5), 1111-1118, 2021. DOI: <link href="https://doi.org/10.14733/cadaps.2021.1111-1118" color="#1864ab">10.14733/cadaps.2021.1111-1118</link>. Supplied PDF copied to references/Dinh_Muller_Quinsat_2021_Layering_Defects.pdf.')
    sub('Local evidence records')
    table(['ID','Project-relative record'],[
        ['E1','results/data_quality/2026-11-08_run01/pilot/final/pilot_audit.json'],
        ['E2','results/data_quality/2026-11-08_run01/spatial/summary.json and candidate_crop_comparison.csv'],
        ['E3','data/cleaned/snow_source_preparation_v1/production_summary.json and source_config.json'],
        ['E4','data/cleaned/snow_source_preparation_v1/catalog/summary.json, per_layer.csv and per_specimen.csv'],
        ['E5','data/cleaned/snow_source_preparation_v1/qa/independent_source_sample_checks.json and final_catalog_verification.json'],
        ['E6','results/data_quality/2026-11-08_run01/verification/source_preparation_preservation.json and spatial_independent_verification.json']], [42,465])
    para('Figure data and provenance are retained beside this PDF in assets/figure_sources.json and example_figure_sources.json. All experimental images are from the local Snow source file and are displayed with the documented provisional conversion. No synthetic experimental observations or performance results are included.','small')
    page()

    # 17-19 Alignment gallery
    for part_id in (2,16,24):
        heading(f'Appendix Candidate alignment views for P{part_id}')
        para('Camera-grid axes are used throughout. Blue solid outlines show the part template; orange dashed outlines show sample-template geometry. The outlines may coincide. XCT grayscale uses percentile contrast. Every cross-grid panel uses the candidate scale mapping; visual agreement alone does not establish exact calibration.','small')
        for layer in (540,600,640):
            figure(f'alignment_P{part_id}_L{layer}.png',f'P{part_id}, layer {layer}: visible image, registered XCT grayscale and nonzero annotation mask. Candidate mapping and targets remain provisional. [E2]',maxheight=2.48*inch)
        page()

    # 20-21 full cohort figures
    for filename,title in [('source_specimen_composition_P02_P33.png','Appendix Source specimens P2 to P33'),
                           ('source_specimen_composition_P35_P66.png','Appendix Source specimens P35 to P66')]:
        heading(title)
        figure(filename,'Composition of prepared inputs across the declared layer range. Blue is candidate 1, gray candidate 0 and orange unknown. All categories are provisional; n is the prepared patch count for that specimen. These are groups within one build, not independent build replicates. [E4]',maxheight=8.35*inch)
        page()

    # 22 distribution appendix
    heading('Appendix Pilot channel distributions')
    figure('pilot_channel_distributions.png','Pilot normalized input distributions. The three channels use the existing divisors 255, 255 and 65,535. Density describes stored pixel values, not a calibrated physical temperature or detector certainty. [E1]',maxheight=4.7*inch)
    para('All pilot values are finite and lie in [0,1]. Across the pilot NIR pixels, 4.377% are at the stored maximum. A maximum endpoint alone is not proof of physical saturation. These plots describe the earlier pilot, not the complete production cohort.')
    para('The fuller source quality summary records 65,712 rows with a maximum endpoint in at least one channel. This is a row-level informational statistic and is different from the pilot pixel-level percentage above. Denominators and populations should not be mixed. [E4]')
    page()

    # 23 dictionary
    heading('Appendix Data dictionary and usable artifacts')
    table(['Field or artifact','Definition and practical limit'],[
        ['sample_id','Stable identifier containing source layer, specimen, camera Y/X and patch size.'],
        ['X','Float32 feature array with shape N x 3 x 24 x 24 in each layer shard.'],
        ['candidate_y','Signed int8: -1 unknown proxy/bounds, 0 no annotation under the candidate rule, 1 nonzero annotation. Not final scientific ground truth.'],
        ['groups / layers / coords','Specimen IDs, source layer indices and camera Y/X array-slice starts. Layer index is not a physical distance or timestamp.'],
        ['part_fraction','Fraction of the camera patch belonging to the selected part. Existing minimum 0.75 is a project heuristic.'],
        ['XCT bounds and count','Half-open rounded candidate crop and nonzero annotation pixels; not pore count or porosity.'],
        ['raw_xct_positive_proxy','Fraction of grayscale XCT crop greater than zero. A proxy, not validated experimental support.'],
        ['sample_template_ids','Nominal geometry lookup IDs. Part IDs and sample IDs use different lookups.'],
        ['quality_flags','Review observations and acquisition context. Categories overlap; flags do not imply automatic exclusion.'],
        ['label_validated / coverage_validated','False for every prepared row at this checkpoint; unresolved evidence, not a declaration that every row is wrong.'],
        ['feature_shard / feature_row','Project-relative compressed NPZ path and row position, permitting bounded loading.'],
        ['catalog manifest','Canonical CSV linking every prepared row to features, candidates, geometry, source paths and quality/provenance fields.']], [154,353])
    para('Location: data/cleaned/snow_source_preparation_v1/. The catalog README explains usage; each layers/layer_NNNN/ folder contains features.npz, manifest.csv, summary.json and shard provenance. Quarantine or geometry-scope records are separate when present. The original data/processed pilot remains unchanged.','small')
    page()

    # 24 reproducibility appendix
    heading('Appendix Reproducibility and progress checklist')
    table(['Component','Location or parameter'],[
        ['Active project','C:/NUS/FYP/FYP Organized'],
        ['Environment','Existing .venv; Python 3.11.4. NumPy 2.4.6, h5py 3.16.0, Matplotlib 3.11.2, SciPy 1.17.1, pandas 3.1.0, Pillow 13.0.0.'],
        ['Code','src/cleaning_pipeline/; original src/*.py retained.'],
        ['Pilot audit','audit_pilot.py; compare_spatial.py; inspect_registration.py; run_audit.py.'],
        ['Source preparation','index_source_layers.py; prepare_source_layer.py; prepare_source_dataset.py.'],
        ['Catalog and report','consolidate_source_preparation.py; write_source_report.py.'],
        ['Saved provenance','Per-shard file hashes; catalog/shard_verification.json; QA records; environment snapshot and pinned audit-package list.']], [131,376])
    sub('Checklist at the report date')
    bullets(['Complete: source inventory and original-script review; pilot audit and exact reproduction.',
             'Complete: expanded 64-specimen, 142-layer extraction, quality screening and catalog consolidation.',
             'Complete: provenance, overwrite guards, preservation checks, representative figures and this progress report.',
             'Pending: a justified working mapping/support/annotation policy and a versioned final or uncertainty-aware target table.',
             'Pending: grouped evaluation design, baseline models, modality comparisons and error analysis.'])
    para('Existing completed runs refuse overwrite. For a new run, use a new output directory and preserve fixed parameters and source version. A resumed incomplete job verifies completed shards before reusing them. Baseline evaluation should follow a documented target policy and split design.')
    para('<b>Suggested supervisor update:</b> I have prepared 329,828 three-channel sensor patches across 64 specimens and 142 nominal gauge layers, while preserving the source data. I reproduced the original pilot, quantified crop-boundary sensitivity, separated unknown candidate targets and retained quality flags. The next step is to justify the working target policy and then evaluate a simple baseline on held-out specimens.')

    doc=Report(PDF)
    doc.build(story)
    with (BASE/'report_manifest.json').open('w',encoding='utf-8') as handle:
        json.dump({'pdf':str(PDF),'section_pages':doc.section_pages,'figures':figures,'figure_count':len(figures),
                   'authoritative_source_rows':total,'source_status':catalog['stage'],'no_new_ml_training':True},handle,indent=2)
    print(json.dumps({'pdf':str(PDF),'pages':doc.page,'figures':len(figures),'sections':doc.section_pages},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--replace',action='store_true',help='Replace only this generated report during layout QA')
    args=parser.parse_args()
    if PDF.exists() and not args.replace:
        raise FileExistsError(PDF)
    build()
