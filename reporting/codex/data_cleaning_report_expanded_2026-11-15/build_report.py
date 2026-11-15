import json, hashlib
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
from pypdf import PdfReader

ROOT=Path(r'C:/NUS/FYP/FYP Organized')
BASE=Path(r'C:/Users/Felix/Documents/Codex/2026-11-08/can')
WORK=BASE/'work/data_cleaning_report_expanded_2026-11-15'
ASSETS=BASE/'work/consolidated_report_2026-11-09/assets'
OUTPUT=BASE/'outputs/FYP_Data_and_Cleaning_Update_2026-11-15.pdf'
summary_path=ROOT/'data/cleaned/snow_source_preparation_v1/catalog/summary.json'
summary=json.loads(summary_path.read_text())
pdfmetrics.registerFont(TTFont('Arial',r'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialBold',r'C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='ArialBold',italic='Arial',boldItalic='ArialBold')
W,H=A4
M=44
CW=W-2*M
NAVY=HexColor('#17324B');BLUE=HexColor('#245E91');GRAY=HexColor('#536574');LIGHT=HexColor('#E8EDF2')
styles={
 'body':ParagraphStyle('body',fontName='Arial',fontSize=10.2,leading=13.4,textColor=NAVY,spaceAfter=6),
 'small':ParagraphStyle('small',fontName='Arial',fontSize=8.6,leading=11.1,textColor=GRAY),
 'cell':ParagraphStyle('cell',fontName='Arial',fontSize=9.5,leading=12.2,textColor=NAVY),
 'ref':ParagraphStyle('ref',fontName='Arial',fontSize=8.55,leading=11.05,textColor=NAVY),
 'h':ParagraphStyle('h',fontName='ArialBold',fontSize=12.5,leading=15.4,textColor=BLUE),
}
c=canvas.Canvas(str(OUTPUT),pagesize=A4,pageCompression=1)
c.setTitle('FYP data preparation and cleaning update')
c.setAuthor('Felix')
c.setSubject('Snow LPBF dataset, preparation scope, technical quality checks and unresolved XCT interpretation')
page_ends=[]

def p(txt,y,style='body',width=CW,x=M,gap=6):
    para=Paragraph(txt,styles[style]);_,hh=para.wrap(width,H)
    if y+hh>H-43: raise RuntimeError(f'Content exceeds page {c.getPageNumber()}: {y+hh:.1f}')
    para.drawOn(c,x,H-y-hh)
    return y+hh+gap

def heading(txt,y): return p(txt,y,'h',gap=7)

def table(rows,widths,y,header=True):
    cellrows=[[Paragraph(str(a),styles['cell']) for a in r] for r in rows]
    t=Table(cellrows,colWidths=widths,hAlign='LEFT')
    rules=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,-1),.4,LIGHT)]
    if header: rules += [('BACKGROUND',(0,0),(-1,0),LIGHT)]
    t.setStyle(TableStyle(rules));_,hh=t.wrap(CW,H)
    if y+hh>H-43: raise RuntimeError(f'Table exceeds page {c.getPageNumber()}: {y+hh:.1f}')
    t.drawOn(c,M,H-y-hh)
    return y+hh+9

def image(path,y,width=CW):
    with Image.open(path) as im: iw,ih=im.size
    height=width*ih/iw
    c.drawImage(str(path),M,H-y-height,width=width,height=height,mask='auto')
    return y+height+5

def start(title,n,subtitle=None):
    c.setFillColor(NAVY);c.setFont('ArialBold',20 if n==1 else 18)
    c.drawString(M,H-50,title)
    c.setStrokeColor(LIGHT);c.setLineWidth(.6);c.line(M,39,W-M,39)
    c.setFont('Arial',8.3);c.setFillColor(GRAY)
    c.drawString(M,25,'FYP data preparation update - Felix')
    c.drawRightString(W-M,25,f'{n} / 6')
    y=67
    if subtitle: y=p(subtitle,y,'small',gap=9)
    return y

