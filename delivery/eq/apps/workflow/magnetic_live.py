"""Personal pure-magnetic M workflow: fresh MDSplus data, reviewed input, pinned native solve.

This adapter calls the packaged standalone-v3 data and kernel code. It never substitutes
archived observations when an experimental fetch fails.
"""
from __future__ import annotations

import gzip
import itertools
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

LOCK = threading.RLock()
SCHEMA = 'fylite.eq.magnetic-live/1'
MAX_CHANNEL_SAMPLES = 2000


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    os.replace(temporary, path)


def update_status(folder, **changes):
    with LOCK:
        old = read(folder / 'status.json')
        value = {**old, **changes, 'updated_at': time.time()}
        write(folder / 'status.json', value)
        return value


def result_verdict(result):
    """Report inner convergence separately from the native result checks."""
    tier = result.get('tiers', {}).get('M') or {}
    facts = tier.get('facts') or {}
    numeric = facts.get('converged')
    numerical = 'converged' if numeric is True or numeric == 1 else 'not_converged'
    check = tier.get('physics_check') or {}
    failed = list(check.get('failed') or [])
    if numerical != 'converged':
        state = 'solver_not_converged'
    elif tier.get('status') == 'ok' and check.get('passed') is True:
        state = 'passed'
    else:
        state = 'physics_gate_failed'
    boundary = tier.get('boundary') or []
    thumb = None
    if boundary:
        step = max(1, len(boundary) // 16)
        thumb = [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in boundary[::step][:16]]
    return {'numerical': numerical, 'gate': {'state': state, 'failed': failed},
            'facts': {k: facts.get(k) for k in ('iterations', 'residual', 'q0', 'q95', 'chi2_mag', 'n_mag_rows')},
            'thumb': thumb}


def verified_status(folder, status):
    """Correct legacy display in memory without changing saved run identities."""
    path = folder / 'result.json'
    if status.get('state') in ('waiting_review', 'reviewed') and path.is_file() and status.get('result_sha256') == digest(path):
        return {**status, **result_verdict(read(path))}
    return status


def archive():
    import archive_v3
    return archive_v3


def base(w, roots):
    path = w.personal(str(Path(roots[0]).expanduser() / 'magnetic-live'), roots)
    path.mkdir(exist_ok=True)
    return path


def casepath(w, roots, cid):
    w.check_id(cid)
    if not cid.startswith('case-'):
        raise ValueError('个人分析编号无效')
    path = w.personal(str(base(w, roots) / cid), roots)
    if not (path / 'case.json').is_file():
        raise ValueError('个人分析不存在')
    return path


def compact(folder):
    case, status = read(folder / 'case.json'), verified_status(folder, read(folder / 'status.json'))
    return {'case_id': case['case_id'], 'shot': case['shot'], 'time_s': case['time_s'],
            'mask_profile': case['mask_profile'], 'created_at': case['created_at'],
            'state': status['state'], 'stage': status.get('stage'), 'numerical': status.get('numerical'), 'gate': status.get('gate'),
            'facts': status.get('facts'), 'thumb': status.get('thumb'),
            'review': status.get('review')}


def clone_adapter(folder, package_root, manifest):
    adapter = folder / 'adapter'
    adapter.mkdir(exist_ok=False)
    source = package_root / 'demo.py'
    if digest(source) != manifest['demo.py']:
        raise ValueError('数据与求解适配器身份不匹配')
    shutil.copyfile(source, adapter / 'demo.py')
    for name in ('libfylite.so', 'libsp.so', 'facts'):
        (adapter / name).symlink_to(package_root / name, target_is_directory=name == 'facts')
    # 输入卡必须每算例一份：不同炮号的纵场、电流目标写在这里，共享文件会互相污染
    shutil.copytree(package_root / 'input', adapter / 'input')
    (adapter / 'output').mkdir()
    return adapter


def deck_facts(adapter, tf):
    """记录本炮的真空场来源。注意：输入卡的 btor/target_ip 在 --run 路径下不被内核读取，
    真正的纵场走 inputs.measurements.tf.f_vac_Tm，这里只做审计留痕。"""
    deck = read(adapter / 'input/native.json')
    return {'f_vac_Tm': float(tf['f_vac_Tm']), 'tf_node': tf.get('node'),
            'deck_btor_unused': deck.get('btor'), 'rcentr': deck.get('rcentr')}


def packaged(folder):
    root, manifest_path, deps = archive().package()
    case = read(folder / 'case.json')
    if case['package_manifest_sha256'] != digest(manifest_path) or case['package_path'] != str(root):
        raise ValueError('独立内核包与分析创建时的身份不同')
    adapter = folder / 'adapter'
    manifest = read(manifest_path)
    if digest(adapter / 'demo.py') != manifest['demo.py']:
        raise ValueError('数据处理脚本身份已变化')
    return root, deps, adapter


def demo_module(adapter):
    spec = importlib.util.spec_from_file_location('fylite_magnetic_adapter', adapter / 'demo.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def raw_window(series, t, half):
    if series is None:
        return {'available': False, 'target_t': [], 'target_y': [], 'baseline_t': [], 'baseline_y': []}
    values, times = series
    if len(values) != len(times) or not all(math.isfinite(x) for x in itertools.chain(values, times)):
        raise ValueError('实验波形存在维度或非有限数错误')
    if any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError('实验时间轴不严格递增')
    target = [(x, y) for x, y in zip(times, values) if abs(x - t) <= half]
    baseline = [(x, y) for x, y in zip(times, values) if -6.9 <= x <= -6.1]
    return {'available': True, 'target_t': [x for x, _ in target], 'target_y': [y for _, y in target],
            'baseline_t': [x for x, _ in baseline], 'baseline_y': [y for _, y in baseline]}


def acquire_worker(folder):
    case = read(folder / 'case.json')
    root, _, adapter = packaged(folder)
    demo = demo_module(adapter)
    host = demo.data_host()
    server = os.environ.get('FYLITE_MDSIP_SERVER', '202.127.204.12:8000')
    src = demo.MagneticsSource(host, case['shot'], 'east', server, 10)
    try:
        src.prefetch(point=False, workers=8)
        measurement = src.at(case['time_s'], point=False)
        names, device = src.names, src.doc
        windows = {}
        for (tree, node), series in src.cache.items():
            key = tree + ':' + node
            windows[key] = raw_window(series, case['time_s'], demo.WINDOW_MS / 1000)
    finally:
        src.close()
    if measurement['shot'] != case['shot'] or measurement['time_s'] != case['time_s']:
        raise ValueError('取数身份与分析对象不符')
    rules = []
    active = {'loops': [], 'probes': [], 'pf': [], 'global': []}
    inactive = []
    old = None
    if case['mask_profile'] == 'm02_pinned':
        old_path = archive().case_input('EQ-M02', root)
        old = read(old_path)
        if device != old['inputs']['device']:
            raise ValueError('本炮装置映射与 M02 掩码基线不一致')
        original = old['inputs']['measurements']
        measurement['fwtsi'] = original['fwtsi']
        measurement['fwtmp2'] = original['fwtmp2']
        measurement['n_probe_active'] = sum(x > 0 for x in original['fwtmp2'])
        options = old['inputs']['options']
        mask_identity = digest(old_path)
    else:
        # 只给最小选项：loops='all' 会强制纳入该炮全部环，坏道无法排除，换炮必然不收敛
        options = {'tiers': 'M', 'p_on': 'M', 'jobs': 1}
        mask_identity = digest(root / 'facts/device/east.jsonld')
    # 竖直设定点交给内核扫描；写死单点 0.03 m 只对 164437 成立，换炮必然全失败
    options.pop('zc_scan', None)
    def inspect(kind, names_list, tree, weights, scales=None, drift=True):
        for i, node in enumerate(names_list):
            key = tree + ':' + (node if node.startswith('\\') else '\\' + node)
            wave = windows.get(key, {'available': False, 'target_t': [], 'baseline_t': []})
            fitted = bool(weights[i] > 0)
            row = {'kind': kind, 'index': i, 'node': node, 'tree': tree, 'role': 'fit' if fitted else 'exclude',
                   'weight': float(weights[i]), 'scale': float(scales[i] if scales else 1), 'drift': drift,
                   'samples': len(wave['target_t']),
                   'baseline_samples': len(wave['baseline_t']), 'source_key': key}
            if fitted:
                if row['samples'] < 2 or (drift and row['baseline_samples'] < 3):
                    raise ValueError(f'有效 {kind} 通道 {node} 缺少目标或炮前基线样本')
                active[kind].append(row)
            else:
                inactive.append(row)
            rules.append(row)
    loop_weights = measurement.get('fwtsi') or [0.0 if x else 1.0 for x in names['loop_drop']]
    inspect('loops', names['loops'], names['tree'], loop_weights,
            [x / (2 * math.pi) for x in names['loop_sign']])
    inspect('probes', names['probes'], names['tree'], measurement['fwtmp2'])
    inspect('pf', names['pf_nodes'], names['tree'], [1] * len(names['pf_nodes']),
            names['pf_turns'], drift=False)
    ip_node = names['ip_node']
    ip_tree = names['tree']
    primary = windows.get(ip_tree + ':' + (ip_node if ip_node.startswith('\\') else '\\' + ip_node)) if ip_node else None
    if not primary or not primary['target_t']:
        ip_node, ip_tree = 'pcrl01', names['pcs_tree']
    if not ip_node or not ip_tree:
        raise ValueError('未记录同期 Ip 原始来源')
    inspect('global', [ip_node], ip_tree, [1],
            [1000 if ip_tree == names['tree'] else 1], drift=False)
    tf = measurement.get('tf') or {}
    if not tf.get('node') or not math.isfinite(tf.get('f_vac_Tm', float('nan'))):
        raise ValueError('未取得同期 TF 电流及真空场输入')
    deck_info = deck_facts(adapter, tf)
    quality = {'passed': bool(active['loops'] and active['probes']),
               'active_counts': {k: len(v) for k, v in active.items()},
               'inactive_count': len(inactive), 'channels': rules,
               'warnings': ['79 道历史掩码沿用旧分析，误差权重未按本次数据重新标定；数值收敛不等于实验资格。'] if old else
                           ['装置默认通道角色与误差规则仅供探索；跨炮号几何、权重和实验资格须独立核对。'],
               'checks': ['原始节点身份', '目标窗样本', '炮前基线样本', '有限数', '时间轴', 'PF/Ip/TF', '输入掩码'],
               'mask_sha256': mask_identity, 'dd_version': device.get('_dd_version'),
               'source_fetch_s': src.fetch_s, 'read_rules': measurement.get('read_rules', [])}
    if not quality['passed']:
        raise ValueError('没有可用的磁通环或磁探针拟合通道')
    diagnostic = {'recipe': 'M', 'inputs': {'device': device, 'measurements': measurement, 'options': options},
                  'source': {'kind': 'mdsplus', 'tree': names['tree'], 'shot': case['shot'],
                             'time_s': case['time_s'], 'measurement_chain': 'east',
                             'libsp_version': demo.SP_VERSION, 'loop_input_units': 'Wb/rad',
                             'acquired_at': time.time()},
                  'audit_provenance': {'mask_profile': case['mask_profile'], 'mask_sha256': mask_identity,
                                       'processing_rule': 'demo.py reduce_series: target ±5 ms, pre-shot linear drift −6.9..−6.1 s'}}
    demo.workflow_validate({'workflow': diagnostic})
    raw = folder / 'raw-windows.json.gz'
    with gzip.open(raw, 'wt', encoding='utf-8') as stream:
        json.dump({'shot': case['shot'], 'time_s': case['time_s'], 'windows': windows}, stream, allow_nan=False)
    write(folder / 'diagnostics.json', diagnostic)
    write(folder / 'quality.json', quality)
    update_status(folder, state='acquired', stage='processing', acquired_at=time.time(),
                  raw_sha256=digest(raw), diagnostics_sha256=digest(folder / 'diagnostics.json'),
                  quality_sha256=digest(folder / 'quality.json'), deck_facts=deck_info, worker_pid=None)


def solve_worker(folder):
    case = read(folder / 'case.json')
    _, deps, adapter = packaged(folder)
    adoption = read(folder / 'adoption.json')
    diagnostic = folder / 'diagnostics.json'
    if digest(diagnostic) != adoption['diagnostics_sha256']:
        raise ValueError('已采纳输入身份变化')
    output = folder / 'result.json'
    if output.exists():
        raise ValueError('已有求解产物，拒绝覆盖')
    cmd = [sys.executable, str(adapter / 'demo.py'), '--run', str(adapter / 'input/native.json'),
           '--diagnostics', str(diagnostic), '--recipe', 'M', '--out', str(output)]
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'LD_LIBRARY_PATH': str(deps) + (':' + os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else '')}
    with (folder / 'native.log').open('xb') as log:
        done = subprocess.run(cmd, cwd=adapter, env=env, stdout=log, stderr=subprocess.STDOUT,
                              timeout=240, check=False)
    if not output.is_file():
        raise ValueError('原生求解未产生结果，退出码 ' + str(done.returncode))
    result = read(output)
    identity = read(folder / 'result.identity.json')
    used = read(folder / 'result.input.json')
    if identity['output_sha256'] != digest(output) or identity['input_sha256'] != digest(folder / 'result.input.json'):
        raise ValueError('求解输入/输出身份校验失败')
    if used['workflow']['inputs']['measurements']['shot'] != case['shot'] or used['workflow']['inputs']['measurements']['time_s'] != case['time_s']:
        raise ValueError('求解器实际输入炮号或时刻与分析对象不符')
    tier = result.get('tiers', {}).get('M') or {}
    used_workflow = used.get('workflow', {})
    used_inputs = used_workflow.get('inputs', {})
    if (used_workflow.get('recipe') != 'M' or 'thomson' in used_inputs or 'profiles' in used_inputs or
            'point' in used_inputs.get('measurements', {}) or 'kinetic_pressure' in used_inputs.get('measurements', {})):
        raise ValueError('实际装配输入超出纯磁 M 路线')
    expected_measurements = read(diagnostic)['inputs']['measurements']
    for key in ('fwtsi', 'fwtmp2'):
        if key in expected_measurements and used_inputs['measurements'].get(key) != expected_measurements[key]:
            raise ValueError('原生实际输入中的通道权重与已采纳版本不一致')
    verdict = result_verdict(result)
    update_status(folder, state='waiting_review', stage='review', ended_at=time.time(),
                  **{k: v for k, v in verdict.items() if k != 'facts'}, result_sha256=digest(output),
                  solver_message=tier.get('error'),
                  actual_input_sha256=digest(folder / 'result.input.json'),
                  result_identity_sha256=digest(folder / 'result.identity.json'),
                  facts={k: tier.get('facts', {}).get(k) for k in
                         ('iterations', 'residual', 'axis_r', 'axis_z', 'q0', 'q95', 'chi2_mag', 'n_mag_rows')},
                  worker_pid=None)


def worker(folder, mode):
    try:
        if mode == 'acquire':
            acquire_worker(folder)
        elif mode == 'solve':
            solve_worker(folder)
        else:
            raise ValueError('未知工作阶段')
    except Exception as exc:
        update_status(folder, state='failed', stage=mode, ended_at=time.time(),
                      error=str(exc)[:800], worker_pid=None)
        raise


def launch(folder, mode, deps):
    log = (folder / (mode + '.log')).open('xb')
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'LD_LIBRARY_PATH': str(deps) + (':' + os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else '')}
    try:
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', mode, str(folder)],
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
    finally:
        log.close()
    return proc.pid


