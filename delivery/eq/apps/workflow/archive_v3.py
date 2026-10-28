"""Pinned standalone-v3 examples, isolated from the rc3 workflow and kernel."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import magnetic_live

EXPECTED_LIBRARY = 'f2632102e950788f96de324bfd7b6c9152604eb72b9ce774613022c29f3ffb94'
EXPECTED_M02_INPUT = '59c78975d62694c7904f868050254a47c2b7e409e3317d029be453561a3b48fe'
CASES = {
    'EQ-M02': {
        'title': 'EAST 164437 · 6.386 s 纯磁 M-129', 'shot': 164437,
        'time_s': 6.386, 'recipe': 'M', 'input': 'm02',
        'scope': '固定 79 道掩码的历史数值回归；不重新在线取数。',
        'limit': '数值收敛，但与同时间 EFIT 边界仍相差约 67 mm；PF 与外部位形未获实验验收。',
    },
    'EQ-D01': {
        'title': 'EAST 137985 · 4.041 s 磁测＋TS 缓存 MP', 'shot': 137985,
        'time_s': 4.041, 'recipe': 'MP', 'input': 'package',
        'scope': '用已保存磁测和 TS 输入执行 M→P 数值路线；不在线取数。',
        'limit': 'TS 清洗可疑：历史运行剔除 8/17 候选点；数值通过不表示诊断或实验合格。',
    },
}
LOCK = threading.Lock()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def write(path: Path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    os.replace(temporary, path)


def package():
    value = os.environ.get('FYLITE_EQ_V3_ROOT')
    if not value:
        raise ValueError('standalone-v3 包路径未配置')
    root = Path(value).resolve(strict=True)
    manifest_path = root / 'MANIFEST.sha256.json'
    manifest = read(manifest_path)
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError('standalone-v3 manifest 无效')
    for name, expected in manifest.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('standalone-v3 manifest 路径无效')
        file = (root / relative).resolve(strict=True)
        if not file.is_relative_to(root) or digest(file) != expected:
            raise ValueError('standalone-v3 文件身份不匹配：' + name)
    if manifest.get('libfylite.so') != EXPECTED_LIBRARY:
        raise ValueError('standalone-v3 原生库版本不匹配')
    dependencies = os.environ.get('FYLITE_EQ_V3_DEPS')
    if not dependencies or not (Path(dependencies) / 'libnetcdf.so.19').is_file() or not (Path(dependencies) / 'libhdf5_serial.so.103').is_file():
        raise ValueError('standalone-v3 的隔离 netCDF/HDF5 依赖未配置')
    return root, manifest_path, Path(dependencies).resolve(strict=True)


def case_input(case_id: str, root: Path) -> Path:
    if case_id == 'EQ-D01':
        return root / 'input/diagnostics_MP_cached.json'
    value = os.environ.get('FYLITE_EQ_V3_M02_INPUT')
    if not value:
        raise ValueError('164437 的冻结磁测输入未配置')
    path = Path(value).resolve(strict=True)
    if digest(path) != EXPECTED_M02_INPUT:
        raise ValueError('164437 的冻结磁测输入身份不匹配')
    return path


def storage(w, roots):
    root = w.personal(str(Path(roots[0]).expanduser() / 'archive-v3'), roots)
    root.mkdir(exist_ok=True)
    return root


def run_directory(w, roots, case_id, run_id):
    if case_id not in CASES:
        raise ValueError('未知算例')
    w.check_id(run_id)
    return w.personal(str(storage(w, roots) / case_id / run_id), roots)


def readiness():
    try:
        root, manifest, dependencies = package()
        for case_id in CASES:
            case_input(case_id, root)
        return {'ready': True, 'package_sha256': digest(manifest), 'library_sha256': EXPECTED_LIBRARY}
    except (OSError, ValueError, KeyError) as exc:
        return {'ready': False, 'reason': str(exc)}


def summaries(w, roots, case_id):
    if case_id not in CASES:
        raise ValueError('未知算例')
    folder = storage(w, roots) / case_id
    if not folder.exists():
        return []
    return [read(path / 'status.json') for path in sorted(folder.glob('run-*'), reverse=True)
            if (path / 'status.json').is_file()]


def execute(w, body, roots):
    if not isinstance(body, dict) or set(body) != {'case_id', 'request_id', 'acknowledged'}:
        raise ValueError('运行请求字段不完整')
    case_id = body['case_id']
    if case_id not in CASES:
        raise ValueError('未知算例')
    if body['acknowledged'] is not True:
        raise ValueError('请先阅读本算例的数据和科学限制')
    request_id = w.check_id(body['request_id'])
    root, manifest, dependencies = package()
    input_path = case_input(case_id, root)
    with LOCK:
        folder = storage(w, roots) / case_id
        folder.mkdir(exist_ok=True)
        for path in folder.glob('run-*'):
            snapshot = path / 'snapshot.json'
            if snapshot.is_file() and read(snapshot).get('request_id') == request_id:
                value = read(path / 'status.json')
                if value['case_id'] != case_id:
                    raise ValueError('请求编号已绑定其他算例')
                return value
        if any(item.get('state') == 'running' for cid in CASES for item in summaries(w, roots, cid)):
            raise ValueError('已有 standalone-v3 算例正在计算')
        run_id = 'run-' + time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '-' + uuid.uuid4().hex[:8]
        run = run_directory(w, roots, case_id, run_id)
        run.mkdir(exist_ok=False)
        snapshot = {
            'case_id': case_id, 'run_id': run_id, 'request_id': request_id,
            'package_manifest_sha256': digest(manifest),
            'library_sha256': EXPECTED_LIBRARY, 'input_sha256': digest(input_path),
            'input_path': str(input_path), 'package_path': str(root),
            'dependencies_path': str(dependencies), 'created_at': time.time(),
            'scope': CASES[case_id]['scope'], 'limit': CASES[case_id]['limit'],
        }
        write(run / 'snapshot.json', snapshot)
        status = {'case_id': case_id, 'run_id': run_id, 'state': 'running',
                  'created_at': snapshot['created_at'], 'numerical': 'not_assessed',
                  'scientific': 'not_experimentally_qualified'}
        write(run / 'status.json', status)
        output = (run / 'worker.log').open('xb')
        try:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', str(run)],
                                     stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                                     env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        except Exception:
            output.close()
            write(run / 'status.json', {**status, 'state': 'failed', 'error': 'worker 启动失败'})
            raise
        output.close()
        return {**status, 'worker_pid': child.pid}


def worker(run: Path):
    snapshot = read(run / 'snapshot.json')
    case_id = snapshot['case_id']
    root = Path(snapshot['package_path'])
    input_path = Path(snapshot['input_path'])
    dependencies = Path(snapshot['dependencies_path'])
    status = read(run / 'status.json')
    try:
        verified_root, _, _ = package()
        if verified_root != root:
            raise ValueError('执行包路径与冻结计划不一致')
        manifest = root / 'MANIFEST.sha256.json'
        if digest(manifest) != snapshot['package_manifest_sha256'] or digest(root / 'libfylite.so') != EXPECTED_LIBRARY or digest(input_path) != snapshot['input_sha256']:
            raise ValueError('运行前制品或输入身份已变化')
        result_path = run / 'result.json'
        command = [sys.executable, str(root / 'demo.py'), '--run', str(root / 'input/native.json'),
                   '--diagnostics', str(input_path), '--recipe', CASES[case_id]['recipe'],
                   '--out', str(result_path)]
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
               'LD_LIBRARY_PATH': str(dependencies) + (':' + os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else '')}
        with (run / 'native.log').open('xb') as log:
            completed = subprocess.run(command, cwd=run, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, timeout=180, check=False)
        if completed.returncode != 0 or not result_path.is_file():
            raise ValueError('原生计算未完成，退出码 ' + str(completed.returncode))
        result = read(result_path)
        identity = read(run / 'result.identity.json')
        if identity['output_sha256'] != digest(result_path) or identity['input_sha256'] != digest(run / 'result.input.json'):
            raise ValueError('结果输入/输出身份不匹配')
        if not result.get('converged'):
            raise ValueError('原生计算未数值收敛')
        tiers = result['tiers']
        if any(tiers[name]['status'] != 'ok' for name in (('M',) if case_id == 'EQ-M02' else ('M', 'P'))):
            raise ValueError('所需层级未完成')
        facts = tiers['M' if case_id == 'EQ-M02' else 'P']['facts']
        if case_id == 'EQ-M02':
            if abs(facts['axis_r'] - 2.00618) >= 1e-4 or abs(facts['chi2_mag'] - 378.31) >= .05:
                raise ValueError('164437 回归指标偏离历史已核对范围')
            warnings = [CASES[case_id]['limit']]
        else:
            certificate = tiers['P'].get('certificate', {})
            if certificate.get('cleaning_suspect') is not True:
                raise ValueError('137985 TS 质量状态与历史记录不符')
            warnings = [CASES[case_id]['limit'], *certificate.get('cleaning_reasons', [])]
        write(run / 'status.json', {**status, 'state': 'completed',
              'ended_at': time.time(), 'numerical': 'converged', 'warnings': warnings,
              'facts': {key: facts.get(key) for key in ('q0', 'q95', 'axis_r', 'axis_z', 'ip', 'chi2_mag', 'iterations', 'residual')}})
    except Exception as exc:
        write(run / 'status.json', {**status, 'state': 'failed', 'ended_at': time.time(),
              'numerical': 'not_confirmed', 'error': str(exc)[:500]})
        raise


def result_view(w, roots, case_id, run_id):
    run = run_directory(w, roots, case_id, run_id)
    status = read(run / 'status.json')
    if status['state'] != 'completed':
        raise ValueError('当前运行没有已核验结果')
    path = run / 'result.json'
    identity = read(run / 'result.identity.json')
    if identity['output_sha256'] != digest(path):
        raise ValueError('结果身份已变化')
    result = read(path)
    tier = result['tiers']['M' if case_id == 'EQ-M02' else 'P']
    return {'case_id': case_id, 'run_id': run_id, 'status': status,
            'facts': tier['facts'], 'boundary': tier['boundary'], 'q': tier['q'],
            'pressure': {k: v for k, v in tier['profiles'].items() if k in ('psin', 'pressure')},
            'identity': identity, 'scope': CASES[case_id]['scope'], 'limit': CASES[case_id]['limit']}


def dispatch(w, method, route, body, root, roots, query):
    if route.startswith('archive-magnetic-'):
        return magnetic_live.dispatch(w, method, route, body, root, roots, query)
    if method == 'GET' and route == 'archive-info':
        return {'schema': 'fylite.eq.archive-v3/1', 'readiness': readiness(),
                'cases': [{'case_id': case_id, **value} for case_id, value in CASES.items()]}
    if method == 'GET' and route == 'archive-runs':
        return {'runs': summaries(w, roots, query.get('case_id', [''])[0])}
    if method == 'GET' and route == 'archive-run':
        return read(run_directory(w, roots, query.get('case_id', [''])[0], query.get('run_id', [''])[0]) / 'status.json')
    if method == 'GET' and route == 'archive-result':
        return result_view(w, roots, query.get('case_id', [''])[0], query.get('run_id', [''])[0])
    if method == 'POST' and route == 'archive-execute':
        return execute(w, body, roots)
    raise ValueError('未知 standalone-v3 接口')


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--worker':
        raise SystemExit('usage: archive_v3.py --worker RUN_DIRECTORY')
    worker(Path(sys.argv[2]))
