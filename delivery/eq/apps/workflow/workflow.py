"""Versioned workflow executor and 94048 fixed-pressure tools; stdlib, native release only."""
from pathlib import Path
import argparse, copy, ctypes, gzip, hashlib, json, math, os, re, secrets, shutil, signal, struct, subprocess, sys, threading, time, uuid
ROOT=Path(__file__).resolve().parents[2]
for folder in (ROOT/'apps/fixed-boundary', ROOT.parents[1]/'tools'):
    if (folder/'eq_delivery.py').is_file(): sys.path.insert(0,str(folder)); break
from eq_delivery import Kernel, personal, process_identity

sys.path.insert(0,str(Path(__file__).resolve().parent))
import pipeline_tools
import processing_tools
import object_contracts
import scientific_views
import point_analysis

def tool_identity():return hobj({p.name:sha(p) for p in [Path(__file__),Path(__file__).with_name('pipeline_tools.py'),Path(__file__).with_name('processing_tools.py'),Path(__file__).with_name('object_contracts.py')]})

def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def hobj(v): return hashlib.sha256(json.dumps(v,sort_keys=True,allow_nan=False).encode()).hexdigest()
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(v,ensure_ascii=False,allow_nan=False,indent=2)+'\n');os.replace(temp,p)
def dataset(): return Path(os.environ.get('FYLITE_EQ_DATA','/project/FyLite/data/eq/east94048/v1')).resolve()
def check_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,80}',value):raise ValueError('无效对象编号')
    return value
DEFINITION=read(ROOT/'cases/EQ-P01-94048/workflow.json')
DEFAULT=DEFINITION['defaults']
NODES=DEFINITION['nodes']
def parameters(v):
    # Legacy cases predate the explicit mode; their behavior was always target.
    if isinstance(v,dict):v={'q_mode':'target','data_source':'frozen',**v}
    if not isinstance(v,dict) or set(v)!=set(DEFAULT):raise ValueError('参数字段不完整或包含未知字段')
    if v['data_source'] not in ('frozen','mdsplus'):raise ValueError('数据来源必须为冻结缓存或MDSplus')
    if v['q_mode'] != 'target':raise ValueError('当前 rc3 内核仅支持 q₀目标归一化＋加权约束；不约束和软约束需升级原生包，不能用权重归零替代。')
    if type(v['drift']) is not bool:raise ValueError('drift 必须为布尔值')
    for key,lo,hi in [('half_window_s',.001,.005),('pressure_scale',.5,1.5),('q_target',.5,3.)]:
        x=v[key]
        if type(x) not in (int,float) or not math.isfinite(x) or not lo<=x<=hi:raise ValueError(f'{key} 超出 [{lo}, {hi}]')
    if type(v['max_iterations']) is not int or not 1<=v['max_iterations']<=150:raise ValueError('迭代上限须为1–150的整数')
    return dict(v)
def manifest(data):
    m=read(data/'manifest.json')
    for name,digest in m['files'].items():
        p=(data/name).resolve()
        if not p.is_relative_to(data) or sha(p)!=digest:raise ValueError('数据身份检查失败: '+name)
    return m