def end(y):
    page_ends.append({'page':c.getPageNumber(),'content_bottom_from_top':round(y,2)})
    c.showPage()

y=start('FYP data preparation and cleaning update',1,'Prepared 15 November 2026. Evidence: preparation completed 8 November 2026; unchanged catalogue verified 15 November 2026.')
y=heading('Executive Summary',y)
y=p('The selected Snow sensor data have been extracted, consistently scaled and checked for technical problems. The prepared set contains <b>329,828 image patches from 64 specimens across 142 layers</b>. These counts describe local image windows, not pores. The linked XCT-derived statuses remain provisional because physical crop correspondence, usable XCT coverage and annotation meaning still need confirmation. [1-3]',y)
y=heading('The research data and project aim',y+2)
y=p('Laser powder bed fusion (LPBF) builds a metal part by melting successive powder layers. Cameras record the process; post-build X-ray computed tomography (XCT) images the inside of the finished part. The FYP investigates how the process images relate to local internal-flaw indications. The Snow release contains one build of stainless-steel 316H fatigue specimens. [1]',y)
y=table([
 ['<b>Quantity</b>','<b>What it means</b>'],
 ['64 specimens','Separate fatigue parts from the same manufacturing build.'],
 ['1,117 source layers','The source camera record contains this many layer images.'],
 ['142 prepared layers','Layers 519-660 inclusive, the nominal XCT gauge-section window around the central test region of the fatigue parts. The other 975 layers are outside this preparation scope.'],
 ['329,828 patches','Each patch is one local 24 x 24 camera-pixel window with three sensor channels, at a recorded specimen, layer and location.'],
 ],[115,CW-115],y)
y=image(ASSETS/'one_sensor_patch.png',y+1)
y=p('<b>Figure 1.</b> The three channels in one prepared patch: visible after melting, visible after powder spreading, and near-infrared (NIR) integrated maximum. Colour scales show fixed normalised stored intensity from 0 to 1. NIR values are not calibrated temperatures. Example: specimen P4, source layer 600. [1,2]',y,'small')
y=heading('What the released files already contain',y+1)
y=p('The source authors corrected and aligned the camera data, aggregated NIR frames, and reconstructed and registered the XCT volumes. The release also contains an algorithm-generated XCT flaw map. This FYP preparation extracts local records from those supplied arrays and preserves their source locations. [1]',y)
end(y)

y=start('What the cleaning did and what the counts mean',2)
y=table([
 ['<b>Preparation step</b>','<b>Reason and recorded outcome</b>'],
 ['Select the research region','Use the supplied maps of the 64 fatigue-part outlines and the selected height window. Retain a 24 x 24 patch when at least 75% of its pixels belong to the part outline. This limits background; 115,484 proposed patch windows were excluded by this rule.'],
 ['Scale and check sensor values','Divide visible values by 255 and NIR values by 65,535, then store decimal arrays. Fixed scaling retains intensity differences between patches. Check array dimensions, invalid numeric values and all-zero three-channel records.'],
 ['Preserve quality information','Retain review flags for flat image channels, pixels at the top of their stored intensity range, and author acquisition notes. Save specimen/layer coordinates, source paths and checksums so each patch can be traced back.'],
 ['Record a provisional XCT status','Look up an XCT crop using the saved camera-to-XCT index rule. Check crop bounds and a positive-intensity proxy before recording whether any nonzero flaw-map pixels occur. Unknowns remain distinct from zero.'],
 ],[128,CW-128],y)
