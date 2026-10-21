"""Experimental input adapters and checks. No equilibrium physics is implemented here."""
import ctypes
import gzip
import hashlib
import json
import math
import os
import struct
import time
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sp_call(library, operation, request):
    lib = ctypes.CDLL(str(library))
    lib.sp_call.argtypes = [ctypes.c_char_p, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_uint64]
    lib.sp_call.restype = ctypes.c_void_p
    lib.sp_result_status.argtypes = [ctypes.c_void_p]
    lib.sp_result_status.restype = ctypes.c_int32
    for name in ('sp_result_json', 'sp_result_error'):
        fn = getattr(lib, name)
        fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64]
        fn.restype = ctypes.c_uint64
    lib.sp_result_array_count.argtypes = [ctypes.c_void_p]
    lib.sp_result_array_count.restype = ctypes.c_uint32
    lib.sp_result_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint64]
    lib.sp_result_array.restype = ctypes.c_uint64
    lib.sp_result_free.argtypes = [ctypes.c_void_p]
    def text(fn, handle):
        size = fn(handle, None, 0)
        buf = ctypes.create_string_buffer(max(size, 1))
        fn(handle, buf, size)
        return buf.raw[:size].decode()
    op = operation.encode()
    raw = json.dumps(request, allow_nan=False).encode()
    handle = lib.sp_call(op, len(op), raw, len(raw))
    if not handle:
        raise ValueError('libsp没有返回读取结果')
    try:
        if lib.sp_result_status(handle):
            raise ValueError(text(lib.sp_result_error, handle))
        result = json.loads(text(lib.sp_result_json, handle))
        arrays = []
        for i in range(lib.sp_result_array_count(handle)):
            size = lib.sp_result_array(handle, i, None, 0)
            buf = ctypes.create_string_buffer(max(size, 1))
            lib.sp_result_array(handle, i, buf, size)
            arrays.append(buf.raw[:size])
    finally:
        lib.sp_result_free(handle)
    def expand(value):
        if isinstance(value, dict):
            if '@array' in value:
                if value['dtype'] not in ('f64', 'i64') or len(value['shape']) != 1:
                    raise ValueError('磁波形要求一维f64/i64数组')
                raw = arrays[value['@array']]
                return list(struct.unpack('<'+str(len(raw)//8)+('d' if value['dtype']=='f64' else 'q'), raw))
            return {k: expand(v) for k, v in value.items()}
        return [expand(v) for v in value] if isinstance(value, list) else value
    return expand(result)


def acquire(data, pars, run):
    """Copy retained windows or read the declared 94048 channel mapping using libsp."""
    mode = pars.get('data_source', 'frozen')
    if mode == 'frozen':
        with gzip.open(data/'raw-waveforms.json.gz', 'rt') as stream:
            traces = json.load(stream)
        provenance = {'mode': mode, 'origin_sha256': digest(data/'raw-waveforms.json.gz'),
                      'description': '读取已冻结实验波形；不是本次在线取数'}
    elif mode == 'mdsplus':
        mapping = read(data/'mapping.json')['mapping']
        nodes = list(dict.fromkeys(mapping['FLUX_LOOP_NODES'] + mapping['B_PROBE_NODES_LEGACY'][:36] + mapping['PF_NODES'] + ['IPM', 'FOCS_IT']))
        server = os.environ.get('FYLITE_MDSIP_SERVER', '202.127.204.12:8000')
        root = Path(os.environ['FYLITE_EQ_ROOT'])
        traces = {}
        for node in nodes:
            normalized = node.lstrip('\\').upper()
            items = [{'tree':'east', 'shot':94048, 'verb':verb, 'node':'\\'+normalized} for verb in ('data', 'dim_of')]
            answer = sp_call(root/'lib/libsp.so', 'mds_read_many', {
                'server':server, 'items':items, 'parallel':2,
                'timeout_ms':10000, 'user':os.environ.get('USER', 'fylite')})['items']
            if len(answer) != 2 or any('error' in item for item in answer):
                raise ValueError('在线读取失败 '+normalized+': '+str(answer)[:500])
            y, t = (item['value'] for item in answer)
            if not isinstance(y, list) or not isinstance(t, list) or len(t) != len(y):
                raise ValueError('在线时间/信号维度不一致: '+normalized)
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in t+y):
                raise ValueError('在线波形有非有限数: '+normalized)
            selected = {}
            for prefix, lo, hi in [('target',5.755,5.765), ('baseline',-6.9,-6.1)]:
                pairs = [(a,b) for a,b in zip(t,y) if lo <= a <= hi]
                selected[prefix+'_t'] = [a for a,b in pairs]
                selected[prefix+'_y'] = [b for a,b in pairs]
            selected['original_npz_sha256'] = None  # Online data is identified by the saved JSON, not a fictitious NPZ.
            selected['online_retained_sha256'] = hashlib.sha256(json.dumps(selected,sort_keys=True,allow_nan=False).encode()).hexdigest()
            traces['east:'+normalized] = selected
        provenance = {'mode':mode, 'server':server, 'tree':'east', 'shot':94048,
                      'acquired_at':time.time(), 'library_sha256':digest(root/'lib/libsp.so'),
                      'description':'本次在线读取后保存窗口；不回退冻结数据'}
    else:
        raise ValueError('不支持的数据来源')
    raw = run/'acquired-waveforms.json.gz'
    with gzip.open(raw, 'wt') as stream:
        json.dump(traces, stream, allow_nan=False)
    return {**provenance, 'waveforms_file':raw.name, 'waveforms_sha256':digest(raw), 'channels':len(traces)}


def quality(data, pars, run):
    source = read(run/'sources.json')
    raw = run/source['acquisition']['waveforms_file']
    if digest(raw) != source['acquisition']['waveforms_sha256']:
        raise ValueError('获取产物身份已改变')
    with gzip.open(raw, 'rt') as stream:
        traces = json.load(stream)
    mapping = read(data/'mapping.json')['mapping']
    expected = mapping['FLUX_LOOP_NODES']+mapping['B_PROBE_NODES_LEGACY'][:36]+mapping['PF_NODES']+['IPM','FOCS_IT']
    rows = []
    for node in expected:
        item = traces.get('east:'+node.lstrip('\\').upper())
        if item is None:
            raise ValueError('缺少必需通道: '+node)
        t, y = item['target_t'], item['target_y']
        if len(t) != len(y) or len(t)<2 or not all(math.isfinite(v) for v in t+y):
            raise ValueError('信号为空、维度不符或非有限: '+node)
        if any(a>=b for a,b in zip(t,t[1:])):
            raise ValueError('时间轴不严格递增: '+node)
        dt = max(b-a for a,b in zip(t,t[1:]))
        if t[0]>5.760-pars['half_window_s']+dt or t[-1]<5.760+pars['half_window_s']-dt:
            raise ValueError('目标时间窗覆盖不足: '+node)
        if pars['drift']:
            bt, by = item['baseline_t'], item['baseline_y']
            if len(bt)!=len(by) or len(bt)<3 or not all(math.isfinite(v) for v in bt+by) or any(a>=b for a,b in zip(bt,bt[1:])):
                raise ValueError('基线无效: '+node)
        rows.append({'node':node,'samples':len(t),'first_s':t[0],'last_s':t[-1], 'constant':min(y)==max(y)})
    if len(mapping['PF_EFIT_ORDER']) != 12 or sorted(mapping['PF_EFIT_ORDER'])!=list(range(12)) or len(mapping['PF_TURNS'])!=12:
        raise ValueError('PF映射不是12槽置换')
    return {'passed':True, 'channels':rows, 'mapping_sha256':digest(data/'mapping.json'),
            'warnings':['压力6.510s与磁测5.760s相差0.750s，仅允许明确知情的历史研究回放。',
                        '单位/极性与响应表沿用历史映射，未独立实验标定；恒定通道需人工检查。'],
            'checks':['文件身份','必需通道','有限数','时间轴顺序','时间窗覆盖','PF槽位置换'],
            'not_verified':['独立几何/极性标定','自动坏道判定','同时间压力有效性']}


def constraints(data, pars, run):
    return {'route':'fixed external pressure + q0 target + fitted PF',
            'measurement':['磁通环','磁探针','PF电流先验','总电流Ip','固定外部压力'],
            'physical_prior':{'q0_mode':pars['q_mode'], 'q0_target':pars['q_target'], 'edge_current':'历史人工约束，非新自举电流'},
            'numerical':'历史正则化、网格及松弛设置',
            'pressure_time_s':6.510,'magnetic_time_s':5.760,
            'template_sha256':digest(data/'native-template.json'),
            'response_tables':{p.name:digest(p) for p in (data/'input/tables').glob('*.ddd')},
            'scope':'当前仅q目标/压力倍率等已开放参数可调；不是任意约束编辑器'}