def numeric_vars(path):
    s='\n'.join(l.split('!')[0] for l in path.read_text().splitlines());hits=list(re.finditer(r'\b([A-Za-z][A-Za-z0-9_]*)\s*=',s));out={}
    for i,m in enumerate(hits):
        vals=s[m.end():hits[i+1].start() if i+1<len(hits) else len(s)]
        out[m[1].upper()]=[float(x.replace('D','E').replace('d','e')) for x in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?',vals)]
    return out

def sources(data,pars,run):
    m=manifest(data)
    snap=read(run/'snapshot.json') if (run/'snapshot.json').exists() else {}
    if snap.get('processing'):
        path,meta=processing_tools.adopted(sys.modules[__name__],run.parent.parent,snap['processing'],pars)
        for name in ('sources.json','acquired-waveforms.json.gz'):
            shutil.copyfile(path/name,run/name)
        return {**read(path/'sources.json'),'reuse':{'preview_id':meta['preview_id'],'dataset_id':meta['dataset_id'],'meaning':'复用已采纳原始数据；本次没有重新取数'}}
    acquisition=pipeline_tools.acquire(data,pars,run)
    limits=[x for x in m['limits'] if not x.startswith('Frozen magnetic windows')]
    limits.insert(0,'本次在线读取磁波形并保存窗口；固定压力与响应表仍来自历史包。' if pars['data_source']=='mdsplus' else '本次读取冻结实验窗口，未进行在线取数。')
    return {'acquisition':acquisition,'dataset':m['dataset_id'],'manifest_sha256':sha(data/'manifest.json'),'shot':94048,'time_s':5.760,'pressure_time_s':6.510,'limits':limits,'sources':m['origins'],'waveform_conversion':m['waveform_conversion'] if pars['data_source']=='frozen' else '本次libsp在线读取，保留目标与基线窗口；来源身份见acquisition。'}
def magnetics(data,pars,run):
    snap=read(run/'snapshot.json') if (run/'snapshot.json').exists() else {}
    if snap.get('processing'):
        path,meta=processing_tools.adopted(sys.modules[__name__],run.parent.parent,snap['processing'],pars)
        return read(path/'magnetics.json')
    source=read(run/'sources.json')['acquisition'];raw=run/source['waveforms_file']
    if sha(raw)!=source['waveforms_sha256']:raise ValueError('原始波形身份已改变')
    with gzip.open(raw,'rt') as f: traces=json.load(f)
    mapping=read(data/'mapping.json')['mapping'];weights=numeric_vars(data/'weights.nml');audit=[]
    def value(node,scale=1.,correct=False):
        a=traces['east:'+node];pairs=[(t,y) for t,y in zip(a['target_t'],a['target_y']) if abs(t-5.760)<=pars['half_window_s']]
        if not pairs:raise ValueError('磁窗口内无数据: '+node)
        slope=intercept=0.
        if correct:
            b=[(t,y) for t,y in zip(a['baseline_t'],a['baseline_y']) if -6.9<=t<=-6.1]
            if len(b)<3:raise ValueError('炮前基线不足: '+node)
            bt=sum(t for t,y in b)/len(b);by=sum(y for t,y in b)/len(b)
            slope=sum((t-bt)*(y-by) for t,y in b)/sum((t-bt)**2 for t,y in b);intercept=by-slope*bt
        result=sum(y-slope*t-intercept for t,y in pairs)/len(pairs)*scale
        audit.append({'node':node,'scale':scale,'drift':correct,'samples':len(pairs),'slope':slope,'intercept':intercept,'raw_mean':sum(y for t,y in pairs)/len(pairs),'reduced':result,'t':[t for t,y in pairs],'raw':[y*scale for t,y in pairs],'processed':[(y-slope*t-intercept)*scale for t,y in pairs],'source_sha256':a.get('online_retained_sha256') or a.get('original_npz_sha256')})
        return result
    loops=[value(n,1/(2*math.pi),pars['drift']) for n in mapping['FLUX_LOOP_NODES']]
    probes=[value(n,1.,pars['drift']) for n in mapping['B_PROBE_NODES_LEGACY'][:36]]
    rawpf=[value(n,t) for n,t in zip(mapping['PF_NODES'],mapping['PF_TURNS'])];pf=[rawpf[i] for i in mapping['PF_EFIT_ORDER']]
    ip=abs(value('IPM',1000));bt=value('FOCS_IT',1.7/1.8/4086)
    frac=struct.unpack('f',struct.pack('f',.03))[0]
    def eff(vals,prior,threshold):return [w/(abs(v)*frac) if abs(v)*frac>threshold else 0. for v,w in zip(vals,prior)]
    lw=eff(loops,weights['FWTSI'],5e-4);lw[0]=weights['FWTSI'][0]/max(abs(v) for v in loops)/frac
    pw=eff(probes,weights['FWTMP2'],1e-3)+[0.]*40
    return {'loop_observed':loops,'probe_observed':probes+[0.]*40,'pf_observed':pf,'ip_observed':ip,'btor':bt,'loop_weights':lw,'probe_weights':pw,'pf_weights':eff(pf,weights['FWTFC'],1e-10),'audit':audit,'window_s':[5.760-pars['half_window_s'],5.760+pars['half_window_s']],'scope':'Retained experimental windows; historical 36 probe mapping and assumed 3% error/priority rules. Flux loops Wb/rad; probes T; PF A.turn; Ip A. No automatic channel rejection.'}
def pressure(data,pars,run):
    fin=numeric_vars(data/'onetwo-final.nml');x=[abs(v) for v in fin['RPRESS'][:201:4]];p=[v*pars['pressure_scale'] for v in fin['PRESSR'][:201:4]]
    if len(p)!=51 or len(x)!=51:raise ValueError('ONETWO压力必须生成51点')
    return {'psi_n':x,'pressure_Pa':p,'sigma_Pa':[.1*v+.02*max(p) for v in p],'weights':[20.]*6+[5.]*20+[15.]*14+[25.]*11,'time_s':6.510,'scale':pars['pressure_scale'],'source_sha256':sha(data/'onetwo-final.nml'),'scope':'Every fourth RPRESS/PRESSR point; SIGPRE and FWTPRE from historical settinglib recipe. ONETWO not rerun; no new bootstrap current.'}
def assemble(data,pars,run):
    pars=parameters(pars)
    c=read(data/'native-template.json');m=read(run/'magnetics.json');p=read(run/'pressure.json');mags=c['measurement_template']['magnetic'];glob=c['measurement_template']['global'];pres=c['measurement_template']['pressure']
    for key in ['loop_observed','probe_observed','loop_weights','probe_weights']:mags[key]=m[key]
    for key in ['pf_observed','pf_weights','ip_observed']:glob[key]=m[key]
    # Observation identity is shared by initialization and subsequent fitting.
    for key in ['loop_observed','loop_weights','pf_observed','pf_weights']:c['initial_pf'][key]=m[key]
    c['initial']['target_ip']=m['ip_observed'];c['measurement_template']['fsa']['measured_ip']=m['ip_observed']
    glob['q_target']=pars['q_target'];c['btor']=m['btor'];c['max_iterations']=pars['max_iterations']
    pres.update(coordinates=[-v for v in p['psi_n']],observed=p['pressure_Pa'],sigma=p['sigma_Pa'],weights=p['weights'])
    return {'config':c,'effective':{'shot':94048,'time_s':5.760,'pressure_time_s':6.510,'time_difference_s':.750,'grid':'129x129','route':'fixed external pressure + q0 target + fitted PF','q_mode':pars['q_mode'],'q_source':'historical recipe / user prior, not an independent measurement','q_normalization':True,'q_target':pars['q_target'],'q_weight':glob['q_weight'],'pf_fit':True,'edge_current':'archived artificial constraints, not new bootstrap','relax':c['relax'],'tolerance':c['tolerance'],'max_iterations':c['max_iterations'],'initialization':'archived shape, current observations synchronized with main fit','magnetic_channels_used':sum(w>0 for w in m['loop_weights']+m['probe_weights']),'inputs_flux':'legacy_wb_per_radian','output_flux':'COCOS17_whole_wb'}}
def solve(data,pars,run):
    root=Path(os.environ['FYLITE_EQ_ROOT']);k=Kernel(root,read(root/'kernel.lock.json') if (root/'kernel.lock.json').exists() else read(root/'releases/kernel-rc3.lock.json'))
    c=read(run/'assemble.json')['config'];tables={str(p.relative_to(data)):p.read_bytes().hex() for p in (data/'input/tables').glob('*.ddd')}
    request={'inputs':{'native_reconstruction':{'config':c,'input_flux_convention':'legacy_wb_per_radian','bound_green_tables':tables}}}
    raw=json.dumps(request,allow_nan=False).encode();code=b'code/kinetic';out,n=ctypes.c_void_p(),ctypes.c_uint64()
    write(run/'native-input-identity.json',{'request_sha256':hashlib.sha256(raw).hexdigest(),'config_sha256':hobj(c),'table_files':{name:sha(data/name) for name in tables},'kernel':k.identity,'recreate':'assemble.json config + dataset response bytes + explicit legacy_wb_per_radian binding'})
    rc=k.call(code,len(code),raw,len(raw),ctypes.byref(out),ctypes.byref(n))
    try:response=json.loads(ctypes.string_at(out,n.value)) if out.value else {}
    finally:
        if out.value:k.release(out,n.value)
    if rc or 'refusal' in response:raise ValueError('内核拒绝: '+str(response)[:1000])
    record=response['record']
    return record

def report(data,pars,run):
    v=read(run/'solve.json');c=read(run/'assemble.json');r=v['result'];ex=v['exports'];old=read(data/'historical-reference.json')['result'];old=old.get('record',old)
    q=ex['q']['profiles'];hist=v.get('history',[]);diagnostics=ex['diagnostics']['diagnostics']
    # Whole-Wb result field is i-major/j-minor; diagnostics loop export remains legacy Wb/rad.
    summary={'converged':v['converged'],'iteration':r['iteration'],'error':r['error'],'ip_A':r['ip'],'q0':q[0]['q'],'axis_R_m':r['geometry']['axis']['r'],'axis_Z_m':r['geometry']['axis']['z'],'magnetic_weighted_squared_residual':ex['diagnostics']['weighted_squared_residual'],'physical':'not_experimentally_qualified'}
    ref={'label':'Historical standalone-v3 no-drift, comparison only','comparison_scope':'historical initialization was not synchronized; reference only','library_sha256':read(data/'historical-reference.json')['identity']['library_sha256'],'same_recipe':False,'delta_q0':q[0]['q']-old['exports']['q']['profiles'][0]['q'],'delta_ip_A':r['ip']-old['result']['ip'],'max_field_absolute_Wb':max(abs(a-b) for a,b in zip(r['field'],old['result']['field']))}
    return {'summary':summary,'effective':c['effective'],'q':q,'pressure':ex['pressure_F']['profiles'],'pressure_input':read(run/'pressure.json'),'history':hist,'diagnostics':diagnostics,'pf':{'observed':c['config']['measurement_template']['global']['pf_observed'],'fitted':r['solution'][:12]},'geometry':r['geometry'],'grid':{'r':c['config']['initial']['r'],'z':c['config']['initial']['z'],'field':r['field']},'reference':ref,'limits':read(run/'sources.json')['limits']+['Diagnostic loop values are Wb/rad; whole-field grid is Wb.','Conditional covariance excludes geometry; not a full equilibrium confidence interval.','No independent experimental qualification; reference agreement is limited to matched recipe.']}
TOOLS={'quality':pipeline_tools.quality,'constraints':pipeline_tools.constraints,'review':lambda data,pars,run: {},'sources':sources,'magnetics':magnetics,'pressure':pressure,'assemble':assemble,'solve':solve,'report':report}
def plan_nodes(definition,target):
    if definition.get('execution_kind','dag')!='dag':raise ValueError('当前执行器仅支持DAG，分支和循环尚未适配')
    nodes=definition['nodes'];by_id={n['id']:n for n in nodes}
    if len(by_id)!=len(nodes):raise ValueError('节点编号重复')
    visiting=set();visited=set();ordered=[]
    def visit(key):
        if key not in by_id:raise ValueError('未知节点或依赖: '+key)
        if key in visiting:raise ValueError('工作流含循环依赖')
        if key in visited:return
        visiting.add(key);node=by_id[key]
        if node.get('tool',key) not in TOOLS:raise ValueError('未注册的工具')
        for dep in node['deps']:visit(dep)
        visiting.remove(key);visited.add(key);ordered.append(node)
    # Validate the entire template, even when executing a partial plan.
    for n in nodes:visit(n['id'])
    visited.clear();visiting.clear();ordered.clear();visit(target)
    return ordered

def closure(target):return plan_nodes(DEFINITION,target)
def worker(run,data):
    snap=read(run/'snapshot.json');pars=parameters(snap['parameters']);status=read(run/'status.json');definition=snap.get('workflow_definition');nodes=plan_nodes(definition,snap['target']) if definition else [];events=read(run/'events.json') if (run/'events.json').exists() else []
    def persist():write(run/'status.json',status);write(run/'events.json',events)
    try:
        if definition is None:raise ValueError("旧运行缺少冻结流程定义；保留只读，请另存新修订后运行")
        manifest(data)
        if snap.get('workflow_sha256') and hobj(definition)!=snap['workflow_sha256']:raise ValueError('冻结工作流身份不一致')
        if sha(data/'manifest.json') != snap['dataset_manifest_sha256'] or tool_identity() != snap['tool_sha256']:
            raise ValueError('执行前数据或工具版本已改变，请重新提交')
        for node in nodes:
            key=node['id'];state=status['steps'][key]
            if state['state'] in ('completed','reused'):
                if sha(run/(key+'.json'))!=state['sha256']:raise ValueError('已有产物被修改: '+key)
                continue
            state.update(state='running',started_at=time.time());status['active_step']=key;status['state']='running';events.append({'step':key,'state':'running','time':time.time()});persist()
            fingerprint=hobj({'tool':tool_identity(),'workflow':hobj(definition),'dataset':sha(data/'manifest.json'),'node':key,'parameters':{k:pars[k] for k in node['parameters']},'deps':{d:sha(run/(d+'.json')) for d in node['deps']},'kernel':snap['kernel_identity'] if key=='solve' else None})
            if node.get('review'):
                receipt=read(run/'approvals.json') if (run/'approvals.json').exists() else {}
                identity=review_identity(run,status,key)
                if receipt.get(key,{}).get('identity')!=identity:
                    payload={'review':node['review'],'identity':identity,'run_id':run.name,'revision':snap['revision'],'parameters':pars,'artifacts':{n:st['sha256'] for n,st in status['steps'].items() if st.get('sha256')},'warnings':read(run/'quality.json')['warnings'] if (run/'quality.json').exists() else [],'meaning':'确认已检查所列输入与限制；不代表独立实验验证'}
                    write(run/(key+'.json'),payload)
                    state.update(state='waiting_review',fingerprint=fingerprint);status.update(state='waiting_review',active_step=key)
                    events.append({'step':key,'state':'waiting_review','time':time.time()});persist();return
                state.update(state='completed',ended_at=time.time(),fingerprint=fingerprint,sha256=sha(run/(key+'.json')))
                events.append({'step':key,'state':'completed','time':time.time(),'reviewed':True});persist();continue
            reused=None
            if key!=snap['target'] and key!='sources':
                for other in sorted(run.parent.iterdir(),reverse=True):
                    if other==run or not (other/'status.json').exists():continue
                    prior=read(other/'status.json').get('steps',{}).get(key,{})
                    file=other/(key+'.json')
                    if prior.get('fingerprint')==fingerprint and prior.get('state') in ('completed','reused') and file.is_file() and sha(file)==prior.get('sha256'):
                        shutil.copy2(file,run/file.name);reused=other.name;break
            if not reused:write(run/(key+'.json'),TOOLS[node.get('tool',key)](data,pars,run))
            state.update(state='reused' if reused else 'completed',ended_at=time.time(),fingerprint=fingerprint,sha256=sha(run/(key+'.json')),reused_from=reused)
            # Preserve identity sidecar for a cached native solve.
            if key=='solve' and reused and (run.parent/reused/'native-input-identity.json').exists():shutil.copy2(run.parent/reused/'native-input-identity.json',run/'native-input-identity.json')
            if key=='solve':status['numerical']='converged' if read(run/'solve.json')['converged'] else 'not_converged'
            events.append({'step':key,'state':state['state'],'time':time.time()});persist()
        status.update(state='completed',active_step=None,ended_at=time.time())
        if (run/'solve.json').exists():status['numerical']='converged' if read(run/'solve.json')['converged'] else 'not_converged'
        status['physical']='not_experimentally_qualified';persist()
    except Exception as e:
        status.update(state='failed',error=str(e),error_detail=object_contracts.error_record(e,status.get('active_step')),ended_at=time.time())
        if status.get('active_step'):status['steps'][status['active_step']].update(state='failed',error=str(e),ended_at=time.time())
        persist();raise

LOCK=threading.Lock()
def base(roots):return personal(str(Path(roots[0]).expanduser()/'workflows'),roots)
def casepath(cid,roots):return personal(str(base(roots)/check_id(cid)),roots)
def runpath(cid,rid,roots):return personal(str(casepath(cid,roots)/'runs'/check_id(rid)),roots)
def info(root):
    ready=True;reason=None
    try:m=manifest(dataset())
    except Exception as e:ready=False;reason=str(e);m={}
    return {'workflow_id':'east94048-fixed-pressure','title':'EAST 94048 · 固定压力平衡工作流','nodes':NODES,'definition':DEFINITION,'defaults':DEFAULT,'tool_definitions':object_contracts.tool_definitions(sys.modules[__name__]),'dataset_ready':ready,'reason':reason,'limits':m.get('limits',[]),'capabilities':{'native_code':'code/kinetic','online_fetch':True,'live_native_iterations':False,'resume_native':False,'agent':False,'processing_preview':True,'processing_api':['processing-import','processing-preview','processing-adopt'],'q_modes':['target'],'human_reviews':True,'supported_shots':[94048]}}
def save(body,roots):
    with LOCK:
        current={}; origin=None
        pars=parameters(body['parameters']);name=body.get('name','').strip()
        if not name or len(name)>100:raise ValueError('请输入1–100字算例名称')
        if body.get('source_case_id'):
            if body.get('case_id'):raise ValueError('另存与更新不能同时进行')
            origin=casepath(body['source_case_id'],roots)
            current=read(origin/'case.json')
            if body.get('source_revision')!=current['revision']:raise ValueError('来源修订已变化，请重新打开')
        if body.get('case_id'):
            path=casepath(body['case_id'],roots);current=read(path/'case.json')
            if body.get('base_revision')!=current['revision']:raise ValueError('算例已被其他操作更新，请重新打开后保存')
            rev=current['revision']+1; staging=path
        else:
            path=casepath('case-'+uuid.uuid4().hex[:12],roots);rev=1
            staging=path.with_name('.pending-'+path.name);staging.mkdir(parents=True,exist_ok=False)
        try:
            case={'case_id':path.name,'name':name,'revision':rev,'workflow_id':'east94048-fixed-pressure','parameters':pars,'updated_at':time.time(),'directory':str(path)}
            if origin:
                case.update(object_contracts.clone_processing(sys.modules[__name__],origin,staging,current,pars))
                case['parent']={'case_id':current['case_id'],'revision':current['revision']}
            elif current.get('processing') and processing_tools.subset(pars)==processing_tools.subset(parameters(current['parameters'])):
                case['processing']=current['processing'];case['processing_receipt']=current.get('processing_receipt',{})
            write(staging/'revisions'/f'{rev}.json',case);write(staging/'case.json',case)
            if staging!=path:os.rename(staging,path)
            return case
        except Exception:
            # Only discard a never-published directory created by this call.
            if staging!=path:shutil.rmtree(staging)
            raise

def execute(body,root,roots):
    with LOCK:
        case=read(casepath(body['case_id'],roots)/'case.json')
        case['parameters']=parameters(case['parameters'])
        if body.get('revision')!=case['revision']:raise ValueError('输入修订已变化，请重新打开')
        key=check_id(body['request_id']);target=body.get('target','report');nodes=closure(target)
        runs=casepath(case['case_id'],roots)/'runs';runs.mkdir(exist_ok=True)
        for p in runs.iterdir():
            if (p/'snapshot.json').exists():
                old=read(p/'snapshot.json')
                if old.get('request_id')==key:
                    if old['revision']!=case['revision'] or old['target']!=target or bool(old.get('fresh_source'))!=bool(body.get('fresh_source')):raise ValueError('幂等键不能绑定不同计划')
                    return {'run_id':p.name,'case_id':case['case_id'],'reused_request':True}
        if body.get('fresh_source'):
            if target!='sources':raise ValueError('重新取数仅用于来源节点')
            case.pop('processing',None)
        elif case.get('processing'):
            processing_tools.adopted(sys.modules[__name__],casepath(case['case_id'],roots),case['processing'],case['parameters'])
        manifest(dataset());identity=Kernel(root,read(root/'kernel.lock.json') if (root/'kernel.lock.json').exists() else read(root/'releases/kernel-rc3.lock.json')).identity
        run=runs/('run-'+time.strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]);run.mkdir()
        write(run/'snapshot.json',{**case,'object_contract':object_contracts.SCHEMA,'hash_profile':object_contracts.HASH_PROFILE,'fresh_source':bool(body.get('fresh_source')),'target':target,'request_id':key,'plan':nodes,'dataset_manifest_sha256':sha(dataset()/'manifest.json'),'kernel_identity':identity,'tool_sha256':tool_identity(),'workflow_definition':copy.deepcopy(DEFINITION),'workflow_sha256':hobj(DEFINITION)})
        write(run/'status.json',{'run_id':run.name,'revision':case['revision'],'state':'starting','numerical':'not_assessed','physical':'not_assessed','started_at':time.time(),'steps':{n['id']:{'state':'pending' if n in nodes else 'skipped'} for n in NODES}})
        launch_worker(run,root)
        return {'run_id':run.name,'case_id':case['case_id'],'reused_request':False}
