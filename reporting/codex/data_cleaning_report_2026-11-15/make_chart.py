import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

root=Path(r'C:/NUS/FYP/FYP Organized')
out=Path(r'C:/Users/Felix/Documents/Codex/2026-11-08/can/work/data_cleaning_report_2026-11-15')
s=json.loads((root/'data/cleaned/snow_source_preparation_v1/catalog/summary.json').read_text())
values=[s['candidate_one'],s['candidate_zero'],s['candidate_unknown']]
labels=['Candidate 1','Candidate 0','Unknown (-1)']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(7.05,1.85))
bars=ax.barh(labels,values,color=['#C77A25','#2D659D','#7A8793'],height=.6,zorder=3)
ax.invert_yaxis()
for bar,value in zip(bars,values):
    ax.text(value+4000,bar.get_y()+bar.get_height()/2,f'{value:,} ({value/s["rows"]:.1%})',va='center',fontsize=10)
ax.set_xlim(0,343000)
ax.set_xticks([0,100000,200000,300000])
ax.xaxis.set_major_formatter(FuncFormatter(lambda value,pos:f'{value/1000:.0f},000' if value else '0'))
ax.set_xlabel('Number of prepared patches',fontsize=10,labelpad=5)
ax.grid(axis='x',color='#E4E8ED',zorder=0)
ax.tick_params(axis='y',length=0)
ax.spines['left'].set_visible(False)
ax.spines['bottom'].set_color('#A0AAB4')
fig.tight_layout(pad=.45)
fig.savefig(out/'candidate_counts.png',dpi=250,facecolor='white')
plt.close(fig)
(out/'chart_values.json').write_text(json.dumps({'denominator':s['rows'],'labels':labels,'counts':values,'fractions':[v/s['rows'] for v in values]},indent=2))