def status_view(folder):
    case, status = read(folder / 'case.json'), read(folder / 'status.json')
    if status['state'] in ('acquiring', 'running') and status.get('worker_pid'):
        pid = status['worker_pid']
        try:
            command = (Path('/proc') / str(pid) / 'cmdline').read_bytes()
        except OSError:
            command = b''
        if str(folder).encode() not in command:
            status = read(folder / 'status.json')
            if status['state'] in ('acquiring', 'running'):
                status = update_status(folder, state='failed', error='工作进程已退出，请检查阶段日志',
                                       ended_at=time.time(), worker_pid=None)
    status = verified_status(folder, status)
    result = {'case': case, 'status': status}
    if (folder / 'quality.json').is_file() and status.get('quality_sha256') == digest(folder / 'quality.json'):
        result['quality'] = quality_with_defaults(read(folder / 'quality.json'))
    if (folder / 'adoption.json').is_file():
        result['adoption'] = read(folder / 'adoption.json')
    return result


MAGNETIC_KINDS = ('loops', 'probes')


def channel_id(row):
    # Source nodes may repeat in a device table; slot identity must remain unique.
    return f"{row['kind']}:{row['index']}"


def quality_with_defaults(quality):
    value = json.loads(json.dumps(quality))
    for row in value['channels']:
        row['channel_id'] = channel_id(row)
        row.setdefault('default_weight', row['weight'])
    return value


