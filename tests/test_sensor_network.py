"""독립/GHZ 센서의 위상 응답·자원 비교·잡음·통계 검증."""
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(name, *args):
    return subprocess.run([sys.executable, str(ROOT / 'examples' / name), *map(str, args)],
                          capture_output=True, text=True, timeout=60, cwd=ROOT)


class SensorNetworkTests(unittest.TestCase):
    def result(self, name, *args):
        p = execute(name, *args)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_independent_ramsey_response_and_actual_result_transmission(self):
        r = self.result('19_independent_sensor_network.py', '--shots', 160, '--repeats', 3)
        self.assertAlmostEqual(r['expected_signal'], -math.sin(0.1))
        self.assertLess(abs(sum(r['observed_signals']) / 3 + math.sin(0.1)), 0.1)
        self.assertEqual(r['sensor_uses'], 1440)
        self.assertEqual(r['received_measurements'], 1440)
        self.assertEqual(r['classical_packets_sent'], 960)
        self.assertLess(r['rmse'], 0.15)
        self.assertAlmostEqual(r['first_trial_trace'][-1]['time_seconds'], 0.025)

    def test_ghz_phase_response_and_equal_attempted_resources(self):
        r = self.result('20_entangled_sensor_network.py', '--shots', 160, '--repeats', 4)
        a, b = r['independent'], r['ghz']
        self.assertAlmostEqual(b['expected_signal'], -math.sin(0.3))
        self.assertEqual(a['sensor_uses'], b['sensor_uses'])
        self.assertEqual(a['quantum_transmissions'], b['quantum_transmissions'])
        self.assertEqual(b['completed_rounds'], 640)
        self.assertLess(b['rmse'], 0.1)
        self.assertAlmostEqual(r['ideal_local_information_gain'], 3)
        self.assertAlmostEqual(b['visibility'], 1)
        self.assertLess(abs(sum(b['observed_signals']) / 4 + math.sin(0.3)), 0.1)

    def test_total_loss_retains_partial_independent_data_but_no_ghz_estimate(self):
        r = self.result('20_entangled_sensor_network.py', '--shots', 8, '--repeats', 2,
                        '--drop-rate', 1)
        self.assertEqual(r['ghz']['completed_rounds'], 0)
        self.assertIsNone(r['ghz']['rmse'])
        self.assertEqual(r['ghz']['estimates'], [None, None])
        self.assertEqual(r['independent']['received_measurements'], 16)
        self.assertEqual(r['ghz']['sensor_uses'], 48)

    def test_t2_decay_matches_storage_intervals_and_suppresses_ghz_visibility(self):
        r = self.result('20_entangled_sensor_network.py', '--shots', 20, '--repeats', 2,
                        '--t2', 0.02)
        # source: 15 ms storage; two remote sensors: 5 ms each.
        self.assertAlmostEqual(r['ghz']['visibility'], math.exp(-0.025 / 0.02))
        self.assertLess(r['ghz']['visibility'], r['independent']['visibility'])

    def test_empirical_noisy_signal_and_repeat_uncertainty(self):
        r = self.result('20_entangled_sensor_network.py', '--shots', 400, '--repeats', 4,
                        '--t2', 0.02, '--phase', 0.2)
        for mode in ('independent', 'ghz'):
            row = r[mode]
            self.assertLess(abs(sum(row['observed_signals']) / 4 - row['expected_signal']), 0.08)
            self.assertIn('estimate_std', row)
            self.assertGreater(row['estimate_std'], 0)
            self.assertAlmostEqual(row['estimate_mean_standard_error'], row['estimate_std'] / 2)

    def test_submicrosecond_delays_use_actual_storage_time_for_calibration(self):
        r = self.result('20_entangled_sensor_network.py', '--shots', 40, '--repeats', 2,
                        '--quantum-delay', 0.0000009, '--interrogation', 0.0000009,
                        '--classical-delay', 0, '--t2', 0.000001)
        for mode in ('independent', 'ghz'):
            row = r[mode]
            self.assertEqual(row['storage_times_seconds'], [0, 0, 0])
            self.assertEqual(row['visibility'], 1)
            self.assertEqual(row['first_complete_round_seconds_if_successful'], 0)

    def test_fisher_information_is_stable_near_both_phase_branch_edges(self):
        for phase in (0.523598775, -0.523598775, 0.52359877):
            r = self.result('20_entangled_sensor_network.py', '--shots', 4, '--repeats', 1,
                            '--phase', phase)
            self.assertAlmostEqual(r['ghz']['expected_fisher_information_per_attempt'], 9)
            self.assertAlmostEqual(r['independent']['expected_fisher_information_per_attempt'], 3)
            self.assertAlmostEqual(r['expected_information_gain'], 3)

    def test_seed_reproducibility_and_phase_branch_validation(self):
        for name in ('19_independent_sensor_network.py', '20_entangled_sensor_network.py'):
            args = ('--shots', 10, '--repeats', 2)
            self.assertEqual(self.result(name, *args), self.result(name, *args))
            for bad in [('--nodes', 1), ('--nodes', 7), ('--phase', 'nan'),
                        ('--phase', 0.6), ('--t2', -1), ('--repeats', 0),
                        ('--shots', 0)]:
                p = execute(name, *bad)
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertNotIn('Traceback', p.stderr)


if __name__ == '__main__':
    unittest.main()
