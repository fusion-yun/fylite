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
 info=api('info');assert info['dataset_ready']
 case=api('save',{'name':'94048 reviewed pipeline acceptance','parameters':info['defaults']});cid=case['case_id']
 body={'case_id':cid,'revision':1,'target':'review_results','request_id':'reviewed-full'}
 full=api('execute',body);rid=full['run_id'];assert api('execute',body)['run_id']==rid
 first=wait(cid,rid);assert first['status']['state']=='waiting_review',first
 assert first['status']['active_step']=='review_data'
 assert first['status']['steps']['solve']['state']=='pending'
 source=artifact(cid,rid,'sources');assert source['acquisition']['mode']=='frozen'
 assert artifact(cid,rid,'quality')['passed']
 # A stale or empty approval cannot advance the solver.
 for extra in ({'identity':'invalid','note':'checked'},{'identity':artifact(cid,rid,'review_data')['identity'],'note':''}):
  try:api('review',{'case_id':cid,'run_id':rid,'approved':True,**extra});raise AssertionError('invalid approval accepted')
  except urllib.error.HTTPError as e:assert e.code==400
 approve(cid,rid,'review_data');second=wait(cid,rid)
 assert second['status']['active_step']=='review_input',second
 assert second['status']['steps']['solve']['state']=='pending'
 cfg=artifact(cid,rid,'assemble')['config'];mag=artifact(cid,rid,'magnetics')
 assert cfg['initial']['target_ip']==mag['ip_observed']==cfg['measurement_template']['fsa']['measured_ip']
 assert cfg['initial_pf']['pf_observed']==mag['pf_observed']
 approve(cid,rid,'review_input');third=wait(cid,rid)
 assert third['status']['active_step']=='review_results',third
 report=artifact(cid,rid,'report');assert report['summary']['converged'];assert abs(report['summary']['q0']-1.05)<1e-4
 assert report['reference']['same_recipe'] is False
 approve(cid,rid,'review_results');done=wait(cid,rid);assert done['status']['state']=='completed',done
 receipts=artifact(cid,rid,'approvals');assert len(receipts)==3
 # New runs require their own approval even if artifacts are reusable.
 retry=api('execute',{**body,'request_id':'reject-review'});pending=wait(cid,retry['run_id']);assert pending['status']['active_step']=='review_data'
 review=artifact(cid,retry['run_id'],'review_data')
 api('review',{'case_id':cid,'run_id':retry['run_id'],'identity':review['identity'],'approved':False,'note':'测试退回修改'})
 assert wait(cid,retry['run_id'])['status']['state']=='rejected'
 receipt={'passed':True,'case_id':cid,'run_id':rid,'summary':report['summary'],'reference':report['reference'],'checks':['data import and quality','three real human-review pauses','stale/empty approval rejected','no solve before input approval','unified initialization observations','native convergence','per-run approvals','rejection stops workflow'],'scope':'automated pipeline tests; approvals are test fixtures, not experimental qualification'}
 (record/'acceptance.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False))
finally:p.terminate();p.wait(timeout=10);log.close()
