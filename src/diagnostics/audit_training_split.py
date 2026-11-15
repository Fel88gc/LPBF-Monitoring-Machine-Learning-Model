"""Check saved Baseline v1 split/model provenance without fitting or rescoring."""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone
import joblib
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/development_diagnostics_v1_2026-11-08/split_audit.json"


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for b in iter(lambda:stream.read(1024*1024),b""):h.update(b)
    return h.hexdigest()


def main():
    if OUT.exists():raise FileExistsError(OUT)
    run_path=ROOT/"results/baseline_v1_2026-11-08/training/run_record.json"
    record=json.loads(run_path.read_text())
    protocol_dir=ROOT/"results/baseline_v1_2026-11-08/protocol"
    protocol=json.loads((protocol_dir/"protocol.json").read_text())
    protocol_hashes=json.loads((protocol_dir/"artifact_hashes.json").read_text())
    for name,expected in protocol_hashes.items():assert sha(protocol_dir/name)==expected,name
    assert record["protocol_sha256"]==sha(protocol_dir/"protocol.json")
    for name,expected in record["input_sha256"].items():assert sha(ROOT/name)==expected,name
    with np.load(protocol_dir/"splits.npz",allow_pickle=False) as split:
        fold=split["fold_id"].copy();eligible=split["eligible"].copy();y=split["candidate_y"].copy();groups=split["groups"].copy()
    dev=eligible&(fold!=0);test=eligible&(fold==0)
    dev_groups=np.unique(groups[dev]);test_groups=np.unique(groups[test])
    assert not set(dev_groups)&set(test_groups)
    assert np.array_equal(eligible,np.isin(y,[0,1]))
    assert (len(y),int(eligible.sum()),int(dev.sum()),int(test.sum()))==(329828,323280,262369,60911)
    assert len(dev_groups)==52 and len(test_groups)==12
    cv=[]
    for val_fold in [1,2,3,4]:
        train=dev&(fold!=val_fold);val=dev&(fold==val_fold)
        assert not set(groups[train])&set(groups[val])
        assert not (train&test).any() and not (val&test).any()
        saved=next(r for r in protocol["development_cv"] if r["validation_fold"]==val_fold)
        assert saved["training_specimens"]==np.unique(groups[train]).tolist()
        assert saved["validation_specimens"]==np.unique(groups[val]).tolist()
        cv.append({"validation_fold":val_fold,"train_rows":int(train.sum()),"validation_rows":int(val.sum()),
                   "training_specimens":len(np.unique(groups[train])),"validation_specimens":len(np.unique(groups[val])),"test_rows_in_either":0})
    feature_dir=ROOT/"data/features/baseline_v1_2026-11-08"
    feature_summary=json.loads((feature_dir/"summary.json").read_text())
    assert feature_summary["fitted_statistics"] is False
    features=np.load(feature_dir/"features.npy",mmap_mode="r",allow_pickle=False)
    model_results=[]
    for name,expected in record["model_files_sha256"].items():
        path=ROOT/"models/baseline_v1_2026-11-08"/name
        assert sha(path)==expected,name
        saved=joblib.load(path)
        assert saved["training_specimens"]==dev_groups.tolist()
        assert not set(saved["training_specimens"])&set(test_groups)
        assert saved["protocol_sha256"]==record["protocol_sha256"]
        scaler_samples=None;mean_error=None
        if name.startswith("logistic_"):
            scaler=saved["estimator"][0]
            assert int(scaler.n_samples_seen_)==int(dev.sum())
            observed=features[dev][:,saved["feature_indices"]].astype(np.float64).mean(axis=0)
            mean_error=float(np.max(np.abs(observed-scaler.mean_)))
            assert mean_error<1e-12
            scaler_samples=int(scaler.n_samples_seen_)
        model_results.append({"file":name,"sha256":expected,"training_specimen_count":len(saved["training_specimens"]),
                              "test_specimens_in_training_metadata":0,"scaler_fitted_rows":scaler_samples,"scaler_mean_max_abs_error":mean_error})
    def counts(mask):
        return {"rows":int(mask.sum()),"specimens":int(np.unique(groups[mask]).size),"candidate_zero":int((mask&(y==0)).sum()),"candidate_one":int((mask&(y==1)).sum())}
    result={"status":"passed","created_utc":datetime.now(timezone.utc).isoformat(),"script_sha256":sha(__file__),
            "all_prepared_rows":len(y),"eligible_rows":int(eligible.sum()),"development":counts(dev),"test":counts(test),
            "unknown_rows":int((~eligible).sum()),"unknown_development_specimen_rows":int(((~eligible)&(fold!=0)).sum()),
            "unknown_test_specimen_rows":int(((~eligible)&(fold==0)).sum()),"development_specimens":dev_groups.tolist(),"test_specimens":test_groups.tolist(),
            "development_cross_validation":cv,"saved_model_audits":model_results,
            "feature_extraction_all_rows":True,"feature_extraction_fits_population_statistics":False,
            "test_interpretation":"Held out of fitting; already inspected for the reported Baseline v1 result. Do not call adaptive repeated use fresh testing.",
            "new_round_policy":"Follow-up distribution, nuisance-model and review-pack work uses fold1-4 development specimens only; no new fold0 feature distributions, predictions or fitting.",
            "evidence_scope":"Agreement among frozen splits, reviewed fit-code masks, saved provenance/hashes, model training-group metadata and independently recomputed final logistic scaler means. Trees do not independently reveal source sample IDs.",
            "no_new_fit":True,"no_test_rescoring":True,"inputs_unchanged":True}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ["status","all_prepared_rows","eligible_rows","development","test","unknown_rows"]},indent=2))


if __name__=="__main__":main()