def configured_channels(diagnostic, quality, selections):
    """Validate a complete slot-keyed selection before changing any files."""
    quality = quality_with_defaults(quality)
    rows = [r for r in quality['channels'] if r['kind'] in MAGNETIC_KINDS]
    expected = {channel_id(r) for r in rows}
    if not isinstance(selections, list) or len(selections) != len(rows):
        raise ValueError('通道设置必须包含本次全部磁通环和探针')
    weights = {}
    for entry in selections:
        if not isinstance(entry, dict) or set(entry) != {'channel_id', 'weight'}:
            raise ValueError('通道设置字段无效')
        key, weight = entry['channel_id'], entry['weight']
        if not isinstance(key, str) or key not in expected or key in weights:
            raise ValueError('通道编号重复或不属于本次分析')
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight < 0:
            raise ValueError('权重必须为有限的非负数；0 表示不纳入')
        if key.startswith('loops:') and weight not in (0, 1):
            raise ValueError('当前内核的磁通环权重仅支持 0 或 1；探针支持连续权重')
        weights[key] = float(weight)
    if set(weights) != expected:
        raise ValueError('通道设置不完整')
    diagnostic = json.loads(json.dumps(diagnostic))
    measurement = diagnostic['inputs']['measurements']
    arrays = {'loops': [None] * len(measurement['coils']),
              'probes': [None] * len(measurement['expmp2'])}
    changes = []
    for row in rows:
        key = channel_id(row)
        weight = weights[key]
        if weight > 0 and (row['samples'] < 2 or row['drift'] and row['baseline_samples'] < 3):
            raise ValueError(f"{row['node']} 缺少目标窗或炮前样本，不能纳入拟合")
        if row['weight'] != weight:
            changes.append({'channel_id': key, 'node': row['node'], 'before': row['weight'], 'after': weight})
        row.update(weight=weight, role='fit' if weight > 0 else 'exclude')
        idx = row['index']
        if not isinstance(idx, int) or not 0 <= idx < len(arrays[row['kind']]) or arrays[row['kind']][idx] is not None:
            raise ValueError('通道槽位与求解输入不一致')
        arrays[row['kind']][idx] = weight
    if any(x is None for values in arrays.values() for x in values):
        raise ValueError('求解输入的通道槽位不完整')
    if not all(any(x > 0 for x in values) for values in arrays.values()):
        raise ValueError('本路线至少保留一个磁通环和一个探针；是否足够约束平衡仍由求解检查')
    measurement['fwtsi'], measurement['fwtmp2'] = arrays['loops'], arrays['probes']
    measurement['n_probe_active'] = sum(x > 0 for x in arrays['probes'])
    quality['active_counts'] = {kind: sum(r['kind'] == kind and r['weight'] > 0 for r in quality['channels'])
                                for kind in quality['active_counts']}
    quality['inactive_count'] = sum(r['weight'] <= 0 for r in quality['channels'])
    quality['channel_customized'] = any(r['weight'] != r['default_weight'] for r in rows)
    quality['passed'] = True
    return diagnostic, quality, changes


