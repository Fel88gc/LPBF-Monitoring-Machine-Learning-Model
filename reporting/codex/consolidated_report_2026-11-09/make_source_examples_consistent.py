"""Create full-source report illustrations from three bounded, traceable crops."""
from pathlib import Path
import hashlib
import json
import shutil
import h5py
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

ROOT = Path('C:/NUS/FYP/FYP Organized')
OUT = Path(__file__).resolve().parent / 'assets'
RAW = ROOT / "data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
BLUE, GRAY, ORANGE = "#2464A1", "#657586", "#C27B21"
plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":11, "axes.titlesize":11,
                     "axes.labelsize":10, "savefig.facecolor":"white"})


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for b in iter(lambda:stream.read(1024*1024),b""): h.update(b)
    return h.hexdigest()


def save(fig,name):
    fig.savefig(OUT/name,dpi=250,facecolor="white")
    plt.close(fig)


def box(ax,x,y,w,h,text,color=BLUE):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.012",facecolor="#F4F7FA",edgecolor=color,linewidth=1.3))
    ax.text(x+w/2,y+h/2,text,ha="center",va="center",fontsize=11,color="#233342")


def arrow(ax,start,end):
    ax.add_patch(FancyArrowPatch(start,end,arrowstyle="-|>",mutation_scale=15,color=GRAY,linewidth=1.4))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=ROOT/"data/cleaned/snow_source_preparation_v1/catalog/manifest.csv"
    expected="71bc9e998c0042b7c630ef6443b4dbfe8bbbd3bec9213f7f8425d360af236010"
    assert sha(manifest)==expected
    columns=["sample_id","part_id","layer","camera_y","camera_x","part_fraction","candidate_y","candidate_flaw_pixels",
             "raw_xct_positive_proxy","xct_y0","xct_y1","xct_x0","xct_x1","feature_shard","feature_row","quality_flags"]
    df=pd.read_csv(manifest,usecols=columns)
    known=df[(df.part_id==4)&(df.layer==600)&(df.part_fraction>=.99)]
    pos=known[(known.candidate_y==1)&(known.candidate_flaw_pixels>=5)].sort_values(["candidate_flaw_pixels","sample_id"]).iloc[0]
    zeros=known[known.candidate_y==0].copy()
    zeros["distance"]=(zeros.camera_y-pos.camera_y)**2+(zeros.camera_x-pos.camera_x)**2
    neg=zeros.sort_values(["distance","sample_id"]).iloc[0]
    unknown=df[(df.part_id==4)&(df.candidate_y==-1)].copy()
    unknown["layer_distance"]=(unknown.layer-600).abs()
    unk=unknown.sort_values(["layer_distance","sample_id"]).iloc[0]
    records=[pos,neg,unk]
    examples=[]
    before=RAW.stat()
    with h5py.File(RAW,"r",rdcc_nbytes=16*1024**2) as h5:
        for row in records:
            with np.load(ROOT/row.feature_shard,allow_pickle=False) as a:
                X=a["X"][int(row.feature_row)].copy()
                assert int(a["candidate_y"][int(row.feature_row)])==int(row.candidate_y)
            y0,y1,x0,x1=(int(row[k]) for k in ("xct_y0","xct_y1","xct_x0","xct_x1"))
            ct=h5["/slices/registered_data/x-ray_ct_data"][int(row.layer),y0:y1,x0:x1]
            mask=h5["/slices/registered_data/x-ray_ct_flaw"][int(row.layer),y0:y1,x0:x1]!=0
            assert int(mask.sum())==int(row.candidate_flaw_pixels)
            assert abs(float(np.mean(ct>0))-row.raw_xct_positive_proxy)<1e-12
            data={k:(v.item() if isinstance(v,np.generic) else v) for k,v in row.items() if k in columns}
            if pd.isna(data["quality_flags"]):data["quality_flags"]=""
            data.update(source_feature_sha256=sha(ROOT/row.feature_shard),xct_shape=list(ct.shape),xct_dtype=str(ct.dtype),
                        xct_min=int(ct.min()),xct_max=int(ct.max()),display="Shared XCT grayscale bounds across selected crops; camera channels fixed [0,1]")
            examples.append({"metadata":data,"X":X,"ct":ct,"mask":mask})
    after=RAW.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)

    fig=plt.figure(figsize=(8.4,3.5),layout="constrained")
    gs=fig.add_gridspec(2,3,height_ratios=[1,.12])
    labels=["Visible after melting","Visible after powder spreading","NIR integrated maximum"]
    for c in range(3):
        ax=fig.add_subplot(gs[0,c])
        im=ax.imshow(examples[0]["X"][c],origin="lower",interpolation="nearest",cmap="gray" if c<2 else "inferno",vmin=0,vmax=1)
        ax.set_title(labels[c]);ax.set_xlabel("Camera patch X index");ax.set_ylabel("Y index" if c==0 else "")
        ax.set_xticks([0,12,23]);ax.set_yticks([0,12,23])
        cb=fig.add_subplot(gs[1,c]);fig.colorbar(im,cax=cb,orientation="horizontal",ticks=[0,.5,1])
    meta=examples[0]["metadata"]
    fig.suptitle(f"One observation: 3 channels x 24 x 24 pixels\nP4 | source layer {meta['layer']} | camera Y={meta['camera_y']}, X={meta['camera_x']}",fontsize=13,fontweight="bold")
    save(fig,"one_sensor_patch.png")

    lo=min(e["ct"].min() for e in examples);hi=max(e["ct"].max() for e in examples)
    fig,axes=plt.subplots(3,5,figsize=(9.0,7.0),layout="constrained")
    for r,e in enumerate(examples):
        meta=e["metadata"]
        for c in range(3):axes[r,c].imshow(e["X"][c],origin="lower",cmap="gray" if c<2 else "inferno",vmin=0,vmax=1,interpolation="nearest")
        axes[r,3].imshow(e["ct"],origin="lower",cmap="gray",vmin=lo,vmax=hi,interpolation="nearest")
        axes[r,4].imshow(e["mask"],origin="lower",cmap="gray",vmin=0,vmax=1,interpolation="nearest")
        name={1:"Candidate 1",0:"Candidate 0",-1:"Unknown (-1)"}[meta["candidate_y"]]
        axes[r,0].set_ylabel(f"{name}\nP4 / layer {meta['layer']}",fontsize=11)
        axes[r,3].set_xlabel(f"Positive-intensity proxy\n{meta['raw_xct_positive_proxy']:.3f}")
        axes[r,4].set_xlabel(f"Nonzero annotation\npixels: {int(meta['candidate_flaw_pixels'])}")
        for ax in axes[r]:ax.set_xticks([]);ax.set_yticks([])
    for ax,label in zip(axes[0],["Visible post-melt","Visible post-recoat","NIR maximum","Mapped XCT grayscale","Mapped flaw raster"]):ax.set_title(label,fontsize=10)
    fig.suptitle("Sensor patches and their current candidate XCT crops",fontweight="bold",fontsize=14)
    fig.supxlabel(f"Camera channels: fixed [0,1]. XCT grayscale: shared stored-value range [{lo:g},{hi:g}].\nBlack/white annotation: zero/nonzero. All candidate targets remain unvalidated.",fontsize=10)
    save(fig,"source_xct_examples.png")

    fig,ax=plt.subplots(figsize=(8.4,4.8));ax.set_axis_off();ax.set_xlim(0,1);ax.set_ylim(0,1)
    box(ax,.02,.60,.28,.25,"During printing\nVisible melt + recoat\nNIR maximum")
    box(ax,.37,.60,.27,.25,"Prepare a local\nthree-channel patch\n(sensor predictors)")
    box(ax,.73,.60,.25,.25,"Fit an image model\nScore annotation\nassociation")
    arrow(ax,(.30,.725),(.37,.725));arrow(ax,(.64,.725),(.73,.725))
    box(ax,.02,.18,.28,.25,"After printing\nRegistered XCT\ngray + flaw raster",GRAY)
    box(ax,.37,.18,.27,.25,"Map same candidate\nregion and make\nprovisional target",ORANGE)
    arrow(ax,(.30,.305),(.37,.305));arrow(ax,(.64,.305),(.855,.60))
    ax.text(.87,.44,"Reference target\nfor fitting",color=GRAY,fontsize=9.5,ha="center",va="center")
    ax.text(.5,.99,"Do process images contain local information\nabout XCT annotations?",fontweight="bold",fontsize=12,va="top",ha="center")
    ax.text(.5,.06,"Model inputs are sensor images. XCT supplies the reference during research.\nPhysical target validity and useful local detection still require evidence.",ha="center",va="center",fontsize=10,color=GRAY)
    save(fig,"research_connection.png")

    fig,axes=plt.subplots(1,2,figsize=(8.4,4.0),layout="constrained")
    for ax,n,label,color in zip(axes,[24,116],["Camera patch: 24 x 24","Candidate XCT crop: about 116 x 116"],[BLUE,ORANGE]):
        ax.add_patch(Rectangle((0,0),n,n,facecolor="#EDF3F9",edgecolor=color,linewidth=2))
        ax.set(xlim=(-1,n+1),ylim=(-1,n+1),aspect="equal",xlabel="X index",ylabel="Y index",title=label)
        ax.text(n/2,n/2,"Proposed same region\nDifferent pixel grids",ha="center",va="center",fontsize=11)
        ax.set_xticks([0,n]);ax.set_yticks([0,n])
    fig.suptitle("Current index rule: scale = 13,752 / 2,844 = 4.835443",fontsize=13,fontweight="bold")
    fig.supxlabel("Round each scaled boundary; retain exact crop bounds in the manifest.\nMatching array-size ratios is a working convention, not independent geometric validation.",fontsize=10)
    save(fig,"candidate_grid_mapping.png")

    originals=[
        ROOT/"reports/fyp_progress_2026-11-08/assets/source_candidate_composition.png",
        ROOT/"reports/fyp_progress_2026-11-08/assets/source_candidates_by_layer.png",
    ]+[ROOT/"reports/baseline_v1_2026-11-08/assets"/f for f in ["model_ap_comparison.png","heldout_precision_recall.png","selected_primary_confusion.png","selected_primary_per_specimen_ap.png","selected_primary_error_gallery.png"]]
    copies=[]
    for path in originals:
        shutil.copy2(path,OUT/path.name)
        copies.append({"source":str(path.relative_to(ROOT)).replace("\\","/"),"file":path.name,"sha256":sha(path)})
    result={"catalog_manifest_sha256":expected,"examples":[e["metadata"] for e in examples],"reused_assets":copies,
            "raw_mode":"r","bounded_xct_crops":3,"source_size_mtime_unchanged":True,"label_policy_unchanged":True,
            "new_assets":["one_sensor_patch.png","source_xct_examples.png","research_connection.png","candidate_grid_mapping.png"]}
    (OUT/"source_example_provenance.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"examples":[{k:e["metadata"][k] for k in ("sample_id","candidate_y","candidate_flaw_pixels","raw_xct_positive_proxy")} for e in examples],"created":result["new_assets"]},indent=2))


if __name__=="__main__":main()
