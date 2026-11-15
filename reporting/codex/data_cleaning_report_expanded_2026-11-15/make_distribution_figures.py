import csv,json,hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter

ROOT=Path(r'C:/NUS/FYP/FYP Organized/data/cleaned/snow_source_preparation_v1/catalog')
OUT=Path(r'C:/Users/Felix/Documents/Codex/2026-11-08/can/work/data_cleaning_report_expanded_2026-11-15')
def read(name):
    with (ROOT/name).open(newline='',encoding='utf8') as f: return [{k:(int(v) if k!='part_name' else v) for k,v in r.items()} for r in csv.DictReader(f)]
layers=sorted(read('per_layer.csv'),key=lambda r:r['layer'])
parts=sorted(read('per_specimen.csv'),key=lambda r:r['part_id'])
for rows in [layers,parts]:
    assert sum(r['rows'] for r in rows)==329828
    assert sum(r['candidate_one'] for r in rows)==73649
    for r in rows: assert sum(r[k] for k in ['candidate_zero','candidate_one','candidate_unknown'])==r['rows']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
colors=['#2D659D','#C77A25','#7A8793']
fig,ax=plt.subplots(figsize=(7.05,2.25))
x=[r['layer'] for r in layers]
ys=[[r[k]/r['rows'] for r in layers] for k in ['candidate_zero','candidate_one','candidate_unknown']]
ax.stackplot(x,ys,colors=colors,labels=['Candidate 0','Candidate 1','Unknown'],linewidth=0)
ax.set(xlim=(519,660),ylim=(0,1),xlabel='Source layer index',ylabel='Share of layer patches')
ax.set_xticks([519,540,560,580,600,620,640,660]);ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
ax.set_yticks([0,.25,.5,.75,1]);ax.legend(loc='upper center',bbox_to_anchor=(.5,1.24),ncol=3,frameon=False,fontsize=9.7)
fig.tight_layout(pad=.5)
fig.savefig(OUT/'distribution_by_layer.png',dpi=250,facecolor='white');plt.close(fig)
fig,ax=plt.subplots(figsize=(7.05,2.25))
x=np.arange(len(parts));bottom=np.zeros(len(parts))
for key,color,label in zip(['candidate_zero','candidate_one','candidate_unknown'],colors,['Candidate 0','Candidate 1','Unknown']):
    ys=np.array([r[key]/r['rows'] for r in parts]);ax.bar(x,ys,bottom=bottom,color=color,label=label,width=.85);bottom+=ys
ax.set(xlim=(-.8,len(parts)-.2),ylim=(0,1),xlabel='Specimen ID in numerical order',ylabel='Share of specimen patches')
idx=list(range(0,len(parts),4))
ax.set_xticks(idx,labels=[f'P{parts[i]["part_id"]:02d}' for i in idx],rotation=45,ha='right',fontsize=8.5)
ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.set_yticks([0,.25,.5,.75,1])
ax.legend(loc='upper center',bbox_to_anchor=(.5,1.24),ncol=3,frameon=False,fontsize=9.7)
fig.tight_layout(pad=.5)
fig.savefig(OUT/'distribution_by_specimen.png',dpi=250,facecolor='white');plt.close(fig)
stats={
 'layer_count':len(layers),'specimen_count':len(parts),
 'layer_rows_min':min(r['rows'] for r in layers),'layer_rows_max':max(r['rows'] for r in layers),
 'specimen_rows_min':min(r['rows'] for r in parts),'specimen_rows_max':max(r['rows'] for r in parts),
 'maximum_layer_unknown':max(layers,key=lambda r:r['candidate_unknown']/r['rows']),
 'part_candidate_one_min':min(parts,key=lambda r:r['candidate_one']/r['rows']),
 'part_candidate_one_max':max(parts,key=lambda r:r['candidate_one']/r['rows']),
 'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['per_layer.csv','per_specimen.csv']},
 'layers':layers,'specimens':parts
}
(OUT/'distribution_evidence.json').write_text(json.dumps(stats,indent=2))
print(json.dumps({k:v for k,v in stats.items() if k not in ['layers','specimens']},indent=2))