y=heading('The current XCT-derived status of each patch',y+2)
y=image(WORK/'candidate_counts.png',y)
y=p('<b>Figure 2.</b> Counts and shares use <b>all 329,828 prepared patches</b> as the denominator. The three categories add to the prepared total. These are patch-status shares, not porosity or the percentage of defective specimens. [2,3]',y,'small')
y=table([
 ['<b>Status</b>','<b>Plain-language meaning</b>'],
 ['Candidate 1: 73,649 (22.3%)','At least one nonzero annotation pixel occurs in the current XCT crop. This is a working indication, not a confirmed physical pore.'],
 ['Candidate 0: 249,631 (75.7%)','No nonzero annotation pixel occurs under the same crop rule. This does not establish that the material is pore-free.'],
 ['Unknown (-1): 6,548 (2.0%)','All current unknowns have too few positive-valued XCT pixels under the screening rule. They are preserved rather than assigned to candidate 0.'],
 ],[155,CW-155],y)
y=p('<b>Technical checks:</b> 0 extracted patches set aside for structural problems and 0 exact three-channel duplicates. <b>72,754 patches carry at least one review flag</b>, including 11 whose NIR window has one value throughout. Flags can overlap and do not, by themselves, mean an image is unusable. Original source data remain unchanged. [2,3]',y)
end(y)

y=start('How the prepared records are distributed',3)
y=p('The patch total summarises one selected height window in one build. The catalogue records <b>2,112-2,368 patches per layer</b> and <b>5,145-5,161 per specimen</b>. Similar image counts do not imply similar XCT-derived statuses. The following charts retain all prepared patches, including unknowns. [2]',y)
y=image(WORK/'distribution_by_layer.png',y+2)
y=p('<b>Figure 3.</b> Status composition in each of the 142 prepared layers. Each vertical slice sums to 100% of that layer\'s prepared patches. A candidate-1 share describes the fraction of windows containing annotation pixels under the current mapping. It is not a pore-volume measurement. Source: catalogue per_layer.csv. [2]',y,'small')
y=p('<b>The overall 2.0% unknown share is unevenly distributed.</b> Layers 656-660 contain 4,630 of the 6,548 unknowns (70.7%). Layer 660 alone has 1,147 unknowns among 2,368 prepared patches (48.4%). These figures describe failure of the current screening proxy; they do not establish a measured-coverage boundary or prove unusable XCT. [2,3]',y)
y=image(WORK/'distribution_by_specimen.png',y+3)
y=p('<b>Figure 4.</b> Status composition for all 64 specimens, in numerical ID order. Each bar sums to 100% of that specimen\'s prepared patches. Only some ID labels are printed for readability. This is not a physical build-position map. Source: catalogue per_specimen.csv. [2]',y,'small')
y=p('All 64 selected specimens contribute records. Unknowns occur in 39 specimens, while the proportion of candidate-1 patches also varies substantially. The 329,828 patch windows represent detailed local sampling within a single build, not that many independent manufacturing experiments. [1,2]',y)
end(y)

y=start('Quality flags and evidence of correct extraction',4)
y=p('<b>72,754 of 329,828 patches (22.1%) have at least one review flag.</b> A flag preserves information for interpretation. It is not an automatic rejection or a confirmed defect. The categories below overlap, so their counts must not be added to obtain a number of distinct flagged patches. [2,3]',y)
y=table([
 ['<b>Recorded flag</b>','<b>Distinct patches</b>','<b>Meaning and limit</b>'],
 ['Any channel reaches its stored maximum','65,712 (19.9%)','At least one pixel is at the channel\'s numeric endpoint. This alone does not prove sensor saturation or an unusable image.'],
 ['Constant NIR window','11 (less than 0.01%)','All NIR pixels in that local window have the same value. The visible channels can still vary.'],
 ['Author acquisition-event context','2,119 (0.6%)','The source layer note identifies a context requiring regional interpretation. It does not prove that every flagged patch is affected.'],
 ['Low positive-intensity XCT proxy','6,548 (2.0%)','These are the unknown-status records. The proxy is a screening rule, not a validated mask of measured material.'],
 ],[132,90,CW-222],y)
