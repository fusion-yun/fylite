"""Explicit fixed-map POINT postprocessing; native quadrature, archived linear fit.
No equilibrium feedback; never edits a run. BNEL units 1e19 m^-2, BPOLAR
units 1e19 T m^-2. Density coefficients and profiles use 1e19 m^-3.
"""
import ctypes
import json
import math
import random
from pathlib import Path


def basis(x, p):
    n=int(p['knecur'][0])
    if n!=3 or p['knefnc'][0]!=0 or p['kedgene'][0]!=1:
        raise ValueError('Only audited polynomial-three/edge density basis is supported')
    pedestal,width=p['tne_psin'][0],p['tne_width'][0]
    return [1-x**3,x-x**3,-(math.tanh((1-pedestal)/width)-math.tanh((x-pedestal)/width))]


def fit(a, b):
    # QR of the small weighted diagnostic design; not an equilibrium solver.
    q=[];r=[[0.0]*3 for _ in range(3)]
    for j in range(3):
        v=[row[j] for row in a]
        for k in range(j):
            r[k][j]=sum(x*y for x,y in zip(q[k],v))
            v=[x-r[k][j]*y for x,y in zip(v,q[k])]
        r[j][j]=math.sqrt(sum(x*x for x in v))
        if r[j][j]<1e-10:raise ValueError('Density design is rank deficient')
        q.append([x/r[j][j] for x in v])
    y=[sum(x*z for x,z in zip(col,b)) for col in q];c=[0.0]*3
    for j in range(2,-1,-1):c[j]=(y[j]-sum(r[j][k]*c[k] for k in range(j+1,3)))/r[j][j]
    return c


def native(k, request):
    raw=json.dumps(request,allow_nan=False).encode();code=b'code/chords'
    out=ctypes.c_void_p();size=ctypes.c_uint64()
    status=k.call(code,len(code),raw,len(raw),ctypes.byref(out),ctypes.byref(size))
    try:value=json.loads(ctypes.string_at(out,size.value)) if out.value else {}
    finally:
        if out.value:k.release(out,size.value)
    if status or 'refusal' in value:raise ValueError('Native chord refusal: '+str(value)[:500])
    result={name:value['fields'][name]['data'] for name in ('chord_nel19','chord_bpolar')}
    if not all(math.isfinite(x) for a in result.values() for x in a):raise ValueError('Nonfinite chord output')
    return result


