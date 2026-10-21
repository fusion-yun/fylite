"""q0 mode capabilities and legacy-input compatibility; no native solve required."""
import copy
import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'delivery/eq/apps/workflow/workflow.py'
spec = importlib.util.spec_from_file_location('workflow_q_modes', path)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
legacy = {k: v for k, v in w.DEFAULT.items() if k != 'q_mode'}
assert w.parameters(legacy) == w.DEFAULT
assert 'q_mode' not in legacy  # Loading does not mutate an old snapshot.
for mode in ('none', 'soft', 'unknown', None):
    try:
        w.parameters({**legacy, 'q_mode': mode})
        raise AssertionError('unsupported mode accepted')
    except ValueError:
        pass
# Assembly preserves the native request for the supported mode and records provenance.
template = {'initial':{}, 'initial_pf':{}, 'measurement_template': {'magnetic': {}, 'global': {'q_weight': 1000}, 'pressure': {}, 'fsa': {}}, 'relax': .5, 'tolerance': 1e-6}
magnetic = {k: [1.] for k in ['loop_observed', 'probe_observed', 'loop_weights', 'probe_weights', 'pf_observed', 'pf_weights']}
magnetic.update(ip_observed=4e5, btor=-1.6)
pressure = {'psi_n': [0., 1.], 'pressure_Pa': [100., 0.], 'sigma_Pa': [10., 2.], 'weights': [1., 1.]}
def read(p):
    return copy.deepcopy({'native-template.json': template, 'magnetics.json': magnetic, 'pressure.json': pressure}[Path(p).name])
with patch.object(w, 'read', side_effect=read):
    old = w.assemble(Path('/data'), legacy, Path('/run'))
    explicit = w.assemble(Path('/data'), w.DEFAULT, Path('/run'))
    assert old['config'] == explicit['config']
    assert explicit['config']['initial']['target_ip'] == magnetic['ip_observed']
    assert explicit['config']['initial_pf']['pf_observed'] == magnetic['pf_observed']
    assert explicit['config']['measurement_template']['fsa']['measured_ip'] == magnetic['ip_observed']
    assert explicit['effective']['q_mode'] == 'target'
    assert explicit['effective']['q_normalization'] is True
print('PASS: legacy target mode, unsupported-mode rejection, unchanged native assembly and explicit provenance')
