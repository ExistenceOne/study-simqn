"""새 예제의 관찰 결과와 실제 파일 출력·프로세스 실행을 검증함."""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(name, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / 'examples' / name), *map(str, args)],
        capture_output=True, text=True, cwd=ROOT, timeout=60, check=False,
    )


class ModuleExamplesTests(unittest.TestCase):
    def result(self, name, *args):
        process = execute(name, *args)
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def test_qubit_factory_applies_bit_flip_to_zero_state(self):
        r = self.result('06_qubit_backend.py', '--shots', 100, '--flip-probability', 1)
        self.assertEqual(r['noisy_zero'], {'0': 0, '1': 100})
        self.assertEqual(r['ideal_zero'], {'0': 100, '1': 0})
        self.assertEqual(r['mixed_density_matrix'], [[0.5, 0.0], [0.0, 0.5]])

    def test_entanglement_operations_consume_inputs_and_change_fidelity(self):
        r = self.result('07_entanglement_backend.py', '--fidelity', 0.9, '--shots', 100)
        self.assertAlmostEqual(r['swapped_fidelity'], 0.8133333333333334)
        self.assertTrue(r['swap_inputs_consumed'])
        self.assertLess(r['stored_fidelity'], 0.9)
        self.assertGreater(r['distillation_successes'], 0)
        self.assertGreater(r['mean_distilled_fidelity'], 0.9)

    def test_bell_swap_extremes_and_ideal_storage(self):
        for probability, successes in [(0, 0), (1, 100)]:
            r = self.result('07_entanglement_backend.py', '--shots', 100,
                            '--bell-swap-probability', probability)['bell']
            self.assertEqual(r['swap_successes'], successes)
            self.assertEqual(r['stored_fidelity'], 1)
            self.assertTrue(r['swap_inputs_consumed'])
            self.assertEqual(r['mean_successful_swap_fidelity'], 1 if successes else None)
            self.assertEqual(r['distilled_fidelity'], 1)

    def test_mixed_weights_storage_and_distillation(self):
        r = self.result('07_entanglement_backend.py', '--shots', 100,
                        '--mixed-weights', 0.9, 0.05, 0.03, 0.02)['mixed']
        self.assertEqual(r['initial_weights'], [0.9, 0.05, 0.03, 0.02])
        self.assertAlmostEqual(sum(r['stored_weights']), 1)
        self.assertLess(r['stored_weights'][0], 0.9)
        self.assertGreater(r['stored_weights'][1], 0.05)
        self.assertTrue(r['swap_inputs_consumed'])
        for actual, expected in zip(r['reference_swapped_weights'], [0.8138, 0.0912, 0.056, 0.039]):
            self.assertAlmostEqual(actual, expected)
        self.assertGreater(r['distillation_successes'], 0)
        self.assertAlmostEqual(r['mean_distilled_fidelity'], 0.8104 / 0.8528)

    def test_mixed_ideal_state_stays_ideal(self):
        r = self.result('07_entanglement_backend.py', '--shots', 10,
                        '--mixed-weights', 1, 0, 0, 0,
                        '--decoherence-rate', 0)['mixed']
        self.assertEqual(r['stored_weights'], [1, 0, 0, 0])
        self.assertEqual(r['swapped_weights'], [1, 0, 0, 0])
        self.assertEqual(r['distillation_successes'], 10)
        self.assertEqual(r['mean_distilled_fidelity'], 1)

    def test_conversion_preserves_werner_fidelity_and_gate_changes_correlation(self):
        r = self.result('08_entanglement_to_qubits.py', '--shots', 100, '--fidelities', 0.25, 1)
        mixed, bell = r['experiments']
        self.assertAlmostEqual(mixed['bell_overlap'], 0.25)
        self.assertEqual(mixed['density_matrix_real'], [[0.25, 0.0, 0.0, 0.0], [0.0, 0.25, 0.0, 0.0], [0.0, 0.0, 0.25, 0.0], [0.0, 0.0, 0.0, 0.25]])
        self.assertAlmostEqual(bell['bell_overlap'], 1)
        self.assertTrue(bell['shared_state'])
        self.assertTrue(bell['entanglement_consumed'])
        self.assertEqual(bell['z_counts']['01'] + bell['z_counts']['10'], 0)
        self.assertEqual(bell['after_x_counts']['00'] + bell['after_x_counts']['11'], 0)
        self.assertEqual(sum(bell['z_counts'].values()), 100)

    def test_topology_edge_counts_and_waxman_reproducibility(self):
        a = self.result('09_topology_generators.py')
        b = self.result('09_topology_generators.py')
        self.assertEqual(a, b)
        self.assertEqual(a['linear']['links'], 8)
        self.assertEqual(a['grid']['links'], 12)
        self.assertTrue(a['waxman']['connected'])
        self.assertEqual(len(a['grid']['edges']), 12)

    def test_entities_operate_received_qubit_and_return_classical_ack(self):
        r = self.result('10_node_entities.py')
        self.assertEqual(r['measurement'], 1)
        self.assertEqual(r['memory_usage_after_read'], 0)
        self.assertEqual(r['ack']['bit'], 1)
        self.assertAlmostEqual(r['quantum_arrival_seconds'], 0.02)
        self.assertAlmostEqual(r['operation_response_seconds'], 0.03)
        self.assertAlmostEqual(r['ack_arrival_seconds'], 0.04)

    def test_classical_forwarder_delivers_through_relay(self):
        r = self.result('11_classical_apps.py', '--count', 3)
        self.assertEqual([x['message']['sequence'] for x in r['received']], [0, 1, 2])
        self.assertAlmostEqual(r['received'][0]['time_seconds'], 0.02)
        self.assertEqual(r['packet_trace'][0]['node'], 'n2')
        self.assertEqual(len(r['packet_trace']), 6)

    def test_bb84_postprocessing_produces_matching_key_blocks(self):
        r = self.result('12_bb84_apps.py')
        self.assertGreater(r['common_key_blocks'], 0)
        self.assertGreater(r['matched_key_bits'], 0)
        self.assertTrue(r['common_blocks_equal'])

    def test_random_requests_replace_manual_request_and_enforce_unique_endpoints(self):
        r = self.result('13_request_management.py')
        self.assertEqual(len(r['manual']), 1)
        self.assertEqual(len(r['unique_random']), 3)
        endpoints = [x[k] for x in r['unique_random'] for k in ('src', 'dest')]
        self.assertEqual(len(set(endpoints)), 6)
        self.assertTrue(r['manual_replaced'])
        self.assertGreater(r['overlay_endpoint_reuses'], 0)

    def test_monitor_writes_periodic_csv_with_observed_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'observations.csv'
            r = self.result('14_data_collector.py', '--output', path)
            self.assertEqual([x['count'] for x in r['records']], [0, 1, 2, 3, 3])
            self.assertEqual([x['time'] for x in r['records']], [0, 0.25, 0.5, 0.75, 1])
            with path.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([int(x['count']) for x in rows], [0, 1, 2, 3, 3])

    def test_event_benchmark_checks_actual_execution(self):
        r = self.result('15_cython_acceleration.py', '--events', 100, '--repeats', 2)
        self.assertEqual(r['invoked'], 100)
        self.assertEqual(r['checksum'], 4950)
        self.assertEqual(len(r['wall_seconds']), 2)
        self.assertIn('qns.simulator.pool', r['modules'])

    def test_parallel_and_serial_sweeps_have_same_seeded_results(self):
        r = self.result('16_parallel_simulations.py', '--shots', 50, '--repeats', 2, '--cores', 2)
        self.assertEqual(len(r['raw']), 6)
        self.assertTrue(r['serial_matches_parallel'])
        for row in r['raw']:
            if row['flip_probability'] == 0:
                self.assertEqual(row['ones'], 0)
            if row['flip_probability'] == 1:
                self.assertEqual(row['ones'], 50)

    def test_invalid_inputs_fail_cleanly(self):
        for name, args in [
            ('06_qubit_backend.py', ['--flip-probability', '1.1']),
            ('07_entanglement_backend.py', ['--shots', '0']),
            ('07_entanglement_backend.py', ['--bell-swap-probability', '1.1']),
            ('07_entanglement_backend.py', ['--mixed-weights', '0', '0', '0', '0']),
            ('07_entanglement_backend.py', ['--mixed-weights', '0.9', '0.1', '0.1', '0.1']),
            ('08_entanglement_to_qubits.py', ['--fidelities', '-0.1']),
            ('09_topology_generators.py', ['--nodes', '8']),
            ('11_classical_apps.py', ['--count', '0']),
            ('12_bb84_apps.py', ['--duration', 'nan']),
            ('13_request_management.py', ['--nodes', '2', '--requests', '2']),
            ('15_cython_acceleration.py', ['--events', '0']),
            ('16_parallel_simulations.py', ['--cores', '0']),
        ]:
            with self.subTest(name=name, args=args):
                p = execute(name, *args)
                self.assertEqual(p.returncode, 2)
                self.assertIn('error:', p.stderr)
                self.assertNotIn('Traceback', p.stderr)

    def test_cython_builder_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            p = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/build_cython_core.py'), '--output', directory],
                capture_output=True, text=True, cwd=ROOT, timeout=30, check=False,
            )
            self.assertEqual(p.returncode, 2)
            self.assertIn('error:', p.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
