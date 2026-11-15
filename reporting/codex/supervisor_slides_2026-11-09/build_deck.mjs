import fs from 'node:fs/promises';

const ROOT = 'C:/NUS/FYP/FYP Organized';
const ASSETS = 'C:/Users/Felix/Documents/Codex/2026-11-08/can/work/consolidated_report_2026-11-09/assets';
export const BUILD = 'C:/Users/Felix/Documents/Codex/2026-11-08/can/work/supervisor_slides_2026-11-09';
export const OUTPUT = 'C:/Users/Felix/Documents/Codex/2026-11-08/can/outputs/FYP_Supervisor_Update_2026-11-09.pptx';
const C = {navy:'#172F46', blue:'#245DA8', orange:'#CE791E', gray:'#586B7A', pale:'#DFE6EC', white:'#FFFFFF'};

function text(slide, name, value, x, y, w, h, size=25, color=C.navy, bold=false) {
  const s=slide.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  s.text=value;
  s.text.style={typeface:'Arial',fontSize:size,color,bold,wrap:'square',autoFit:'none',verticalAlignment:'top',insets:0};
  return s;
}
function slide(p, title, n) {
  const s=p.slides.add(); s.setViewportSize(1280,720); s.background.fill=C.white;
  text(s,'title',title,72,49,1136,102,44,C.navy,true);
  text(s,'page',String(n).padStart(2,'0'),1162,666,46,24,17,C.gray);
  return s;
}
function note(s, speech, sources) {s.speakerNotes.text=speech+'\n\nSources\n'+sources.join('\n');}
function bars(s, title, categories, vals, x,y,w,h,colors) {
 return s.charts.add('bar',{
  position:{left:x,top:y,width:w,height:h},title,titleTextStyle:{fontSize:25,bold:true,fill:C.navy},
  categories,series:[{name:title,values:vals,fill:C.blue,points:vals.map((_,idx)=>({idx,fill:colors[idx]})),valuesFormatCode:'0.000'}],
  barOptions:{direction:'column',grouping:'clustered',gapWidth:110},hasLegend:false,
  xAxis:{textStyle:{fontSize:23,fill:C.navy},line:{fill:C.gray,width:1},majorGridlines:null},
  yAxis:{min:0,max:1,majorUnit:0.2,numberFormatCode:'0.0',textStyle:{fontSize:19,fill:C.gray},majorGridlines:{fill:C.pale,width:1},line:{fill:'none',width:0}},
  dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.000',textStyle:{fontSize:24,bold:true,fill:C.navy}},
  chartFill:C.white,plotAreaFill:C.white,chartLine:{fill:'none',width:0},plotAreaLine:{fill:'none',width:0}
 });
}
function csv(raw) {const lines=raw.trim().split(/\r?\n/);const head=lines.shift().split(',');return lines.map(l=>Object.fromEntries(l.split(',').map((v,i)=>[head[i],v])));}

