"""Print-sized figures from unchanged, saved development-only chart values."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator,PercentFormatter

ROOT=Path('C:/NUS/FYP/FYP Organized')
WORK=Path(__file__).resolve().parent
SOURCE=ROOT/'results/development_diagnostics_v1_2026-11-08/distributions'
ASSETS=WORK/'assets'
BLUE='#2464A1';ORANGE='#C27B21';DARK='#435260'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':9,'axes.labelsize':8.5,'xtick.labelsize':7.5,'ytick.labelsize':7.5,'savefig.facecolor':'white'})
items=[('visible_melt_mean','Visible\npost-melt'),('visible_recoat_mean','Visible\npost-recoat'),('nir_max_mean','NIR\nmaximum')]
hist=pd.read_csv(SOURCE/'mean_histogram_bins.csv',dtype={'candidate_y':str})
stats=pd.read_csv(SOURCE/'feature_summary.csv').set_index('feature')
qq=pd.read_csv(SOURCE/'qq_plot_values.csv')
var=pd.read_csv(SOURCE/'variance_decomposition.csv').set_index('feature')

def save(fig,name):
    fig.savefig(ASSETS/name,dpi=300,facecolor='white');plt.close(fig)

fig,axes=plt.subplots(1,3,figsize=(6.5,3.8))
for ax,(name,label) in zip(axes,items):
    for group,color,title in [('pooled',DARK,'All development'),('0',BLUE,'Candidate 0'),('1',ORANGE,'Candidate 1')]:
        df=hist[(hist.feature==name)&(hist.candidate_y==group)].sort_values('bin_index')
        assert df['count'].sum()==df.population_n.iloc[0]
        edges=np.r_[df.bin_left.values,df.bin_right.iloc[-1]]
        ax.stairs(df.density.values,edges,color=color,linewidth=1.2,label=title)
    mu=float(stats.loc[name,'mean']);sd=float(stats.loc[name,'std_population']);grid=np.linspace(0,1,600)
    ref=np.exp(-.5*((grid-mu)/sd)**2)/(sd*np.sqrt(2*np.pi))
    ax.plot(grid,ref,'--',color='black',linewidth=1.1,label='Normal reference')
    ax.set(xlim=(0,1),ylim=(0,None),title=label,xlabel='Patch mean\n(stored normalized scale)')
    ax.xaxis.set_major_locator(MaxNLocator(3));ax.yaxis.set_major_locator(MaxNLocator(4));ax.grid(alpha=.15)
    ax.spines[['top','right']].set_visible(False)
axes[0].set_ylabel('Density within population')
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.5,.91),fontsize=8)
fig.suptitle('Development patch-mean distributions',fontsize=11,fontweight='bold',y=.99)
fig.subplots_adjust(left=.09,right=.985,top=.65,bottom=.23,wspace=.39)
fig.text(.5,.025,'262,369 patches / 52 specimens. Each histogram integrates to 1.\nNormal curves use saved pooled moments; no transformation.',ha='center',fontsize=8)
save(fig,'distribution_channel_means_print.png')

fig,axes=plt.subplots(1,3,figsize=(6.5,3.7))
for ax,(name,label) in zip(axes,items):
    df=qq[qq.feature==name].sort_values('rank');x=df.normal_reference_quantile.values;y=df.observed_subset_quantile.values
    low=min(x.min(),y.min());high=max(x.max(),y.max());pad=.03*(high-low);limits=(low-pad,high+pad)
    ax.plot(x,y,color=BLUE,linewidth=1.3,label='Observed quantiles')
    ax.plot(limits,limits,'--',color=DARK,linewidth=1,label='Normal reference')
    ax.set(xlim=limits,ylim=limits,title=label,xlabel='Normal quantile')
    ax.set_aspect('equal',adjustable='box');ax.xaxis.set_major_locator(MaxNLocator(3));ax.yaxis.set_major_locator(MaxNLocator(4));ax.grid(alpha=.18)
axes[0].set_ylabel('Observed quantile')
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.5,.91),fontsize=8)
fig.suptitle('Normal-reference quantile comparisons',fontsize=11,fontweight='bold',y=.99)
fig.subplots_adjust(left=.085,right=.99,top=.69,bottom=.23,wspace=.40)
fig.text(.5,.025,'10,400 systematic development rows: 200 per specimen.\nReference uses subset mean/SD; original observed values retained.',ha='center',fontsize=8)
save(fig,'distribution_normal_qq_print.png')

fig,ax=plt.subplots(figsize=(6.5,3.0))
ys=np.arange(3);within=[var.loc[name,'within_fraction'] for name,_ in items];between=[var.loc[name,'between_fraction'] for name,_ in items]
assert np.allclose(np.array(within)+between,1)
ax.barh(ys,within,color=BLUE,label='Within specimens',height=.6)
ax.barh(ys,between,left=within,color=ORANGE,hatch='///',edgecolor='white',label='Between specimen means',height=.6)
for i,(a,b) in enumerate(zip(within,between)):
    ax.text(a/2,i,f'{a:.1%}',ha='center',va='center',color='white',fontsize=9)
    ax.text(a+b/2,i,f'{b:.1%}',ha='center',va='center',color='black',fontsize=9,bbox={'facecolor':'white','edgecolor':'none','pad':1,'alpha':.90})
ax.set_yticks(ys,['Visible melt mean','Visible recoat mean','NIR mean']);ax.invert_yaxis();ax.set_xlim(0,1)
ax.xaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('Share of total development feature variance')
ax.spines[['top','right']].set_visible(False)
fig.legend(loc='upper center',bbox_to_anchor=(.5,.91),ncol=2,frameon=False,fontsize=8)
fig.suptitle('Within- and between-specimen variation',fontsize=11,fontweight='bold',y=.99)
fig.subplots_adjust(left=.25,right=.985,top=.70,bottom=.24)
fig.text(.5,.025,'Patch-weighted population-variance decomposition; descriptive, not causal.',ha='center',fontsize=8)
save(fig,'distribution_variance_components_print.png')

provenance={'purpose':'Print readability only; no new fitting, feature statistics, filtering or test-data access',
 'sources':{str(SOURCE/name):hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in ['mean_histogram_bins.csv','feature_summary.csv','qq_plot_values.csv','variance_decomposition.csv']},
 'figures':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ASSETS.glob('*_print.png')}}
(WORK/'print_figure_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
print('Created three print-sized figures from saved development-only tables.')
