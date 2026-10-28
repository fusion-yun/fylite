import base64,hashlib,json,os,socket,struct,subprocess,sys,time,urllib.request,urllib.parse,shutil
from pathlib import Path
import argparse,tempfile
parser=argparse.ArgumentParser(description='W2 local browser regression; copied history only, never executes the solver')
parser.add_argument('--source-run',type=Path,required=True)
parser.add_argument('--data',type=Path,required=True)
parser.add_argument('--artifacts',type=Path,required=True)
parser.add_argument('--browser',required=True)
parser.add_argument('--browser-lib-path')
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
scratch=Path(tempfile.mkdtemp(prefix='fylite-w2-browser-'))
print('Evidence directory: '+str(scratch),flush=True)
personal=scratch/'personal';source=args.source_run.resolve()
case=personal/'workflows/case-browser-fixture';case.mkdir(parents=True,exist_ok=True)
data=args.data.resolve();manifest=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False))
definition=json.loads((repo/'delivery/eq/cases/EQ-P01-94048/workflow.json').read_text())
for name in ('run-fixture-a','run-fixture-b'):
 dest=case/'runs'/name
 if not dest.exists():shutil.copytree(source,dest)
 snap=json.loads((dest/'snapshot.json').read_text());snap.update(case_id=case.name,parameters=definition['defaults'],dataset_manifest_sha256=manifest)
 write(dest/'snapshot.json',snap)
 for log in ('stdout.log','stderr.log'):
  if not (dest/log).exists():(dest/log).write_text('')
write(case/'case.json',{'case_id':case.name,'name':'浏览器夹具：同一历史结果的两份副本，非新计算','revision':1,'parameters':definition['defaults'],'directory':str(case)})
# A third explicit UI fixture combines historical results with freshly processed frozen
# waveforms. It is never presented as a newly solved equilibrium.
import importlib.util
sys.dont_write_bytecode=True
os.environ['FYLITE_EQ_DATA']=str(data)
spec=importlib.util.spec_from_file_location('browser_workflow',repo/'delivery/eq/apps/workflow/workflow.py')
w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)
rawrun=case/'runs/run-fixture-raw';shutil.copytree(case/'runs/run-fixture-b',rawrun)
state=w.read(rawrun/'status.json')
for name,fn in [('sources',w.sources),('quality',w.pipeline_tools.quality),('magnetics',w.magnetics)]:
 w.write(rawrun/(name+'.json'),fn(data,w.DEFAULT,rawrun))
 state['steps'].setdefault(name,{}).update(state='completed',sha256=w.sha(rawrun/(name+'.json')))