export async function build(p) {
 if(p.slides.items.length) throw new Error('Expected an empty presentation');
 p.theme.defaultFont='Arial';

 let s=p.slides.add(); s.setViewportSize(1280,720);s.background.fill=C.navy;
 text(s,'cover-title','FYP progress\nupdate',72,112,1120,168,64,C.white,true);
 text(s,'cover-subtitle','Predicting local XCT flaw candidates\nfrom LPBF process images',76,336,1090,108,36,C.white);
 text(s,'cover-stage','Data preparation and exploratory baselines complete',76,500,1100,48,27,'#AFC9E6');
 text(s,'presenter','Felix\n9 November 2026',76,608,840,62,23,C.white);
 note(s,'My FYP asks whether visible-light and near-infrared images collected during laser powder bed fusion can help predict local internal-flaw annotations from post-build X-ray computed tomography. The data preparation and first exploratory models are complete. The current targets are algorithmic XCT candidates, so the central open issue is whether the image-to-XCT correspondence and target meaning are scientifically sound. This update covers the full-source work only.',[
 ROOT+'/references/Snow_README.txt',ROOT+'/references/Snow_Methods.docx',ROOT+'/results/baseline_v1_2026-11-08/protocol/protocol.json']);

 s=slide(p,'Prepared research dataset',2);
 text(s,'count','329,828',72,157,485,72,62,C.blue,true);
 text(s,'scope','three-channel patches from one LPBF build',72,237,1115,42,29);
 text(s,'cohort','64 fatigue specimens, 142 selected layers (519–660)',72,292,1115,42,27,C.gray);
 s.images.add({path:ASSETS+'/one_sensor_patch.png',alt:'One 24 by 24 patch in visible post-melt, visible post-recoat and NIR channels',position:{left:72,top:366,width:704,height:293.33},fit:'contain'});
 text(s,'cleaning','Fixed channel scaling preserves intensity differences.\n\nGeometry and XCT checks flag uncertainty.\n\n6,548 unknown targets remain outside modelling.',823,365,385,250,25);
 note(s,'The working cohort contains 64 fatigue specimens from a single Snow build and 142 selected layers. Each observation is a 24 by 24 patch with visible post-melt, visible post-recoat and NIR integrated-maximum channels. The source authors already reconstructed and registered the XCT data. Our preparation extracts patches, applies fixed scaling and records quality and target uncertainty. Fixed scales use the stored channel ranges rather than normalising every patch independently, which would erase intensity differences. There are 73,649 candidate-1 patches, 249,631 candidate-0 patches and 6,548 unknown patches. Unknowns are not forced into the negative class. Candidate 1 means the working crop contains a nonzero annotation, not a confirmed physical pore. The illustrated P4 patch is an example of data structure only, not an added development observation. Original source data remain preserved.',[
 ROOT+'/data/cleaned/snow_source_preparation_v1/catalog/summary.json',ROOT+'/references/Snow_Methods.docx',ASSETS+'/source_example_provenance.json']);

 s=slide(p,'Evaluation uses separate specimens',3);
 text(s,'dev-count','52',72,176,440,96,82,C.blue,true);
 text(s,'dev-name','development specimens',72,285,500,42,30,C.blue,true);
 text(s,'dev-details','262,369 eligible patches\nFour specimen-based validation folds',72,346,500,91,27);
 text(s,'test-count','12',692,176,440,96,82,C.orange,true);
 text(s,'test-name','test specimens for baseline v1',692,285,516,78,30,C.orange,true);
 text(s,'test-details','60,911 eligible patches\nNo specimens overlap with development',692,381,516,91,27);
 text(s,'model','42 image descriptors per patch\nDummy prior, logistic regression and random forest',72,511,1100,90,28);
 text(s,'test-status','The v1 test has now been evaluated. Future adaptive reuse would not be fresh testing.',72,633,1090,48,20,C.gray);
 note(s,'The baseline did not train on all the data. We fixed five folds at specimen level, reserved fold zero as test and used the other four folds for development. During development each model trains on three development folds and validates on the fourth. We selected the primary model using mean development average precision, then refit on all 52 development specimens and evaluated the 12 separate test specimens. The scaler learns only from each training subset. The 42 features describe sensor appearance only. The primary models do not use specimen IDs, coordinates, layer indices or XCT counts as predictors. The test patches have now been inspected in the v1 analysis, so a future model chosen in response to these findings must not claim an untouched test simply by reusing the same twelve specimens.',[
 ROOT+'/results/baseline_v1_2026-11-08/protocol/protocol.json',ROOT+'/results/baseline_v1_2026-11-08/protocol/split_summary.json',ROOT+'/data/features/baseline_v1_2026-11-08/feature_dictionary.json',ROOT+'/results/development_diagnostics_v1_2026-11-08/split_audit.json']);

 s=slide(p,'Baseline v1: pooled and local performance',4);
 bars(s,'Test average precision',['Dummy','Logistic','Forest'],[0.25154733956099884,0.7627205610835559,0.7822046553001454],65,181,650,386,[C.gray,C.orange,C.blue]);
 text(s,'local-value','0.576',787,190,400,76,60,C.blue,true);
 text(s,'local-label','Mean AUC within\nindividual test specimens',787,275,412,83,28);
 text(s,'recall-value','10.8%',787,395,400,76,60,C.orange,true);
 text(s,'recall-label','Recall across the other\n10 test specimens*',787,480,412,83,28);
 text(s,'baseline-takeaway','The pooled result overstates how well the model locates candidates within a specimen.',72,595,1110,66,27,C.navy,true);
 note(s,'The development-selected random forest reaches test average precision 0.782, compared with 0.252 for the constant-prior baseline and 0.763 for logistic regression. Average precision summarises the precision-recall ranking across thresholds and is not accuracy. The pooled score looks promising, but the mean AUC calculated separately within each test specimen is only 0.576, where 0.5 corresponds to chance ranking. The asterisk on recall means the other ten specimens after excluding P43 and P59: those two contain 61.5 percent of test positives and 93.4 percent of true positives. Across the remaining ten, recall is 637 divided by 5,902, or 10.8 percent, at the fixed 0.5 threshold. This is a reason to investigate local performance and contextual structure. It does not establish a validated pore detector. Test population: 60,911 eligible patches in twelve specimens.',[
 ROOT+'/results/baseline_v1_2026-11-08/training/test_metrics.csv',ROOT+'/results/baseline_v1_2026-11-08/training/test_per_specimen.csv']);

 s=slide(p,'Layer and position carry substantial signal',5);
 text(s,'diag-scope','Development only: the same four validation folds and 52 specimens',72,145,1125,54,27,C.gray);
 bars(s,'Mean fold average precision',['Images','Layer + XY'],[0.7120148874431333,0.7111718706008594],62,226,556,320,[C.blue,C.orange]);
 bars(s,'Mean AUC within specimens',['Images','Layer + XY'],[0.5808219915149091,0.539033855621049],662,226,556,320,[C.blue,C.orange]);
 text(s,'diag-takeaway','Sensor features add modest local ranking information beyond broad context.',72,580,1110,72,28,C.navy,true);
 text(s,'diag-caution','Layer + XY uses layer index and camera coordinates. Similar AP alone does not prove confounding.',72,659,1082,35,18,C.gray);
 note(s,'To investigate the pooled-local gap without further test adaptation, we trained a context control using only layer index and camera Y and X coordinates on the 52 development specimens. We kept the same four specimen folds and fixed model-family settings. The image random forest has mean fold AP 0.712, while the layer-position forest has 0.711. For ranking within specimens, image features achieve mean AUC 0.581 versus 0.539 for context. The central question becomes what local sensor information adds beyond layer and location. These are descriptive results, not proof of causality, statistical equivalence, metadata superiority or leakage. Metadata here means layer and camera coordinates, not actual process parameters or specimen IDs. These development metrics must not be directly combined with the test metrics from the previous slide.',[
 ROOT+'/results/development_diagnostics_v1_2026-11-08/nuisance/method_summary.csv',ROOT+'/results/development_diagnostics_v1_2026-11-08/nuisance/summary.json']);

 s=slide(p,'Gaussian check: the intended quantity is open',6);
 const dist=ROOT+'/results/development_diagnostics_v1_2026-11-08/distributions/';
 const bins=csv(await fs.readFile(dist+'mean_histogram_bins.csv','utf8')).filter(r=>r.feature==='nir_max_mean');
 const points=cls=>bins.filter(r=>r.candidate_y===cls).map(r=>({x:(+r.bin_left + +r.bin_right)/2,y:+r.density}));
 const p0=points('0'),p1=points('1');
 const moments=csv(await fs.readFile(dist+'normal_reference_moments.csv','utf8')).find(r=>r.feature==='nir_max_mean'&&r.population==='all_eligible_development_patches');
 const mu=+moments.mean,sd=+moments.std_population;
 const density=x=>Math.exp(-0.5*((x-mu)/sd)**2)/(sd*Math.sqrt(2*Math.PI));
 s.charts.add('scatter',{
  position:{left:60,top:177,width:760,height:414},title:'NIR patch-mean density',titleTextStyle:{fontSize:26,fill:C.navy,bold:true},
  series:[
   {name:'Candidate 0',xValues:p0.map(v=>v.x),values:p0.map(v=>v.y),line:{fill:C.blue,width:3},marker:{symbol:'none'}},
   {name:'Candidate 1',xValues:p1.map(v=>v.x),values:p1.map(v=>v.y),line:{fill:C.orange,width:3},marker:{symbol:'none'}},
   {name:'Pooled normal reference',xValues:p0.map(v=>v.x),values:p0.map(v=>density(v.x)),line:{fill:C.gray,width:2,style:'dash'},marker:{symbol:'none'}}],
  scatterOptions:{style:'line'},hasLegend:true,legend:{position:'bottom',overlay:false,textStyle:{fontSize:19,fill:C.navy}},
  xAxis:{min:0,max:1,majorUnit:0.2,title:{text:'Normalised patch mean',textStyle:{fontSize:22,fill:C.navy}},numberFormatCode:'0.0',textStyle:{fontSize:19,fill:C.gray},majorGridlines:null},
  yAxis:{min:0,max:9,majorUnit:3,title:{text:'Density',textStyle:{fontSize:22,fill:C.navy}},textStyle:{fontSize:19,fill:C.gray},majorGridlines:{fill:C.pale,width:1}},
  chartFill:C.white,plotAreaFill:C.white,chartLine:{fill:'none',width:0}
 });
 text(s,'gaussian-question','A distribution assumption\nor an image filter?',866,191,342,91,30,C.blue,true);
 text(s,'gaussian-details','NIR means show a mixture.\n\nClarify the quantity and purpose before choosing a method.\n\nNo normality transformation or outlier deletion applied.',866,324,342,276,25);
 text(s,'gaussian-scope','262,369 development patches. Curves join the saved histogram-bin densities.',72,633,1080,39,20,C.gray);
 note(s,'The exact meaning of the supervisor\'s Gaussian suggestion is still unknown. It could refer to the distribution of a measured quantity, a Gaussian image filter or another method. We inspected development feature distributions without forcing them into a normal shape. This plot uses saved NIR patch-mean histogram densities for candidate zero and one. The normal reference uses the pooled development mean and population standard deviation. Every class histogram integrates to one. The curves connect bin centres for readability. These are distributions of normalised patch means, not raw pixel histograms. The NIR distribution contains marked mixture structure; 74.4 percent of total patch-mean variance lies between specimen means under the descriptive variance decomposition. This does not prove why the groups differ. Logistic regression and random forests do not require Gaussian feature distributions. Standard scaling changes location and scale, not the distribution\'s shape. No formal normality claim, new Gaussian filter, transformation or three-sigma deletion was applied.',[
 dist+'mean_histogram_bins.csv',dist+'normal_reference_moments.csv',dist+'variance_decomposition.csv',dist+'summary.json']);

 s=slide(p,'Target review remains the main scientific gap',7);
 text(s,'review-ready','32 development cases ready for review',72,144,1120,44,30,C.blue,true);
 text(s,'review-questions','Confirm camera/XCT correspondence, measured support and annotation meaning.',72,197,1110,67,26);
 s.images.add({path:ASSETS+'/review_01.png',alt:'Selected development review case R01, specimen P18 layer627, with all three sensor channels, XCT grayscale and annotation mask',position:{left:72,top:289,width:1136,height:377},fit:'contain',crop:{left:0.04,top:0.105,right:0.025,bottom:0.652}});
 // The selected row is a focused excerpt. All five evidence panels remain visible.
 note(s,'The prepared packet contains 32 deliberately selected development cases from 24 specimens. It covers ordinary candidate positives and zeros, unknowns, boundary cases, author events and constant-NIR cases. It is a discussion sample, not a population-accuracy estimate. This slide shows only R01, P18 at source layer 627, from development fold two. White mask pixels denote nonzero annotations. The fixed XCT stored-value display can look dark and is not evidence of missing structure. We need a working judgement on physical camera-to-XCT correspondence, which locations have measured XCT support, and what nonzero annotations mean for a binary target. Dinh, Muller and Quinsat (2021) motivate comparing in-process visible images with CT and highlight the need for local comparison. Their study uses different material, hardware and processing, so it does not validate our registration or labels. Their quoted image and CT defect fractions are volume measures, not classifier performance. Human scientific review of this packet remains pending.',[
 ROOT+'/results/development_diagnostics_v1_2026-11-08/review/selection_provenance.json',ROOT+'/results/development_diagnostics_v1_2026-11-08/review/machine_checks.json',ASSETS+'/review_01.png',
 'Dinh, D. M., Muller, N., and Quinsat, Y. (2021). Layering Defects Detection in Laser Powder Bed Fusion using Embedded Vision System. Computer-Aided Design & Applications 18(5), 1111–1118. https://doi.org/10.14733/cadaps.2021.1111-1118',ROOT+'/references/Dinh_Muller_Quinsat_2021_Layering_Defects.pdf']);

 s=slide(p,'Supervisor decisions and next experiment',8);
 const rows=[
  ['Target definition','Review the 32 cases and record the mapping, support and uncertainty policy.'],
  ['Gaussian purpose','Specify the quantity to model, or the image operation to investigate.'],
  ['Controlled comparison','Compare context only, sensors only and their combination on development folds.'],
  ['Evaluation plan','Freeze the next protocol before further test use. Consider a compact CNN after target review.']
 ];
 rows.forEach((r,i)=>{const y=163+i*112;text(s,'decision-label-'+i,r[0],72,y,278,74,27,C.blue,true);text(s,'decision-body-'+i,r[1],390,y,818,89,27);});
 text(s,'lit-link','Dinh et al. (2021) supports the optical/XCT motivation and the need for local validation.',72,638,1072,49,20,C.gray);
 note(s,'My proposed immediate step is to review the packet with the supervisor and record a defensible working target policy. I would also clarify what Gaussian quantity or operation was intended. The next modelling question is whether sensor appearance adds information beyond layer and location. A controlled development comparison should therefore include context-only, sensor-only and combined models, with local metrics reported alongside pooled metrics. The next protocol should state how to handle future evaluation because the v1 test has already been inspected. A compact CNN can follow once the target and evaluation policy are clear. The professor\'s tomography links have a conditional role: the supplied XCT is already reconstructed and registered. TomoPy and ASTRA focus on tomographic processing or reconstruction, so a new reconstruction phase needs a defined reason and the appropriate inputs. Algotom may help with a specific reslicing or bounded inspection task on reconstructed data. Installing these tools alone cannot resolve annotation semantics or mapping validity.',[
 'C:/Users/Felix/Documents/Codex/2026-11-08/can/outputs/FYP_Baseline_v2_Protocol_Draft_2026-11-09.md',
 'C:/Users/Felix/Documents/Codex/2026-11-08/can/outputs/FYP_Questions_for_Supervisor_2026-11-09.md',
 'https://doi.org/10.14733/cadaps.2021.1111-1118','https://tomopy.readthedocs.io/en/stable/','https://algotom.readthedocs.io/en/latest/','https://astra-toolbox.com/']);
 return {slides:p.slides.items.length,output:OUTPUT};
}