def save_channel_revision(w, roots, folder, body):
    if set(body) != {'case_id', 'diagnostics_sha256', 'channels'}:
        raise ValueError('通道修订字段无效')
    status = read(folder / 'status.json')
    if status['state'] not in ('acquired', 'adopted', 'waiting_review', 'reviewed'):
        raise ValueError('请等待取数或求解结束后再调整通道')
    if body['diagnostics_sha256'] != status['diagnostics_sha256']:
        raise ValueError('页面的输入版本已过期，请刷新后重试')
    for name, field in [('diagnostics.json', 'diagnostics_sha256'), ('quality.json', 'quality_sha256'),
                        ('raw-windows.json.gz', 'raw_sha256')]:
        if digest(folder / name) != status[field]:
            raise ValueError('原始或处理数据身份已变化，拒绝创建通道修订')
    diagnostic, quality, changes = configured_channels(read(folder / 'diagnostics.json'),
                                                       read(folder / 'quality.json'), body['channels'])
    if not changes:
        return status_view(folder)
    package_root, _, _ = packaged(folder)
    # Use the same package manifest resolution as ordinary case creation.
    _, manifest_path, _ = archive().package()
    manifest = read(manifest_path)
    cid = 'case-' + uuid.uuid4().hex[:12]
    destination = base(w, roots) / cid
    pending = base(w, roots) / ('.pending-' + uuid.uuid4().hex)
    pending.mkdir()
    try:
        parent = read(folder / 'case.json')
        case = {**parent, 'case_id': cid, 'created_at': time.time(),
                'parent_case_id': parent['case_id'], 'channel_revision': parent.get('channel_revision', 0) + 1}
        edit = {'parent_case_id': parent['case_id'], 'parent_diagnostics_sha256': status['diagnostics_sha256'],
                'changes': changes, 'created_at': case['created_at'], 'actor': os.environ.get('USER', 'local-user')}
        write(pending / 'channel-config.json', edit)
        diagnostic.setdefault('audit_provenance', {})['channel_config_sha256'] = digest(pending / 'channel-config.json')
        diagnostic['audit_provenance']['parent_diagnostics_sha256'] = status['diagnostics_sha256']
        write(pending / 'case.json', case)
        write(pending / 'diagnostics.json', diagnostic)
        write(pending / 'quality.json', quality)
        shutil.copyfile(folder / 'raw-windows.json.gz', pending / 'raw-windows.json.gz')
        clone_adapter(pending, package_root, manifest)
        write(pending / 'status.json', {'state': 'acquired', 'stage': 'processing', 'numerical': 'not_assessed',
               'scientific': 'not_experimentally_qualified', 'created_at': case['created_at'],
               'updated_at': time.time(), 'acquired_at': status.get('acquired_at'),
               'raw_sha256': status['raw_sha256'], 'diagnostics_sha256': digest(pending / 'diagnostics.json'),
               'quality_sha256': digest(pending / 'quality.json'), 'worker_pid': None})
        os.rename(pending, destination)
    except Exception:
        shutil.rmtree(pending)
        raise
    return status_view(destination)