y=heading('What the saved verification actually checked',y+1)
y=table([
 ['<b>Check</b>','<b>Recorded evidence and its boundary</b>'],
 ['Output consistency','The catalogue reconciles all 142 layer records and 329,828 patch entries. Saved verification confirms the layer-file checksums and catalogue totals. This checks consistency, not physical labels.'],
 ['Direct-source spot checks','12 deliberately selected records across 4 layers and 4 specimens reproduced sensor values, source-content hashes, crop annotation counts and the intensity proxy. This is a limited engineering sample, not an estimate of true-flaw accuracy.'],
 ['Source preservation','Preparation opened the original source in read-only mode. File size and modification time remained unchanged during the recorded run. No new raw-volume extraction was performed for this report.'],
 ['Protection against accidental overwrite','Saved checks confirm that completed extraction and consolidation outputs refused reuse and remained unchanged.'],
 ],[132,CW-132],y)
y=heading('Traceability remains attached to every patch',y+2)
y=p('Each record retains its specimen ID, layer, camera location, part fraction, current XCT crop bounds, provisional status, quality flags and source-content identifier. The local three-channel image data and catalogue index remain linked, so a reported example can be located and checked again. [2,3]',y)
y=p('<b>What this establishes:</b> the selected data have a reproducible preparation trail and recorded technical checks. <b>What remains open:</b> the physical interpretation of crop correspondence, usable XCT support and annotations described on page 5. Zero structural rejections and zero exact duplicates do not establish that all data are scientifically validated.',y)
end(y)

y=start('XCT correspondence and points needing input',5)
y=p('The camera and registered XCT arrays use different grids: 2,844 x 2,844 and 13,752 x 13,752 pixels per layer. The current lookup applies their dimension ratio, approximately 4.835, and rounds the crop boundaries. That is a reproducible index rule; its exact physical correspondence remains unvalidated. [1-3]',y)
y=image(ASSETS/'source_xct_examples.png',y+1)
y=p('<b>Figure 5.</b> Illustrative candidate-1, candidate-0 and unknown patches with their current XCT crops. White mask pixels denote nonzero flaw annotations. The bottom crop has a positive-intensity fraction of 0.171, below the 0.50 threshold. This fraction is a screening proxy, not a measured-coverage mask. CT grey levels use one shared display range across these examples. Annotation-pixel counts are not pore counts. [2,3]',y,'small')
y=heading('Scientific interpretation still requiring confirmation',y+2)
y=p('<b>Grid correspondence.</b> What physical origin, extent and pixel-centre or pixel-boundary convention should relate the camera grid to the registered XCT grid? The released registration alone does not verify this local crop conversion.',y)
y=p('<b>Usable XCT support.</b> What field or mask establishes where XCT measurements are valid? The current rule requires at least half of the crop pixels to have stored XCT intensity above zero; zero intensity can have several meanings.',y)
y=p('<b>Annotation meaning.</b> Is any nonzero flaw-map pixel an appropriate working indication for a local patch, and how should boundary or uncertain cases be interpreted? All label-validation and coverage-validation flags remain false. [2,3]',y)
end(y)

y=start('Relation to the supplied paper and resources',6)
y=heading('Dinh, Muller and Quinsat (2021)',y)
y=p('The paper connects visible process observations with CT assessment in LPBF. It uses geometric alignment and image processing to form potential-defect regions. This supports the FYP\'s motivation for linking process images to XCT evidence and makes accurate spatial correspondence important. [4]',y)
y=p('Its reported CT comparison is global across four Inconel 718 parts. It does not establish matched local pore detection or validate the Snow crop mapping. The Snow build uses a different material, machine and reference-processing method. The paper therefore provides methodological context, while the local interpretation questions on page 5 remain open. [1,4]',y)
y=heading('The three tomography resources',y+2)
y=table([
 ['<b>Resource</b>','<b>Documented role and relevance to the present data</b>'],
 ['TomoPy [5]','Tomographic reconstruction and processing, including filtering and projection operators. The current FYP data already include reconstructed XCT volumes.'],
 ['Algotom [6]','Tomographic preprocessing, reconstruction and postprocessing. Its operations on reconstructed volumes include statistics, rescaling and reslicing, which relate to volume inspection.'],
 ['ASTRA Toolbox [7]','2D/3D tomography algorithms and GPU projection/backprojection using specified imaging geometries. Its main role concerns reconstruction and projection calculations.'],
 ],[110,CW-110],y)