def launch_worker(run,root):
    token=uuid.uuid4().hex
    env={**os.environ,'FYLITE_EQ_ROOT':str(root),'PYTHONDONTWRITEBYTECODE':'1'}
    with (run/'stdout.log').open('ab') as out,(run/'stderr.log').open('ab') as err:
        proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker','--run',str(run),'--data',str(dataset()),'--token',token],cwd=run,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True,env=env)
    write(run/'job.json',{'pid':proc.pid,'token':token,'start_ticks':(process_identity(proc.pid) or {}).get('start_ticks')})
    threading.Thread(target=proc.wait,daemon=True).start()

def review_identity(run,status,step):
    snap=read(run/'snapshot.json')
    artifacts={}
    for key,state in status['steps'].items():
        if key!=step and state['state'] in ('completed','reused'):
            actual=sha(run/(key+'.json'))
            if actual!=state['sha256']:raise ValueError('产物已改变: '+key)
            artifacts[key]=actual
    if (run/'sources.json').exists():
        acquired=read(run/'sources.json').get('acquisition')
        if acquired and sha(run/acquired['waveforms_file'])!=acquired['waveforms_sha256']:raise ValueError('获取波形已改变')
    return hobj({'snapshot':sha(run/'snapshot.json'),'step':step,'artifacts':artifacts})

