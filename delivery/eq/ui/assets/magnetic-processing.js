/* Magnetic task editor. Uses the same versioned API as automation clients. */
'use strict';
(() => {
  let preview = null, previous = null, active = false, edited = false;
  const el = id => document.getElementById('mp-' + id);
  function emit(){window.dispatchEvent(new CustomEvent('fylite-mag-state',{detail:{hasPreview:!!preview,busy:active,edited}}))}
  function placeholders(){for(const [id,text] of [['dataset','尚未读取数据'],['channel','生成预览后可选择通道'],['run','暂无可用历史运行']]){const select=el(id);if(![...select.options].some(o=>o.value)){const o=new Option(text,'');o.disabled=true;o.selected=true;select.replaceChildren(o);}}}
  const message = text => { el('status').textContent = text; };
  function controls() {
    el('preview').disabled=active||!el('dataset').value;
    el('adopt').disabled=active||!preview;
    el('import').disabled=active||!el('run').value;
    for(const id of ['cases','new','save','fork','execute'])$(id).disabled=active;placeholders();emit();
  }
  function ready() {
    requireSelection();
    if (!caseDoc || dirty) throw Error('请先保存当前算例，再读取或处理实验数据。');
    if (active) throw Error('当前数据操作尚未完成。');
  }
  function invalidate() {
    preview = null;
    el('adopt').disabled = true;
    el('plot').hidden = true;
    el('values').replaceChildren();
    el('samples').replaceChildren(); el('warnings').textContent='';
    el('channel').replaceChildren();placeholders();emit();
    message('处理草稿已变化，请生成新预览；尚未影响求解器输入。');
  }
  function draft() {
    return {...caseDoc.parameters, data_source: el('dataset').selectedOptions[0]?.dataset.mode,
      half_window_s: Number(el('window').value), drift: el('drift').checked};
  }
  async function action(fn) {
    try {
      ready(); active = true;
      for (const b of el('actions').querySelectorAll('button')) b.disabled = true;
      controls();await fn(caseDoc.case_id, caseDoc.revision);
    } catch (e) { message(e.message || String(e)); }
    finally {
      active = false;
      for (const b of el('actions').querySelectorAll('button')) b.disabled = false;
      controls();
    }
  }
  async function refresh(reset = false) {
    if (!caseDoc) { for (const id of ['dataset','run','channel']) el(id).replaceChildren(); el('adopted').textContent=''; message('选择数据来源，点击“保存并读取数据”；会自动建立个人算例。'); controls();return; }
    const cid = caseDoc.case_id;
    const [objects, history] = await Promise.all([
      api('processing-objects?'+new URLSearchParams({case_id:cid})),
      api('runs?'+new URLSearchParams({case_id:cid}))]);
    if (caseDoc?.case_id !== cid) return;
    const selected = el('dataset').value;
    el('dataset').replaceChildren(new Option('请选择已读取的数据', ''));
    for (const d of objects.datasets) {
      const o = new Option(`${d.dataset_id} · ${d.mode} · ${d.time_s} s`, d.dataset_id);
      o.dataset.mode = d.mode; el('dataset').add(o);
    }
    if (objects.datasets.some(d=>d.dataset_id===selected)) el('dataset').value=selected;
    else if (objects.datasets.length) el('dataset').value=objects.datasets.at(-1).dataset_id;
    el('run').replaceChildren(new Option('选择已完成取数的运行', ''));
    for (const r of history.runs) if (['completed','reused'].includes(r.status.steps.sources?.state))
      el('run').add(new Option(r.run_id, r.run_id));
    el('adopted').textContent=caseDoc.processing
      ? `当前求解输入：修订 ${caseDoc.revision}，已采纳 ${caseDoc.processing.preview_id}。后续运行复用这些原始数据与处理值。`
      : '下一步：读取或选择数据 → 生成预览 → 采纳。完成后才可准备平衡计算。';
    controls();
    if (reset) {
      edited=false;invalidate(); previous=null;
      el('window').value=caseDoc.parameters.half_window_s;
      el('drift').checked=caseDoc.parameters.drift;
      el('note').value='';
      message('选择缓存数据，调整参数并预览；确认后采纳为新的算例修订。');
    }
  }
  function chart(a, old) {
    const canvas=el('plot'), g=canvas.getContext('2d'); canvas.hidden=false;
    const series=[{name:'原始（已换算单位）',color:'#9b4a20',t:a.t,y:a.raw},
      {name:'本次处理',color:'#006c78',t:a.t,y:a.processed}];
    if(old)series.push({name:'上一预览',color:'#7756a5',t:old.t,y:old.processed});
    const xs=series.flatMap(s=>s.t), ys=series.flatMap(s=>s.y);
    let lo=Math.min(...ys),hi=Math.max(...ys);const margin=(hi-lo)*.08||Math.max(Math.abs(lo)*.01,1e-8);lo-=margin;hi+=margin;
    const xmin=Math.min(...xs),xmax=Math.max(...xs),W=canvas.width,H=canvas.height;
    const X=x=>90+(x-xmin)/(xmax-xmin||1)*(W-115),Y=y=>H-50-(y-lo)/(hi-lo)*(H-95);
    g.clearRect(0,0,W,H);g.font='13px sans-serif';g.lineWidth=1;
    for(let i=0;i<=5;i++){
      const x=xmin+(xmax-xmin)*i/5,y=lo+(hi-lo)*i/5;
      g.strokeStyle='#dce2e7';g.beginPath();g.moveTo(X(x),45);g.lineTo(X(x),H-50);g.moveTo(90,Y(y));g.lineTo(W-25,Y(y));g.stroke();
      g.fillStyle='#263b47';g.fillText(x.toFixed(4),X(x)-22,H-27);g.fillText(y.toPrecision(4),5,Y(y)+4);
    }
    series.forEach((s,j)=>{g.strokeStyle=s.color;g.fillStyle=s.color;g.lineWidth=1.8;g.beginPath();s.t.forEach((t,i)=>i?g.lineTo(X(t),Y(s.y[i])):g.moveTo(X(t),Y(s.y[i])));g.stroke();g.fillText(s.name,95+j*220,23)});
    g.fillStyle='#263b47';g.fillText('时间 / s',W/2,H-5);
  }
  function render() {
    if (!preview) return;
    const a=preview.magnetics.audit.find(x=>x.node===el('channel').value);
    if(!a)return;
    const old=previous?.magnetics.audit.find(x=>x.node===a.node);
    chart(a,old);
    el('values').innerHTML=table(['通道','样本数','换算系数','原始均值 × 系数','处理后均值','与上次预览均值之差'],
      [[a.node,a.samples,a.scale,a.raw_mean*a.scale,a.reduced,old?a.reduced-old.reduced:'无上一预览']])+
      `<p>对比预览：${esc(previous?.preview.preview_id||'无')}。线性修正：${esc(a.drift?'开启':'关闭')}；炮前拟合斜率 ${esc(fmt(a.slope))}，截距 ${esc(fmt(a.intercept))}（换算前单位）。</p>`;
    el('samples').innerHTML=table(['时间 / s','原始（换算后）','处理后'],a.t.map((t,i)=>[t,a.raw[i],a.processed[i]]));
  }
  el('refresh').onclick=()=>refresh().catch(e=>message(e.message));
  el('read').onclick=async()=>{try{if(active)return;requireSelection();
    if(!caseDoc||dirty)await save();
    const history=await api('runs?'+new URLSearchParams({case_id:caseDoc.case_id}));
    if(history.runs.some(r=>['starting','running','waiting_review'].includes(r.status.state)))throw Error('该算例已有运行或待确认任务，请先在运行记录中继续、退回或停止，避免重复取数。');
    await action(async(cid,revision)=>{
    message('正在显式读取实验数据；在线读取可能需要数分钟。请勿关闭或切换算例。');
    const run=await api('execute',{case_id:cid,revision,target:'sources',fresh_source:true,request_id:crypto.randomUUID()});
    await selectRun(run.run_id);tab('magnetic-task');await runs();
    const started=Date.now();let result;
    for(let i=0;i<1200;i++){
      result=await api('run?'+new URLSearchParams({case_id:cid,run_id:run.run_id}));
      message('正在读取 '+(caseDoc.parameters.data_source==='mdsplus'?'MDSplus 在线数据':'冻结实验缓存')+' · 已等待 '+Math.round((Date.now()-started)/1000)+' 秒。只读取数据，不进行平衡计算；可用顶部“停止”取消。');
      if(['completed','failed','cancelled'].includes(result.status.state))break;
      await new Promise(resolve=>setTimeout(resolve,1000));
    }
    if(result.status.state!=='completed')throw Error(result.status.error||'读取尚未完成，请在运行记录中检查；完成后可导入。');
    const obj=await api('processing-import',{case_id:cid,base_revision:revision,run_id:run.run_id});
    if(caseDoc?.case_id!==cid)return;
    await refresh();el('dataset').value=obj.dataset_id;invalidate();
    message('读取完成。下一步：检查窗口与漂移 → 点击“生成处理预览”。后续不会重新连接 MDSplus。');await runs();
    });}catch(e){message(e.message);}
  };
  el('import').onclick=()=>action(async(cid,revision)=>{
    const obj=await api('processing-import',{case_id:cid,base_revision:revision,run_id:el('run').value});
    if(caseDoc?.case_id!==cid)return;
    await refresh();el('dataset').value=obj.dataset_id;invalidate();message('已登记历史运行的原始波形；没有重新读取实验数据库。');
  });
  el('preview').onclick=()=>action(async(cid,revision)=>{
    if(!el('dataset').value)throw Error('请先读取或选择一份原始数据。');
    const requestedDataset=el('dataset').value, requestedDraft=JSON.stringify(draft());
    const candidate=await api('processing-preview',{case_id:cid,base_revision:revision,dataset_id:el('dataset').value,parameters:draft()});
    if(caseDoc?.case_id!==cid||caseDoc.revision!==revision)return;
    if(requestedDataset!==el('dataset').value||requestedDraft!==JSON.stringify(draft()))throw Error('预览期间参数发生变化，请重新生成；未采纳。');
    previous=preview||previous;preview=candidate;emit();
    const channel=el('channel').value;el('channel').replaceChildren();
    for(const a of preview.magnetics.audit)el('channel').add(new Option(a.node,a.node));
    if(preview.magnetics.audit.some(a=>a.node===channel))el('channel').value=channel;
    render();message(`预览 ${preview.preview.preview_id}；原始数据未重读，未启动求解器，尚未采纳。`);
    el('warnings').textContent=preview.quality.warnings.join('；');
  });
  el('adopt').onclick=()=>action(async(cid,revision)=>{
    if(!preview)throw Error('请先生成预览。');
    const c=await api('processing-adopt',{case_id:cid,base_revision:revision,preview_id:preview.preview.preview_id,
      identity:preview.identity,parameters:draft(),note:el('note').value});
    if(caseDoc?.case_id!==cid)return;
    showCase(c);await cases();await runs();await refresh(true);
    message('已采纳为修订 '+c.revision+'。进入“② 约束配置”，完成后点击“③ 检查并计算”，，求解器使用此处理版本；仍需检查输入与结果。');
  });
  el('channel').onchange=render;el('run').onchange=controls;
  for(const id of ['dataset','window','drift'])el(id).onchange=()=>{edited=true;previous=preview||previous;invalidate();controls()};
  document.querySelector('[data-tab="magnetic-task"]').addEventListener('click',()=>refresh().catch(e=>message(e.message)));
  controls();
  window.addEventListener('fylite-case-changed',()=>{edited=false;preview=null;previous=null;emit();el('adopt').disabled=true;el('plot').hidden=true;el('values').replaceChildren();el('samples').replaceChildren();el('warnings').textContent='';refresh(true).catch(e=>message(e.message));});
})();
