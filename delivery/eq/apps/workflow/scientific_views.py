"""Read-only W2 task views; no execution, adoption, or implicit coordinate conversion."""
import gzip
import json


def artifact(w, run, name):
    status = w.read(run/'status.json')['steps'].get(name, {})
    path = run/(name+'.json')
    if status.get('state') not in ('completed', 'reused') or not path.is_file():
        raise ValueError('该运行尚无可用产物: '+name)
    if w.sha(path) != status.get('sha256'):
        raise ValueError('运行产物身份已变化: '+name)
    return w.read(path)


def differences(left, right, path=''):
    if isinstance(left, dict) and isinstance(right, dict):
        result=[]
        for key in sorted(set(left)|set(right)):
            field=path+'.'+key if path else key
            if key not in left or key not in right:
                result.append({'field':field, 'left':left.get(key), 'right':right.get(key), 'change':'missing'})
            else: result.extend(differences(left[key],right[key],field))
        return result
    if left == right:return []
    if isinstance(left,list) and isinstance(right,list):
        indexes=[i for i in range(max(len(left),len(right))) if i>=len(left) or i>=len(right) or left[i]!=right[i]]
        return [{'field':path,'change':'array','left_count':len(left),'right_count':len(right),'changed_count':len(indexes),'examples':[{'index':i,'left':left[i] if i<len(left) else None,'right':right[i] if i<len(right) else None} for i in indexes[:8]]}]
    return [{'field':path,'left':left,'right':right,'change':'value'}]


def dispatch(w, route, roots, query):
    get=lambda key,default='':query.get(key,[default])[0]
    if route=='pressure-preview':
        pars=w.parameters({**w.DEFAULT,'pressure_scale':float(get('scale','1'))})
        data=w.dataset();w.manifest(data)
        return {'kind':'draft-preview','pressure':w.pressure(data,pars,None),
                'magnetic_time_s':5.760,'dataset_manifest_sha256':w.sha(data/'manifest.json'),
                'meaning':'只读压力倍率预览；未保存、采纳或启动求解。'}
    run=w.runpath(get('case_id'),get('run_id'),roots)
    snap=w.read(run/'snapshot.json')
    if route=='compare':
        other=w.runpath(get('other_case_id',get('case_id')),get('other_run_id'),roots)
        other_snap=w.read(other/'snapshot.json')
        a=artifact(w,run,'assemble');b=artifact(w,other,'assemble')
        warnings=[]
        for key in ('shot','time_s','pressure_time_s','inputs_flux','output_flux','q_mode'):
            if a['effective'].get(key)!=b['effective'].get(key):warnings.append('比较口径不同: '+key)
        if snap.get('dataset_manifest_sha256')!=other_snap.get('dataset_manifest_sha256'):warnings.append('数据包身份不同')
        reports=[]
        for folder in (run,other):
            if w.read(folder/'status.json')['steps'].get('report',{}).get('state') in ('completed','reused'):
                reports.append(artifact(w,folder,'report'))
            else:reports.append(None)
        return {'left':{'case_id':get('case_id'),'run_id':run.name,'revision':snap['revision']},
                'right':{'case_id':get('other_case_id',get('case_id')),'run_id':other.name,'revision':other_snap['revision']},
                'input_diff':differences(a,b),'warnings':warnings,'aligned':not warnings,
                'reports':reports,'meaning':'原坐标分别展示；不插值、不重新求解，不把差异下降当作物理验收。'}
    if route=='channel-view':
        kind=get('kind');index=int(get('index'))
        if kind not in ('loops','probes') or index<0:raise ValueError('无效磁诊断槽位')
        mag=artifact(w,run,'magnetics');assembly=artifact(w,run,'assemble');source=artifact(w,run,'sources')
        data=w.dataset();w.manifest(data)
        if snap['dataset_manifest_sha256']!=w.sha(data/'manifest.json'):raise ValueError('原运行映射数据不可用；不能用当前数据替代')
        mapping=w.read(data/'mapping.json')['mapping']
        names=mapping['FLUX_LOOP_NODES'] if kind=='loops' else mapping['B_PROBE_NODES_LEGACY'][:36]
        if index>=len(names):raise ValueError('此槽位无原始测量（可能为历史补零槽），不能回溯为实测通道')
        node=names[index];audit=next((x for x in mag['audit'] if x['node']==node),None)
        if audit is None:raise ValueError('原运行缺少该通道处理记录')
        prefix='loop' if kind=='loops' else 'probe'
        raw=None;acq=source.get('acquisition')
        if acq:
            if acq['waveforms_file']!='acquired-waveforms.json.gz':raise ValueError('非法波形引用')
            path=run/acq['waveforms_file']
            if w.sha(path)!=acq['waveforms_sha256']:raise ValueError('原波形已改变')
            with gzip.open(path,'rt') as stream:raw=json.load(stream).get('east:'+node)
        return {'case_id':get('case_id'),'run_id':run.name,'revision':snap['revision'],'kind':kind,'index':index,
                'node':node,'audit':audit,'raw':raw,'raw_available':raw is not None,
                'observed':mag[prefix+'_observed'][index],'weight':mag[prefix+'_weights'][index],
                'used':mag[prefix+'_weights'][index]>0,'unit':'Wb/rad' if kind=='loops' else 'T',
                'geometry':assembly['config']['initial'].get('limiter'),
                'geometry_note':'这里只提供该运行的WALL；尚未提供逐探针位置/方向，不能据此宣称几何已核验。'}
    raise ValueError('未知科学视图')