def review(body,root,roots):
    with LOCK:
        run=runpath(body['case_id'],body['run_id'],roots);st=state(run);snap=read(run/'snapshot.json')
        if st['state']!='waiting_review':raise ValueError('运行不处于待确认状态')
        if read(casepath(body['case_id'],roots)/'case.json')['revision']!=snap['revision']:raise ValueError('算例修订已改变，请以新修订重新运行')
        step=st['active_step'];identity=review_identity(run,st,step)
        if body.get('identity')!=identity:raise ValueError('确认内容已变化，请重新检查')
        if tool_identity()!=snap['tool_sha256'] or sha(dataset()/'manifest.json')!=snap['dataset_manifest_sha256']:raise ValueError('工具或数据版本已改变，请重新运行')
        manifest(dataset())
        note=body.get('note','').strip()
        if not note or len(note)>2000:raise ValueError('请填写检查结论或退回原因（1–2000字）')
        approved=body.get('approved')
        if type(approved) is not bool:raise ValueError('缺少确认决定')
        receipts=read(run/'approvals.json') if (run/'approvals.json').exists() else {}
        receipts[step]={'identity':identity,'approved':approved,'note':note,'time':time.time(),'actor':os.environ.get('USER','local-user')}
        write(run/'approvals.json',receipts)
        if not approved:
            st.update(state='rejected',ended_at=time.time());st['steps'][step]['state']='rejected';write(run/'status.json',st)
        else:
            st.update(state='starting');write(run/'status.json',st);launch_worker(run,root)
        return {'run_id':run.name,'decision':'approved' if approved else 'rejected'}

