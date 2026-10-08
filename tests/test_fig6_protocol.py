"""Fig. 6 physics, protocol, event workload and boundary regressions."""
import importlib.util
import math
import unittest

SETTINGS = dict(duration=.003, send_rate=1000, link_length_km=10,
                speed_km_s=200000, depolar_rate=200,
                noise_during_transit=True, initial_fidelity=1)


class Fig6ProtocolTests(unittest.TestCase):
    def runner(self):
        self.assertIsNotNone(importlib.util.find_spec('evaluations.fig6_protocol'),
                             'Fig. 6 protocol is not implemented')
        from evaluations.fig6_protocol import run_trial
        return run_trial

    def test_zero_noise_corrected_chain(self):
        run = self.runner()
        for nodes in [2, 3, 4]:
            for seed in range(8):
                result = run('qubit', nodes, {**SETTINGS, 'depolar_rate': 0}, seed)
                self.assertEqual(result['completed_pairs'], 3)
                self.assertTrue(all(abs(f - 1) < 1e-10 for f in result['completion_fidelities']))
                self.assertEqual(len(set(result['completed_rounds'])), 3)

    def test_backend_noise_and_event_workload_equivalence(self):
        run = self.runner()
        for nodes in [2, 3, 4]:
            q = run('qubit', nodes, SETTINGS, 42)
            w = run('werner', nodes, SETTINGS, 42)
            self.assertEqual(q['completion_times'], w['completion_times'])
            self.assertEqual(q['event_count'], w['event_count'])
            expected = (1 + 3 * math.exp(-.02 * (2 * nodes - 3))) / 4
            for fq, fw in zip(q['completion_fidelities'], w['completion_fidelities']):
                self.assertAlmostEqual(fq, expected, places=10)
                self.assertAlmostEqual(fw, expected, places=10)

    def test_50_node_state_bound_and_late_completion(self):
        run = self.runner()
        result = run('qubit', 50, {**SETTINGS, 'duration': .003}, 4)
        self.assertEqual(result['completed_pairs'], 1)
        self.assertEqual(result['scheduled_rounds'], 3)
        self.assertLessEqual(result['max_state_qubits'], 4)
        self.assertAlmostEqual(result['completion_times'][0], .00245, places=9)

    def test_split_noise_and_both_halves(self):
        self.runner()
        from evaluations.fig6_backends import make_backend
        for name in ['qubit', 'werner']:
            adapter = make_backend(name, SETTINGS, 42)
            pair = adapter.create_link(0)
            adapter.apply_noise(pair, .00002)
            adapter.apply_noise(pair, .00005)
            self.assertAlmostEqual(adapter.fidelity(pair),
                                   (1 + 3 * math.exp(-.02)) / 4, places=10)
            before = adapter.fidelity(pair)
            adapter.apply_noise(pair, .00005)
            self.assertAlmostEqual(adapter.fidelity(pair), before, places=10)

    def test_all_bell_branches_correct(self):
        self.runner()
        from evaluations.fig6_backends import make_backend
        branches = set()
        for seed in range(100):
            adapter = make_backend('qubit', {**SETTINGS, 'depolar_rate': 0}, seed)
            pair, x, z = adapter.swap(adapter.create_link(0), adapter.create_link(0), 0)
            branches.add((x, z))
            adapter.correct(pair, x, z)
            self.assertAlmostEqual(adapter.fidelity(pair), 1, places=10)
        self.assertEqual(branches, {(0, 0), (0, 1), (1, 0), (1, 1)})

    @unittest.skipUnless(importlib.util.find_spec('netsquid'), 'Optional NetSquid environment')
    def test_netsquid_matches_simqn(self):
        run = self.runner()
        for nodes in [2, 4, 10]:
            net = run('netsquid', nodes, SETTINGS, 42)
            q = run('qubit', nodes, SETTINGS, 42)
            self.assertEqual(net['completed_pairs'], q['completed_pairs'])
            self.assertEqual(net['event_count'], q['event_count'])
            for a, b in zip(net['completion_times'], q['completion_times']):
                self.assertAlmostEqual(a, b, places=9)
            for a, b in zip(net['completion_fidelities'], q['completion_fidelities']):
                self.assertAlmostEqual(a, b, places=10)