def compute(w, root, run, document):
    assembly=w.scientific_views.artifact(w,run,'assemble');solved=w.scientific_views.artifact(w,run,'solve')
    e=assembly['effective']
    if e['shot']!=document['shot'] or abs(e['time_s']-document['time_s'])>1e-9:
        raise ValueError('POINT inputs do not match the selected shot/time')
    p=document['parameters'];g=assembly['config']['initial'];state=solved['result'];geom=state['geometry']
    if any(t!=0 for t in p['thetapol']):raise ValueError('Only audited horizontal POINT chords are supported')
    lock=root/'kernel.lock.json'
    if not lock.exists():lock=w.ROOT.parents[1]/'releases/kernel-rc3.lock.json'
    k=w.Kernel(root,w.read(lock))
    settings={'nw':len(g['r']),'nh':len(g['z']),'r_min':g['r'][0],'r_max':g['r'][-1],
              'z_min':g['z'][0],'z_max':g['z'][-1],'rows':0,'n_samples':801,'length':2.2}
    request={'settings':settings,'inputs':{'device':{'fylite:point':{'interferometer':[
        {'first_point':{'r':r,'z':z},'fylite:theta':0} for r,z in zip(p['rpol'],p['zpol'])]}},
        'equilibrium':{'time_slice':{'profiles_2d':{'psi':state['field']},'global_quantities':{
            'psi_axis':[geom['axis']['flux']],'psi_boundary':[geom['boundary_flux']]}}}}}
    x=[i/1024 for i in range(1025)];b=[basis(t,p) for t in x];edge=p['tne_edge'][0]
    forwards=[]
    for profile in [[1.0]*len(x)]+[[row[j] for row in b] for j in range(3)]:
        request['inputs']['discharge']={'fylite:ne_profile':[v*1e19 for v in profile]}
        forwards.append(native(k,request))
    nel=[[v['chord_nel19'][i] for v in forwards[1:]] for i in range(11)]
    bp=[[v['chord_bpolar'][i] for v in forwards[1:]] for i in range(11)]
    rows=[];values=[];sigmas=[]
    for i,weight in enumerate(p['fwtnel']):
        if weight>0:
            rows.append([v*weight for v in nel[i]])
            values.append((p['bnel'][i]-edge*forwards[0]['chord_nel19'][i])*weight)
            sigmas.append(p['signel'][i]*weight)
    if p['fwtne0'][0]>0:
        # matrixnel uses bsnel(knefnc,nk,0)-bsnel(...,.05), including nk=3.
        rows.append([((1 if j==0 else 0)-(.05**j-.05**3))*p['fwtne0'][0] for j in range(3)])
        values.append(0.0);sigmas.append(0.0)
    for psi,obs,sigma,weight in zip(p['psi_ne_ts'],p['bne_ts'],p['sig_ne_ts'],p['fwt_ne_ts']):
        if weight>0:
            rows.append([v*weight for v in basis(psi,p)]);values.append((obs-edge)*weight);sigmas.append(sigma*weight)
    coeff=fit(rows,values)
    density=lambda c:[edge+sum(v*z for v,z in zip(row,c)) for row in b]
    nominal=density(coeff)
    if min(nominal)<0:raise ValueError('Nominal density is negative; no physical profile published')
    rng=random.Random(94048);samples=[];negative=0
    for _ in range(256):
        c=fit(rows,[v+rng.gauss(0,s) for v,s in zip(values,sigmas)]);profile=density(c)
        negative+=min(profile)<0;samples.append(profile)
    def quantile(vals,f):
        v=sorted(vals);t=(len(v)-1)*f;i=int(t);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(t-i)
    profiles=[{'psi_n':t,'ne19':nominal[i],'p16':quantile([s[i] for s in samples],.16),'p84':quantile([s[i] for s in samples],.84)} for i,t in enumerate(x)]
    chords=[{'channel':i+1,'bnel':p['bnel'][i],'bnel_model':edge*forwards[0]['chord_nel19'][i]+sum(v*c for v,c in zip(nel[i],coeff)),
             'signel':p['signel'][i],'fwtnel':p['fwtnel'][i],'bpolar':p['bpolar'][i],
             'bpolar_model':edge*forwards[0]['chord_bpolar'][i]+sum(v*c for v,c in zip(bp[i],coeff)),
             'sigpol':p['sigpol'][i],'fwtpol':p['fwtpol'][i]} for i in range(11)]
    return {'chords':chords,'density':profiles,'coefficients':coeff,'samples':256,'seed':94048,'negative_samples':negative,
        'kernel':k.identity,'source':document['source'],'model':'Archived KNEFNC=0, KNECUR=3, edge tanh; BNEL and axis density fit; FWTNE0 smoothing. BPOLAR comparison only.',
        'scope':'Fixed magnetic field; 256 independent Gaussian BNEL/axis-density perturbations. All samples retained, including negative ones. No equilibrium feedback; not full reconstruction confidence. Native chord sampling uses 0<=psiN<=1, without LCFS polygon clipping.',
        'units':{'density':'1e19 m^-3','bnel':'1e19 m^-2','bpolar':'1e19 T m^-2'}}


def dispatch(w, method, body, query, root, roots):
    args=body if method=='POST' else {k:v[0] for k,v in query.items()}
    run=w.runpath(args['case_id'],args['run_id'],roots)
    source=w.ROOT/'cases/EQ-P01-94048/point-observations.json';doc=w.read(source)
    w.scientific_views.artifact(w,run,'solve');w.scientific_views.artifact(w,run,'assemble')
    identity={'kernel_sha256':w.sha(root/'lib/libfylite_kernel.so'),'run_id':run.name,'solve_sha256':w.sha(run/'solve.json'),'assemble_sha256':w.sha(run/'assemble.json'),
              'observations_sha256':w.sha(source),'adapter_sha256':w.sha(Path(__file__))}
    ident=w.hobj(identity);folder=w.casepath(args['case_id'],roots)/'diagnostic-analyses';path=folder/('point-'+ident+'.json')
    if path.exists():
        value=w.read(path)
        if value['identity']!=identity or value['result_sha256']!=w.hobj(value['result']):raise ValueError('POINT analysis integrity mismatch')
        return value
    if method=='GET':return {'state':'not_computed','identity':identity}
    with w.LOCK:
        value={'state':'completed','identity':identity,'result':compute(w,root,run,doc)}
        value['result_sha256']=w.hobj(value['result']);w.write(path,value)
    return value
