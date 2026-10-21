import argparse,json,time,urllib.request,urllib.error,subprocess,socket,os,hashlib
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--data',required=True);ap.add_argument('--personal',required=True);ap.add_argument('--record',required=True);a=ap.parse_args();root=Path(a.root);record=Path(a.record);record.mkdir(parents=True,exist_ok=False);Path(a.personal).mkdir(parents=True,exist_ok=True)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
log=(record/'server.log').open('wb');env={**os.environ,'FYLITE_EQ_DATA':a.data,'PYTHONDONTWRITEBYTECODE':'1'}
p=subprocess.Popen([str(root/'bin/fylite-eq'),'serve','--personal-root',a.personal,'--port',str(port),'--backend','direct'],stdout=log,stderr=log,env=env)
base=f'http://127.0.0.1:{port}'
def get(route):
 with urllib.request.urlopen(base+route,timeout=30)as r:return json.load(r)
def api(route,body=None):
 path='/fylite/eq/api/workflow/'+route
 if body is None:return get(path)
 req=urllib.request.Request(base+path,json.dumps(body).encode(),headers={'Content-Type':'application/json','X-FyLite-Token':token})
 with urllib.request.urlopen(req,timeout=30)as r:return json.load(r)
def wait(case,run):
 for _ in range(600):
  d=api('run?case_id='+case+'&run_id='+run)
  if d['status']['state'] in ('completed','failed','cancelled','waiting_review','rejected'):return d
  time.sleep(.3)
 raise RuntimeError('timeout')
def artifact(case,run,name):return api(f'artifact?case_id={case}&run_id={run}&name={name}.json')

def approve(cid,rid,step):
 review=artifact(cid,rid,step)
 return api('review',{'case_id':cid,'run_id':rid,'identity':review['identity'],'approved':True,'note':'自动验收脚本确认测试夹具身份与已知限制；不代表用户或实验有效性认证'})
try:
 for _ in range(100):
  try:token=get('/fylite/eq/api/info')['token'];break
  except urllib.error.URLError:time.sleep(.1)
 info=api('info');case=api('save',{'name':'magnetic processing acceptance','parameters':info['defaults']});cid=case['case_id']
 def post(route,**kw):return api(route,{'case_id':cid,'base_revision':case['revision'],**kw})
 def rejected(route,**kw):
  try:post(route,**kw);raise AssertionError('invalid request accepted: '+route)
  except urllib.error.HTTPError as e:assert e.code==400
 fetched=api('execute',{'case_id':cid,'revision':1,'target':'sources','fresh_source':True,'request_id':'fetch-once'})
 assert wait(cid,fetched['run_id'])['status']['state']=='completed'
 data=post('processing-import',run_id=fetched['run_id'])
 pars=case['parameters'];first=post('processing-preview',dataset_id=data['dataset_id'],parameters=pars)
 assert len(first['magnetics']['audit'])==85
 changed={**pars,'half_window_s':.003}
 second=post('processing-preview',dataset_id=data['dataset_id'],parameters=changed)
 assert second['preview']['files']['acquired-waveforms.json.gz']==first['preview']['files']['acquired-waveforms.json.gz']
 assert second['magnetics']['audit'][0]['samples']<first['magnetics']['audit'][0]['samples']
 rejected('processing-adopt',preview_id=second['preview']['preview_id'],identity=second['identity'],parameters=pars,note='stale parameters')
 rejected('processing-adopt',preview_id=second['preview']['preview_id'],identity='bad',parameters=changed,note='bad identity')
 rejected('processing-adopt',preview_id=second['preview']['preview_id'],identity=second['identity'],parameters=changed,note='')
 case=post('processing-adopt',preview_id=second['preview']['preview_id'],identity=second['identity'],parameters=changed,note='automated fixture: inspect reduced window, not experimental approval')
 assert case['revision']==2 and case['parameters']['half_window_s']==.003
 rejected('processing-adopt',preview_id=second['preview']['preview_id'],identity=second['identity'],parameters=changed,note='old revision preview')
 case=api('save',{'case_id':cid,'base_revision':2,'name':case['name'],'parameters':{**case['parameters'],'q_target':1.1}})
 assert case['processing']['preview_id']==second['preview']['preview_id']
 full=api('execute',{'case_id':cid,'revision':3,'target':'review_results','request_id':'adopted-full'});rid=full['run_id']
 st=wait(cid,rid);assert st['status']['active_step']=='review_data',st
 source=artifact(cid,rid,'sources');assert source['reuse']['dataset_id']==data['dataset_id']
 assert source['acquisition']['waveforms_sha256']==first['preview']['files']['acquired-waveforms.json.gz']
 assert artifact(cid,rid,'magnetics')==second['magnetics']
 approve(cid,rid,'review_data');st=wait(cid,rid);assert st['status']['active_step']=='review_input',st
 cfg=artifact(cid,rid,'assemble')['config'];assert cfg['measurement_template']['magnetic']['loop_observed']==second['magnetics']['loop_observed']
 assert cfg['initial_pf']['pf_observed']==second['magnetics']['pf_observed']
 approve(cid,rid,'review_input');st=wait(cid,rid);assert st['status']['active_step']=='review_results',st
 report=artifact(cid,rid,'report');assert report['summary']['converged'],report['summary']
 assert abs(report['summary']['q0']-1.1)<1e-4
 approve(cid,rid,'review_results');assert wait(cid,rid)['status']['state']=='completed'
 # Parameter edits invalidate adoption; existing run stays tied to its snapshot.
 before=api(f'run?case_id={cid}&run_id={rid}')['snapshot']
 case=api('save',{'case_id':cid,'base_revision':3,'name':case['name'],'parameters':{**case['parameters'],'drift':True}})
 assert 'processing' not in case
 assert api(f'run?case_id={cid}&run_id={rid}')['snapshot']==before
 receipt={'passed':True,'case_id':cid,'run_id':rid,'summary':report['summary'],'checks':['85 channels','one acquisition reused across two previews and solver','changed window changes sample count','stale parameter/hash/empty-note/revision rejected','q edit preserves adoption','magnetic edit invalidates adoption','assembled values equal adopted preview','three review gates and native convergence','old snapshot unchanged']}
 (record/'acceptance.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False))
finally:p.terminate();p.wait(timeout=10);log.close()
