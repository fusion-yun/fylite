import json,hashlib,gzip,shutil
from pathlib import Path
import numpy as np
import argparse
ap=argparse.ArgumentParser(description="Freeze audited 94048 magnetic NPZ windows, historical ONETWO and response tables into a runtime data package; no solver source dependency.")
ap.add_argument('--raw-replay',required=True,type=Path)
ap.add_argument('--legacy-input-package',required=True,type=Path)
ap.add_argument('--kefit-data',required=True,type=Path)
ap.add_argument('--output',required=True,type=Path)
args=ap.parse_args()
root=args.raw_replay.resolve();original=args.legacy_input_package.resolve();k=args.kefit_data.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
origin={}
def copy(src,name):
 dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);origin[name]={'source':str(src),'sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
copy(original/'input/native.json','native-template.json')
copy(root/'legacy-node-map.json','mapping.json')
copy(k/'output/kefit/kin/temp','weights.nml')
copy(k/'output/onetwo/94048/12_K94048.6510_final','onetwo-final.nml')
for p in (original/'input/tables').glob('*.ddd'):copy(p,'input/tables/'+p.name)
copy(root/'raw-index-legacy.json','raw-index.json')
traces={}
for entry in json.loads((root/'raw-index-legacy.json').read_text()):
 if entry.get('missing'):continue
 p=root/entry['retained_file'];sha=hashlib.sha256(p.read_bytes()).hexdigest();assert sha==entry['retained_sha256']
 a=np.load(p);traces[entry['tree'].lower()+':'+entry['node'].lstrip('\\').upper()]={'original_npz_sha256':sha,**{n:a[n].tolist() for n in ['target_t','target_y','baseline_t','baseline_y']}}
with gzip.open(out/'raw-waveforms.json.gz','wt') as f:json.dump(traces,f,allow_nan=False)
old=json.loads((root/'raw-replay-no-drift.json').read_text())
(out/'historical-reference.json').write_text(json.dumps({'identity':json.loads((root/'raw-replay-no-drift.identity.json').read_text()),'result':old}))
manifest={'dataset_id':'east94048-fixed-pressure-v1','shot':94048,'magnetic_time_s':5.760,'pressure_time_s':6.510,'origins':origin,'waveform_conversion':'Lossless numeric JSON representation of retained NPZ target/baseline arrays; original NPZ hashes linked through raw-index.json. No new acquisition.','limits':['Frozen magnetic windows; no online acquisition in this workflow.','ONETWO final imported; ONETWO not rerun.','Archived 129x129 response tables and initialization retained, not regenerated.','Pressure time differs from equilibrium by 0.750 s.','q0 target, fitted PF, artificial edge-current and regularization are active.'],'files':{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}}
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(out,len(traces),'traces')
