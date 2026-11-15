"""Readable report figures from the existing pilot and bounded raw examples."""
import csv
import json
from pathlib import Path
import h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

ROOT=Path.cwd()
OUT=ROOT/'reports/fyp_progress_2026-11-08/assets'
PILOT=ROOT/'results/data_quality/2026-11-08_run01/pilot/final'
SPATIAL=ROOT/'results/data_quality/2026-11-08_run01/spatial'
RAW=ROOT/'data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5'
plt.rcParams.update({'font.size':9,'axes.titlesize':9,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,
                     'font.family':'DejaVu Sans','savefig.facecolor':'white'})


def save(fig,name):
    fig.savefig(OUT/name,dpi=300,facecolor='white')
    plt.close(fig)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    pilot=json.loads((PILOT/'pilot_audit.json').read_text(encoding='utf-8'))
    records=pilot['per_specimen']
    fig,ax=plt.subplots(figsize=(6.5,3.2),layout='constrained')
    positions=np.arange(len(records))
    negative=[r['negative'] for r in records]; positive=[r['positive'] for r in records]
    ax.bar(positions,negative,color='#adb5bd',edgecolor='white',label='Provisional 0')
    ax.bar(positions,positive,bottom=negative,color='#1864ab',edgecolor='white',label='Provisional 1')
    for x,r in zip(positions,records):
        ax.text(x,260,str(r['positive']),ha='center',fontsize=8)
    ax.set_xticks(positions,[f"P{r['part_id']}" for r in records]);ax.set_ylim(0,310)
    ax.set_ylabel('Pilot patches'); ax.set_xlabel('Selected specimen')
    ax.legend(loc='upper center',ncols=2,frameon=False,fontsize=8)
    ax.spines[['top','right']].set_visible(False)
    save(fig,'pilot_specimen_balance.png')

    sensitivity=pilot['threshold_sensitivity']
    fig,ax=plt.subplots(figsize=(6.5,2.8),layout='constrained')
    bars=ax.bar(range(len(sensitivity)),[r['positive'] for r in sensitivity],color='#1864ab',width=.65)
    ax.bar_label(bars,padding=3,fontsize=9)
    ax.set_xticks(range(len(sensitivity)),[f">={r['minimum_flaw_pixels']}" for r in sensitivity])
    ax.set_xlabel('Minimum nonzero XCT annotation pixels per crop');ax.set_ylabel('Provisional positive patches')
    ax.set_ylim(0,1080);ax.spines[['top','right']].set_visible(False)
    save(fig,'pilot_threshold_sensitivity.png')

    with (SPATIAL/'label_disagreements.csv').open(newline='',encoding='utf-8') as handle:
        flips=list(csv.DictReader(handle))
    fig,ax=plt.subplots(figsize=(6.5,3.4),layout='constrained')
    p=np.arange(len(flips));w=.25
    for offset,method,label,color,hatch in [(-1,'pilot_round','Pilot round','#1864ab',''),
        (0,'audit_floor_ceil','Floor / ceil','#d17b00','//'),(1,'export_floor','Floor / floor','#adb5bd','..')]:
        bars=ax.bar(p+offset*w,[int(r[f'{method}_flaw_pixels']) for r in flips],w,label=label,color=color,edgecolor='black',linewidth=.4,hatch=hatch)
        ax.bar_label(bars,padding=2,fontsize=8)
    ax.set_xticks(p,[f"P{r['part_id']}\nL{r['layer']}" for r in flips]);ax.set_ylim(0,5.3)
    ax.set_ylabel('Nonzero XCT annotation pixels');ax.set_xlabel('Six pilot records whose >0 target changes')
    ax.yaxis.set_major_locator(MaxNLocator(integer=True));ax.legend(ncols=3,loc='upper center',fontsize=8,frameon=False)
    ax.spines[['top','right']].set_visible(False)
    save(fig,'pilot_crop_sensitive_cases.png')

    with np.load(ROOT/'data/processed/snow_pilot_patches.npz.npz',allow_pickle=False) as archive:
        X=archive['X']
    fig,axes=plt.subplots(3,1,figsize=(6.5,4.7),layout='constrained',sharex=True)
    for c,name in enumerate(['Visible post-melt','Visible post-recoat','NIR integrated max']):
        axes[c].hist(X[:,c].ravel(),bins=np.linspace(0,1,101),density=True,color='#1864ab',alpha=.85)
        axes[c].set_title(name,loc='left');axes[c].set_ylabel('Density');axes[c].spines[['top','right']].set_visible(False)
    axes[-1].set_xlabel('Stored normalized input value');axes[-1].set_xlim(0,1)
    save(fig,'pilot_channel_distributions.png')

    with h5py.File(RAW,'r',rdcc_nbytes=32*1024**2) as h5:
        sensors=[h5[path] for path in ('/slices/camera_data/visible/0','/slices/camera_data/visible/1','/slices/camera_data/nir/1')]
        ct_ds=h5['/slices/registered_data/x-ray_ct_data'];flaw_ds=h5['/slices/registered_data/x-ray_ct_flaw']
        scale=ct_ds.shape[1]/h5['/slices/part_ids'].shape[1]
        examples=[]
        for label,y in [('positive',1997),('negative',2021)]:
            x=1994;size=24
            bounds=(round(y*scale),round((y+size)*scale),round(x*scale),round((x+size)*scale))
            y0,y1,x0,x1=bounds
            images=[ds[600,y:y+size,x:x+size] for ds in sensors]
            ct=ct_ds[600,y0:y1,x0:x1];flaw=flaw_ds[600,y0:y1,x0:x1]
            fig=plt.figure(figsize=(6.5,3.35),layout='constrained')
            grid=fig.add_gridspec(2,6,height_ratios=[1,1.2])
            axes=[fig.add_subplot(grid[0,0:2]),fig.add_subplot(grid[0,2:4]),fig.add_subplot(grid[0,4:6]),
                  fig.add_subplot(grid[1,0:3]),fig.add_subplot(grid[1,3:6])]
            for c,image in enumerate(images):
                axes[c].imshow(image,origin='lower',interpolation='nearest',cmap='gray' if c<2 else 'inferno',vmin=0,vmax=255 if c<2 else 65535)
            lo,hi=np.percentile(ct,[2,98]);axes[3].imshow(ct,origin='lower',cmap='gray',vmin=lo,vmax=max(hi,lo+1))
            axes[4].imshow(flaw!=0,origin='lower',cmap='binary',interpolation='nearest',vmin=0,vmax=1)
            for ax,title in zip(axes,['Visible post-melt','Visible post-recoat','NIR max','XCT grayscale',f'Annotation: {np.count_nonzero(flaw)} pixels']):
                ax.set_title(title);ax.set_xticks([]);ax.set_yticks([])
            save(fig,f'p16_{label}_trace.png')
            examples.append({'example':label,'layer':600,'part_id':16,'camera_y':y,'camera_x':x,'xct_bounds_y0_y1_x0_x1':bounds,'nonzero_annotation_pixels':int(np.count_nonzero(flaw))})
        # Compare the known positive crop without changing the coordinate policy.
        fig,axes=plt.subplots(1,3,figsize=(6.5,3.3),layout='constrained')
        for ax,name,bounds in zip(axes,['Pilot round','Floor / ceil','Floor / floor'],
            [(9656,9772,9642,9758),(9656,9773,9641,9758),(9656,9772,9641,9757)]):
            y0,y1,x0,x1=bounds;mask=flaw_ds[600,y0:y1,x0:x1]!=0
            ax.imshow(mask,origin='lower',cmap='binary',interpolation='nearest',vmin=0,vmax=1)
            ax.set_title(name);ax.set_xlabel(f'{mask.shape[0]} x {mask.shape[1]} pixels\n{np.count_nonzero(mask)} annotation pixels')
            ax.set_xticks([]);ax.set_yticks([])
        save(fig,'known_positive_crop_rounding.png')
        images=[ds[580,2279:2303,357:381] for ds in sensors]
        fig,axes=plt.subplots(1,3,figsize=(6.5,2.25),layout='constrained')
        for c,(ax,image) in enumerate(zip(axes,images)):
            ax.imshow(image,origin='lower',cmap='gray' if c<2 else 'inferno',interpolation='nearest',vmin=0,vmax=255 if c<2 else 65535)
            ax.set_title(['Visible post-melt','Visible post-recoat','NIR max: constant 65535'][c]);ax.set_xticks([]);ax.set_yticks([])
        save(fig,'constant_nir_example.png')
        # Reflow the nine candidate registration views at their intended print width.
        for layer in (540,600,640):
            parts=h5['/slices/part_ids'][layer];samples=h5['/slices/sample_ids'][layer]
            for part_id in (2,16,24):
                yy,xx=np.where(parts==part_id)
                y0,y1=max(0,int(yy.min())-20),min(parts.shape[0],int(yy.max())+21)
                x0,x1=max(0,int(xx.min())-20),min(parts.shape[1],int(xx.max())+21)
                cy0,cy1,cx0,cx1=round(y0*scale),round(y1*scale),round(x0*scale),round(x1*scale)
                visible=sensors[0][layer,y0:y1,x0:x1]
                ct=ct_ds[layer,cy0:cy1,cx0:cx1];flaw=flaw_ds[layer,cy0:cy1,cx0:cx1]
                extent=(x0,x1,y0,y1);ct_extent=(cx0/scale,cx1/scale,cy0/scale,cy1/scale)
                fig,axes=plt.subplots(1,3,figsize=(6.5,2.48),layout='constrained')
                axes[0].imshow(visible,origin='lower',extent=extent,cmap='gray',vmin=0,vmax=255)
                positive=ct[ct>0];lo,hi=np.percentile(positive,[2,98]) if positive.size else (0,1)
                axes[1].imshow(ct,origin='lower',extent=ct_extent,cmap='gray',vmin=lo,vmax=max(hi,lo+1))
                axes[2].imshow(flaw!=0,origin='lower',extent=ct_extent,cmap='binary',vmin=0,vmax=1)
                for ax,title in zip(axes,['Visible','XCT grayscale','XCT annotation']):
                    ax.set_title(title)
                    for mask,color,style in [(parts[y0:y1,x0:x1]==part_id,'#1864ab','solid'),(samples[y0:y1,x0:x1]>0,'#d17b00','dashed')]:
                        if mask.min()!=mask.max():
                            ax.contour(mask.astype(float),levels=[.5],origin='lower',extent=extent,colors=[color],linestyles=[style],linewidths=.7)
                    ax.set_xlim(x0,x1);ax.set_ylim(y0,y1)
                    ax.xaxis.set_major_locator(MaxNLocator(3));ax.yaxis.set_major_locator(MaxNLocator(3))
                    ax.tick_params(labelsize=7)
                    ax.set_xlabel('Camera-grid X',fontsize=8)
                axes[0].set_ylabel('Camera-grid Y',fontsize=8)
                save(fig,f'alignment_P{part_id}_L{layer}.png')
        with (OUT/'example_figure_sources.json').open('x',encoding='utf-8') as handle:
            json.dump({'raw_file':str(RAW),'mode':'r','examples':examples,'origin':'lower','alignment_transform':'candidate dimension ratio, round boundaries; not independent validation','notes':'Bounded source reads only. XCT display uses percentile contrast; annotation display is nonzero mask. No source file changed.'},handle,indent=2)
    print('Report examples and pilot figures complete.')


if __name__=='__main__':
    main()