w.write(rawrun/'status.json',state)
original_hashes={str(p.relative_to(case/'runs')):w.sha(p) for p in (case/'runs').rglob('*') if p.is_file()}
# These disposable test copies adapt provenance solely for UI regression. Original captured records are unchanged.
def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
http=port();env={**os.environ,'FYLITE_EQ_DATA':str(data),'PYTHONDONTWRITEBYTECODE':'1'}
serverlog=(scratch/'server.log').open('wb');browserlog=(scratch/'browser.log').open('wb')
server=subprocess.Popen([sys.executable,str(repo/'tools/eq_delivery.py'),'serve','--artifacts',str(args.artifacts.resolve()),'--personal-root',str(personal),'--port',str(http),'--backend','direct'],env=env,stdout=serverlog,stderr=serverlog)
profile=scratch/('profile-'+str(os.getpid()))
if args.browser_lib_path:env['LD_LIBRARY_PATH']=args.browser_lib_path
browser=subprocess.Popen([args.browser,'--headless','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(profile),'--window-size=1366,768','about:blank'],env=env,stdout=browserlog,stderr=browserlog)
checks=[];events=[];ws=None
try:
 for _ in range(150):
  if (profile/'DevToolsActivePort').exists():break
  if browser.poll() is not None:raise RuntimeError((scratch/'browser.log').read_text()[-3000:])
  time.sleep(.1)
 debug=int((profile/'DevToolsActivePort').read_text().splitlines()[0])
 targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{debug}/json'));url=urllib.parse.urlparse(next(x['webSocketDebuggerUrl'] for x in targets if x['type']=='page'))
 ws=socket.create_connection((url.hostname,url.port));ws.settimeout(20)
 key=base64.b64encode(os.urandom(16)).decode();ws.sendall(f'GET {url.path} HTTP/1.1\r\nHost: {url.hostname}:{url.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
 header=b''
 while not header.endswith(b'\r\n\r\n'):header+=ws.recv(1)
 assert b'101' in header,header
 ident=0
 def receive(n):
  result=b''
  while len(result)<n:
   chunk=ws.recv(n-len(result))
   if not chunk:raise EOFError('CDP disconnected')
   result+=chunk
  return result
 def call(method,params={}):
  global ident
  ident+=1;raw=json.dumps({'id':ident,'method':method,'params':params}).encode();mask=os.urandom(4)
  head=b'\x81'+(bytes([128+len(raw)]) if len(raw)<126 else b'\xfe'+struct.pack('!H',len(raw)) if len(raw)<65536 else b'\xff'+struct.pack('!Q',len(raw)))
  ws.sendall(head+mask+bytes(x^mask[i%4] for i,x in enumerate(raw)))
  while True:
   op,size=receive(2);size &=127
   if size==126:size=struct.unpack('!H',receive(2))[0]
   elif size==127:size=struct.unpack('!Q',receive(8))[0]
   message=json.loads(receive(size))
   if message.get('id')==ident:
    if 'error' in message:raise RuntimeError(message['error'])
    return message['result']
   events.append(message)
 def js(expression):
  result=call('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
  if result.get('exceptionDetails'):raise RuntimeError(result['exceptionDetails'])
  return result['result'].get('value')
 def wait(expression):
  for _ in range(150):
   if js(expression):return
   time.sleep(.1)
  raise AssertionError('Timeout: '+expression)
 call('Runtime.enable');call('Page.enable');call('Emulation.setDeviceMetricsOverride',{'width':1366,'height':768,'deviceScaleFactor':1,'mobile':False})
 call('Page.navigate',{'url':f'http://127.0.0.1:{http}/fylite/eq/workflow.html'})
 wait("typeof dataReady!=='undefined' && dataReady && document.querySelector('#cases').options.length>1")
 assert js("!document.getElementById('overview').hidden")
 checks.append('default overview and real API load')
 js("openNode('pressure')");wait("!!document.querySelector('#node-content svg')")
 assert js("document.querySelector('#node-content').textContent.includes('6.51')")
 js("let input=document.querySelector('#node-content input');input.value='1.2';input.dispatchEvent(new Event('input'));[...document.querySelectorAll('#node-content button')].find(b=>b.textContent==='更新曲线预览').click()")
 wait("[...document.querySelectorAll('#node-content button')].some(b=>b.textContent==='将倍率写入配置草稿'&&!b.disabled)")
 js("[...document.querySelectorAll('#node-content button')].find(b=>b.textContent==='将倍率写入配置草稿').click()")
 assert js("document.getElementById('pressure_scale').value==='1.2' && dirty")
 checks.append('pressure source, error bars, draft multiplier preview/apply; no execute')
 js("document.getElementById('cases').value='case-browser-fixture';document.getElementById('cases').dispatchEvent(new Event('change'))")
 wait("document.querySelectorAll('#runs button').length===3")
 js("[...document.querySelectorAll('#runs button')].find(b=>b.textContent.includes('run-fixture-b')).click()")
 wait("lastRun!==null")
 js("document.querySelector('[data-tab=results]').click()")
 wait("!!document.querySelector('.run-comparator button') && !document.querySelector('.run-comparator button').disabled")
 js("document.querySelector('.run-comparator button').click()")
 wait("document.querySelector('.run-comparator').textContent.includes('实际输入一致')")
 assert js("document.querySelectorAll('.run-comparator svg').length===2")
 checks.append('two run input comparison and q/pressure overlays')
 assert js("document.querySelectorAll('.scientific-overview figure').length===7")
 assert js("document.querySelectorAll('.scientific-overview [data-diagnostic]').length===3")
 assert js("document.querySelector('.scientific-overview').textContent.includes('条件 ±1σ')")
 result_image=call('Page.captureScreenshot',{'format':'png'})['data']
 (scratch/'result-overview.png').write_bytes(base64.b64decode(result_image))
 checks.append('scientific overview: surfaces, six physical plots, native conditional bands and three explicit missing diagnostic panels')
 js("[...document.querySelectorAll('#analysis-panel button')].find(b=>b.textContent==='计算 POINT 诊断后处理').click()")
 wait("document.querySelectorAll('.scientific-overview figure').length===10")
 assert js("document.querySelector('.scientific-overview').textContent.includes('256次独立高斯观测扰动')")
 assert js("document.querySelectorAll('.scientific-overview [data-diagnostic]').length===0")
 point_image=call('Page.captureScreenshot',{'format':'png'})['data'];(scratch/'point-overview.png').write_bytes(base64.b64decode(point_image))
 point_files=list((case/'diagnostic-analyses').glob('point-*.json'));assert len(point_files)==1
 point=json.loads(point_files[0].read_text());assert len(point['result']['chords'])==11 and len(point['result']['density'])==1025
 assert point['result_sha256']==w.hobj(point['result'])
 checks.append('explicit native POINT postprocessing: BNEL/BPOLAR/ne quantiles, persisted separate hash-bound artifact; no equilibrium solve')
 js("FyScientificTasks.channel('loops',0)")
 wait("document.getElementById('node-content').textContent.includes('此页只读')")
 assert js("[...document.querySelectorAll('#node-content button')].some(b=>b.textContent.includes('选择此运行')&&b.disabled)")
 checks.append('same-run residual channel trace; missing raw data disclosed and reprocessing disabled')
 image=call('Page.captureScreenshot',{'format':'png'})['data'];(scratch/'channel.png').write_bytes(base64.b64decode(image))
 # Follow the exact raw run back into processing, then save-as the adoption.
 js("[...document.querySelectorAll('#runs button')].find(b=>b.textContent.includes('run-fixture-raw')).click()")
 wait("runId==='run-fixture-raw' && lastRun?.status")
 js("FyScientificTasks.channel('loops',0)")
 wait("[...document.querySelectorAll('#node-content button')].some(b=>b.textContent.includes('选择此运行')&&!b.disabled)")
 js("[...document.querySelectorAll('#node-content button')].find(b=>b.textContent.includes('选择此运行')).click()")
 wait("document.getElementById('mp-run').value==='run-fixture-raw'")
 js("document.getElementById('mp-import').click()")
 wait("!!document.getElementById('mp-dataset').value && !document.getElementById('mp-preview').disabled")
 js("document.getElementById('mp-preview').click()")
 wait("!document.getElementById('mp-adopt').disabled")
 js("document.getElementById('mp-note').value='浏览器工程验收：核对冻结波形处理，不代表科学验收';document.getElementById('mp-adopt').click()")
 wait("caseDoc?.revision===2 && !!caseDoc.processing && !document.getElementById('fork').disabled")
 adopted=w.read(case/'case.json');reference=adopted['processing']
 object_hashes={str(p.relative_to(case)):w.sha(p) for folder in ('datasets','previews') for p in (case/folder).rglob('*') if p.is_file()}
 js("document.getElementById('name').value='浏览器另存验证';document.getElementById('fork').click()")
 wait("caseDoc?.case_id!=='case-browser-fixture' && !!caseDoc?.processing")
 clone_id=js('caseDoc.case_id');clone=personal/'workflows'/clone_id
 assert w.read(clone/'case.json')['processing']==reference
 assert object_hashes=={str(p.relative_to(clone)):w.sha(p) for folder in ('datasets','previews') for p in (clone/folder).rglob('*') if p.is_file()}
 assert original_hashes=={str(p.relative_to(case/'runs')):w.sha(p) for p in (case/'runs').rglob('*') if p.is_file()}
 assert w.read(case/'case.json')==adopted
 call('Page.navigate',{'url':'about:blank'})
 wait("typeof dataReady==='undefined'")
 call('Page.navigate',{'url':f'http://127.0.0.1:{http}/fylite/eq/workflow.html'})
 wait("typeof dataReady!=='undefined' && dataReady && [...document.getElementById('cases').options].some(o=>o.value==="+json.dumps(clone_id)+")")
 js("document.getElementById('cases').value="+json.dumps(clone_id)+";document.getElementById('cases').dispatchEvent(new Event('change'))")
 wait("caseDoc?.case_id==="+json.dumps(clone_id)+" && !!caseDoc.processing")
 checks.append('exact raw run → import → preview → adopt → Save As → reload; copied object hashes identical and historical runs unchanged')
 parsed=js("Promise.all(['workflow.js','workflow-graph.js','magnetic-processing.js','scientific-tasks.js','analysis.js'].map(async f=>{const response=await fetch('/fylite/eq/ui/assets/'+f);if(!response.ok)throw Error(f);new Function(await response.text());return f;}))")
 checks.append('browser JS syntax parsing: '+', '.join(parsed))
 errors=[e for e in events if e.get('method')=='Runtime.exceptionThrown']
 assert not errors,errors
 receipt={'passed':True,'checks':checks,'scope':'real Chromium and API using disposable historical-result fixtures; no solver and no scientific certification','viewport':js('({width:innerWidth,height:innerHeight})'),'errors':errors}
 (scratch/'acceptance.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False))
finally:
 if ws:ws.close()
 browser.terminate();server.terminate();browser.wait(timeout=10);server.wait(timeout=10);serverlog.close();browserlog.close()
