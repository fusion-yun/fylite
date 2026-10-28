import copy
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'delivery/eq/apps/workflow/magnetic_live.py'
if not MODULE.exists():
    MODULE = Path(__file__).with_name('magnetic_live.py')
spec = importlib.util.spec_from_file_location('magnetic_live_channels_test', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ChannelConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.diag = {'inputs': {'measurements': {'coils': [1.0, 2.0], 'expmp2': [3.0, 4.0],
                    'fwtsi': [1.0, 0.0], 'fwtmp2': [1.0, 1.0], 'n_probe_active': 2}}}
        rows = []
        for kind, weights in [('loops', [1.0, 0.0]), ('probes', [1.0, 1.0])]:
            for i, w in enumerate(weights):
                rows.append({'kind': kind, 'index': i, 'node': 'shared' if kind == 'probes' else 'FL'+str(i),
                             'weight': w, 'role': 'fit' if w else 'exclude', 'samples': 10,
                             'baseline_samples': 30, 'drift': True})
        self.q = {'channels': rows, 'active_counts': {'loops': 1, 'probes': 2}, 'inactive_count': 1, 'passed': True}
        self.selection = [{'channel_id': m.channel_id(r), 'weight': r['weight']} for r in rows]

    def test_defaults_leave_values_and_input_unchanged(self):
        before = copy.deepcopy((self.diag, self.q))
        d, q, changes = m.configured_channels(self.diag, self.q, self.selection)
        self.assertEqual(d, self.diag)
        self.assertEqual(changes, [])
        self.assertFalse(q['channel_customized'])
        self.assertEqual((self.diag, self.q), before)

    def test_edit_maps_slots_including_duplicate_node_names(self):
        self.selection[1]['weight'] = 1
        self.selection[2]['weight'] = .5
        self.selection[3]['weight'] = 0
        d, q, changes = m.configured_channels(self.diag, self.q, self.selection)
        self.assertEqual(d['inputs']['measurements']['fwtsi'], [1, 1])
        self.assertEqual(d['inputs']['measurements']['fwtmp2'], [.5, 0])
        self.assertEqual(d['inputs']['measurements']['n_probe_active'], 1)
        self.assertEqual(q['active_counts'], {'loops': 2, 'probes': 1})
        self.assertEqual(len(changes), 3)
        self.assertEqual(q['channels'][1]['default_weight'], 0)
        self.assertTrue(q['channel_customized'])
        reset = [{'channel_id': m.channel_id(r), 'weight': r['default_weight']} for r in q['channels']]
        restored, restored_q, _ = m.configured_channels(d, q, reset)
        self.assertEqual(restored, self.diag)
        self.assertFalse(restored_q['channel_customized'])

    def test_rejects_non_effective_loop_weight_and_invalid_numbers(self):
        for idx, value in [(0, .5), (2, -1), (2, float('nan')), (2, float('inf')), (2, True)]:
            with self.subTest(idx=idx, value=value):
                x = copy.deepcopy(self.selection)
                x[idx]['weight'] = value
                with self.assertRaises(ValueError):
                    m.configured_channels(self.diag, self.q, x)

    def test_rejects_missing_duplicate_and_unknown_slots(self):
        for x in [self.selection[:-1], self.selection[:-1]+[self.selection[0]],
                  self.selection[:-1]+[{'channel_id': 'probes:99', 'weight': 1}]]:
            with self.assertRaises(ValueError):
                m.configured_channels(self.diag, self.q, x)

    def test_cannot_enable_missing_samples_or_remove_whole_family(self):
        self.q['channels'][1]['samples'] = 0
        self.selection[1]['weight'] = 1
        with self.assertRaises(ValueError):
            m.configured_channels(self.diag, self.q, self.selection)
        self.selection[1]['weight'] = 0
        self.selection[0]['weight'] = 0
        with self.assertRaises(ValueError):
            m.configured_channels(self.diag, self.q, self.selection)


if __name__ == '__main__':
    unittest.main()