def state(run,cancel=False):
    st=read(run/'status.json')
    if cancel and st['state']=='waiting_review':
        st['steps'][st['active_step']]['state']='cancelled';st.update(state='cancelled',active_step=None,ended_at=time.time());write(run/'status.json',st);return st
    if st['state'] in ('starting','running'):
        j=read(run/'job.json');ident=process_identity(j['pid']);matches=bool(ident and ident['start_ticks']==j['start_ticks'])
        if matches:
            args=Path('/proc')/str(j['pid'])/'cmdline'
            try:
                matches=j['token'].encode() in args.read_bytes().split(b'\0') and os.getpgid(j['pid'])==j['pid'] and args.stat().st_uid==os.getuid()
            except (FileNotFoundError, ProcessLookupError):
                matches=False
        if cancel and matches:
            try:os.killpg(j['pid'],signal.SIGTERM)
            except ProcessLookupError:return read(run/'status.json')
            st.update(state='cancelled',ended_at=time.time())
            for step in st['steps'].values():
                if step['state']=='running':step.update(state='cancelled',ended_at=st['ended_at'])
            st['active_step']=None;write(run/'status.json',st)
        elif not matches:
            # Re-read: worker may have completed between the first read and process check.
            st=read(run/'status.json')
            if st['state'] in ('starting','running'):st.update(state='failed',error='工作进程已退出，请查看日志');write(run/'status.json',st)
    return st