def failure_view(tier):
    if tier.get('status') != 'error':
        return None
    scan = []
    for round_ in (tier.get('rounds') or []):
        for item in (round_.get('scan') or []):
            scan.append({'zc': item.get('zc'), 'error': item.get('error'),
                         'chi2': item.get('chi2'), 'q0': item.get('q0'),
                         'converged': item.get('converged')})
    return {'message': tier.get('error'), 'mode': (tier.get('scan') or {}).get('mode'),
            'count': len(scan), 'sample': scan[:5]}


def result_view(folder):
    status = read(folder / 'status.json')
    if status['state'] not in ('waiting_review', 'reviewed'):
        raise ValueError('本分析尚无可审阅结果')
    path = folder / 'result.json'
    if digest(path) != status['result_sha256']:
        raise ValueError('结果身份已变化')
    result = read(path)
    status = {**status, **result_verdict(result)}
    tier = result['tiers']['M']
    identity = read(folder / 'result.identity.json')
    return {'case': read(folder / 'case.json'), 'status': status,
            'facts': tier.get('facts', {}), 'boundary': tier.get('boundary', []),
            'q': tier.get('q', {'x': [], 'q': []}),
            'channels': tier.get('channels', {'loops': [], 'probes': []}),
            'profiles': tier.get('profiles', {}), 'grid': tier.get('grid'), 'psi': tier.get('psi'),
            'pressure_input': tier.get('pressure_input') or result.get('pressure_input'),
            'pressure_provenance': result.get('pressure_provenance'),
            'limiter': (result.get('device') or {}).get('limiter'),
            'solver_message': tier.get('error'), 'history': result.get('history', []),
            'failure': failure_view(tier),
            'physics_check': tier.get('physics_check'), 'assessment': tier.get('assessment'),
            'identity': identity, 'input_identity': {'diagnostics_sha256': read(folder / 'adoption.json')['diagnostics_sha256'],
                                                    'actual_input_sha256': status['actual_input_sha256']},
            'interpretation': {'numerical': '原生 M 档数值状态；不是实验物理资格',
                               'geometry': '磁测位置、PF 拟合假设与 EFIT 的同口径比较仍需独立核对',
                               'uncertainty': '通道误差为历史/装置规则，未完成独立实验标定'}}


def channel_view(folder, key, slot=None):
    status = read(folder / 'status.json')
    if status['state'] not in ('acquired', 'adopted', 'running', 'waiting_review', 'reviewed'):
        raise ValueError('尚无实验波形')
    quality = read(folder / 'quality.json')
    row = next((x for x in quality['channels'] if x['source_key'] == key and (slot is None or channel_id(x) == slot)), None)
    if row is None:
        raise ValueError('通道不属于本分析')
    raw = folder / 'raw-windows.json.gz'
    if digest(raw) != status['raw_sha256']:
        raise ValueError('原始窗口身份已变化')
    with gzip.open(raw, 'rt', encoding='utf-8') as stream:
        wave = json.load(stream)['windows'][key]
    n = len(wave['target_t'])
    stride = max(1, math.ceil(n / MAX_CHANNEL_SAMPLES))
    diagnostic = read(folder / 'diagnostics.json')['inputs']['measurements']
    processed = None
    if row['kind'] == 'loops':
        processed = diagnostic['coils'][row['index']]
    elif row['kind'] == 'probes':
        processed = diagnostic['expmp2'][row['index']]
    elif row['kind'] == 'pf':
        device = read(folder / 'diagnostics.json')['inputs']['device']
        pf = device['pf_active'].get('fylite:channel') or []
        slot = pf[row['index']]['efit_index'] if pf else row['index']
        processed = diagnostic['brsp'][slot]
    elif row['kind'] == 'global':
        processed = diagnostic['plasma']
    bt, by = wave['baseline_t'], wave['baseline_y']
    if row['drift'] and len(bt) >= 3:
        centre = sum(bt) / len(bt)
        average = sum(by) / len(by)
        xx = sum((x - centre) ** 2 for x in bt)
        slope = sum((x - centre) * (y - average) for x, y in zip(bt, by)) / xx if xx else 0.0
        intercept = average - slope * centre
    else:
        slope = intercept = 0.0
    processed_wave = [(y - slope * t - intercept) * row['scale']
                      for t, y in zip(wave['target_t'], wave['target_y'])]
    return {'channel': row, 'target_t': wave['target_t'][::stride], 'target_y': wave['target_y'][::stride],
            'processed_y': processed_wave[::stride], 'baseline_samples': len(bt),
            'drift_fit': {'slope': slope, 'intercept': intercept} if row['drift'] and len(bt) >= 3 else None,
            'processed_value': processed,
            'raw_sha256': status['raw_sha256'], 'sample_stride': stride}


def active_elsewhere(w, roots, current):
    for item in base(w, roots).glob('case-*'):
        if item == current or not (item / 'status.json').is_file():
            continue
        state = status_view(item)['status']['state']
        if state in ('acquiring', 'running'):
            return item.name
    return None


