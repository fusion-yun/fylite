/* Read-only scientific task views; no hidden execution or adoption. */
'use strict';
window.FyScientificTasks=(()=>{
 let serial=0;
 const element=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e};
 function plot(host,sets,xlabel,ylabel,errors=[],zero=true){
  const points=sets.flatMap(s=>s.points),all=points.concat(errors.flatMap(p=>[[p[0],p[1]-p[2]],[p[0],p[1]+p[2]]]));
  if(!all.length){host.textContent='无图表数据';return;}
  const x0=Math.min(...all.map(p=>p[0])),x1=Math.max(...all.map(p=>p[0]));let y0=Math.min(...all.map(p=>p[1]),...(zero?[0]:[])),y1=Math.max(...all.map(p=>p[1]));if(y1===y0)y1=y0+1;
  const X=x=>80+(x-x0)/(x1-x0||1)*790,Y=y=>310-(y-y0)/(y1-y0)*250;
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.style.width='100%';svg.style.height='auto';svg.setAttribute('viewBox','0 0 900 370');svg.setAttribute('role','img');svg.setAttribute('aria-label',xlabel+' / '+ylabel+'，具体数值见数据表');
  let markup='<rect width="900" height="370" fill="white"/>';
  for(let i=0;i<=5;i++){const x=x0+(x1-x0)*i/5,y=y0+(y1-y0)*i/5;markup+='<path d="M'+X(x)+' 60V310M80 '+Y(y)+'H870" stroke="#dce3e8"/><text x="'+(X(x)-14)+'" y="333">'+esc(x.toPrecision(6))+'</text><text x="4" y="'+(Y(y)+4)+'">'+esc(y.toPrecision(3))+'</text>';}
  markup+='<text x="4" y="18">'+esc(ylabel)+'</text><text x="425" y="362">'+esc(xlabel)+'</text>';
  sets.forEach((s,i)=>{markup+='<text x="'+(85+i*230)+'" y="40" fill="'+s.color+'">'+esc(s.label)+'</text><polyline fill="none" stroke="'+s.color+'" stroke-width="2" points="'+s.points.map(p=>X(p[0])+','+Y(p[1])).join(' ')+'"/>';});
  for(const [x,y,e] of errors)markup+='<path stroke="#64748b" d="M'+X(x)+' '+Y(y-e)+'V'+Y(y+e)+'M'+(X(x)-3)+' '+Y(y-e)+'h6M'+(X(x)-3)+' '+Y(y+e)+'h6"/>';
  svg.innerHTML=markup;host.replaceChildren(svg);
 }
 async function pressure(host){
  const ticket=++serial,cid=caseDoc?.case_id,rid=runId;host.textContent='读取固定压力来源…';
  const response=await api('pressure-preview?scale='+encodeURIComponent(parameters().pressure_scale));
  let previous=null;
  if(rid&&['completed','reused'].includes(lastRun?.status.steps.pressure?.state))previous=await artifact('pressure');
  if(ticket!==serial||cid!==caseDoc?.case_id||rid!==runId||nodeId!=='pressure')return;
  host.replaceChildren();const note=element('p','固定压力来自ONETWO final，未重跑ONETWO。压力 '+response.pressure.time_s+' s；磁测 '+response.magnetic_time_s+' s。误差棒来自历史配方，不是新测量误差。');
  const label=element('label','压力倍率（草稿） '),scale=element('input');scale.type='number';scale.min='.5';scale.max='1.5';scale.step='.05';scale.value=$('pressure_scale').value;label.append(scale);
  const preview=element('button','更新曲线预览'),apply=element('button','将倍率写入配置草稿'),status=element('p',response.meaning),chart=element('div'),details=element('details'),summary=element('summary','压力点、误差与拟合权重'),values=element('div');details.append(summary,values);
  host.append(note,label,preview,apply,status,chart,details);let shown=response.pressure,displayedScale=Number(scale.value),request=0;
  function draw(){plot(chart,[{label:'草稿倍率 '+displayedScale,color:'#147a86',points:shown.psi_n.map((x,i)=>[x,shown.pressure_Pa[i]/1000])},...(previous?[{label:'所选运行 '+rid,color:'#aa5361',points:previous.psi_n.map((x,i)=>[x,previous.pressure_Pa[i]/1000])}]:[])],'ψN','压力 / kPa',shown.psi_n.map((x,i)=>[x,shown.pressure_Pa[i]/1000,shown.sigma_Pa[i]/1000]));values.innerHTML=table(['ψN','压力 Pa','配方 σ Pa','拟合权重'],shown.psi_n.map((x,i)=>[x,shown.pressure_Pa[i],shown.sigma_Pa[i],shown.weights[i]]));status.textContent='只读预览；来源SHA '+shown.source_sha256+(rid?'；对照绑定运行 '+rid:'；尚未选择运行');}
  scale.oninput=()=>{apply.disabled=true;status.textContent='倍率已改变，请先更新曲线预览。';};
  preview.onclick=async()=>{const n=++request;preview.disabled=true;apply.disabled=true;try{const value=Number(scale.value),r=await api('pressure-preview?scale='+encodeURIComponent(value));if(n!==request||!host.isConnected||cid!==caseDoc?.case_id||rid!==runId)return;shown=r.pressure;displayedScale=value;draw();apply.disabled=Number(scale.value)!==value;}catch(e){status.textContent=e.message;}finally{preview.disabled=false;}};
  apply.onclick=()=>{if(Number(scale.value)!==displayedScale)return;$('pressure_scale').value=String(displayedScale);markDirty();status.textContent='已写入配置草稿；尚未保存或启动求解。磁处理采纳不受此倍率变化影响。';};draw();
 }
 async function comparison(host){
  const cid=caseDoc?.case_id,rid=runId,ticket=++serial;
  host.replaceChildren(element('p','选择另一次运行，比较实际生效输入与结果；不修改任何输入。'));
  if(!cid||!rid){host.append(element('p','请先选择一次已有运行。'));return;}
  const list=await api('cases');if(ticket!==serial||cid!==caseDoc?.case_id||rid!==runId)return;
  const casesSelect=element('select'),runsSelect=element('select'),button=element('button','比较所选运行'),output=element('div');casesSelect.setAttribute('aria-label','对照算例');runsSelect.setAttribute('aria-label','对照运行');
  for(const c of list.cases)casesSelect.add(new Option(c.name,c.case_id));casesSelect.value=cid;
  host.append(casesSelect,runsSelect,button,output);
  async function refresh(){const selected=casesSelect.value;runsSelect.replaceChildren(new Option('正在读取…',''));button.disabled=true;const d=await api('runs?case_id='+encodeURIComponent(selected));if(selected!==casesSelect.value||!host.isConnected)return;runsSelect.replaceChildren();for(const r of d.runs)runsSelect.add(new Option(r.run_id+' · r'+r.status.revision,r.run_id));button.disabled=!runsSelect.value;}
  casesSelect.onchange=()=>refresh().catch(error);await refresh();
  button.onclick=async()=>{const otherCase=casesSelect.value,otherRun=runsSelect.value;output.textContent='读取实际输入与结果…';try{const d=await api('compare?'+new URLSearchParams({case_id:cid,run_id:rid,other_case_id:otherCase,other_run_id:otherRun}));if(cid!==caseDoc?.case_id||rid!==runId||otherCase!==casesSelect.value||otherRun!==runsSelect.value||!host.isConnected)return;output.replaceChildren(element('p',rid+' ↔ '+otherRun),element('p',d.warnings.length?d.warnings.join('；')+'。仅显示输入差异，禁止自动对齐图表。':d.meaning));const diff=element('div');diff.innerHTML=table(['实际输入字段','左运行','右运行'],d.input_diff.map(x=>[x.field,x.change==='array'?JSON.stringify({count:x.left_count,changed:x.changed_count,examples:x.examples}):JSON.stringify(x.left),x.change==='array'?'长度 '+x.right_count:JSON.stringify(x.right)]));output.append(diff);if(!d.input_diff.length)output.append(element('p','实际输入一致。'));if(d.aligned&&d.reports.every(Boolean)){for(const [key,field,label] of [['q','q','q'],['pressure','pressure_Pa','压力 Pa']]){const chart=element('div');output.append(chart);plot(chart,d.reports.map((r,i)=>({label:i?'右运行':'左运行',color:i?'#ad5265':'#147a86',points:r[key].map(p=>[p.psi_n,p[field]])})),'ψN',label);}}else output.append(element('p','结果图未生成或比较口径不一致；没有替代结果。'));}catch(e){output.textContent=e.message;}};
 }
 async function channel(kind,index){
  const cid=caseDoc?.case_id,rid=runId;if(!cid||!rid)return;
  nodeId='magnetics';eventStep='magnetics';updateHelp();renderNodes();tab('process');$('node-title').textContent='残差通道 → 原运行数据';const host=$('node-content');host.textContent='读取原运行通道…';
  try{const d=await api('channel-view?'+new URLSearchParams({case_id:cid,run_id:rid,kind,index}));if(cid!==caseDoc?.case_id||rid!==runId)return;host.replaceChildren(element('p',rid+' · r'+d.revision+' · '+d.node+'；此页只读。'),element('p',d.geometry_note));const chart=element('div');host.append(chart);plot(chart,[{label:'原始（单位换算后）',color:'#ae6e36',points:d.audit.t.map((t,i)=>[t,d.audit.raw[i]])},{label:'实际处理后',color:'#147a86',points:d.audit.t.map((t,i)=>[t,d.audit.processed[i]])}],'时间 s',d.unit,[],false);const facts=element('div');facts.innerHTML=table(['通道','参与拟合','有效权重','实际观测','换算系数','样本数'],[[d.node,d.used,d.weight,d.observed,d.audit.scale,d.audit.samples]]);host.append(facts);const details=element('details');details.append(element('summary','原始窗口、基线与处理参数'));details.append(element('pre',JSON.stringify({audit:d.audit,raw:d.raw},null,2)));host.append(details);if(!d.raw_available)host.append(element('p','该历史运行未保存完整原始窗口；上图来自当时保存的处理审计，不冒充完整原始数据。'));const edit=element('button','返回磁处理，选择此运行原始数据');edit.disabled=!d.raw_available;edit.title=d.raw_available?'选择原运行后，再复用、预览和采纳':'历史运行缺少完整原始波形，不能建立新处理预览';edit.onclick=()=>{openNode('magnetics');window.dispatchEvent(new CustomEvent('fylite-inspect-source',{detail:{caseId:cid,runId:rid}}));};host.append(edit);}catch(e){host.textContent=e.message;}
 }
 return {pressure,comparison,channel};
})();
