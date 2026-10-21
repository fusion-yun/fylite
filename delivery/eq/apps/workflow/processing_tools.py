"""Personal immutable magnetic datasets and previews; shared UI/automation API."""
import shutil
import time
import uuid

KEYS = ('data_source', 'half_window_s', 'drift')

def subset(pars):
    return {key: pars[key] for key in KEYS}

def folder(w, case, kind, ident):
    path = case / kind / w.check_id(ident)
    if path.resolve() != path.absolute():
        raise ValueError('个人数据对象不能使用符号链接')
    return path

def validate(w, path):
    meta = w.read(path / 'object.json')
    for name, digest in meta['files'].items():
        if name not in ('sources.json', 'acquired-waveforms.json.gz', 'quality.json', 'magnetics.json'):
            raise ValueError('未知处理产物')
        if w.sha(path / name) != digest:
            raise ValueError('数据或预览产物已被修改: ' + name)
    if meta['manifest_sha256'] != w.sha(w.dataset() / 'manifest.json'):
        raise ValueError('参考数据包版本已变化，请重新读取并预览')
    return meta

def publish(w, path, meta, names):
    meta.update(files={name: w.sha(path / name) for name in names},
                manifest_sha256=w.sha(w.dataset() / 'manifest.json'), created_at=time.time())
    w.write(path / 'object.json', meta)
    return meta

def adopted(w, case, reference, pars):
    path = folder(w, case, 'previews', reference['preview_id'])
    meta = validate(w, path)
    if w.sha(path / 'object.json') != reference['sha256']:
        raise ValueError('采纳的预览身份已变化')
    if meta['parameters'] != subset(pars) or meta['tool_sha256'] != w.tool_identity():
        raise ValueError('处理参数或工具已变化，请重新预览并采纳')
    return path, meta

def dispatch(w, method, route, body, roots, query):
    cid = query.get('case_id', [''])[0] if method == 'GET' else body['case_id']
    case = w.casepath(cid, roots)
    if method == 'GET':
        if route == 'processing-objects':
            return {kind: [w.read(p / 'object.json') for p in sorted((case / kind).glob('*')) if (p / 'object.json').exists()]
                    for kind in ('datasets', 'previews')}
        path = folder(w, case, 'previews', query.get('preview_id', [''])[0])
        meta = validate(w, path)
        return {'identity': w.sha(path / 'object.json'), 'preview': meta,
                'magnetics': w.read(path / 'magnetics.json'), 'quality': w.read(path / 'quality.json')}
    with w.LOCK:
        current = w.read(case / 'case.json')
        if body.get('base_revision') != current['revision']:
            raise ValueError('算例修订已变化，请重新打开')
        if route == 'processing-import':
            run = w.runpath(cid, body['run_id'], roots)
            status = w.read(run / 'status.json')['steps']['sources']
            if status['state'] not in ('completed', 'reused') or w.sha(run / 'sources.json') != status['sha256']:
                raise ValueError('取数尚未完成或来源身份已变化')
            source = w.read(run / 'sources.json')
            acq = source['acquisition']
            if acq['waveforms_file'] != 'acquired-waveforms.json.gz' or w.sha(run / acq['waveforms_file']) != acq['waveforms_sha256']:
                raise ValueError('原始波形身份不一致')
            snap = w.read(run / 'snapshot.json')
            if snap['dataset_manifest_sha256'] != w.sha(w.dataset() / 'manifest.json'):
                raise ValueError('原运行数据包与当前版本不同')
            ident = 'data-' + uuid.uuid4().hex[:12]
            path = folder(w, case, 'datasets', ident); path.mkdir(parents=True)
            for name in ('sources.json', 'acquired-waveforms.json.gz'):
                shutil.copyfile(run / name, path / name)
            return publish(w, path, {'dataset_id': ident, 'source_run': run.name, 'mode': acq['mode'],
                                      'shot': source['shot'], 'time_s': source['time_s']},
                           ('sources.json', 'acquired-waveforms.json.gz'))
        if route == 'processing-preview':
            pars = w.parameters(body['parameters'])
            data_path = folder(w, case, 'datasets', body['dataset_id'])
            data_meta = validate(w, data_path)
            if pars['data_source'] != data_meta['mode']:
                raise ValueError('所选数据来源与处理参数不一致')
            ident = 'preview-' + uuid.uuid4().hex[:12]
            path = folder(w, case, 'previews', ident); path.mkdir(parents=True)
            for name in ('sources.json', 'acquired-waveforms.json.gz'):
                shutil.copyfile(data_path / name, path / name)
            w.manifest(w.dataset())
            w.write(path / 'quality.json', w.pipeline_tools.quality(w.dataset(), pars, path))
            w.write(path / 'magnetics.json', w.magnetics(w.dataset(), pars, path))
            meta = publish(w, path, {'preview_id': ident, 'dataset_id': data_meta['dataset_id'],
                                     'base_revision': current['revision'], 'parameters': subset(pars),
                                     'tool_sha256': w.tool_identity()},
                           ('sources.json', 'acquired-waveforms.json.gz', 'quality.json', 'magnetics.json'))
            return {'identity': w.sha(path / 'object.json'), 'preview': meta,
                    'magnetics': w.read(path / 'magnetics.json'), 'quality': w.read(path / 'quality.json')}
        if route == 'processing-adopt':
            pars = w.parameters(body['parameters'])
            reference = {'preview_id': body['preview_id'], 'sha256': body['identity']}
            path, meta = adopted(w, case, reference, pars)
            if meta['base_revision'] != current['revision']:
                raise ValueError('预览基于旧修订，请重新生成')
            note = body.get('note', '').strip()
            if not note or len(note) > 2000:
                raise ValueError('请填写采纳依据（1–2000字）')
            current.update(parameters={**current['parameters'], **meta['parameters']},
                           processing=reference, revision=current['revision'] + 1, updated_at=time.time(),
                           processing_receipt={'note': note, 'actor': w.os.environ.get('USER', 'local-user'),
                                               'time': time.time(), 'preview_identity': body['identity']})
            w.write(case / 'revisions' / (str(current['revision']) + '.json'), current)
            w.write(case / 'case.json', current)
            return current
    raise ValueError('未知处理操作')
