"""Minimal immutable-object contracts; legacy JSON/file hashes remain unchanged."""
import copy
import hashlib
import json
import re
import shutil

HASH_PROFILE = 'legacy-python-json-sort-keys-v1'
SCHEMA = 'fylite.research-object/1'
KINDS = ('Dataset', 'ProcessingRevision', 'ConstraintSet', 'InputBundle', 'Plan', 'Run', 'Artifact')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def envelope(kind, identity, payload, refs=()):
    if kind not in KINDS:
        raise ValueError('未知科研对象类型')
    return {'schema': SCHEMA, 'kind': kind, 'id': identity,
            'hash_profile': HASH_PROFILE, 'content_sha256': digest(payload),
            'references': copy.deepcopy(list(refs)), 'payload': copy.deepcopy(payload)}


def error_record(error, node=None):
    return {'code': 'INVALID_INPUT' if isinstance(error, ValueError) else 'EXECUTION_ERROR',
            'category': 'validation' if isinstance(error, ValueError) else 'runtime',
            'node_id': node, 'retryable': False, 'message': str(error)}


def clone_processing(w, source, destination, case, parameters):
    """Copy adopted object closure byte-for-byte; never rewrite source metadata."""
    reference = case.get('processing')
    if not reference:
        return {}
    preview = w.processing_tools.folder(w, source, 'previews', reference['preview_id'])
    meta = w.processing_tools.validate(w, preview)
    if w.sha(preview / 'object.json') != reference['sha256']:
        raise ValueError('采纳预览身份已变化，不能另存')
    data = w.processing_tools.folder(w, source, 'datasets', meta['dataset_id'])
    data_meta = w.processing_tools.validate(w, data)
    # The selected dataset must contain the actual original bytes used by this preview.
    for name in ('sources.json', 'acquired-waveforms.json.gz'):
        if meta['files'].get(name) != data_meta['files'].get(name):
            raise ValueError('预览与原始数据引用不一致')
    for kind, old, obj in (('datasets', data, data_meta), ('previews', preview, meta)):
        new = destination / kind / old.name
        new.mkdir(parents=True, exist_ok=False)
        for name in ['object.json', *obj['files']]:
            p = old / name
            if p.is_symlink() or not p.is_file():
                raise ValueError('数据对象引用非法')
            shutil.copyfile(p, new / name)
            if w.sha(p) != w.sha(new / name):
                raise ValueError('另存数据校验失败')
    if w.processing_tools.subset(parameters) != meta['parameters']:
        # Keep the data and preview for inspection, but invalidate adoption.
        return {}
    return {'processing': copy.deepcopy(reference),
            'processing_receipt': copy.deepcopy(case.get('processing_receipt', {}))}


def tool_definitions(w):
    """Describe only the registered DAG tools, not future loop/model capabilities."""
    return {name: {'tool_id': name, 'version': w.tool_identity(),
                   'entrypoint_id': name, 'input_schema': 'fylite.workflow-node-input/1',
                   'output_schema': 'fylite.workflow-node-output/1',
                   'kind': 'native' if name == 'solve' else 'registered-python',
                   'environment': {'python': 'stdlib', 'kernel': 'locked ABI163' if name == 'solve' else None},
                   'retry': 'manual-new-run', 'checkpoint': False,
                   'cancel': 'worker-process', 'thread_safe': 'not_declared'}
            for name in w.TOOLS}


def run_objects(w, run):
    """Read-only typed view. Legacy files/hashes are never migrated in place."""
    snap = w.read(run/'snapshot.json')
    status = w.read(run/'status.json')
    scope = snap.get('case_id', run.parent.parent.name) + ':' + run.name
    result = []
    def add(kind, suffix, payload, refs=()):
        obj = envelope(kind, scope+':'+suffix, payload, refs)
        result.append(obj)
        return {'id':obj['id'], 'sha256':obj['content_sha256']}
    snapshot_ref = {'id':scope+':snapshot', 'sha256':w.sha(run/'snapshot.json')}
    definition = snap.get('workflow_definition')
    plan = add('Plan', 'plan', {'definition':definition, 'nodes':snap.get('plan'),
                              'target':snap.get('target'), 'parameters':snap.get('parameters'),
                              'kernel_identity':snap.get('kernel_identity'),
                              'tool_sha256':snap.get('tool_sha256'),
                              'definition_known':definition is not None}, [snapshot_ref])
    add('Run', 'run', {'snapshot_sha256':snapshot_ref['sha256'], 'plan_ref':plan}, [plan])
    refs = {}
    for key, state in status.get('steps',{}).items():
        if state.get('state') not in ('completed','reused'):
            continue
        if not isinstance(key,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",key):
            raise ValueError("非法节点标识")
        path = run/(key+'.json')
        if path.is_symlink() or not path.is_file() or w.sha(path) != state.get('sha256'):
            raise ValueError('运行产物引用已损坏: '+key)
        value = w.read(path)
        refs[key] = add('Artifact', key, {'name':path.name, 'byte_sha256':w.sha(path),
                                       'producer':key, 'value':value}, [snapshot_ref])
        if key == 'sources':
            acq = value.get('acquisition')
            if acq:
                if acq['waveforms_file'] != 'acquired-waveforms.json.gz':
                    raise ValueError('非法原始波形引用')
                raw = run/acq['waveforms_file']
                if raw.is_symlink() or not raw.is_file() or w.sha(raw) != acq['waveforms_sha256']:
                    raise ValueError('原始波形引用已损坏')
            add('Dataset','dataset',value,[refs[key]])
        elif key == 'magnetics':
            add('ProcessingRevision','processing', {'parameters':snap.get('parameters'),
                'adopted':snap.get('processing'), 'values':value}, [refs[key]])
        elif key == 'constraints':
            add('ConstraintSet','constraints',value,[refs[key]])
        elif key == 'assemble':
            add('InputBundle','input', {'effective':value['effective'], 'config':value['config'],
                'dataset_manifest_sha256':snap.get('dataset_manifest_sha256'),
                'kernel_identity':snap.get('kernel_identity'), 'tool_sha256':snap.get('tool_sha256')},
                [snapshot_ref, *refs.values()])
    return {'schema':'fylite.object-view/1', 'hash_profile':HASH_PROFILE,
            'read_only':True, 'legacy':not bool(snap.get('object_contract')),
            'definition_revision':definition.get('version') if definition else None,
            'execution_allowed_by_view':False, 'objects':result}