y=p('These packages describe available tomography operations. The cleaning described here uses the supplied reconstructed, registered XCT; none of the packages by itself establishes annotation meaning, physical crop alignment or usable measured coverage. [1,5-7]',y)
y=heading('Sources',y+3)
refs=[
 '[1] Snow, Z., et al. (2025). <i>In situ Visible Light and Thermal Imaging Data from a Laser Powder Bed Fusion Additive Manufacturing Process Co-Registered to X-ray Computed Tomography and Fatigue Data.</i> ORNL. <link href="https://doi.org/10.13139/ORNLNCCS/2524534" color="#245E91">doi:10.13139/ORNLNCCS/2524534</link>. Dataset descriptions: supplied Snow_README.txt and Snow_Methods.docx.',
 '[2] FYP preparation catalogue, completed 8 November 2026: data/cleaned/snow_source_preparation_v1/catalog/summary.json, manifest.csv, per_layer.csv and per_specimen.csv. Counts and metadata independently checked on 15 November 2026. Figures 1 and 5 use traceable prepared records; Figures 2-4 use catalogue counts.',
 '[3] FYP preparation configuration and code: source_config.json, production_summary.json and src/cleaning_pipeline/prepare_source_layer.py. Saved QA: independent_source_sample_checks.json, final_catalog_verification.json and completed_output_guard_checks.json. Original source reads used read-only mode. Engineering checks do not establish physical registration.',
 '[4] Dinh, D. M., Muller, N., and Quinsat, Y. (2021). <i>Layering Defects Detection in Laser Powder Bed Fusion using Embedded Vision System.</i> Computer-Aided Design &amp; Applications, 18(5), 1111-1118. Supplied PDF. <link href="https://doi.org/10.14733/cadaps.2021.1111-1118" color="#245E91">doi:10.14733/cadaps.2021.1111-1118</link>.',
 '[5] <link href="https://tomopy.readthedocs.io/en/stable/" color="#245E91">TomoPy official documentation</link>. [6] <link href="https://algotom.readthedocs.io/en/latest/" color="#245E91">Algotom official documentation</link> and <link href="https://algotom.readthedocs.io/en/latest/toc/api/algotom.post.postprocessing.html" color="#245E91">postprocessing API</link>. [7] <link href="https://astra-toolbox.com/" color="#245E91">ASTRA Toolbox official documentation</link>. Accessed 15 November 2026.'
]
for ref in refs:y=p(ref,y,'ref',gap=6)
end(y)
c.save()
reader=PdfReader(str(OUTPUT))
assert len(reader.pages)==6
text='\n'.join(page.extract_text() or '' for page in reader.pages)
for forbidden in ['baseline','pilot','recommendation']:
    assert forbidden not in text.lower(),forbidden
for expected in ['329,828','73,649','249,631','6,548','72,754','Dinh','TomoPy','Algotom','ASTRA']:
    assert expected in text,expected
links=[]
for page in reader.pages:
    for annotation in page.get('/Annots',[]):
        action=annotation.get_object().get('/A',{})
        if action.get('/URI'):links.append(str(action['/URI']))
assert len(links)>=6
(WORK/'report_text.txt').write_text(text,encoding='utf8')
qa={'output':str(OUTPUT),'pages':len(reader.pages),'sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),'page_ends':page_ends,'links':links,'catalog_sha256':hashlib.sha256(summary_path.read_bytes()).hexdigest(),'evidence_completed':'2026-11-08','report_date':'2026-11-15','raw_hdf5_read_this_report':False}
(WORK/'build_record.json').write_text(json.dumps(qa,indent=2),encoding='utf8')
print(json.dumps(qa,indent=2))
