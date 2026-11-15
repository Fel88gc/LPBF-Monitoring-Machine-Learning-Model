from pathlib import Path
import json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch

WORK=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9.2,'savefig.facecolor':'white'})
fig,ax=plt.subplots(figsize=(6.5,6.5));ax.set(xlim=(0,1),ylim=(0,1));ax.set_axis_off()
steps=[
 ('1. Author-supplied processing','Supplied','Camera correction; XCT reconstruction/registration;\nalgorithmic flaw raster provided in the release.','#657586'),
 ('2. Selected-source preparation','Complete','64 fatigue specimens; layers 519-660; 329,828 patches.\nThree sensor channels, fixed scaling, flags and provenance.','#2464A1'),
 ('3. Working candidate convention','Provisional','73,649 candidate 1; 249,631 candidate 0; 6,548 unknown.\nGrid correspondence, measured support and meaning need evidence.','#C27B21'),
 ('4. Baseline v1 and specimen holdout','Complete','Fit: 52 development specimens / 262,369 eligible rows.\nTest: 12 specimens / 60,911 rows, already inspected for v1.','#2464A1'),
 ('5. Development-only diagnostics','Complete','Feature distributions, normal references and layer/XY controls.\nPooled versus local ranking investigated; fold 0 excluded.','#2464A1'),
 ('6. Scientific review and next decision','Ready / pending','32 cases from 24 development specimens are prepared.\nHuman target review and revised experiment decisions remain open.','#C27B21'),
]
for i,(title,status,detail,color) in enumerate(steps):
 y=.80-i*.143
 ax.add_patch(FancyBboxPatch((.02,y),.96,.12,boxstyle='round,pad=0.008',edgecolor=color,facecolor='white',linewidth=1.05,linestyle='--' if i in [2,5] else '-'))
 ax.text(.045,y+.09,title,fontsize=9.8,fontweight='bold',va='center',color='#243648')
 ax.text(.955,y+.09,status,fontsize=8.5,ha='right',va='center',color=color)
 ax.text(.045,y+.043,detail,fontsize=8.9,va='center',linespacing=1.45,color='#4b5f72')
 if i<5:ax.add_patch(FancyArrowPatch((.5,y-.010),(.5,y-.023),arrowstyle='-|>',mutation_scale=10,color='#8396a8'))
ax.text(.02,.98,'FYP evidence from supplied data to scientific review',fontsize=11.3,fontweight='bold',va='top',color='#18334b')
ax.text(.5,.015,'One build. Completed computations do not validate physical targets\nor establish cross-build transfer.',fontsize=8.7,ha='center',va='center',color='#4b5f72')
fig.subplots_adjust(left=.02,right=.98,bottom=.025,top=.98)
out=WORK/'assets/workflow_current.png';fig.savefig(out,dpi=300,facecolor='white');plt.close(fig)
(WORK/'workflow_provenance.json').write_text(json.dumps({'scope':'Reviewed saved source preparation, Baseline v1 and development-only diagnostics; no new computations or training','steps':[{'title':a,'status':b,'detail':c} for a,b,c,_ in steps],'figure_sha256':hashlib.sha256(out.read_bytes()).hexdigest()},indent=2)+'\n')
print(out)
