'use strict';
const $=id=>document.getElementById(id),prefix='/fylite/eq/api/workflow/';let token='',caseDoc=null,runId=null,nodeId='sources',nodes=[],lastRun=null,dirty=true,pending=null,busy=false,view={},selectionPending=false,definition=null,definitionNodes=[],eventStep=null,touched=false;
let magUI={hasPreview:false,busy:false,edited:false},dataReady=false,nextBusy=false;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>typeof v==='number'?Number(v).toPrecision(6):String(v??'—');
const states={waiting_review:'待审阅',rejected:'用户退回',pending:'未开始',running:'运行中',completed:'已完成',reused:'复用上游',failed:'失败',skipped:'本计划未选',starting:'启动中',cancelled:'已取消',converged:'收敛',not_converged:'未收敛',not_assessed:'未判定'};
function error(e){$('alert').textContent=e.message||String(e)}
async function api(route,body){const r=await fetch(prefix+route,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-FyLite-Token':token},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||r.status);return d}
function query(route,extra={}){return route+'?'+new URLSearchParams({case_id:caseDoc.case_id,run_id:runId,...extra})}
function tab(id){if(id==='overview')requestAnimationFrame(()=>$('zoom-fit').click());for(const b of document.querySelectorAll('[data-tab]')){const active=b.dataset.tab===id;b.setAttribute('aria-selected',active);b.tabIndex=active?0:-1;}for(const el of document.querySelectorAll('.tab'))el.hidden=el.id!==id;for(const b of document.querySelectorAll('[data-tab]'))b.classList.toggle('active',b.dataset.tab===id)}
for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>{tab(b.dataset.tab);if(b.dataset.tab==='results')loadReport().catch(error)};
function parameters(){return{data_source:$('data_source').value,q_mode:$('q_mode').value,half_window_s:Number($('half_window_s').value),drift:$('drift').value==='true',pressure_scale:Number($('pressure_scale').value),q_target:Number($('q_target').value),max_iterations:Number($('max_iterations').value)}}
function markDirty(){document.title='* FyLite · 磁平衡工作台';dirty=true;touched=true;pending=null;updateIdentity();$('saved').textContent='未保存的修改'}
for(const id of ['data_source','q_mode','half_window_s','drift','pressure_scale','q_target','max_iterations','name'])$(id).onchange=markDirty;

// Only the fixed-pressure route can be transferred to the current 94048 executor.
function plannerTransferIssue(c) {
  if (!c || c.schema_version !== 'fylite.eq.plan-config/1') return '方案格式不受支持。';
  if (!view.selection || selectionPending) return '请先在顶部核对已加载的炮号与时间。';
  if (c.route !== 'fixed_pressure' || c.context?.device !== view.selection.device ||
      c.context?.shot !== view.selection.shot || c.context?.time_s !== view.selection.time_s)
    return '当前仅能应用已加载的 94048 固定压力路线。';
  if (c.context?.data_source !== $('data_source').value) return '方案数据来源与当前算例不同；请先在“读取与处理”中选择来源。';
  if (c.boundary !== 'free' || c.pressure?.source !== 'imported_total' ||
      c.pressure?.constraint !== 'soft' || c.pressure?.update !== 'never' ||
      c.pressure?.time_s !== 6.510 || c.outer?.mode !== 'none' ||
      !Array.isArray(c.outer?.updates) || c.outer.updates.length || c.outer.max_rounds !== 0)
    return '边界、压力或外环模式尚未接入当前执行器。';
  if (c.current?.source !== 'free_pprime_ffprime' || c.current?.update !== 'never' ||
      c.current?.residual_model !== 'fitted' || c.constraints?.q0?.weight !== 1 ||
      c.constraints?.q0?.mode !== 'target' || c.constraints?.ip !== 'measurement_soft' ||
      c.constraints?.pf !== 'prior_fitted' || c.constraints?.edge_current !== 'prior' ||
      c.constraints?.profile_basis !== 'pprime_ffprime')
    return '所选电流、q₀、Ip、PF 或边缘约束尚未接入当前执行器。';
  if (Object.values(c.profiles||{}).some(p=>p.source!=='none') ||
      ['point_bnel','point_bpolar','mse'].some(f=>c.diagnostics?.[f]?.channels?.some(x=>x.role!=='exclude')))
    return '当前工作流不会消费所选动理学剖面或内部诊断。';
  const magnetic=c.diagnostics?.magnetic?.channels;
  if (JSON.stringify(magnetic)!==JSON.stringify([{id:'FL01',role:'fit'},{id:'FL02',role:'fit'},{id:'MP35',role:'holdout'}]))
    return '示例通道的逐道改动不能应用到当前实际磁测；请在数据处理页核对真实通道。';
  if (!Array.isArray(c.reference?.roles) || c.reference.roles.some(x=>!['initial_guess','comparison'].includes(x)))
    return '所选旧平衡角色尚未接入当前执行器。';
  const target=c.constraints.q0.target,iterations=c.numerics?.max_inner_iterations;
  if (!Number.isFinite(target) || target<0.5 || target>3 ||
      !Number.isInteger(iterations) || iterations<1 || iterations>150 ||
      c.numerics?.grid_id !== '129x129' || c.numerics?.inner_tolerance!==1e-6 || c.numerics?.relaxation!==0.5)
    return 'q₀目标或内层设置超出当前工作流能力。';
  return '';
}
window.addEventListener('message', event => {
  if (event.origin !== location.origin || event.source !== $('planner-frame')?.contentWindow ||
      event.data?.type !== 'fylite:eq:apply-plan/1') return;
  const c=event.data.config,issue=plannerTransferIssue(c);
  if (issue) { $('alert').textContent='方案未应用：'+issue; return; }
  $('q_mode').value='target';$('q_target').value=String(c.constraints.q0.target);
  $('max_iterations').value=String(c.numerics.max_inner_iterations);$('pressure_scale').value='1';
  markDirty();tab('inputs');$('alert').textContent='固定压力方案已写入当前草稿（q₀、压力倍率和内层迭代上限）。请核对真实磁测输入并保存修订后计算；其他示例通道没有传入求解器。';
});

function showCase(c){document.title='FyLite · 磁平衡工作台';caseDoc=c;$('data_source').value=c.parameters.data_source||'frozen';$('q_mode').value=c.parameters.q_mode||'target';for(const[k,v]of Object.entries(c.parameters))$(k).value=String(v);$('name').value=c.name;dirty=false;touched=false;$('saved').textContent='已保存修订 '+c.revision;$('directory').textContent='个人目录：'+c.directory;pending=null;clearRun();window.dispatchEvent(new Event('fylite-case-changed'))}
function clearRun(){$('review-banner').hidden=true;runId=null;lastRun=null;eventStep=null;syncGraph();renderProgress();renderStepRuntime();updateIdentity();clearResult();$('node-content').replaceChildren();$('events').replaceChildren();$('logs').textContent='';$('run-summary').textContent='';renderNodes()}
function clearResult(){if($('analysis-panel'))$('analysis-panel').replaceChildren();for(const id of ['metrics','diagnostics','pf','comparison','download'])$(id).replaceChildren();$('result-identity').textContent=runId?'当前运行 '+runId+'：尚未读取结果。':'请选择一次运行。'}
async function cases(){const d=await api('cases'),select=$('cases');select.replaceChildren(new Option('新建个人算例',''));for(const c of d.cases)select.add(new Option(c.name+' · r'+c.revision,c.case_id));select.value=caseDoc?.case_id||''}
async function save(fork=false){requireSelection();const body={name:$('name').value,parameters:parameters()};if(caseDoc&&fork)Object.assign(body,{source_case_id:caseDoc.case_id,source_revision:caseDoc.revision});if(caseDoc&&!fork)Object.assign(body,{case_id:caseDoc.case_id,base_revision:caseDoc.revision});const c=await api('save',body);showCase(c);await cases();await runs();$('alert').textContent=''}
$('save').onclick=()=>save().catch(error);$('fork').onclick=()=>save(true).catch(error);
function confirmDiscard(){return !(touched||magUI.edited||magUI.hasPreview||selectionPending)||window.confirm('当前草稿或处理预览尚未保存，确定放弃修改并切换算例？')}
function beginNew(){caseDoc=null;dirty=true;touched=false;$('name').value=view.name||'个人算例';for(const [key,value] of Object.entries(definition?.defaults||{}))if($(key))$(key).value=String(value);clearRun();$('cases').value='';$('saved').textContent='新建个人算例';$('runs').replaceChildren();$('directory').textContent='';window.dispatchEvent(new Event('fylite-case-changed'))}
$('new').onclick=()=>{if(confirmDiscard())beginNew()};
$('cases').onchange=async()=>{const selected=$('cases').value;if(!confirmDiscard()){$('cases').value=caseDoc?.case_id||'';return}try{if(!selected){beginNew();return}showCase(await api('case?'+new URLSearchParams({case_id:selected})));await runs()}catch(e){$('cases').value=caseDoc?.case_id||'';error(e)}};
function table(headers,rows){return '<table><thead><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(v=>'<td>'+esc(fmt(v))+'</td>').join('')+'</tr>').join('')+'</tbody></table>'}
function renderNodes(){renderFlow();updateHelp();const box=$('nodes'),opened=new Set([...box.querySelectorAll('details[open]')].map(x=>x.dataset.group));const fresh=!box.children.length,current=lastRun?.status.active_step||nodeId,currentGroup=nodes.find(n=>n.id===current)?.group||nodes[0]?.group;box.replaceChildren();for(const group of [...new Set(nodes.map(n=>n.group||'steps'))]){const branch=document.createElement('details');branch.dataset.group=group;branch.open=opened.has(group)||(fresh&&group===currentGroup);const summary=document.createElement('summary');summary.textContent=(graphDefinition()?.groups||[]).find(g=>g.id===group)?.title||group;branch.append(summary);for(const n of nodes.filter(n=>(n.group||'steps')===group)){const st=lastRun?.status.steps[n.id]?.state||'pending',b=document.createElement('button');b.className='node '+st+(nodeId===n.id?' active':'')+(lastRun?.status.active_step===n.id?' next-node':'');if(lastRun?.status.active_step===n.id)b.setAttribute('aria-current','step');b.innerHTML='<span class="tree-icon">▧</span>'+esc(title(n.id))+'<span class="tree-state">'+(lastRun?esc(states[st]||st):'流程节点')+'</span>';b.onclick=()=>openNode(n.id);branch.append(b)}box.append(branch)}}
function openNode(id){if(['sources','magnetics'].includes(id)){nodeId=id;renderNodes();tab('magnetic-task');document.querySelector('[data-tab=magnetic-task]').click();return;}document.body.classList.remove('inspector-hidden');nodeId=id;eventStep=id;renderEvents();renderStepRuntime();renderNodes();tab('process');loadNode().catch(error)}
async function runs(){if(!caseDoc)return;const d=await api('runs?'+new URLSearchParams({case_id:caseDoc.case_id}));$('runs').replaceChildren();for(const r of d.runs){const b=document.createElement('button');b.className='run '+r.status.state;b.innerHTML=esc(r.run_id)+'<span class="state">修订 '+r.status.revision+' · '+esc(states[r.status.state]||r.status.state)+' · 到 '+esc(title(r.target))+'</span>';b.onclick=()=>selectRun(r.run_id);$('runs').append(b)}}
async function selectRun(id){$('graph-mode').value='run';eventStep=null;runId=id;lastRun=null;clearResult();$('node-content').replaceChildren();try{await status();await loadNode();if(!$('results').hidden)await loadReport()}catch(e){error(e)}}
async function status(){if(!caseDoc||!runId)return;const id=runId,cid=caseDoc.case_id;const d=await api(query('run'));if(id!==runId||cid!==caseDoc.case_id)return;lastRun=d;renderReviewBanner();syncGraph();renderNodes();renderProgress();renderStepRuntime();renderEvents();$('run-summary').textContent=id+' · r'+d.snapshot.revision+' · '+(states[d.status.state]||d.status.state)+' · 数值：'+(states[d.status.numerical]||d.status.numerical)+(d.status.error?' · '+d.status.error:'');$('logs').textContent=d.stdout+'\n'+d.stderr;renderUX();return d}
async function execute(target){requireSelection();if(!caseDoc||dirty)throw Error('请先保存当前输入修订。');if(busy)return;busy=true;try{const plan={case_id:caseDoc.case_id,revision:caseDoc.revision,target};if(!pending||JSON.stringify(pending.plan)!==JSON.stringify(plan))pending={plan,request_id:crypto.randomUUID()};const d=await api('execute',{...plan,request_id:pending.request_id});pending=null;tab('process');await selectRun(d.run_id);await runs();$('alert').textContent=''}finally{busy=false}}
$('execute').onclick=async()=>{try{requireSelection();if(caseDoc){const history=await api('runs?'+new URLSearchParams({case_id:caseDoc.case_id}));const existing=history.runs.find(r=>['starting','running','waiting_review'].includes(r.status.state));if(existing){await selectRun(existing.run_id);nodeId=lastRun.status.active_step||'sources';tab('process');await loadNode();$('alert').textContent='已打开现有任务，请继续检查或停止；未启动重复计算。';return;}}if(!caseDoc?.processing){tab('magnetic-task');document.querySelector('[data-tab=magnetic-task]').click();throw Error('请先完成：读取数据 → 生成处理预览 → 采纳为输入。此按钮不会替你重新取数。');}if(dirty)await save();if(!caseDoc.processing)throw Error('磁数据来源已改变，请重新预览并采纳。');await execute(definition?.terminal||'report');}catch(e){error(e)}};$('step').onclick=()=>execute(nodeId).catch(error);$('refresh').onclick=async()=>{try{await runs();await status();await loadNode();if(!$('results').hidden)await loadReport()}catch(e){error(e)}};
$('cancel').onclick=async()=>{if(!runId)return;try{await api('cancel',{case_id:caseDoc.case_id,run_id:runId});await status();await runs()}catch(e){error(e)}};
async function artifact(name){return api(query('artifact',{name:name+'.json'}))}
function line(canvas,series,xlabel,ylabel,bounds=series){const c=typeof canvas==='string'?$(canvas):canvas,g=c.getContext('2d');g.clearRect(0,0,c.width,c.height);const vals=bounds.flatMap(s=>s.points).filter(p=>p.every(Number.isFinite));if(!vals.length)return;let xmin=Math.min(...vals.map(p=>p[0])),xmax=Math.max(...vals.map(p=>p[0])),ymin=Math.min(...vals.map(p=>p[1])),ymax=Math.max(...vals.map(p=>p[1]));if(xmin===xmax)xmax=xmin+1;if(ymin===ymax)ymax=ymin+1;const X=x=>65+(x-xmin)/(xmax-xmin)*(c.width-90),Y=y=>c.height-45-(y-ymin)/(ymax-ymin)*(c.height-85);g.font='13px sans-serif';g.strokeStyle='#9db1bc';g.strokeRect(65,40,c.width-90,c.height-85);g.fillStyle='#344f5d';g.fillText(ylabel,8,20);g.fillText(xlabel,c.width/2,c.height-8);g.fillText(ymax.toPrecision(4),2,48);g.fillText(ymin.toPrecision(4),2,c.height-44);g.fillText(xmin.toPrecision(4),65,c.height-25);g.fillText(xmax.toPrecision(4),c.width-75,c.height-25);series.forEach((s,i)=>{g.strokeStyle=s.color;g.fillStyle=s.color;g.lineWidth=1.6;g.beginPath();s.points.forEach(([x,y],j)=>{if(!Number.isFinite(x)||!Number.isFinite(y))return;if(s.dots){g.moveTo(X(x)+2,Y(y));g.arc(X(x),Y(y),2,0,2*Math.PI)}else j?g.lineTo(X(x),Y(y)):g.moveTo(X(x),Y(y))});g.stroke();g.fillText(s.label,90+i*180,30)})}
async function loadNode(){$('step').hidden=true;const selected=nodeId,id=runId;$('node-title').textContent=title(nodeId);updateHelp();updateIdentity();$('node-content').replaceChildren();if(nodeId==='pressure'){await FyScientificTasks.pressure($('node-content'));return;}if(!runId){$('node-content').textContent='此处用于查看运行产物。请先进入“① 读取与处理”，然后配置约束并点击顶部“下一步”。';return}const st=lastRun?.status.steps[nodeId]?.state;if(st==='waiting_review'){await showReview();return}if(!['completed','reused'].includes(st)){$('node-content').textContent=st==='running'?'此步骤正在执行。内部迭代将在原生调用结束后提供。':'此步骤尚未生成数据。请按“读取与处理 → 约束配置 → 检查并计算”的顺序操作。';return}const d=await artifact(nodeId);if(id!==runId||selected!==nodeId)return;const box=$('node-content');
if(nodeId==='magnetics'){box.innerHTML='<div class="row"><label>查看通道<select id="channel"></select></label><label>对照方式<select id="wave-mode"><option value="split">左右对照</option><option value="overlay">叠加对照</option></select></label></div><div class="plots"><figure><canvas id="wave" width="600" height="320"></canvas><figcaption>原始信号（单位已换算）</figcaption></figure><figure id="processed-panel"><canvas id="processed-wave" width="600" height="320"></canvas><figcaption>处理后信号</figcaption></figure></div><p>左右图使用同一纵轴范围；未启用漂移修正时，两条曲线可能相同。</p><div id="channel-info"></div>';for(const a of d.audit)$('channel').add(new Option(a.node,a.node));const plot=()=>{const a=d.audit.find(x=>x.node===$('channel').value);const raw={label:'原始',color:'#a7613b',points:a.t.map((t,i)=>[t,a.raw[i]])},processed={label:'处理后',color:'#147a86',points:a.t.map((t,i)=>[t,a.processed[i]])},split=$('wave-mode').value==='split';$('processed-panel').hidden=!split;const both=[raw,processed];line('wave',split?[raw]:both,'时间 s','信号',both);if(split)line('processed-wave',[processed],'时间 s','信号',both);$('channel-info').innerHTML=table(['通道','样本数','换算系数','处理后均值'],[[a.node,a.samples,a.scale,a.reduced]])};$('channel').onchange=$('wave-mode').onchange=plot;plot();}
else if(nodeId==='pressure'){box.innerHTML='<p>来源时刻 6.510 s；51 点固定压力，未重跑 ONETWO。</p><canvas id="pinput" width="850" height="320"></canvas>';line('pinput',[{label:'提取压力',color:'#147a86',points:d.psi_n.map((x,i)=>[x,d.pressure_Pa[i]/1000]),dots:true}],'ψN','压力 kPa')}
else if(nodeId==='quality'){box.innerHTML='<p>'+esc(d.warnings.join('；'))+'</p>'+table(['通道','样本','起始s','结束s','恒定'],d.channels.map(x=>[x.node,x.samples,x.first_s,x.last_s,x.constant]));}
else if(nodeId==='constraints'){box.innerHTML=table(['约束类别','内容'],Object.entries(d).map(([k,v])=>[k,typeof v==='object'?JSON.stringify(v):v]));}
else if(nodeId==='assemble'){box.innerHTML=table(['生效项目','值'],Object.entries(d.effective));const compareHost=document.createElement('section');box.append(compareHost);await FyScientificTasks.comparison(compareHost);}
else if(nodeId==='sources'){box.innerHTML='<p>'+esc(JSON.stringify(d.acquisition||{}))+'</p><p>'+esc(d.dataset)+' · '+esc(d.manifest_sha256)+'</p><ul>'+d.limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>'+table(['数据','SHA256'],Object.entries(d.sources).map(([k,v])=>[k,v.sha256]));}
else if(nodeId==='solve'){box.innerHTML=table(['项目','实际值'],[['收敛',d.converged],['迭代',d.result.iteration],['误差',d.result.error],['Ip A',d.result.ip]]);}
else{box.innerHTML='<p>结果检查已完成。请进入“结果分析”查看。</p>';}
const detail=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='查看结构化产物';pre.textContent=JSON.stringify(d,null,2).slice(0,18000);detail.append(summary,pre);box.append(detail);const a=document.createElement('a');a.href=prefix+query('artifact',{name:nodeId+'.json'});a.textContent='下载此节点完整产物';a.download=nodeId+'.json';box.append(a);}
async function loadReport(){clearResult();if(!runId||!['completed','reused'].includes(lastRun?.status.steps.report?.state)){$('result-identity').textContent=runId+'：尚无结果检查产物，请完成读取、处理和输入检查后生成分析结果。';return}const id=runId,d=await api(query('analysis'));if(id!==runId)return;renderAnalysis(d,$('analysis-panel'));const compareHost=document.createElement('section');compareHost.className='run-comparator';$('analysis-panel').append(compareHost);FyScientificTasks.comparison(compareHost).catch(error);$('result-identity').textContent=id+' · 输入修订 '+lastRun.snapshot.revision+'；当前草稿修订 '+caseDoc.revision+'。实验资格未通过验收。';$('metrics').innerHTML=Object.entries(d.summary).map(([k,v])=>'<span class="metric">'+esc(k)+'<br><strong>'+esc(fmt(v))+'</strong></span>').join('');$('diagnostics').innerHTML=table(['类型','槽位','使用','观测','预测','残差','加权残差'],d.diagnostics.map(x=>[x.kind,x.index,x.used_in_fit,x.observed,x.predicted,x.predicted-x.observed,x.weighted_residual]));$('pf').innerHTML=table(['PF槽','观测','拟合','变化'],d.pf.observed.map((v,i)=>[i+1,v,d.pf.fitted[i],d.pf.fitted[i]-v]));$('comparison').innerHTML='<p>'+esc(d.reference.same_recipe?'相同默认配方，与旧版历史结果比较；不作为独立实验真值。':'参数已变化，历史参考不是同条件验收目标。')+'</p>'+table(['指标','值'],Object.entries(d.reference));$('download').innerHTML=['report','solve','assemble','snapshot','native-input-identity'].map(n=>'<a download="'+n+'.json" href="'+esc(prefix+query('artifact',{name:n+'.json'}))+'">'+esc(n)+'.json</a>').join(' · ')}
(async()=>{try{const r=await fetch('/fylite/eq/api/info');token=(await r.json()).token;const d=await api('info');dataReady=d.dataset_ready;definition=d.definition||{nodes:d.nodes};definitionNodes=definition.nodes;nodes=definitionNodes;const catalog=await fetch('ui/workflows.json?v=pipeline11').then(r=>{if(!r.ok)throw Error('算例界面配置读取失败');return r.json()});view=catalog[d.workflow_id]||{};resetSelection();$('case-context').textContent=view.context||d.title;$('case-route').textContent=view.route||'';$('name').value=view.name||'个人算例';$('case-guide').href=view.guide||'index.html';$('recipe-warning').textContent=view.warning||'';$('recipe-intro').textContent=view.intro||'';$('recipe-fixed').textContent=view.fixed||'';renderNodes();renderProgress();tab('planner');$('readiness').textContent=d.dataset_ready?'数据包已检查 · 原生求解 · direct':'数据未就绪：'+d.reason;$('execute').disabled=$('step').disabled=!d.dataset_ready;$('limits').innerHTML=d.limits.map(x=>'<li>'+esc(x)+'</li>').join('');await cases();renderUX()}catch(e){error(e)}})();
let polling=false;setInterval(async()=>{if(polling||!runId||!lastRun||!['starting','running'].includes(lastRun.status.state))return;polling=true;try{const prev=lastRun.status.state;await status();if(prev!==lastRun.status.state){await runs();await loadNode();if(!$('results').hidden)await loadReport()}}catch(e){error(e)}finally{polling=false}},2000);

function title(id){return nodes.find(n=>n.id===id)?.title||id}
function updateIdentity(){renderUX();if(!$('artifact-identity'))return;$('artifact-identity').textContent=runId?'正在查看 '+runId+' · 输入修订 '+(lastRun?.snapshot.revision??'读取中')+(dirty?'；草稿已修改，这些数据尚未随草稿更新。':caseDoc&&lastRun&&caseDoc.revision!==lastRun.snapshot.revision?'；与当前保存修订不同。':''):'尚未选择运行；处理后数据将在执行后生成。'}
function updateHelp(){const n=nodes.find(x=>x.id===nodeId),m=n?.ui||view.steps?.[nodeId];if(!n)return;$('step').textContent=m?.action||n.title;$('step-plan').textContent=n.deps.length?'自动准备：'+n.deps.map(title).join('、')+'。完成本步骤后停止；匹配的上游结果可以复用。':'检查数据来源与完整性，完成后停止。';$('step-help').innerHTML='<h3>'+esc(n.title)+'</h3>'+[['直接输入',n.deps.length?n.deps.map(title).join('、'):'无上游步骤'],['做什么',m?.purpose],['使用什么',m?.inputs],['完成后看什么',m?.check]].map(([k,v])=>'<p><strong>'+k+'</strong><br>'+esc(v||'参见算例说明')+'</p>').join('')}
let graphScale=1;
function renderFlow(){FyWorkflowGraph.render($('flowchart'),{nodes,selected:document.body.classList.contains('inspector-hidden')?null:nodeId,state:id=>$('graph-mode').value==='definition'?'configured':nodeState(id),status:graphStatus,title,showAll:$('all-dependencies').checked,scale:graphScale,note:$('dependency-note'),select:id=>{nodeId=id;document.body.classList.remove('inspector-hidden');updateHelp();updateIdentity();eventStep=id;renderEvents();renderStepRuntime();renderFlow()},open:openNode})}
function graphStatus(id){if($('graph-mode').value==='definition')return '◇ 配置节点';const st=nodeState(id);return ({completed:'✓',reused:'↻',running:'◉',failed:'×',cancelled:'■',skipped:'—',waiting_review:'?',rejected:'×'}[st]||'○')+' '+(states[st]||st)+nodeElapsed(id)}
$('zoom-in').onclick=()=>{graphScale=Math.min(1.8,graphScale+.15);renderFlow()};$('zoom-out').onclick=()=>{graphScale=Math.max(.8,graphScale-.15);renderFlow()};$('zoom-fit').onclick=()=>{const surface=$('flowchart').firstElementChild;if(surface){graphScale=Math.min(1,Math.max(.8,Math.min(($('flowchart').clientWidth-20)/parseFloat(surface.style.width),($('flowchart').clientHeight-20)/parseFloat(surface.style.height))));renderFlow()}};
for(const b of document.querySelectorAll('[data-command]'))b.onclick=()=>{$(b.dataset.command).click();b.closest('details').open=false};for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>{tab(b.dataset.view);if(b.dataset.view==='results')loadReport().catch(error);b.closest('details').open=false};
function consoleVisible(show){document.body.classList.toggle('console-hidden',!show)}
$('toggle-console').onclick=()=>consoleVisible(document.body.classList.contains('console-hidden'));$('collapse-console').onclick=()=>consoleVisible(false);
$('show-events').onclick=()=>{$('events').hidden=false;$('logs').hidden=true;$('show-events').classList.add('active');$('show-logs').classList.remove('active')};$('show-logs').onclick=()=>{$('events').hidden=true;$('logs').hidden=false;$('show-logs').classList.add('active');$('show-events').classList.remove('active')};
$('help-guide').onclick=()=>{location.href=$('case-guide').href};
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();save().catch(error)}});
$('open-flow').onclick=()=>tab('overview');$('open-settings').onclick=()=>tab('inputs');

function resetSelection(){const s=view.selection;if(!s)return;$('device').value=s.device;$('shot').value=s.shot;$('target-time').value=s.time_s.toFixed(3);selectionPending=false;$('shot-entry').classList.remove('pending');$('selection-status').textContent='已加载：'+s.device+' / '+s.shot+' / '+s.time_s.toFixed(3)+' s；来源见“① 读取与处理”，执行读取后生效。'}
function requireSelection(){if(selectionPending)throw Error('炮号或时间尚未匹配已加载数据。请先检查数据，或恢复已加载值。')}
for(const id of ['device','shot','target-time'])$(id).addEventListener('input',()=>{selectionPending=true;$('shot-entry').classList.add('pending');$('selection-status').textContent='输入已更改，尚未加载；当前图表仍属于原算例。'});
$('reset-selection').onclick=()=>{resetSelection();$('alert').textContent=''};
$('shot-entry').onsubmit=e=>{e.preventDefault();const s=view.selection,shot=Number($('shot').value),time=Number($('target-time').value);if(!s)return;if(!Number.isInteger(shot)||shot<1||!Number.isFinite(time)||time<0){error(Error('请输入有效整数炮号和非负时间（秒）。'));return}if($('device').value!==s.device||shot!==s.shot||Math.abs(time-s.time_s)>1e-9){selectionPending=true;$('shot-entry').classList.add('pending');$('selection-status').textContent='未接入该炮号/时间；尚未加载新数据。';error(Error('当前仅提供 '+s.device+' '+s.shot+'、'+s.time_s.toFixed(3)+' s 的冻结磁测数据。其他炮号或时间需要接入取数与处理流程；不会使用原数据替代。'));return}resetSelection();$('alert').textContent='';};

function graphDefinition(){return $('graph-mode').value==='run'&&lastRun?(lastRun.snapshot.workflow_definition||{nodes:lastRun.snapshot.plan,groups:definition?.groups}):definition}
function syncGraph(){nodes=graphDefinition()?.nodes||definitionNodes;if(!nodes.some(n=>n.id===nodeId))nodeId=nodes[0]?.id||'sources'}
function nodeState(id){return $('graph-mode').value==='run'?(lastRun?.status.steps[id]?.state||'pending'):'pending'}
function duration(step){if(!step?.started_at)return '';const end=step.ended_at||(['completed','failed','cancelled'].includes(lastRun?.status.state)?lastRun.status.ended_at:Date.now()/1000);return Math.max(0,(end||Date.now()/1000)-step.started_at).toFixed(1)+' s'}
function nodeElapsed(id){return $('graph-mode').value==='run'&&duration(lastRun?.status.steps[id])?' · '+duration(lastRun.status.steps[id]):''}
function renderProgress(){const box=$('graph-progress');if($('graph-mode').value!=='run'){box.textContent='定义版本 '+(definition?.version||'—')+' · '+(definition?.title||'')+' · 仅显示依赖，不表示运行状态';return}if(!lastRun){box.textContent='请从运行记录中选择一次运行。';return}const steps=Object.values(lastRun.status.steps),planned=steps.filter(s=>s.state!=='skipped'),done=planned.filter(s=>['completed','reused'].includes(s.state)),active=lastRun.status.active_step;box.textContent=runId+' · 输入修订 '+lastRun.snapshot.revision+' · 已完成 '+done.length+'/'+planned.length+' 步 · '+(states[lastRun.status.state]||lastRun.status.state)+(active?' · '+title(active)+nodeElapsed(active):'')+(lastRun.snapshot.workflow_definition?' · 冻结流程 v'+lastRun.snapshot.workflow_definition.version:' · 旧记录：仅含执行计划')+'；步骤数不代表耗时百分比';}
function renderStepRuntime(){const box=$('step-runtime');box.replaceChildren();if($('graph-mode').value!=='run'||!lastRun)return;const s=lastRun.status.steps[nodeId];if(!s)return;box.innerHTML=table(['执行属性','值'],[['状态',states[s.state]||s.state],['开始',s.started_at?new Date(s.started_at*1000).toLocaleString():'—'],['耗时',duration(s)||'—'],['复用来源',s.reused_from||'—'],['错误',s.error||'—']]);}
function renderEvents(){if(!$('event-filter-label'))return;$('event-filter-label').textContent=eventStep?'步骤：'+title(eventStep):'全部步骤';$('events').innerHTML=table(['步骤','状态','时间'],(lastRun?.events||[]).filter(e=>!eventStep||e.step===eventStep).map(e=>[title(e.step),states[e.state]||e.state,new Date(e.time*1000).toLocaleTimeString()]));}
$('graph-mode').onchange=()=>{syncGraph();renderNodes();renderProgress();renderStepRuntime()};$('all-events').onclick=()=>{eventStep=null;renderEvents()};
setInterval(()=>{if(lastRun&&['running','starting'].includes(lastRun.status.state)){renderProgress();renderStepRuntime();for(const b of document.querySelectorAll('.flow-node')){const n=nodes.find(n=>b.dataset.nodeId===n.id);if(n)b.querySelector('small').textContent=graphStatus(n.id)}}},1000);

$('all-dependencies').onchange=renderFlow;
$('close-inspector').onclick=()=>{document.body.classList.add('inspector-hidden');renderFlow()};
$('footer-console').onclick=()=>consoleVisible(document.body.classList.contains('console-hidden'));
const workspaceTabs=[...document.querySelectorAll('[data-tab]')];
workspaceTabs[0].parentElement.setAttribute('role','tablist');
workspaceTabs.forEach((button,index)=>{button.id='tab-'+button.dataset.tab;button.setAttribute('role','tab');button.setAttribute('aria-controls',button.dataset.tab);const panel=$(button.dataset.tab);panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);button.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%workspaceTabs.length;if(event.key==='ArrowLeft')next=(index+workspaceTabs.length-1)%workspaceTabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=workspaceTabs.length-1;if(next!==undefined){event.preventDefault();workspaceTabs[next].focus();workspaceTabs[next].click()}})});
document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('.more-menu[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus()})});

function renderReviewBanner(){
 const banner=$('review-banner');banner.hidden=lastRun?.status.state!=='waiting_review';
 if(banner.hidden)return;
 banner.replaceChildren();const text=document.createElement('span');text.textContent='流程已暂停：'+title(lastRun.status.active_step)+'。请查看数据和限制，填写结论后继续。';
 const button=document.createElement('button');button.textContent='打开确认步骤';button.onclick=()=>openNode(lastRun.status.active_step);banner.append(text,button);
}
async function showReview(){
 $('step').hidden=true;const captured=runId,selected=nodeId,d=await artifact(nodeId);if(captured!==runId||selected!==nodeId)return;
 const box=$('node-content');box.innerHTML='<h3>需要你的检查结论</h3><p>'+esc(d.meaning)+'</p><ul>'+d.warnings.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>';
 const links=document.createElement('div');links.className='row';
 for(const key of Object.keys(d.artifacts)){const button=document.createElement('button');button.textContent='查看：'+title(key);button.onclick=()=>openNode(key);links.append(button)}
 box.append(links);
 const label=document.createElement('label');label.textContent='检查结论 / 退回原因（必填）';const note=document.createElement('textarea');note.id='review-note';note.rows=3;note.maxLength=2000;label.append(note);box.append(label);
 const checked=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.id='review-checked';check.style.width='auto';checked.append(check,document.createTextNode('我已检查上述数据、约束和时间差；此次确认不代表实验有效性认证。'));box.append(checked);
 const accept=document.createElement('button'),reject=document.createElement('button');accept.textContent='确认并继续';reject.textContent='退回，修改后重新运行';accept.id='approve-review';reject.id='reject-review';
 const decide=async approved=>{if(dirty||selectionPending)throw Error('草稿已变化，请保存新修订后重新运行。');if(!note.value.trim())throw Error('请填写检查结论或退回原因。');if(approved&&!check.checked)throw Error('请先勾选确认已检查。');accept.disabled=reject.disabled=true;try{await api('review',{case_id:caseDoc.case_id,run_id:captured,identity:d.identity,approved,note:note.value});await status();await loadNode();await runs()}finally{accept.disabled=reject.disabled=false}};
 accept.onclick=()=>decide(true).catch(error);reject.onclick=()=>decide(false).catch(error);box.append(accept,reject);
 const identity=document.createElement('p');identity.className='muted';identity.textContent='绑定运行 '+d.run_id+' / 修订 '+d.revision+' / 输入身份 '+d.identity;box.append(identity);
}

// Derived presentation state only; execution and review contracts stay unchanged.
function renderUX(){
 const state=lastRun?.status.state,running=['running','starting'].includes(state),waiting=state==='waiting_review';
 const sourceRun=lastRun?.snapshot.target==='sources',runStage=sourceRun?'准备 2/4':'计算 4/4';
 let label='未保存',kind='draft';
 if(running||waiting){label=states[state];kind=waiting?'review':'busy'}
 else if(!caseDoc||dirty){}
 else if(state==='completed'&&lastRun?.snapshot.target===definition?.terminal&&lastRun?.snapshot.revision===caseDoc.revision){label='已完成';kind='adopted'}
 else if(['failed','rejected','cancelled'].includes(state)){label=states[state];kind='review'}
 else{label='已保存';kind='idle'}
 $('case-state').textContent='● '+label;$('case-state').dataset.state=kind;
 let action='save',text='下一步：保存修订（准备 1/4）';
 if(running){action='busy';text='正在执行…（'+runStage+'）'}
 else if(waiting){action='review';text='下一步：查看待审阅内容（'+runStage+'）'}
 else if(!caseDoc||dirty){}
 else if(['failed','rejected','cancelled'].includes(state)){action='details';text='查看运行详情'}
 else if(magUI.hasPreview){action='adopt';text='下一步：采纳为修订（准备 3/4）'}
 else if(caseDoc.processing&&!magUI.edited){if(state==='completed'&&lastRun?.snapshot.target===definition?.terminal&&lastRun?.snapshot.revision===caseDoc.revision){action='results';text='查看本次结果'}else{action='run';text='下一步：运行到首个确认点（计算 4/4）'}}
 else if(!$('mp-dataset').value){action='read';text='下一步：读取数据（准备 2/4）'}
 else {action='preview';text='下一步：生成处理预览（准备 2/4）'}
 $('next').textContent=text;$('next').dataset.action=action;
 $('next').disabled=running||magUI.busy||nextBusy||!dataReady;
 const reason=!dataReady?'数据未就绪':running||waiting?'有运行未结束':!caseDoc||dirty?'草稿未保存':magUI.busy?'正在处理数据':!caseDoc.processing||magUI.edited||magUI.hasPreview?'请先采纳处理预览':'';
 $('execute').disabled=Boolean(reason);$('cancel').hidden=!running;
 $('readiness').textContent=reason?'计算不可用：'+reason:'数据已就绪 · 已采纳输入 · direct';
 $('mp-adopt-hint').hidden=!$('mp-adopt').disabled;
 $('stale-results').hidden=!(dirty&&runId);
 const phase=action==='adopt'?'adopt':['run','review','busy','results','details'].includes(action)&&!sourceRun?'run':'read';
 for(const button of document.querySelectorAll('#quick-guide [data-guide]')){if(button.dataset.guide===phase)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current')}
}
for(const button of document.querySelectorAll('#quick-guide [data-guide]'))button.onclick=()=>{const stage=button.dataset.guide;if(stage==='run'){tab(lastRun?.status.state==='completed'?'results':runId?'process':'inputs');if(lastRun?.status.state==='completed')loadReport().catch(error)}else{tab('magnetic-task');if(stage==='adopt')$('mp-adopt-panel').scrollIntoView({block:'start',behavior:'smooth'})}};
$('guide-dismiss').onclick=()=>{$('quick-guide').hidden=true;sessionStorage.setItem('fylite-guide-dismissed-v1','1')};
if(sessionStorage.getItem('fylite-guide-dismissed-v1')==='1')$('quick-guide').hidden=true;
window.addEventListener('fylite-mag-state',event=>{magUI=event.detail;renderUX()});
window.addEventListener('fylite-case-changed',()=>{magUI={hasPreview:false,busy:false,edited:false};renderUX()});
$('mp-preview-link').onclick=()=>{tab('magnetic-task');$('mp-preview').focus();$('mp-preview').click()};
$('next').onclick=async()=>{
 if(nextBusy)return;const action=$('next').dataset.action;nextBusy=true;renderUX();
 try{
  if(action==='save')await save();
  else if(action==='review'){nodeId=lastRun.status.active_step;tab('process');await loadNode();}
  else if(action==='run')await execute(definition.terminal);
  else if(action==='results'){tab('results');await loadReport()}
  else if(action==='details'){tab('process');await loadNode()}
  else if(['read','preview','adopt'].includes(action)){tab('magnetic-task');if(action==='adopt'&&!$('mp-note').value.trim()){$('mp-note').focus();$('mp-status').textContent='请填写检查结论，再采纳当前预览。';}else $('mp-'+action).click();}
 }catch(e){error(e)}finally{nextBusy=false;renderUX()}
};
renderUX();
