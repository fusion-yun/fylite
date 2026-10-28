/* A single analysis object, with its persisted source, adopted input and native result. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const prefix = '/fylite/eq/api/workflow/';
  const steps = [
    ['实验数据', '实验数据是否来自所选炮号与时刻？', '读取 MDSplus 原始波形，并保存本次使用的目标窗和炮前窗口。'],
    ['处理与质量', '哪些磁测量可以进入求解？', '逐道查看原始／处理后信号、历史掩码、处理规则和质量限制。'],
    ['求解输入', '实际准备了什么纯磁输入？', '核对测量值、PF／Ip／TF、通道角色和输入版本；本路线不引入压力或 q₀ 目标。'],
    ['运行与审阅', '求解是否完成，结果是否可用于分析？', '启动原生 M 档求解，并分别记录数值结果和人工审阅结论。'],
    ['结果解释', '这个结果支持什么结论？', '查看磁面、q 剖面和逐通道残差，再回到对应观测与处理记录。']
  ];
  const names = {created:'待取数',acquiring:'读取中',acquired:'待采纳',adopted:'输入已采纳',running:'求解中',waiting_review:'待审阅',reviewed:'已审阅',failed:'失败',cancelled:'已停止'};
  let token = '', doc = null, stage = 0, input = null, result = null, channel = null, channelKey = null, channelSlot = null;
  let poll = null, loading = false, channelDraft = null, savingChannels = false;
  const E = (tag, value, cls) => {const x=document.createElement(tag);if(value!==undefined)x.textContent=String(value);if(cls)x.className=cls;return x};
  const B = (label, fn, cls='secondary') => {const x=E('button',label,cls);x.type='button';x.onclick=fn;return x};
  const fmt = n => typeof n==='number' && Number.isFinite(n) ? Number(n).toPrecision(6) : String(n??'—');
  function note(host,message,kind=''){host.append(E('p',message,'statebar '+kind))}
  function failureBlock(host,failure){
    if(!failure||!failure.count)return;
    const det=E('details',undefined,'gate-box');det.open=true;
    det.append(E('summary','竖直设定点扫描：'+failure.count+' 个候选全部失败','gate-sum'));
    const list=E('div',undefined,'gate-list');
    (failure.sample||[]).forEach(function(s){
      const detail=s.error?String(s.error).replace(/^: /,''):('χ² '+Math.round(s.chi2||0)+' · q₀ '+((s.q0==null)?'—':Number(s.q0).toFixed(3))+' · '+(s.converged?'收敛':'未收敛'));
      const row=E('div',undefined,'gate-row bad');
      row.append(E('b','✗'),E('code','zc = '+s.zc),E('span',detail,'gate-why'),E('em','','gate-bound'));
      list.append(row);
    });
    if(failure.count>(failure.sample||[]).length){
      const more=E('div',undefined,'tree-dd more');
      more.textContent='… 还有 '+(failure.count-(failure.sample||[]).length)+' 个候选';
      list.append(more);
    }
    det.append(list);host.append(det);
  }
  function showVerdict(host,status,check,failure){
    const numeric=status.numerical==='converged',gate=status.gate?.state;
    note(host,`求解：${numeric?'内层数值已收敛':'内层数值未收敛'} · 迭代 ${fmt(status.facts?.iterations)} · 迭代残差 ${fmt(status.facts?.residual)}`,numeric?'ok':'error');
    note(host,`结果检查：${gate==='passed'?'通过':gate==='physics_gate_failed'?'未通过':gate==='solver_not_converged'?'数值未收敛，无法通过':'尚未完成'} · 实验物理资格：未认证`,gate==='passed'?'ok':'error');
    const checks=check?.checks||[];
    if(checks.length){
      const bad=checks.filter(x=>!x.pass).length;
      const det=E('details',undefined,'gate-box');det.open=bad>0;
      det.append(E('summary',`物理门禁 ${checks.length-bad}/${checks.length} 通过${bad?'（'+bad+' 项未过）':''}`,'gate-sum'));
      const list=E('div',undefined,'gate-list');
      for(const c of checks){
        const row=E('div',undefined,'gate-row'+(c.pass?'':' bad'));
        row.append(E('b',c.pass?'✓':'✗'),E('code',c.id),E('span',c.why||'','gate-why'),
                   E('em',Array.isArray(c.bound)?('∈ ['+c.bound[0]+', '+c.bound[1]+']'):String(c.bound||''),'gate-bound'));
        list.append(row);
      }
      det.append(list);host.append(det);
    }
    failureBlock(host,failure);
    if(gate==='physics_gate_failed')host.append(E('p','迭代残差衡量求解器内部停止条件；逐道观测的拟合误差另见结果页。','hint'));
  }
  function facts(rows){const dl=E('dl',undefined,'data-facts');for(const [k,v] of rows){const d=E('div');d.append(E('dt',k),E('dd',v));dl.append(d)}return dl}
  function error(e){const msg=e?.message||String(e);const target=$('workspace').classList.contains('visible')?$('stage-body'):$('start-error');target.prepend(E('p',msg,'statebar error'))}
  async function api(route,body){const res=await fetch(prefix+route,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-FyLite-Token':token},body:JSON.stringify(body)});const data=await res.json();if(!res.ok)throw Error(data.error||`HTTP ${res.status}`);return data}
  const cid=()=>doc?.case.case_id;
  const state=()=>doc?.status.state;
  const finishedSource=()=>['acquired','adopted','running','waiting_review','reviewed'].includes(state());
  const adopted=()=>['adopted','running','waiting_review','reviewed'].includes(state());
  const resultReady=()=>['waiting_review','reviewed'].includes(state());
  function header(){const c=doc.case;$('case-title').textContent=`EAST ${c.shot} · ${c.time_s.toFixed(3)} s`;$('case-kind').textContent=channelPolicy();$('case-badge').textContent=names[state()]||state()}
  async function recent(){try{const list=await api('archive-magnetic-cases');renderTree(list.cases);const box=$('recent');box.replaceChildren();if(!list.cases.length){box.append(E('p','当前个人工作区还没有纯磁分析。','hint'));return}for(const c of list.cases.slice(0,12)){const row=E('div',undefined,'route'),text=E('div');text.append(E('strong',`EAST ${c.shot} · ${Number(c.time_s).toFixed(3)} s`),E('small',`${c.mask_profile==='m02_pinned'?'164437 历史通道默认':'装置默认规则 · 探索'} · ${names[c.state]||c.state}`));row.append(text,E('span',names[c.state]||c.state,'pill'));row.append(B('继续分析',()=>openCase(c.case_id)));box.append(row)}}catch(e){$('recent').textContent=e.message}}
  function treeTone(s){return s==='reviewed'?'ok':s==='failed'||s==='cancelled'?'bad':s==='running'||s==='acquiring'?'run':''}
  function markTreeSelection(id){for(const node of document.querySelectorAll('.tree-node'))node.classList.toggle('sel',node.dataset.caseId===id)}
  function showDup(dup,d){
    let box=$('dup-box');
    if(!box){box=E('div');box.id='dup-box';box.className='dup-box';const host=$('create');if(host&&host.parentNode)host.parentNode.appendChild(box)}
    box.replaceChildren();
    box.append(E('b','同一炮号与时刻已有 '+dup.length+' 个算例'),
               E('p',dup.map(c=>c.case_id+'（'+c.time_s.toFixed(3)+' s · '+c.mask_profile+'）').join('、')+'。若只是想看结果，建议直接打开；换掩码再建也合理。'));
    const acts=E('div',undefined,'dup-acts');
    acts.append(B('打开 '+dup[0].case_id,()=>{box.remove();openCase(dup[0].case_id)}),
                B('仍然新建',()=>{window.__allowDup=true;box.remove();$('create').click()}));
    box.append(acts);
  }
  function stageIdx(c){
    const s=c.state, t=c.stage;
    if(t==='processing')return 1;
    if(t==='input')return 2;
    if(t==='solve')return 3;
    if(t==='review'||t==='result')return 4;
    if(s==='acquired')return 1;
    if(s==='adopted')return 2;
    if(s==='running'||s==='failed'||s==='cancelled')return 3;
    if(s==='waiting_review'||s==='reviewed')return 4;
    return 0;
  }
  function thumbSvg(pts){
    const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
    const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
    const w=Math.max(x1-x0,1e-9),h=Math.max(y1-y0,1e-9),s=18/Math.max(w,h);
    const d=pts.map(p=>((p[0]-x0)*s+2).toFixed(1)+','+((y1-p[1])*s+2).toFixed(1)).join(' ');
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 22 22');svg.setAttribute('class','tree-thumb');
    const pl=document.createElementNS('http://www.w3.org/2000/svg','polygon');
    pl.setAttribute('points',d);pl.setAttribute('fill','none');pl.setAttribute('stroke','#19718a');pl.setAttribute('stroke-width','1.4');
    svg.append(pl);return svg;
  }
  function renderTreeRaw(cases){
    const host=$('tree-body');if(!host)return;
    const selId=doc&&doc.case?doc.case.case_id:new URLSearchParams(location.search).get('case_id');
    host.replaceChildren();
    const count=$('tree-count');if(count)count.textContent=cases.length?String(cases.length):'';
    if(!cases.length){host.append(E('p','当前工作区还没有纯磁分析。','tree-hint'));return}
    const groups=new Map();
    for(const c of cases){const shot=String(c.shot);if(!groups.has(shot))groups.set(shot,[]);groups.get(shot).push(c)}
    for(const [shot,items] of groups){
      const group=E('div',undefined,'tree-group'),head=E('div',undefined,'tree-group-head');
      head.append(E('b',shot),E('em',`· ${items.length} 次分析`));group.append(head);
      for(const c of items){
        const g=c.gate&&c.gate.state;
        const tone=(g==='physics_gate_failed'||g==='solver_not_converged')?'bad':treeTone(c.state);
        const label=g==='physics_gate_failed'?'门禁未过':g==='solver_not_converged'?'未收敛':(names[c.state]||c.state);
        const node=E('button',undefined,'tree-node'),meta=E('span',undefined,'tree-node-meta');
        node.type='button';node.dataset.caseId=c.case_id;
        meta.append(E('span',`${Number(c.time_s).toFixed(3)} s`,'tree-time'),E('span',label,'tree-tag '+tone));
        if(c.thumb&&c.thumb.length)node.append(thumbSvg(c.thumb));else node.append(E('span',undefined,'tree-dot '+(tone||'idle')));node.append(E('span',c.case_id,'tree-node-id'),meta);
        node.onclick=()=>openCase(c.case_id);group.append(node);
        if(c.case_id===selId){
          const cur=stageIdx(c);
          const kids=E('div',undefined,'tree-kids');
          steps.forEach(([label],i)=>{const b=B(label,()=>openCase(c.case_id,i));b.className='tree-kid'+(i===cur?' active':'')+(i<cur?' done':'');kids.append(b)});
          const out=B('输出与产物',()=>openCase(c.case_id,4));out.className='tree-kid output';kids.append(out);
          group.append(kids);
        }
      }
      host.append(group);
    }
    markTreeSelection(doc?.case.case_id||new URLSearchParams(location.search).get('case_id'));
  }
  async function openCase(id,forced){const wantTab0=new URLSearchParams(location.search).get('tab');if(channelDirty()&&!window.confirm('通道修改尚未保存，是否离开当前记录？'))return;channelDraft=null;try{doc=await api('archive-magnetic-case?'+new URLSearchParams({case_id:id}));input=null;result=null;channel=null;channelKey=null;channelSlot=null;stage=(forced!=null)?forced:(state()==='created'||state()==='acquiring'?0:state()==='acquired'?1:state()==='adopted'?2:state()==='running'||state()==='failed'?3:4);history.replaceState(null,'','?case_id='+encodeURIComponent(id)+(wantTab0?'&tab='+wantTab0:''));$('start-view').hidden=true;$('workspace').classList.add('visible');await ensureData();render();startPoll();markTreeSelection(id);switchTab(wantTab0==='result'&&resultReady()?'result':'process',true);window.scrollTo(0,0)}catch(e){error(e)}}
  async function ensureData(){if(adopted()&&!input)input=await api('archive-magnetic-input?'+new URLSearchParams({case_id:cid()}));if(resultReady()&&!result)result=await api('archive-magnetic-result?'+new URLSearchParams({case_id:cid()}))}
  function startPoll(){if(poll)clearInterval(poll);poll=setInterval(async()=>{if(loading||!['acquiring','running'].includes(state()))return;loading=true;try{const before=state();doc=await api('archive-magnetic-case?'+new URLSearchParams({case_id:cid()}));if(before!==state())await ensureData();render()}catch(e){error(e)}finally{loading=false}},2000)}
  async function action(route,body){try{doc=await api(route,body);if(['archive-magnetic-adopt','archive-magnetic-execute'].includes(route))input=null;await ensureData();render();startPoll();recent()}catch(e){error(e)}}
  let currentTab='process';
  function switchTab(name,silent){
    currentTab=name;
    const p=$('tab-process'),r=$('tab-result');
    if(p)p.classList.toggle('active',name==='process');
    if(r)r.classList.toggle('active',name==='result');
    const stageSection=document.querySelector('#workspace .stage');
    const progress=$('progress'),foot=document.querySelector('.footer-actions');
    if(stageSection)stageSection.hidden=name!=='process';
    if(progress)progress.hidden=name!=='process';
    if(foot)foot.hidden=name!=='process';
    const rv=$('result-view');if(rv)rv.hidden=name!=='result';
    if(name==='result')openResultTab();
    if(!silent){try{const u=new URL(location.href);u.searchParams.set('tab',name);history.replaceState(null,'',u)}catch(e){}}
  }
  const tabP=document.getElementById('tab-process'), tabR=document.getElementById('tab-result');
  if(tabP)tabP.onclick=()=>switchTab('process');
  if(tabR)tabR.onclick=()=>switchTab('result');
  async function openResultTab(){
    const host=$('result-body');if(!host)return;
    if(!resultReady()){host.replaceChildren(E('p','此算例尚无结果；先完成运行与审阅。','hint'));return}
    if(!result){try{await ensureData()}catch(e){host.textContent=e.message;return}}
    if(!result)return;
    if(host.dataset.rendered===cid())return;
    host.replaceChildren();
    const grid=E('div',undefined,'eqp-grid');host.append(grid);
    if(window.EQP)EQP.render(grid,result);
    host.dataset.rendered=cid();
    buildDdTree();
  }
  function renderOverview(){
    const host=$('result-body');if(!host||!result)return;
    host.replaceChildren();
    const grid=E('div',undefined,'eqp-grid');host.append(grid);
    if(window.EQP)EQP.render(grid,result);
    document.querySelectorAll('#dd-tree button.sel').forEach(function(x){x.classList.remove('sel')});
  }
  async function buildDdTree(){
    const host=$('dd-tree');if(!host)return;
    host.replaceChildren(E('div','当前算例没有 DD 文件。'));
    try{
      const d=await api('archive-magnetic-dd?'+new URLSearchParams({case_id:cid()}));
      host.replaceChildren();
      host.append(E('div',undefined,'dd-head'),E('span','dd/ · '+d.files.length+' 个节点','dd-head'),B('概览 · 六联图',function(){renderOverview()}));
      const root={};
      d.files.forEach(function(f){
        const parts=f.path.split('/');let node=root;
        parts.forEach(function(p,i){ node[p]=node[p]||{}; if(i<parts.length-1) node=node[p]; });
        node[parts[parts.length-1]]=node[parts[parts.length-1]]||{}; node[parts[parts.length-1]].__file=f;
      });
      host.append(ddRender(root,''));
    }catch(e){ host.replaceChildren(E('p',e.message,'hint')) }
  }
  function ddRender(node,depth){
    const wrap=E('div');
    Object.keys(node).sort().forEach(function(k){
      const child=node[k];
      if(child.__file){
        const b=B(k,function(){ddPreview(child.__file,this)});
        b.title=child.__file.path+' · '+child.__file.size+' B';
        b.dataset.path=child.__file.path;
        wrap.append(b);
      }else{
        const det=E('details');det.open=true;
        det.append(E('summary',k));
        det.append(ddRender(child,depth+1));
        wrap.append(det);
      }
    });
    return wrap;
  }
  function ddFmt(v){
    const a=Math.abs(v);
    if(!isFinite(v))return '—';
    if(a===0)return '0';
    if(a>=1e5)return (v/1e3).toFixed(0)+'k';
    if(a>=1e3)return v.toFixed(0);
    if(a>=10)return v.toFixed(1);
    if(a>=1)return v.toFixed(2);
    return v.toPrecision(2);
  }
  function ddSetup(host,W,H){
    const cv=document.createElement('canvas');
    const dpr=Math.min(window.devicePixelRatio||1,2);
    cv.width=W*dpr;cv.height=H*dpr;cv.style.width='100%';cv.style.maxWidth=W+'px';
    const ctx=cv.getContext('2d');ctx.scale(dpr,dpr);
    host.append(cv);
    return {ctx:ctx,W:W,H:H};
  }
  function ddAxes(ctx,W,H,xr,yr,xlab,ylab,equal){
    const L=70,R=W-26,T=24,B=H-52;
    ctx.clearRect(0,0,W,H);
    let sx=function(v){return L+(R-L)*(v-xr[0])/((xr[1]-xr[0])||1)};
    let sy=function(v){return B-(B-T)*(v-yr[0])/((yr[1]-yr[0])||1)};
    if(equal){
      const k=Math.min((R-L)/((xr[1]-xr[0])||1),(B-T)/((yr[1]-yr[0])||1));
      const cx=(L+R)/2,cy=(T+B)/2,mx=(xr[0]+xr[1])/2,my=(yr[0]+yr[1])/2;
      sx=function(v){return cx+(v-mx)*k};
      sy=function(v){return cy-(v-my)*k};
    }
    ctx.strokeStyle='#b9c9d2';ctx.lineWidth=1;ctx.strokeRect(L,T,R-L,B-T);
    ctx.fillStyle='#5b7080';ctx.font='11px ui-monospace,Consolas,monospace';
    ctx.textAlign='right';ctx.textBaseline='middle';
    [0,0.25,0.5,0.75,1].forEach(function(f){
      const v=yr[0]+(yr[1]-yr[0])*f,y=sy(v);
      ctx.strokeStyle='#eef3f6';ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(R,y);ctx.stroke();
      ctx.fillText(ddFmt(v),L-8,y);
    });
    ctx.textAlign='center';ctx.textBaseline='top';
    [0,0.25,0.5,0.75,1].forEach(function(f){
      const v=xr[0]+(xr[1]-xr[0])*f,x=sx(v);
      ctx.strokeStyle='#eef3f6';ctx.beginPath();ctx.moveTo(x,T);ctx.lineTo(x,B);ctx.stroke();
      ctx.fillText(ddFmt(v),x,B+6);
    });
    ctx.fillStyle='#526c79';
    if(xlab)ctx.fillText(xlab,(L+R)/2,B+26);
    if(ylab){ctx.save();ctx.translate(16,(T+B)/2);ctx.rotate(-Math.PI/2);ctx.textBaseline='middle';ctx.fillText(ylab,0,0);ctx.restore()}
    return {sx:sx,sy:sy,L:L,R:R,T:T,B:B};
  }
  function ddLineChart(host,xs,ys,xlab,ylab,opts){
    opts=opts||{};
    const g0=ddSetup(host,760,380),ctx=g0.ctx,W=g0.W,H=g0.H;
    let x0=Math.min.apply(null,xs),x1=Math.max.apply(null,xs);
    let y0=Math.min.apply(null,ys),y1=Math.max.apply(null,ys);
    if(opts.ymin!=null)y0=opts.ymin; if(opts.ymax!=null)y1=opts.ymax;
    const pad=(y1-y0)*0.06||1;y0-=pad;y1+=pad;
    const g=ddAxes(ctx,W,H,[x0,x1],[y0,y1],xlab,ylab,!!opts.equal);
    ctx.strokeStyle=opts.color||'#17657f';ctx.lineWidth=2;ctx.beginPath();
    for(let i=0;i<xs.length;i++){const X=g.sx(xs[i]),Y=g.sy(ys[i]);i?ctx.lineTo(X,Y):ctx.moveTo(X,Y)}
    ctx.stroke();
  }
  function ddContour(host,X,Y,Z,xlab,ylab){
    const g0=ddSetup(host,760,460),ctx=g0.ctx,W=g0.W,H=g0.H;
    const nr=X.length,nz=Y.length;
    let lo=Infinity,hi=-Infinity,i,j;
    for(i=0;i<nr;i++)for(j=0;j<nz;j++){const v=Z[i][j];if(v<lo)lo=v;if(v>hi)hi=v}
    const g=ddAxes(ctx,W,H,[X[0],X[nr-1]],[Y[0],Y[nz-1]],xlab,ylab,true);
    const span=hi-lo||1;
    [0.1,0.22,0.34,0.46,0.58,0.7,0.82,0.94].forEach(function(f,idx){
      const t=lo+span*f;
      ctx.strokeStyle=idx===7?'#17657f':'rgba(23,101,127,0.4)';
      ctx.lineWidth=idx===7?2.2:1;ctx.beginPath();
      for(i=0;i<nr-1;i++)for(j=0;j<nz-1;j++){
        const a=Z[i][j],b=Z[i+1][j],c=Z[i+1][j+1],d=Z[i][j+1],pts=[];
        if((a<t)!==(b<t))pts.push([(t-a)/(b-a||1e-12),0]);
        if((b<t)!==(c<t))pts.push([1,(t-b)/(c-b||1e-12)]);
        if((d<t)!==(c<t))pts.push([(t-d)/(c-d||1e-12),1]);
        if((a<t)!==(d<t))pts.push([0,(t-a)/(d-a||1e-12)]);
        if(pts.length>=2){
          const p1=pts[0],p2=pts[1];
          const r1=X[i]+(X[i+1]-X[i])*p1[0],z1=Y[j]+(Y[j+1]-Y[j])*p1[1];
          const r2=X[i]+(X[i+1]-X[i])*p2[0],z2=Y[j]+(Y[j+1]-Y[j])*p2[1];
          ctx.moveTo(g.sx(r1),g.sy(z1));ctx.lineTo(g.sx(r2),g.sy(z2));
        }
      }
      ctx.stroke();
    });
  }
  function ddBars(host,vals,ylab){
    const g0=ddSetup(host,760,300),ctx=g0.ctx,W=g0.W,H=g0.H;
    const mx=Math.max.apply(null,vals.map(Math.abs))||1;
    const g=ddAxes(ctx,W,H,[0,vals.length],[-mx,mx],'通道序号',ylab||'σ',false);
    const bw=Math.max(1.2,(g.R-g.L)/vals.length*0.6);
    vals.forEach(function(v,i){
      const x=g.sx(i+0.5),y0=g.sy(0),y1=g.sy(Math.max(-mx,Math.min(mx,v)));
      const mag=Math.abs(v);
      ctx.fillStyle=mag>2?'#a3453b':mag>1?'#c08a2e':'#17657f';
      ctx.fillRect(x-bw/2,Math.min(y0,y1),bw,Math.abs(y1-y0)||1);
    });
  }
  async function ddPreview(file,btn){
    document.querySelectorAll('#dd-tree button.sel').forEach(function(x){x.classList.remove('sel')});
    if(btn)btn.classList.add('sel');
    const host=$('result-body');
    const panel=E('div',undefined,'dd-preview');
    panel.append(E('h3',file.path),E('small',file.size+' 字节 · dd/'+file.path));
    host.replaceChildren(panel);
    try{
      const d=await api('archive-magnetic-dd-file?'+new URLSearchParams({case_id:cid(),path:file.path}));
      if(d.grid&&d.psi)ddContour(panel,d.grid.r,d.grid.z,d.psi,'R / m','Z / m');
      else if(d.q&&d.psi)ddLineChart(panel,d.psi,d.q,'ψN','q',{});
      else if(d.pressure&&d.psi)ddLineChart(panel,d.psi,d.pressure.map(function(v){return v/1000}),'ψN','p / kPa',{});
      else if(d.f&&d.psi)ddLineChart(panel,d.psi,d.f,'ψN','F / T·m',{});
      else if(d.j_tor&&d.psi)ddLineChart(panel,d.psi,d.j_tor,'ψN','j / A·m⁻²',{});
      else if(d.r&&d.z)ddLineChart(panel,d.r,d.z,'R / m','Z / m',{equal:true});
      else if(d.channels&&d.channels.length&&d.channels[0]&&d.channels[0].sigma!=null)ddBars(panel,d.channels.map(function(c){return c.sigma}),'σ');
      else panel.append(E('pre',JSON.stringify(d,null,1).slice(0,3000)));
    }catch(e){ panel.append(E('p',e.message,'error')) }
  }  function render(){if(!doc)return;header();const nav=$('progress');nav.replaceChildren();steps.forEach(([label],i)=>{const button=B(label,()=>go(i),i===stage?'active':'');button.append(E('b','0'+(i+1)));nav.append(button)});$('stage-index').textContent=`阶段 ${stage+1} / 5`;$('stage-title').textContent=steps[stage][1];$('stage-lead').textContent=steps[stage][2];$('stage-body').replaceChildren();[source,processing,solverInput,runReview,results][stage]();$('tab-result').disabled=!resultReady();$('prev').disabled=stage===0;$('next').hidden=stage===4;$('next').textContent=stage===4?'':stage===3?'查看结果':'继续：'+steps[stage+1][0];$('next').disabled=(stage===0&&!finishedSource())||(stage===1&&(!adopted()||channelDirty()))||(stage===2&&!adopted())||(stage===3&&!resultReady());$('footer-status').textContent=`分析记录 ${cid()} · ${names[state()]||state()}`}
  async function go(i){stage=i;try{await ensureData();render();window.scrollTo(0,0)}catch(e){error(e)}}
  function source(){const body=$('stage-body'),c=doc.case,s=doc.status;body.append(E('p','本次只接受所选炮号和时刻的实际实验读取。修改任一项需建立新分析。','question'));
    body.append(facts([['装置与炮号',`EAST ${c.shot}`],['目标时刻',`${c.time_s.toFixed(3)} s，处理窗 ±5 ms`],['实验来源','EAST MDSplus · east / pcs_east'],['磁测链','east'],['通道方案',channelPolicy()],['输入制品身份',c.package_manifest_sha256]]));
    if(state()==='created'){note(body,'尚未读取实验波形。读取时不会使用 164437 的冻结观测值。');body.append(B('读取实验数据',()=>action('archive-magnetic-acquire',{case_id:cid()}),'primary'))}
    else if(state()==='acquiring'){note(body,'正在从实验数据树读取磁通环、探针、PF、Ip 和 TF。此步可能持续约一分钟。','running');body.append(B('停止取数',()=>stop(), 'secondary'))}
    else if(state()==='failed'||state()==='cancelled'){note(body,s.error||'当前分析已停止；请新建分析后重试。','error')}
    else{note(body,`原始窗口已保存并核对 · SHA256 ${s.raw_sha256}`,'ok');const q=doc.quality;body.append(facts([['按规则拟纳入的磁通环',q.active_counts.loops],['按规则拟纳入的磁探针',q.active_counts.probes],['PF 通道',q.active_counts.pf],['质量检查',q.checks.join('、')],['IMAS DD 版本',q.dd_version||'未记录'],['目标数据获取耗时',fmt(q.source_fetch_s)+' s']]));body.append(E('p','来源节点、时间窗和每道原始波形可在“处理与质量”逐一查看。','hint'))}
  }
  function processing(){const body=$('stage-body');if(!finishedSource()){note(body,state()==='failed'?doc.status.error:'先完成实验取数。','error');body.append(B('去读取实验数据',()=>go(0)));return}const q=doc.quality;body.append(E('p','处理规则：目标时刻 ±5 ms 均值；磁测先扣除 −6.9 至 −6.1 s 的线性基线与漂移。PF、Ip 不做该漂移修正。','question'));for(const warning of q.warnings)note(body,warning,'');body.append(facts([['质量状态',q.passed?'处理检查通过':'未通过'],['按规则拟纳入求解',`${q.active_counts.loops} 环＋${q.active_counts.probes} 探针`],['规则预设排除的通道',q.inactive_count],['通道规则',q.read_rules.length+' 条已解析规则'],['掩码／权重身份',q.mask_sha256],['本次处理结果身份',doc.status.diagnostics_sha256]]));
    renderWeights(body,q);
    const picker=E('div',undefined,'channel-picker'),label=E('label','选择磁通环或磁探针'),select=E('select');const rows=q.channels.filter(x=>x.kind==='loops'||x.kind==='probes');for(const r of rows){const o=new Option(`${r.node} · ${r.role==='fit'?'拟纳入':'预设排除'} · ${r.samples} 点`,slotId(r));select.add(o)}if(!rows.some(r=>slotId(r)===channelSlot)){const first=rows.find(r=>r.source_key===channelKey)||rows.find(r=>r.role==='fit')||rows[0];channelSlot=first?slotId(first):null;channelKey=first?.source_key}select.value=channelSlot;select.onchange=()=>{channelSlot=select.value;channelKey=rows.find(r=>slotId(r)===channelSlot)?.source_key;channel=null;renderChannel()};label.append(select);picker.append(label);body.append(picker);
    const host=E('div');host.id='channel-host';body.append(host);renderChannel();
    if(state()==='acquired'){const field=E('div',undefined,'field'),lab=E('label','采纳依据'),noteInput=E('textarea');noteInput.id='adopt-note';noteInput.placeholder='记录已检查的通道、异常和仍存在的限制';lab.append(noteInput);field.append(lab);body.append(field);const confirm=B('确认处理结果，用于本次计算',()=>{if(channelDirty()){error('请先保存通道修改');return}const note=$('adopt-note').value.trim();action('archive-magnetic-adopt',{case_id:cid(),note})},'primary');confirm.id='adopt-input';confirm.disabled=channelDirty();body.append(confirm)}
    else if(doc.adoption){note(body,'已采纳 · '+doc.adoption.note,'ok')}
  }
  const slotId = r => r.channel_id || `${r.kind}:${r.index}`;
  function magneticRows(){return (doc?.quality?.channels||[]).filter(r=>r.kind==='loops'||r.kind==='probes')}
  function channelDirty(){return !!channelDraft && channelDraft.caseId===cid() && magneticRows().some(r=>channelDraft.values[slotId(r)]!==r.weight)}
  function channelPolicy(){return (doc?.quality?.channel_customized?'自定义通道；默认来源：':'默认通道来源：')+(doc?.case.mask_profile==='m02_pinned'?'164437 历史配置':'装置规则（探索）')}
  function renderWeights(body,q){
    const rows=magneticRows(),editable=['acquired','adopted','waiting_review','reviewed'].includes(state());
    if(!channelDraft||channelDraft.caseId!==cid()||channelDraft.hash!==doc.status.diagnostics_sha256)channelDraft={caseId:cid(),hash:doc.status.diagnostics_sha256,values:Object.fromEntries(rows.map(r=>[slotId(r),r.weight]))};
    body.append(E('h3','通道选择与权重'));
    body.append(E('p','已填入当前方案默认值，不修改即可使用。勾选决定是否计划纳入；探针权重越大，对拟合的影响越强。0 表示不纳入。这里的权重不是测量误差 σ。','hint'));
    body.append(E('p','当前内核：磁通环只支持 0／1，因此用勾选开关；探针可输入非负权重。内核仍会检查装置规则和重复节点，实际拟合通道以运行结果为准。','hint'));
    const toolbar=E('div',undefined,'weight-toolbar'),search=E('input'),filter=E('select');search.type='search';search.placeholder='搜索通道名，例如 FL1A';search.setAttribute('aria-label','搜索通道');
    for(const [v,t] of [['all','全部通道'],['fit','本次拟纳入'],['changed','仅看已修改'],['missing','样本不足']])filter.add(new Option(t,v));filter.setAttribute('aria-label','筛选通道');toolbar.append(search,filter);body.append(toolbar);
    const wrap=E('div',undefined,'weight-scroll'),table=E('table',undefined,'ledger weight-table'),thead=E('thead'),tr=E('tr');
    for(const title of ['通道','类型','默认设置','本次参与','本次权重','数据检查','波形'])tr.append(E('th',title));thead.append(tr);table.append(thead);const tbody=E('tbody');table.append(tbody);wrap.append(table);body.append(wrap);
    const elements=[];
    function refreshFilter(){for(const x of elements){const w=channelDraft.values[x.key];x.row.hidden=!(x.name.toLowerCase().includes(search.value.trim().toLowerCase())&&(filter.value==='all'||filter.value==='fit'&&w>0||filter.value==='changed'&&w!==x.saved||filter.value==='missing'&&!x.eligible))}}
    function refreshSummary(){const changed=rows.filter(r=>channelDraft.values[slotId(r)]!==r.weight).length;const counts=['loops','probes'].map(k=>rows.filter(r=>r.kind===k&&channelDraft.values[slotId(r)]>0).length);summary.textContent=`本次计划：${counts[0]} 环＋${counts[1]} 探针 · ${changed} 道修改尚未保存`;
      save.disabled=!editable||!changed||savingChannels;const adopt=$('adopt-input');if(adopt)adopt.disabled=!!changed||savingChannels;if(stage===1)$('next').disabled=!adopted()||!!changed;refreshFilter()}
    for(const r of rows){const key=slotId(r),row=E('tr'),check=E('input'),weight=E('input'),eligible=r.samples>=2&&(!r.drift||r.baseline_samples>=3),defaultWeight=r.default_weight??r.weight;let lastPositive=channelDraft.values[key]>0?channelDraft.values[key]:defaultWeight>0?defaultWeight:1;
      row.dataset.channelId=key;row.append(E('td',r.node),E('td',r.kind==='loops'?'磁通环':'探针'),E('td',(defaultWeight>0?'纳入 · ':'排除 · ')+defaultWeight));
      check.type='checkbox';check.checked=channelDraft.values[key]>0;check.disabled=!editable||!eligible;check.setAttribute('aria-label',r.node+' 本次参与');const checkCell=E('td');checkCell.append(check);row.append(checkCell);
      weight.type='number';weight.min='0';weight.step=r.kind==='loops'?'1':'any';if(r.kind==='loops')weight.max='1';weight.value=String(channelDraft.values[key]);weight.readOnly=r.kind==='loops';weight.disabled=!editable||!eligible||!check.checked;weight.setAttribute('aria-label',r.node+' 本次权重');const weightCell=E('td');weightCell.append(weight);row.append(weightCell);
      row.append(E('td',eligible?`目标 ${r.samples} 点 / 基线 ${r.baseline_samples} 点`:'样本不足，不能纳入'));const wave=E('td');wave.append(B('查看',()=>{channelKey=r.source_key;channelSlot=key;channel=null;const picker=document.querySelector('.channel-picker select');if(picker)picker.value=channelSlot;renderChannel();$('channel-host')?.scrollIntoView({block:'start',behavior:'smooth'})}));row.append(wave);tbody.append(row);
      check.onchange=()=>{if(check.checked)channelDraft.values[key]=r.kind==='loops'?1:lastPositive;else{if(channelDraft.values[key]>0)lastPositive=channelDraft.values[key];channelDraft.values[key]=0}weight.value=String(channelDraft.values[key]);weight.disabled=!check.checked;refreshSummary()};
      weight.oninput=()=>{const n=weight.valueAsNumber;channelDraft.values[key]=n;check.checked=Number.isFinite(n)&&n>0;if(n>0)lastPositive=n;refreshSummary()};
      elements.push({key,row,name:r.node,saved:r.weight,eligible,check,weight});
    }
    const summary=E('p',undefined,'read-only'),actions=E('div',undefined,'inline-actions');summary.id='weight-summary';body.append(summary);
    const reset=B('恢复方案默认值',()=>{for(const r of rows)channelDraft.values[slotId(r)]=r.default_weight??r.weight;for(const e of elements){const w=channelDraft.values[e.key];e.check.checked=w>0;e.weight.value=String(w);e.weight.disabled=!editable||!e.eligible||w<=0}refreshSummary()});reset.disabled=!editable;
    const save=B('保存修改为新修订',async()=>{if(savingChannels)return;const editingCase=cid();const selections=rows.map(r=>({channel_id:slotId(r),weight:channelDraft.values[slotId(r)]}));if(selections.some(x=>!Number.isFinite(x.weight)||x.weight<0)){error('请填写有限的非负权重');return}savingChannels=true;refreshSummary();try{const next=await api('archive-magnetic-channels',{case_id:cid(),diagnostics_sha256:doc.status.diagnostics_sha256,channels:selections});savingChannels=false;channelDraft=null;await openCase(next.case.case_id)}catch(e){error(e)}finally{savingChannels=false;if(channelDraft?.caseId===editingCase)refreshSummary()}},'primary');save.id='save-channel-weights';actions.append(reset,save);body.append(actions);
    body.append(E('p',editable?'修改会另存为新修订，并要求重新确认输入；原始波形可复用，已有结果保持对应原设置。':'求解运行中不能修改通道。完成后可另存修订调整。','hint'));
    search.oninput=refreshFilter;filter.onchange=refreshFilter;refreshSummary();
  }

  function renderChannel(){const host=$('channel-host');if(!host||!channelKey)return;host.replaceChildren();if(channel?.key===channelKey&&channel?.slot===channelSlot&&channel?.caseId===cid()){showChannel(host,channel.data);return}host.append(E('p','正在读取所选通道的原始窗口…','hint'));const key=channelKey,slot=channelSlot,caseId=cid();api('archive-magnetic-channel?'+new URLSearchParams({case_id:caseId,key,...(slot?{channel_id:slot}:{})})).then(data=>{if(key!==channelKey||slot!==channelSlot||caseId!==cid()||!$('channel-host'))return;channel={key,slot,caseId,data};host.replaceChildren();showChannel(host,data)}).catch(error)}
  function showChannel(host,d){const r=d.channel;host.append(facts([['来源节点',`${r.tree} / ${r.node}`],['运行前通道规则',r.role==='fit'?'拟纳入求解':'预设排除'],['已保存的本次权重',fmt(r.weight)],['目标窗样本',r.samples],['炮前样本',d.baseline_samples],['处理后的求解值',fmt(d.processed_value)],['单位',r.kind==='loops'?'Wb/rad':'T']]));const plots=E('div',undefined,'plot-grid');for(const [title,values] of [['原始波形',d.target_y],['处理后波形',d.processed_y]]){const fig=E('figure'),canvas=E('canvas');canvas.width=650;canvas.height=260;fig.append(canvas,E('figcaption',title+' · '+(r.kind==='loops'&&title==='处理后波形'?'Wb/rad':r.kind==='probes'?'T':'原始节点单位')));plots.append(fig);requestAnimationFrame(()=>drawLine(canvas,d.target_t,values,title))}host.append(plots)}
  function solverInput(){const body=$('stage-body');if(!adopted()){note(body,'请先检查并采纳处理结果。','error');body.append(B('返回处理与质量',()=>go(1)));return}const d=input?.diagnostics;const m=d?.inputs?.measurements,o=d?.inputs?.options;if(!m){note(body,'正在读取已采纳输入…');return}body.append(E('p','这份输入保留 M 档纯磁配方；未加入压力、TS、POINT 或 q₀ 目标。','question'));const grid=E('div',undefined,'summary');for(const [k,v] of [['计划提交的磁测观测',`${doc.quality.active_counts.loops} 环＋${doc.quality.active_counts.probes} 探针`],['电流／环向场',`Ip ${fmt(m.plasma)} A · TF ${fmt(m.tf?.f_vac_Tm)} T·m`],['PF 与数值设置',`${m.brsp.length} 组 PF · ${o.scan} 扫描`]]){const box=E('div');box.append(E('b',k),E('span',v));grid.append(box)}body.append(grid);body.append(facts([['实际炮号／时间',`${m.shot} / ${m.time_s.toFixed(3)} s`],['通道方案',channelPolicy()],['读取与处理来源',d.source.kind+' / '+d.source.tree],['数据版本',doc.adoption.diagnostics_sha256],['原始窗口身份',doc.adoption.raw_sha256],['采纳说明',doc.adoption.note],['内核制品身份',doc.case.package_manifest_sha256]]));if(doc.status.actual_input_sha256)note(body,'原生求解器实际装配输入 SHA256：'+doc.status.actual_input_sha256,'ok');else note(body,'以上是已确认的输入数据；运行时会保存求解器实际使用的最终输入，便于核对。');body.append(E('p',channelPolicy()+'。本次实际选择和权重可在“处理与质量”的通道表查看；权重不会随时刻自动重新标定。','callout'))}
  function runReview(){const body=$('stage-body'),s=doc.status;if(!adopted()){note(body,'先完成数据读取、质量检查和输入采纳。','error');body.append(B('返回数据处理',()=>go(1)));return}body.append(E('p','运行前核对输入身份、掩码及科学限制。点击运行后，服务才会调用独立原生 M 档求解器。','question'));body.append(facts([['炮号／时刻',`${doc.case.shot} / ${doc.case.time_s.toFixed(3)} s`],['按规则拟纳入的磁道数',doc.quality.active_counts.loops+doc.quality.active_counts.probes],['已采纳输入 SHA256',doc.adoption.diagnostics_sha256],['内核版本 SHA256','f2632102e950788f96de324bfd7b6c9152604eb72b9ce774613022c29f3ffb94']]));
    if(state()==='adopted')body.append(B('运行纯磁求解',()=>action('archive-magnetic-execute',{case_id:cid()}),'primary'));
    else if(state()==='running'){note(body,'原生求解正在运行。结果会保存实际输入和求解器身份。','running');body.append(B('停止求解',()=>stop()))}
    else if(state()==='failed'||state()==='cancelled'){note(body,s.error||'计算已停止。','error');if(state()==='failed')body.append(B('重试本次求解（旧产物存档）',()=>action('archive-magnetic-retry',{case_id:cid()}),'primary'))}
    else{showVerdict(body,s,result?.physics_check,result?.failure);body.append(E('p','人工审阅应判断这次输入与结果能否用于后续分析；不会授予实验物理资格。','callout'));if(state()==='waiting_review'){const choices=E('div',undefined,'review-choice');for(const [value,label] of [['accept','可用于本次分析'],['reject','退回本次结果']]){const l=E('label'),i=E('input');i.type='radio';i.name='review-decision';i.value=value;const canAccept=s.gate?.state==='passed'&&(doc.case.mask_profile!=='device_default'||doc.quality?.channel_customized);if(value===(canAccept?'accept':'reject'))i.checked=true;if(value==='accept'&&!canAccept)i.disabled=true;l.append(i,E('span',label));choices.append(l)}body.append(choices);const field=E('div',undefined,'field'),l=E('label','审阅说明'),textarea=E('textarea');textarea.id='review-note';textarea.placeholder='写下数值、输入和物理限制的判断';l.append(textarea);field.append(l);body.append(field);body.append(B('保存审阅结论',()=>{const accepted=document.querySelector('input[name=review-decision]:checked')?.value==='accept';action('archive-magnetic-review',{case_id:cid(),accepted,note:$('review-note').value.trim()})},'primary'))}else note(body,'审阅结论：'+(s.review?.accepted_for_analysis?'可用于本次分析':'已退回')+'；'+s.review?.note,s.review?.accepted_for_analysis?'ok':'error')}
    const details=E('details'),summary=E('summary','查看任务与原生日志'),pre=E('pre','正在读取日志…','log');details.append(summary,pre);details.ontoggle=()=>{if(details.open)api('archive-magnetic-log?'+new URLSearchParams({case_id:cid(),kind:'native'})).then(d=>{pre.textContent=d.text||'本阶段尚无原生日志'}).catch(e=>pre.textContent=e.message)};body.append(details)
  }
  function results(){const body=$('stage-body');if(resultReady()&&result){const go=B('打开结果页 →',()=>switchTab('result'),'primary');body.append(go);failureBlock(body,result.failure)}if(!resultReady()||!result){note(body,'本次分析尚无可审阅的求解结果。');body.append(B('返回运行阶段',()=>go(3)));return}const f=result.facts;body.append(E('p','先区分“数值收敛”与“实验物理资格”。下面图表和指标均来自本次保存的原生结果。','question'));showVerdict(body,result.status,result.physics_check);if(result.solver_message)note(body,'原生求解器：'+result.solver_message,'error');const metrics=E('div',undefined,'metrics');for(const [label,value] of [['迭代次数',f.iterations],['最终残差',f.residual],['轴上 q₀',f.q0],['q₉₅',f.q95],['磁轴 R / m',f.axis_r],['磁 χ²',f.chi2_mag],['求解器实际拟合磁道',f.n_mag_rows]]){const x=E('div',undefined,'metric');x.append(E('b',label),E('strong',fmt(value)));metrics.append(x)}body.append(metrics);if(window.EQP&&result.profiles&&result.grid){const h=E('div',undefined,'eqp-grid');body.append(h);requestAnimationFrame(()=>EQP.render(h,result))}else if(result.boundary?.length&&result.q?.x?.length){const plots=E('div',undefined,'plot-grid');const bound=E('figure'),bc=E('canvas');bc.width=650;bc.height=370;bound.append(bc,E('figcaption','LCFS 边界 · R/Z [m]'));plots.append(bound);const qfig=E('figure'),qc=E('canvas');qc.width=650;qc.height=370;qfig.append(qc,E('figcaption','安全因子 q(ψN)'));plots.append(qfig);body.append(plots);requestAnimationFrame(()=>{drawPairs(bc,result.boundary,'R / m','Z / m');drawLine(qc,result.q.x,result.q.q,'q(ψN)')})}else note(body,'本次没有收敛的磁面或 q 剖面；不能绘制结果曲线。','error');
        const rows=[...(result.channels?.loops||[]),...(result.channels?.probes||[])].filter(x=>x.used).sort((a,b)=>Math.abs(b.sigma)-Math.abs(a.sigma)).slice(0,12);if(rows.length)body.append(E('h3','加权残差较大的已使用通道'));const table=E('table',undefined,'ledger'),head=E('tr');['通道','残差 / σ','来源动作'].forEach(x=>head.append(E('th',x)));const thead=E('thead');thead.append(head);table.append(thead);const tb=E('tbody');for(const row of rows){const tr=E('tr');tr.append(E('td',row.name),E('td',fmt(row.sigma)));const td=E('td'),link=B('回到观测与处理',()=>{const c=doc.quality.channels.find(x=>x.node===row.name);if(c){channelKey=c.source_key;channelSlot=slotId(c);channel=null;go(1)}},'secondary');td.append(link);tr.append(td);tb.append(tr)}table.append(tb);if(rows.length)body.append(table);for(const line of Object.values(result.interpretation))note(body,line);const links=E('div',undefined,'result-links');links.append(B('返回实验来源',()=>go(0)),B('返回处理质量',()=>go(1)),B('核对求解输入',()=>go(2)));body.append(links);body.append(facts([['结果 SHA256',result.status.result_sha256],['实际原生输入 SHA256',result.status.actual_input_sha256],['独立原生库 SHA256',result.identity.library_sha256]]))
  }
  function drawLine(canvas,x,y,label){if(!canvas||!x?.length||!y?.length)return;const g=canvas.getContext('2d'),w=canvas.width,h=canvas.height;g.clearRect(0,0,w,h);let xmin=Math.min(...x),xmax=Math.max(...x),ymin=Math.min(...y),ymax=Math.max(...y);if(xmin===xmax)xmax=xmin+1;if(ymin===ymax){const p=Math.abs(ymin)*.05||1;ymin-=p;ymax+=p}const X=v=>60+(v-xmin)/(xmax-xmin)*(w-85),Y=v=>h-40-(v-ymin)/(ymax-ymin)*(h-75);g.strokeStyle='#cadbe1';g.strokeRect(60,25,w-85,h-65);g.fillStyle='#405f6c';g.font='12px sans-serif';g.fillText(label,65,18);g.fillText(fmt(ymax),4,32);g.fillText(fmt(ymin),4,h-40);g.fillText(fmt(xmin),60,h-20);g.fillText(fmt(xmax),w-100,h-20);g.strokeStyle='#176e87';g.lineWidth=2;g.beginPath();x.forEach((v,i)=>i?g.lineTo(X(v),Y(y[i])):g.moveTo(X(v),Y(y[i])));g.stroke()}
  function drawPairs(canvas,pairs,xlabel,ylabel){if(!pairs?.length)return;drawLine(canvas,pairs.map(x=>x[0]),pairs.map(x=>x[1]),xlabel+' / '+ylabel)}
  async function stop(){if(!window.confirm('停止当前实验取数或求解？已保存的其他分析不受影响。'))return;await action('archive-magnetic-cancel',{case_id:cid()})}
  const sceneSpecs={
    magnetic:{title:'单次反演',description:'完成一次内层求解（内部仍有迭代），不执行外环。压力来源可选，但只有“无（仅磁测）”已接通当前在线 M 档；拟合出的 p′/FF′ 不能当作已验证的物理压力。',rules:[['磁测预处理','目标时刻 ±5 ms；磁测扣除炮前线性漂移'],['PF、Ip、TF','按装置映射装配；不做物理源项外环']]},
    geometry:{title:'诊断重映射',description:'新磁面下重映射诊断坐标，压力来源在外环中保持不变。这是几何自洽层次；当前尚无完整可运行链。',rules:[['磁测与诊断位置','需要已核对的测量与位置映射'],['压力来源冻结','外环只更新诊断坐标，不重算物理量']]},
    physics:{title:'源项重算',description:'新磁面下从诊断重算压力或电流等物理来源。这是物理自洽层次；当前尚无完整可运行闭环。',rules:[['磁测与剖面来源','需要可追溯的测量、误差和模型来源'],['外环收敛','更新物理来源后再求解并审阅']]},
    fixed:{title:'固定边界正解',description:'给定解析边界和源项，由原生内核求解；不读取实验炮号与目标时刻。当前开放 Solov’ev 合成示范。',rules:[['固定解析边界','给定 ψ=0 边界'],['给定 p′ 与 FF′','正向求解输入，不做实验反演'],['网格分辨率','可选 33、65 或 129']]}
  };
  const updateLabels={point_density:'诊断位置重映射',thermal_pressure:'热压力',fast_pressure:'快离子压力',bootstrap_current:'自举电流'};
  function updateMask(){const pinned=$('mask').querySelector('[value=m02_pinned]');pinned.disabled=Number($('shot').value)!==164437;if(pinned.disabled)$('mask').value='device_default'}
  function selectedUpdates(){return [...document.querySelectorAll('#update-controls input:checked')].map(x=>x.value)}
  function classify(mode,updates){if(mode==='none')return 'single_pass';if(updates.some(x=>['thermal_pressure','fast_pressure','bootstrap_current','external_current'].includes(x)))return 'source_feedback';return 'remap'}
  function ruleDraft(){const scene=$('scenario').value,pressure=$('pressure-source').value,updates=scene==='magnetic'?[]:scene==='geometry'?['point_density']:selectedUpdates(),mode=scene==='magnetic'?'none':scene==='geometry'?'point_density':'source_feedback';return {schema:'fylite.eq.scene-draft/1',device:$('device').value,shot:scene==='fixed'?null:Number($('shot').value),time_s:scene==='fixed'?null:Number($('time').value),task:scene==='fixed'?'forward_fixed_boundary':'magnetic_reconstruction',selection:scene,class:scene==='fixed'?'forward_fixed_boundary':classify(mode,updates),pressure:{source:scene==='fixed'?'not_applicable':pressure,constraint:scene==='fixed'?'not_applicable':pressure==='unconstrained'?'none':$('pressure-constraint').value,update:updates.includes('thermal_pressure')?'recompute':'never'},current:{source:scene==='fixed'?'not_applicable':scene==='physics'?$('current-source').value:'free_pprime_ffprime',update:updates.includes('bootstrap_current')?'recompute':'never'},outer:{mode:scene==='fixed'?'none':mode,updates},mask_profile:scene==='magnetic'&&pressure==='unconstrained' ? $('mask').value:null,grid:scene==='fixed'?Number($('grid').value):null,runnable:scene==='fixed'||scene==='magnetic'&&pressure==='unconstrained'} }
  function draftIssue(d){if(d.selection==='fixed')return [33,65,129].includes(d.grid)?null:'请选择支持的网格';if(!Number.isInteger(d.shot)||d.shot<=0||!Number.isFinite(d.time_s)||d.time_s<=0)return '请输入有效炮号和目标时刻';if(d.selection==='physics'){const physical=d.outer.updates.filter(x=>['thermal_pressure','fast_pressure','bootstrap_current'].includes(x));if(!physical.length)return '源项重算至少需要勾选一项：热压力、快离子压力或自举电流';if(d.outer.updates.includes('thermal_pressure')&&!['diagnostic_thermal','thermal_plus_fast'].includes(d.pressure.source))return '导入总压力没有分量来源，不能逐轮重算；请改选诊断合成';if(d.outer.updates.includes('fast_pressure')&&d.pressure.source!=='thermal_plus_fast')return '快离子压力重算需要压力来源为“诊断合成 + 快离子”';if(d.outer.updates.includes('bootstrap_current')&&d.current.source!=='bootstrap_plus_residual')return '自举电流重算需要选择自举＋剩余电流模型'}if(d.selection==='geometry'&&d.class!=='remap')return '诊断重映射只更新诊断坐标，不重算物理量；请改用源项重算';return null}
  function updateSceneState(){const d=ruleDraft(),issue=draftIssue(d),scene=d.selection,available=d.runnable&&!issue;$('pressure-constraint-wrap').hidden=scene==='fixed'||d.pressure.source==='unconstrained';$('scene-plan').textContent=scene==='fixed'?'固定边界正解 · 网格 '+d.grid+' × '+d.grid: `方案分类 ${{single_pass:'单次反演',remap:'诊断重映射',source_feedback:'源项重算'}[d.class]} · 外环更新：${d.outer.updates.map(x=>updateLabels[x]).join('、')||'无'} · 压力：${$('pressure-source').selectedOptions[0].textContent}`;$('create').disabled=!available;$('download-draft').hidden=available||scene==='fixed';$('download-draft').disabled=!!issue;$('scene-availability').textContent=issue|| (available?(scene==='fixed'?'已接通固定边界正解；下一页保存个人配置后运行。':'已接通实验纯磁 M 档；逐步读取、采纳、运行。'):'仅提供配置草稿；当前没有可运行求解链。');$('scene-availability').classList.toggle('unavailable',!available);$('create').textContent=scene==='fixed'?'进入固定边界正解':available?'建立纯磁分析':'当前组合尚未接入'}
  function renderScene(){const selected=$('scenario').value,spec=sceneSpecs[selected],forward=selected==='fixed';$('device').value=forward?'analytic':'EAST';$('device').querySelector('[value=EAST]').disabled=forward;$('device').querySelector('[value=analytic]').disabled=!forward;$('shot').disabled=forward;$('time').disabled=forward;$('scene-controls').hidden=forward;$('magnetic-rules').hidden=selected!=='magnetic'||$('pressure-source').value!=='unconstrained';$('fixed-rules').hidden=!forward;$('scene-title').textContent=spec.title;$('scene-description').textContent=spec.description;const list=$('scene-options');list.replaceChildren();for(const [name,detail] of spec.rules){const label=E('div',undefined,'scene-option locked'),mark=E('span','✓'),txt=E('span');txt.append(E('strong',name),E('small',detail));label.append(mark,txt);list.append(label)}const updates=$('update-controls');updates.replaceChildren();updates.hidden=selected==='magnetic'||forward;if(selected==='geometry'||selected==='physics'){const keys=selected==='geometry'?['point_density']:Object.keys(updateLabels);for(const key of keys){const label=E('label',undefined,'scene-option'),box=E('input'),span=E('span');box.type='checkbox';box.value=key;box.checked=selected==='geometry'||key==='thermal_pressure';box.disabled=selected==='geometry';box.onchange=updateSceneState;span.append(E('strong',updateLabels[key]),E('small',selected==='geometry'?'必选；取消即退回单次反演':'写入外环更新项'));label.append(box,span);updates.append(label)}}$('current-source-wrap').hidden=selected!=='physics';$('start-error').textContent='';updateMask();updateSceneState()}
  $('scenario').onchange=renderScene;$('shot').onchange=()=>{updateMask();updateSceneState()};$('time').onchange=updateSceneState;$('device').onchange=renderScene;$('pressure-source').onchange=()=>{$('magnetic-rules').hidden=$('scenario').value!=='magnetic'||$('pressure-source').value!=='unconstrained';updateSceneState()};$('pressure-constraint').onchange=updateSceneState;$('current-source').onchange=updateSceneState;$('grid').onchange=updateSceneState;$('mask').onchange=updateSceneState;
  $('download-draft').onclick=()=>{const d=ruleDraft(),issue=draftIssue(d);if(issue){$('start-error').textContent=issue;return}const url=URL.createObjectURL(new Blob([JSON.stringify(d,null,2)],{type:'application/json'})),a=E('a');a.href=url;a.download='fylite-equilibrium-scene-draft.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000)};
  $('create').onclick=async()=>{try{$('start-error').textContent='';const d=ruleDraft(),issue=draftIssue(d);if(issue)throw Error(issue);if(d.selection==='fixed'){location.href='../?nr='+encodeURIComponent(d.grid)+'#compute';return}if(!d.runnable)throw Error('当前组合尚未接通可运行求解链');if(d.device!=='EAST')throw Error('当前纯磁取数只支持 EAST');const dup=treeCases.filter(c=>String(c.shot)===String(d.shot)&&Math.abs(Number(c.time_s)-Number(d.time_s))<1e-6);
      if(dup.length&&!window.__allowDup){showDup(dup,d);return}
      window.__allowDup=false;
      const value=await api('archive-magnetic-create',{shot:d.shot,time_s:d.time_s,mask_profile:d.mask_profile});await openCase(value.case.case_id);await recent()}catch(e){$('start-error').textContent=e.message}};
  window.addEventListener('beforeunload',e=>{if(channelDirty()){e.preventDefault();e.returnValue=''}});
  renderScene();
  $('tree-new').onclick=()=>{try{history.replaceState(null,'',location.pathname)}catch(e){};$('back-start').click()};
  $('back-start').onclick=()=>{if(channelDirty()&&!window.confirm('通道修改尚未保存，是否离开当前记录？'))return;channelDraft=null;$('workspace').classList.remove('visible');$('start-view').hidden=false;recent()};
  $('prev').onclick=()=>go(Math.max(0,stage-1));$('next').onclick=()=>go(Math.min(4,stage+1));
  (async()=>{try{token=(await fetch('/fylite/eq/api/info').then(r=>r.json())).token;const info=await api('archive-magnetic-info');if(!info.readiness.ready)$('start-error').textContent='计算包未就绪：'+info.readiness.reason;await recent();const id=new URLSearchParams(location.search).get('case_id');if(id)await openCase(id)}catch(e){$('start-error').textContent='服务连接失败：'+e.message}})();
  let treeCases=[];
  let fileCat=null, fileCatCase=null;
  function treeMatchStatus(c,q){
    if(!q)return true;
    if(q==='running')return c.state==='running'||c.state==='acquiring';
    if(q==='failed')return c.state==='failed'||c.state==='cancelled';
    return c.state===q;
  }
  function paintTree(){
    const kw=($('tree-search')?.value||'').trim().toLowerCase();
    const st=$('tree-status')?.value||'';
    const filtered=treeCases.filter(c=>{
      if(!treeMatchStatus(c,st))return false;
      if(!kw)return true;
      return [c.case_id,String(c.shot),Number(c.time_s).toFixed(3),c.mask_profile||''].join(' ').toLowerCase().includes(kw);
    });
    const host=$('tree-body'),count=$('tree-count');
    if(treeCases.length&&!filtered.length){
      if(host){host.replaceChildren();host.append(E('p','没有匹配的算例。','tree-hint'))}
      if(count)count.textContent='0 / '+treeCases.length;
      return;
    }
    renderTreeRaw(filtered);
    if(count)count.textContent=filtered.length===treeCases.length?String(treeCases.length):filtered.length+' / '+treeCases.length;
  }
  let treeTimer=null;
  function maybePoll(){
    const active=treeCases.some(c=>c.state==='running'||c.state==='acquiring');
    if(active&&!treeTimer)treeTimer=setInterval(()=>{recent()},1500);
    if(!active&&treeTimer){clearInterval(treeTimer);treeTimer=null}
  }
  function renderTree(cases){
    treeCases=cases||[];
    const s=$('tree-search'),sel=$('tree-status');
    if(s&&!s.dataset.bound){s.dataset.bound='1';s.addEventListener('input',paintTree)}
    if(sel&&!sel.dataset.bound){sel.dataset.bound='1';sel.addEventListener('change',paintTree)}
    paintTree();
    maybePoll();
  }})();
