import csv,json,math,hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

SOURCE=Path(r'C:/NUS/FYP/FYP Organized/results/development_diagnostics_v1_2026-11-08/distributions')
OUT=Path(r'C:/Users/Felix/Documents/Codex/2026-11-08/can/work/data_cleaning_report_gaussian_2026-11-15')
def read(name):
    with (SOURCE/name).open(newline='',encoding='utf8') as f:return list(csv.DictReader(f))
summary=json.loads((SOURCE/'summary.json').read_text())
assert summary['rows']==262369 and summary['specimens']==52
bins=[r for r in read('mean_histogram_bins.csv') if r['feature']=='nir_max_mean' and r['candidate_y']=='pooled']
bins.sort(key=lambda r:int(r['bin_index']))
moments=[r for r in read('normal_reference_moments.csv') if r['population']=='all_eligible_development_patches']
moment={r['feature']:r for r in moments}
mu=float(moment['nir_max_mean']['mean']);sd=float(moment['nir_max_mean']['std_population']);n=summary['rows']
assert sum(int(r['count']) for r in bins)==n
left=[float(r['bin_left']) for r in bins];right=[float(r['bin_right']) for r in bins]
centres=[(a+b)/2 for a,b in zip(left,right)];widths=[b-a for a,b in zip(left,right)]
assert all(abs(w-.0125)<1e-10 for w in widths)
cdf=lambda x:.5*(1+math.erf((x-mu)/(sd*math.sqrt(2))))
observed=[int(r['count'])/n for r in bins]
normal=[cdf(b)-cdf(a) for a,b in zip(left,right)]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(7.05,2.8))
ax.bar(centres,observed,width=widths,color='#2D659D',alpha=.83,linewidth=0,label='Observed NIR patch means',zorder=3)
ax.plot(centres,normal,color='#C77A25',linestyle='--',linewidth=2.4,label='Gaussian reference (same mean and SD)',zorder=4)
ax.set(xlim=(0,1),ylim=(0,.11),xlabel='Mean scaled NIR intensity within a patch',ylabel='Share of subset patches per bin')
ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.set_yticks([0,.02,.04,.06,.08,.10])
ax.grid(axis='y',color='#E6EAF0',zorder=0)
ax.legend(loc='upper right',frameon=False,fontsize=9.8)
fig.tight_layout(pad=.5)
fig.savefig(OUT/'nir_gaussian_comparison.png',dpi=250,facecolor='white');plt.close(fig)
record={'n':n,'specimens':52,'unknowns_excluded':summary['unknown_rows_in_development_excluded'],'reserved_specimens_excluded':len(summary['excluded_test_specimen_ids']),'bin_width':.0125,'mean':mu,'population_sd':sd,'normal_reference_method':'Normal CDF difference at identical saved histogram-bin edges; untruncated and not renormalized over [0,1]','observed_bin_count_total':n,'observed_shares':observed,'normal_expected_bin_shares':normal,'moments':moments,'source_sha256':{name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in ['summary.json','mean_histogram_bins.csv','normal_reference_moments.csv']}}
(OUT/'gaussian_figure_evidence.json').write_text(json.dumps(record,indent=2))
print(json.dumps({k:v for k,v in record.items() if k not in ['observed_shares','normal_expected_bin_shares','moments']},indent=2))