DD_NODES = [
    ('magnetics/flux_loop', 'diagnostics', 'flux_loop'),
    ('magnetics/bpol_probe', 'diagnostics', 'bpol_probe'),
    ('pf_active/coil', 'diagnostics', 'pf_coil'),
    ('equilibrium/time_slice/0/global_quantities/ip', 'diagnostics', 'ip'),
    ('equilibrium/time_slice/0/profiles_1d/psi', 'result', 'psi'),
    ('equilibrium/time_slice/0/profiles_1d/pressure', 'result', 'pressure'),
    ('equilibrium/time_slice/0/profiles_1d/q', 'result', 'q'),
    ('equilibrium/time_slice/0/profiles_1d/f', 'result', 'f'),
    ('equilibrium/time_slice/0/profiles_1d/j_tor', 'result', 'j_tor'),
    ('equilibrium/time_slice/0/boundary/outline', 'result', 'outline'),
    ('equilibrium/time_slice/0/profiles_2d/psi', 'result', 'psi2d'),
    ('equilibrium/time_slice/0/global_quantities/magnetic_axis', 'result', 'axis'),
    ('equilibrium/time_slice/0/global_quantities/beta_p', 'result', 'beta_p'),
    ('equilibrium/time_slice/0/global_quantities/li_3', 'result', 'li_3'),
]