def dispatch(method,route,body,root,roots,query):
    if route=='point-analysis':return point_analysis.dispatch(sys.modules[__name__],method,body,query,root,roots)
    if (method=='GET' and route in ('processing-objects','processing-preview')) or (method=='POST' and route in ('processing-import','processing-preview','processing-adopt')):
        return processing_tools.dispatch(sys.modules[__name__],method,route,body,roots,query)
    if method=='GET':
        if route in ('pressure-preview','compare','channel-view'):return scientific_views.dispatch(sys.modules[__name__],route,roots,query)
        if route=='info':return info(root)
        if route=='cases':return {'cases':[read(p/'case.json') for p in sorted(base(roots).glob('case-*')) if (p/'case.json').is_file()]}
        cid=query.get('case_id',[''])[0];path=casepath(cid,roots)
        if route=='case':return read(path/'case.json')
        if route=='runs':return {'runs':[{'run_id':p.name,'status':state(p),'target':read(p/'snapshot.json')['target']} for p in sorted((path/'runs').glob('run-*'),reverse=True)]}
        run=runpath(cid,query.get('run_id',[''])[0],roots)
        if route=='run':return {'status':state(run),'snapshot':read(run/'snapshot.json'),'events':read(run/'events.json') if (run/'events.json').exists() else [],'stdout':(run/'stdout.log').read_text(errors='replace')[-6000:],'stderr':(run/'stderr.log').read_text(errors='replace')[-6000:]}
        if route=='objects':return object_contracts.run_objects(sys.modules[__name__],run)
        if route=='analysis':
            result=read(run/'report.json');data=dataset();manifest(data)
            snap=read(run/'snapshot.json')
            if sha(data/'manifest.json')!=snap['dataset_manifest_sha256']:raise ValueError('参考数据身份已变化，不能用于该运行')
            old=read(data/'historical-reference.json')['result'];old=old.get('record',old)
            initial=read(data/'native-template.json')['initial']
            result['reference_data']={'q':old['exports']['q']['profiles'],'pressure':old['exports']['pressure_F']['profiles'],'geometry':{'axis':old['result']['geometry']['axis'],'boundary_flux':old['result']['geometry']['boundary_flux'],'contour':old['result']['geometry']['contour']},'grid':{'r':initial['r'],'z':initial['z'],'field':old['result']['field']}}
            geometry_path=ROOT/'cases/EQ-P01-94048/device-geometry.json'
            result['device_geometry']={**read(geometry_path),'limiter':read(run/'assemble.json')['config']['initial']['limiter'],'limiter_source':'run assemble.json / config.initial.limiter','geometry_sha256':sha(geometry_path)}
            solved=scientific_views.artifact(sys.modules[__name__],run,'solve')
            result['conditional_bands']=solved['result'].get('conditional_bands')
            result['diagnostic_availability']={key:{'state':'not_computed','reason':reason} for key,reason in (
                ('BNEL','本运行未保存POINT弦几何、线积分观测与密度拟合产物。'),
                ('BPOLAR','本运行未保存POINT偏振观测及同一平衡上的前向积分产物。'),
                ('density','本运行未生成密度拟合及扰动分位数；不能由压力唯一确定密度。'))}
            result['analysis_identity']={'run_id':run.name,'revision':snap['revision'],'report_sha256':sha(run/'report.json'),'reference_sha256':sha(data/'historical-reference.json')}
            return result
        if route=='artifact':
            name=query.get('name',[''])[0]
            if name not in [n['id']+'.json' for n in NODES]+['snapshot.json','native-input-identity.json','approvals.json']:raise ValueError('未知产物')
            return read(run/name)
    else:
        if route=='save':return save(body,roots)
        if route=='execute':return execute(body,root,roots)
        if route=='review':return review(body,root,roots)
        if route=='cancel':return state(runpath(body['case_id'],body['run_id'],roots),True)
    raise ValueError('未知workflow操作')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['worker']);ap.add_argument('--run',required=True);ap.add_argument('--data',required=True);ap.add_argument('--token',required=True);a=ap.parse_args();worker(Path(a.run),Path(a.data))
