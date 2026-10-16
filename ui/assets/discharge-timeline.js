/* Native discharge result explorer; rendering and file import only. */
(function(root){
'use strict';
const FORMAT='fy-discharge-demo-v1';
const quantities={ip_a:['Ip 设定','MA',1e-6],w_th_j:['热储能','MJ',1e-6],p_aux_w:['辅助加热','MW',1e-6],beta_n:['βN','1',1],te_axis_ev:['轴心电子温度','keV',1e-3],ne_axis_m3:['轴心电子密度','10¹⁹ m⁻³',1e-19]};
function validate(data){
 if(!data||data.format!==FORMAT)throw Error('文件不是受支持的放电时序结果。');
 if(typeof data.device!=='string'||!Array.isArray(data.frames)||!data.frames.length)throw Error('结果缺少装置或时间切片。');
 let previous=-Infinity;
 const numbers=(a,n,label)=>{if(!Array.isArray(a)||(n!==undefined&&a.length!==n)||a.some(x=>!Number.isFinite(x)))throw Error(label+' 数据无效。');};
 data.frames.forEach((f,index)=>{
  if(!Number.isFinite(f.t)||f.t<=previous)throw Error('物理时刻必须有限且严格递增。');previous=f.t;
  if(f.globals&&Object.values(f.globals).some(x=>x!==null&&!Number.isFinite(x)))throw Error('全局时序包含非法读数。');
  if(f.profiles){const p=f.profiles;numbers(p.rho,undefined,'径向网格');if(p.rho.length<3||p.rho.some((x,i)=>i&&x<=p.rho[i-1]))throw Error('径向网格须递增。');for(const key of ['te','ti','ne','q','j_total','psi'])if(p[key]!==undefined)numbers(p[key],p.rho.length,key);}
  if(f.equilibrium){const e=f.equilibrium;numbers(e.r,undefined,'R 网格');numbers(e.z,undefined,'Z 网格');if(e.r.length<2||e.z.length<2)throw Error('平衡网格过小。');numbers(e.psi,e.r.length*e.z.length,'磁通');if(!Number.isFinite(e.psi_axis)||!Number.isFinite(e.psi_boundary))throw Error('磁通边界读数无效。');}
  if(f.current_profile){const c=f.current_profile;numbers(c.rho,undefined,'电流径向坐标');numbers(c.i_enclosed,c.rho.length,'包围电流');if(c.rho.length<2||c.rho.some((x,i)=>i&&x<=c.rho[i-1]))throw Error('电流径向坐标须递增。');}
  if(f.pf){numbers(f.pf.aturns,undefined,'PF');if(!Array.isArray(f.pf.names)||f.pf.names.length!==f.pf.aturns.length||f.pf.names.some(x=>typeof x!=='string'))throw Error('PF 通道映射无效。');}
 });return data;
}
root.FyDischargeTimeline={FORMAT,validate};
if(typeof document==='undefined')return;
const $=id=>document.getElementById(id),state={datasets:[],index:0,frame:0,timer:null};
const colors=['#1768aa','#d75c4b','#268878','#936bb0'];
function text(id,value){$(id).textContent=value;}
function number(x){return Number.isFinite(x)?(Math.abs(x)>=1e5||Math.abs(x)>0&&Math.abs(x)<1e-3?x.toExponential(2):x.toFixed(3).replace(/\.?0+$/,'')):'—';}
function canvas(id){const c=$(id),rect=c.getBoundingClientRect(),dpr=root.devicePixelRatio||1,w=Math.max(1,rect.width),h=Math.max(1,rect.height);c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);const ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);ctx.font='11px system-ui';return {ctx,w,h};}
function empty(id,message){const {ctx,w,h}=canvas(id);ctx.fillStyle='#587083';ctx.textAlign='center';ctx.fillText(message||'该时刻暂无数据',w/2,h/2);}
function plot(id,series,xlabel,ylabel,selected){
 const usable=series.filter(s=>Array.isArray(s.x)&&s.x.length&&s.x.length===s.y.length);if(!usable.length){empty(id);return;}
 const {ctx,w,h}=canvas(id),box={l:63,r:w-16,t:28,b:h-34};
 const xs=usable.flatMap(s=>s.x),ys=usable.flatMap(s=>s.y).filter(Number.isFinite);if(!ys.length){empty(id);return;}
 let xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);if(xmax===xmin)xmax=xmin+1;if(ymax===ymin){const pad=Math.max(1,Math.abs(ymax)*.05);ymin-=pad;ymax+=pad;}else{const pad=(ymax-ymin)*.08;ymin-=pad;ymax+=pad;}
 const X=x=>box.l+(x-xmin)/(xmax-xmin)*(box.r-box.l),Y=y=>box.b-(y-ymin)/(ymax-ymin)*(box.b-box.t);
 ctx.strokeStyle='#e3e9ee';ctx.fillStyle='#587083';ctx.textAlign='right';for(let i=0;i<=4;i++){const y=ymin+(ymax-ymin)*i/4;ctx.beginPath();ctx.moveTo(box.l,Y(y));ctx.lineTo(box.r,Y(y));ctx.stroke();ctx.fillText(number(y),box.l-7,Y(y)+4);}
 ctx.textAlign='center';for(let i=0;i<=4;i++){const x=xmin+(xmax-xmin)*i/4;ctx.fillText(number(x),X(x),box.b+17);}ctx.fillText(xlabel,(box.l+box.r)/2,h-3);ctx.textAlign='left';ctx.fillText(ylabel,5,14);
 usable.forEach((s,index)=>{ctx.strokeStyle=s.color||colors[index%colors.length];ctx.lineWidth=s.faint?1:2;ctx.globalAlpha=s.faint ? 0.3 : 1;ctx.beginPath();let active=false;s.x.forEach((x,i)=>{if(!Number.isFinite(s.y[i])){active=false;return;}if(active)ctx.lineTo(X(x),Y(s.y[i]));else{ctx.moveTo(X(x),Y(s.y[i]));active=true;}});ctx.stroke();ctx.globalAlpha=1;ctx.fillStyle=ctx.strokeStyle;ctx.fillText(s.name||'',box.l+index*90,16);});
 if(Number.isFinite(selected)){ctx.strokeStyle='#172b3b';ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(X(selected),box.t);ctx.lineTo(X(selected),box.b);ctx.stroke();ctx.setLineDash([]);}
}
function equilibrium(data,frame){
 const e=frame.equilibrium;if(!e){empty('equilibrium');text('equilibrium-caption','该时刻尚无平衡切片');return;}
 const {ctx,w,h}=canvas('equilibrium'),wall=data.geometry&&data.geometry.wall,coils=data.geometry&&data.geometry.coils||[];
 let rmin=e.r[0],rmax=e.r[e.r.length-1],zmin=e.z[0],zmax=e.z[e.z.length-1];
 coils.forEach(c=>{if(Number.isFinite(c.r)&&Number.isFinite(c.z)){rmin=Math.min(rmin,c.r-(c.width||0)/2);rmax=Math.max(rmax,c.r+(c.width||0)/2);zmin=Math.min(zmin,c.z-(c.height||0)/2);zmax=Math.max(zmax,c.z+(c.height||0)/2);}});
 const scale=Math.min((w-70)/(rmax-rmin),(h-50)/(zmax-zmin)),xc=(rmin+rmax)/2,zc=(zmin+zmax)/2,X=r=>w/2+(r-xc)*scale,Y=z=>h/2-(z-zc)*scale;
 const line=(r,z,color)=>{if(!r||!z||r.length!==z.length)return;ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.beginPath();r.forEach((v,i)=>i?ctx.lineTo(X(v),Y(z[i])):ctx.moveTo(X(v),Y(z[i])));ctx.stroke();};
 if(wall)line(wall.r,wall.z,'#687b88');
 const nr=e.r.length,nz=e.z.length;
 for(let level=1;level<=10;level++){const v=e.psi_axis+(e.psi_boundary-e.psi_axis)*level/10;if(e.psi_boundary===e.psi_axis)break;ctx.strokeStyle=level===10?'#d75c4b':'#79a8c8';ctx.lineWidth=level===10?1.8:.7;ctx.beginPath();for(let iz=0;iz<nz-1;iz++)for(let ir=0;ir<nr-1;ir++){
  const points=[[e.r[ir],e.z[iz],e.psi[iz*nr+ir]],[e.r[ir+1],e.z[iz],e.psi[iz*nr+ir+1]],[e.r[ir+1],e.z[iz+1],e.psi[(iz+1)*nr+ir+1]],[e.r[ir],e.z[iz+1],e.psi[(iz+1)*nr+ir]]],cross=[];
  for(let k=0;k<4;k++){const a=points[k],b=points[(k+1)%4];if((a[2]<v)!==(b[2]<v)){const t=(v-a[2])/(b[2]-a[2]);cross.push([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]);}}
  for(let k=0;k+1<cross.length;k+=2){ctx.moveTo(X(cross[k][0]),Y(cross[k][1]));ctx.lineTo(X(cross[k+1][0]),Y(cross[k+1][1]));}
 }ctx.stroke();}
 if(e.boundary)line(e.boundary.r,e.boundary.z,'#d75c4b');
 coils.forEach((c,i)=>{if(!Number.isFinite(c.r)||!Number.isFinite(c.z))return;ctx.fillStyle=colors[i%colors.length];ctx.globalAlpha=.7;ctx.fillRect(X(c.r)-(c.width||.05)*scale/2,Y(c.z)-(c.height||.05)*scale/2,(c.width||.05)*scale,(c.height||.05)*scale);ctx.globalAlpha=1;});
 if(e.axis&&Number.isFinite(e.axis.r)&&Number.isFinite(e.axis.z)){ctx.fillStyle='#172b3b';ctx.beginPath();ctx.arc(X(e.axis.r),Y(e.axis.z),3,0,Math.PI*2);ctx.fill();}
 ctx.fillStyle='#587083';ctx.textAlign='center';ctx.fillText('R [m]',w/2,h-4);ctx.textAlign='left';ctx.fillText('Z [m]',5,14);text('equilibrium-caption','磁通单位 Wb · 红线为边界 · '+nr+' × '+nz+' 网格');
}
function pf(frame){if(!frame.pf){empty('pf');return;}const p=frame.pf,{ctx,w,h}=canvas('pf'),count=p.aturns.length;if(!count){empty('pf','暂无 PF 通道');return;}const max=Math.max(1,...p.aturns.map(Math.abs)),left=52,right=w-12,top=24,bottom=h-47,mid=(top+bottom)/2,bar=(right-left)/count;ctx.strokeStyle='#d9e2e9';ctx.beginPath();ctx.moveTo(left,mid);ctx.lineTo(right,mid);ctx.stroke();p.aturns.forEach((value,i)=>{const y=mid-value/max*(bottom-top)/2;ctx.fillStyle=colors[i%colors.length];ctx.fillRect(left+i*bar+bar*.15,Math.min(mid,y),bar*.7,Math.max(1,Math.abs(y-mid)));ctx.save();ctx.translate(left+(i+.5)*bar,bottom+9);ctx.rotate(-.65);ctx.fillStyle='#587083';ctx.textAlign='right';ctx.fillText(p.names[i],0,0);ctx.restore();});ctx.fillStyle='#587083';ctx.fillText(number(max),4,top+3);ctx.fillText('0',35,mid+3);ctx.fillText(number(-max),4,bottom+3);}
function stop(){if(state.timer)clearInterval(state.timer);state.timer=null;text('play','播放');}
function render(){
 if(!state.datasets.length){['equilibrium','globals','pf','thermal','current'].forEach(id=>empty(id,'导入时序结果后显示'));return;}
 const data=state.datasets[state.index],frame=data.frames[state.frame],g=frame.globals||{},p=frame.profiles,initial=data.frames.find(x=>x.profiles)?.profiles;
 text('subtitle',data.device+' · '+(data.title||'原生建模时序'));text('time',number(frame.t)+' s');text('metric-ip',Number.isFinite(g.ip_a)?number(g.ip_a*1e-6)+' MA':'—');text('metric-w',Number.isFinite(g.w_th_j)?number(g.w_th_j*1e-6)+' MJ':'—');text('metric-power',Number.isFinite(g.p_aux_w)?number(g.p_aux_w*1e-6)+' MW':'—');text('metric-phase',(frame.phase||'模型')+' · '+(state.frame+1)+'/'+data.frames.length);
 const key=$('global-quantity').value,q=quantities[key];plot('globals',[{x:data.frames.map(f=>f.t),y:data.frames.map(f=>Number.isFinite(f.globals?.[key])?f.globals[key]*q[2]:NaN),name:q[0]}],'t [s]',q[1],frame.t);
 equilibrium(data,frame);pf(frame);
 const series=(key,name,factor,color)=>p&&p[key]?{x:p.rho,y:p[key].map(x=>x*factor),name,color}:null;
 let thermal=$('profile-quantity').value==='density'?[series('ne','ne',1e-19,colors[2])]:[series('te','Te',1e-3,colors[0]),series('ti','Ti',1e-3,colors[1])];
 for(const option of $('current-quantity').options)option.disabled=option.value==='i_enclosed'?!frame.current_profile:!p?.[option.value];
 if($('current-quantity').selectedOptions[0].disabled){const available=Array.from($('current-quantity').options).find(o=>!o.disabled);if(available)$('current-quantity').value=available.value;}
 const currentKey=$('current-quantity').value,currentUnit={i_enclosed:'MA',j_total:'MA/m²',q:'1',psi:'Wb'}[currentKey],currentFactor=['j_total','i_enclosed'].includes(currentKey)?1e-6:1;let current=currentKey==='i_enclosed'?(frame.current_profile?[{x:frame.current_profile.rho,y:frame.current_profile.i_enclosed.map(x=>x*1e-6),name:'I(ρ)',color:colors[0]}]:[]):[series(currentKey,{j_total:'j total',q:'q',psi:'ψ'}[currentKey],currentFactor,colors[0])];
 if($('compare').checked&&initial){thermal.forEach(s=>{if(s){const k=s.name==='ne'?'ne':s.name==='Te'?'te':'ti',factor=k==='ne'?1e-19:1e-3;if(initial[k])thermal.push({x:initial.rho,y:initial[k].map(x=>x*factor),color:s.color,faint:true});}});if(currentKey==='i_enclosed'){const c=data.frames.find(f=>f.current_profile)?.current_profile;if(c)current.push({x:c.rho,y:c.i_enclosed.map(x=>x*1e-6),name:'初态',faint:true});}else if(initial[currentKey])current.push({x:initial.rho,y:initial[currentKey].map(x=>x*currentFactor),name:'初态',faint:true});}
 plot('thermal',thermal.filter(Boolean),'ρ [m]',$('profile-quantity').value==='density'?'10¹⁹ m⁻³':'keV');plot('current',current.filter(Boolean),'ρ [m]',currentUnit);
 const diagnostics=data.meta?.initial_equilibrium_diagnostics;const diagnosticText=diagnostics?'\n初始 GS：收敛 '+(diagnostics.converged?.value===1?'是':'否')+'；残差 '+number(diagnostics.residual?.value)+'；目标边界 RMS 偏差 '+number(diagnostics.boundary_gap_rms?.value)+' m':'';text('scope',(data.meta?.model_scope||'结果未提供模型说明。')+diagnosticText);$('timeline').value=String(state.frame);
}
$('files').addEventListener('change',async event=>{stop();const accepted=[];let failures=[];for(const file of event.target.files){try{if(file.size>50*1024*1024)throw Error('文件超过 50 MB。');const data=validate(JSON.parse(await file.text()));accepted.push(data);}catch(error){failures.push(file.name+'：'+error.message);}}if(accepted.length){state.datasets.push(...accepted);state.index=state.datasets.length-accepted.length;state.frame=0;const select=$('datasets');select.replaceChildren(...state.datasets.map((data,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=data.device+' · '+(data.title||'时序结果');return option;}));select.value=String(state.index);select.disabled=false;$('play').disabled=false;$('timeline').disabled=false;$('timeline').max=String(state.datasets[state.index].frames.length-1);render();}text('status',failures.length?failures.join('；'):'已导入 '+accepted.length+' 个数据集。');$('status').classList.toggle('error',!!failures.length);});
$('datasets').addEventListener('change',()=>{stop();state.index=Number($('datasets').value);state.frame=0;$('timeline').max=String(state.datasets[state.index].frames.length-1);render();});$('timeline').addEventListener('input',()=>{state.frame=Number($('timeline').value);render();});$('play').addEventListener('click',()=>{if(state.timer){stop();return;}if(state.frame===state.datasets[state.index].frames.length-1)state.frame=0;text('play','暂停');state.timer=setInterval(()=>{const last=state.datasets[state.index].frames.length-1;if(state.frame>=last){stop();return;}state.frame++;render();},150);});['global-quantity','profile-quantity','current-quantity','compare'].forEach(id=>$(id).addEventListener('change',render));root.addEventListener('resize',render);render();
})(typeof window!=='undefined'?window:globalThis);