def export_dd(folder):
    """把输入与结果按 IMAS DD 路径写成独立文件；无论运行是否通过都写。"""
    root = folder / 'dd'
    root.mkdir(exist_ok=True)
    diag_path, res_path = folder / 'diagnostics.json', folder / 'result.json'
    diag = read(diag_path) if diag_path.is_file() else None
    result = read(res_path) if res_path.is_file() else None
    tier = (result or {}).get('tiers', {}).get('M') or {}
    pr = tier.get('profiles') or {}
    written = 0
    for dd, src, key in DD_NODES:
        body = None
        if src == 'diagnostics' and diag is not None:
            m = diag.get('inputs', {}).get('measurements', {})
            if key == 'flux_loop':
                body = {'ids': 'magnetics', 'path': 'flux_loop', 'channels': m.get('loops') or []}
            elif key == 'bpol_probe':
                body = {'ids': 'magnetics', 'path': 'bpol_probe', 'channels': m.get('probes') or []}
            elif key == 'pf_coil':
                body = {'ids': 'pf_active', 'path': 'coil', 'currents': m.get('pf') or m.get('pf_currents') or []}
            elif key == 'ip':
                body = {'ids': 'equilibrium', 'path': 'time_slice/0/global_quantities/ip',
                        'value': m.get('plasma'), 'unit': 'A'}
        elif src == 'result' and result is not None:
            if key in ('psi', 'pressure', 'q', 'f'):
                mapping = {'psi': 'psi', 'pressure': 'pres', 'q': 'qpsi', 'f': 'fpol'}
                arr = pr.get(mapping[key])
                if arr:
                    body = {'ids': 'equilibrium', 'path': 'time_slice/0/profiles_1d/' + key,
                            'psi': pr.get('psin'), key: arr}
            elif key == 'j_tor':
                if pr.get('jphi'):
                    body = {'ids': 'equilibrium', 'path': 'time_slice/0/profiles_1d/j_tor',
                            'psi': pr.get('jphi_psin'), 'j_tor': pr.get('jphi'), 'unit': 'A/m^2'}
            elif key == 'outline':
                if tier.get('boundary'):
                    body = {'ids': 'equilibrium', 'path': 'time_slice/0/boundary/outline',
                            'r': [p[0] for p in tier['boundary']], 'z': [p[1] for p in tier['boundary']]}
            elif key == 'psi2d':
                if tier.get('grid') and tier.get('psi'):
                    body = {'ids': 'equilibrium', 'path': 'time_slice/0/profiles_2d/psi',
                            'grid': tier['grid'], 'psi': tier['psi'], 'unit': 'Wb'}
            elif key == 'axis':
                f = tier.get('facts') or {}
                if f.get('axis_r') is not None:
                    body = {'ids': 'equilibrium', 'path': 'time_slice/0/global_quantities/magnetic_axis',
                            'r': f.get('axis_r'), 'z': f.get('axis_z'), 'unit': 'm'}
            elif key in ('beta_p', 'li_3'):
                f = tier.get('facts') or {}
                v = f.get('beta_p' if key == 'beta_p' else 'li3')
                if v is not None:
                    body = {'ids': 'equilibrium', 'path': 'time_slice/0/global_quantities/' + key, 'value': v}
        if body is None:
            continue
        target = root / (dd + '.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        write(target, body)
        written += 1
    return written


def dd_list(folder):
    export_dd(folder)
    root = folder / 'dd'
    files = []
    for path in sorted(root.rglob('*.json')):
        files.append({'path': str(path.relative_to(root)), 'size': path.stat().st_size})
    return {'files': files, 'root': 'dd/'}


def dd_read(folder, rel):
    root = (folder / 'dd').resolve()
    target = (root / rel).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise ValueError('DD 路径无效')
    return read(target)

def file_catalog(folder):
    inputs, outputs = [], []

    def add(bucket, dd, name, note):
        path = folder / name
        if path.is_file():
            bucket.append({'dd': dd, 'file': name, 'size': path.stat().st_size,
                           'sha256': digest(path)[:16], 'note': note})

    diag = 'diagnostics.json'
    add(inputs, 'magnetics/flux_loop', diag, '磁通环')
    add(inputs, 'magnetics/bpol_probe', diag, '磁探针')
    add(inputs, 'pf_active/coil', diag, 'PF 回路电流')
    add(inputs, 'equilibrium/time_slice/0/global_quantities/ip', diag, '等离子体电流')
    add(inputs, 'raw/magnetics (raw windows)', 'raw-windows.json.gz', '原始波形窗')
    res = 'result.json'
    for dd, note in (
            ('equilibrium/time_slice/0/profiles_1d/psi', '极向磁通'),
            ('equilibrium/time_slice/0/profiles_1d/pressure', '压力'),
            ('equilibrium/time_slice/0/profiles_1d/q', '安全因子'),
            ('equilibrium/time_slice/0/profiles_1d/f', '极向电流函数'),
            ('equilibrium/time_slice/0/profiles_1d/j_tor', '环向电流密度'),
            ('equilibrium/time_slice/0/boundary/outline', 'LCFS 边界'),
            ('equilibrium/time_slice/0/profiles_2d/psi', 'ψ(R,Z) 网格'),
            ('equilibrium/time_slice/0/global_quantities/magnetic_axis', '磁轴位置'),
            ('equilibrium/time_slice/0/global_quantities/beta_p', '极向比压'),
            ('equilibrium/time_slice/0/global_quantities/li_3', '内电感')):
        add(outputs, dd, res, note)
    return {'inputs': inputs, 'outputs': outputs}


def dispatch(w, method, route, body, root, roots, query):
    op = route.removeprefix('archive-magnetic-')
    if method == 'GET':
        if op == 'info':
            ready = archive().readiness()
            return {'schema': SCHEMA, 'readiness': ready,
                    'features': ['mdsplus-acquire', 'raw-window', 'quality', 'adopt', 'native-M', 'review', 'channel-revisions'],
                    'mask_profiles': {'m02_pinned': '164437 历史 79 道掩码与固定权重',
                                      'device_default': '装置解析得到的默认通道角色；探索性运行'}}
        if op == 'cases':
            return {'cases': [compact(p) for p in sorted(base(w, roots).glob('case-*'), reverse=True)
                              if (p / 'case.json').is_file()]}
        folder = casepath(w, roots, query.get('case_id', [''])[0])
        if op == 'case':
            return status_view(folder)
        if op == 'result':
            return result_view(folder)
        if op == 'channel':
            return channel_view(folder, query.get('key', [''])[0], query.get('channel_id', [None])[0])
        if op == 'log':
            kind = query.get('kind', ['acquire'])[0]
            if kind not in ('acquire', 'solve', 'native'):
                raise ValueError('未知日志类别')
            path = folder / (kind + '.log')
            return {'kind': kind, 'text': path.read_text(errors='replace')[-8000:] if path.is_file() else ''}
        if op == 'dd':
            return dd_list(folder)
        if op == 'dd-file':
            return dd_read(folder, query.get('path', [''])[0])
        if op == 'files':
            return file_catalog(folder)
        if op == 'input':
            status = read(folder / 'status.json')
            if status['state'] not in ('adopted', 'running', 'waiting_review', 'reviewed'):
                raise ValueError('尚未采纳求解输入')
            return {'diagnostics': read(folder / 'diagnostics.json'),
                    'adoption': read(folder / 'adoption.json'),
                    'actual_input': read(folder / 'result.input.json') if (folder / 'result.input.json').is_file() else None}
        raise ValueError('未知纯磁查询')
    if method != 'POST' or not isinstance(body, dict):
        raise ValueError('未知纯磁操作')
    if op == 'create':
        if set(body) != {'shot', 'time_s', 'mask_profile'}:
            raise ValueError('新建分析字段不完整')
        shot, target, profile = body['shot'], body['time_s'], body['mask_profile']
        if isinstance(shot, bool) or not isinstance(shot, int) or shot <= 0 or not isinstance(target, (int, float)) or not math.isfinite(target) or target <= 0:
            raise ValueError('炮号或目标时刻无效')
        if profile not in ('m02_pinned', 'device_default') or profile == 'm02_pinned' and shot != 164437:
            raise ValueError('历史 M02 掩码只适用于 164437；其他炮号请选择装置默认规则')
        package_root, manifest_path, deps = archive().package()
        if profile == 'm02_pinned':
            archive().case_input('EQ-M02', package_root)
        cid = 'case-' + uuid.uuid4().hex[:12]
        folder = base(w, roots) / cid
        folder.mkdir(exist_ok=False)
        case = {'schema': SCHEMA, 'case_id': cid, 'device': 'EAST', 'shot': shot, 'time_s': float(target),
                'mask_profile': profile, 'package_path': str(package_root),
                'package_manifest_sha256': digest(manifest_path), 'created_at': time.time(),
                'scientific_scope': '纯磁 M 档；不加入压力、TS、POINT 或 q₀ 目标；实验资格未认证'}
        write(folder / 'case.json', case)
        clone_adapter(folder, package_root, read(manifest_path))
        write(folder / 'status.json', {'state': 'created', 'stage': 'source', 'numerical': 'not_assessed',
                                       'scientific': 'not_experimentally_qualified', 'created_at': case['created_at'],
                                       'updated_at': case['created_at']})
        return status_view(folder)
    folder = casepath(w, roots, body.get('case_id', ''))
    with LOCK:
        status = read(folder / 'status.json')
        if op == 'channels':
            return save_channel_revision(w, roots, folder, body)
        if op == 'acquire':
            if set(body) != {'case_id'} or status['state'] != 'created':
                raise ValueError('仅新建分析可以启动实验取数')
            other = active_elsewhere(w, roots, folder)
            if other:
                raise ValueError('已有实验取数或求解进行中：' + other)
            _, _, deps = archive().package()
            write(folder / 'status.json', {**status, 'state': 'acquiring', 'stage': 'source', 'started_at': time.time()})
            pid = launch(folder, 'acquire', deps)
            update_status(folder, worker_pid=pid)
            return status_view(folder)
        if op == 'adopt':
            if set(body) != {'case_id', 'note'} or status['state'] != 'acquired':
                raise ValueError('请先完成实验取数与质量检查')
            note = str(body['note']).strip()
            if not 1 <= len(note) <= 2000:
                raise ValueError('请填写采纳依据（1–2000字）')
            quality = read(folder / 'quality.json')
            if not quality['passed'] or digest(folder / 'quality.json') != status['quality_sha256']:
                raise ValueError('质量检查身份不符')
            adoption = {'note': note, 'adopted_at': time.time(), 'actor': os.environ.get('USER', 'local-user'),
                        'diagnostics_sha256': status['diagnostics_sha256'],
                        'raw_sha256': status['raw_sha256'], 'quality_sha256': status['quality_sha256']}
            write(folder / 'adoption.json', adoption)
            update_status(folder, state='adopted', stage='input', adopted_at=adoption['adopted_at'])
            return status_view(folder)
        if op == 'retry':
            if set(body) != {'case_id'}:
                raise ValueError('重试字段不完整')
            if status['state'] != 'failed':
                raise ValueError('仅失败的运行可重试')
            other = active_elsewhere(w, roots, folder)
            if other:
                raise ValueError('已有实验取数或求解进行中：' + other)
            adoption = read(folder / 'adoption.json')
            if digest(folder / 'diagnostics.json') != adoption['diagnostics_sha256']:
                raise ValueError('已采纳输入身份变化，无法重试')
            _, _, deps = archive().package()
            attempts = folder / 'attempts'
            attempts.mkdir(exist_ok=True)
            used = [int(p.name.split('-')[-1]) for p in attempts.glob('attempt-*') if p.name.split('-')[-1].isdigit()]
            target = attempts / ('attempt-%02d' % (1 + (max(used) if used else 0)))
            target.mkdir()
            for name in ('result.json', 'result.identity.json', 'result.input.json', 'solve.log', 'native.log'):
                src = folder / name
                if src.is_file():
                    shutil.move(str(src), str(target / name))
            keep = {k: v for k, v in status.items()
                    if k not in ('error', 'ended_at', 'worker_pid', 'result_sha256',
                                 'actual_input_sha256', 'result_identity_sha256', 'solver_message')}
            write(folder / 'status.json', {**keep, 'state': 'adopted', 'stage': 'input'})
            write(folder / 'status.json', {**read(folder / 'status.json'), 'state': 'running',
                                           'stage': 'solve', 'started_solve_at': time.time()})
            pid = launch(folder, 'solve', deps)
            update_status(folder, worker_pid=pid)
            return {**status_view(folder), 'attempt': target.name}
        if op == 'execute':
            if set(body) != {'case_id'} or status['state'] != 'adopted':
                raise ValueError('仅已采纳的输入可启动一次求解')
            other = active_elsewhere(w, roots, folder)
            if other:
                raise ValueError('已有实验取数或求解进行中：' + other)
            _, _, deps = archive().package()
            if digest(folder / 'diagnostics.json') != read(folder / 'adoption.json')['diagnostics_sha256']:
                raise ValueError('已采纳输入身份变化')
            write(folder / 'status.json', {**status, 'state': 'running', 'stage': 'solve', 'started_solve_at': time.time()})
            pid = launch(folder, 'solve', deps)
            update_status(folder, worker_pid=pid)
            return status_view(folder)
        if op == 'cancel':
            if set(body) != {'case_id'} or status['state'] not in ('acquiring', 'running'):
                raise ValueError('当前没有可停止的任务')
            pid = status.get('worker_pid')
            if not isinstance(pid, int) or pid <= 0:
                raise ValueError('工作进程身份尚未就绪')
            process = Path('/proc') / str(pid)
            try:
                command = process.joinpath('cmdline').read_bytes().split(b'\0')
                verified = str(folder).encode() in command and process.stat().st_uid == os.getuid() and os.getpgid(pid) == pid
            except (OSError, ProcessLookupError):
                verified = False
            if not verified:
                raise ValueError('工作进程身份不匹配，拒绝停止')
            os.killpg(pid, signal.SIGTERM)
            update_status(folder, state='cancelled', stage=status['stage'], ended_at=time.time(), worker_pid=None)
            return status_view(folder)
        if op == 'review':
            if set(body) != {'case_id', 'accepted', 'note'} or status['state'] != 'waiting_review':
                raise ValueError('仅待审阅结果可以提交结论')
            if not isinstance(body['accepted'], bool):
                raise ValueError('审阅结论必须明确')
            note = str(body['note']).strip()
            if not 1 <= len(note) <= 2000:
                raise ValueError('请填写审阅说明（1–2000字）')
            if body['accepted'] and verified_status(folder, status).get('gate', {}).get('state') != 'passed':
                raise ValueError('原生结果检查未通过，不能标记为分析可用')
            if (body['accepted'] and read(folder / 'case.json')['mask_profile'] == 'device_default' and
                    not read(folder / 'quality.json').get('channel_customized')):
                raise ValueError('装置默认掩码仅供探索；请基于通道检查建立修订后再审阅')
            review = {'accepted_for_analysis': body['accepted'], 'note': note,
                      'reviewed_at': time.time(), 'actor': os.environ.get('USER', 'local-user'),
                      'scope': '仅为本次分析审阅，不授予实验物理资格'}
            write(folder / 'review.json', review)
            update_status(folder, state='reviewed', stage='result', review=review)
            return status_view(folder)
    raise ValueError('未知纯磁操作')


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] != '--worker' or sys.argv[2] not in ('acquire', 'solve'):
        raise SystemExit('worker 参数无效')
    worker(Path(sys.argv[3]).resolve(strict=True), sys.argv[2])
