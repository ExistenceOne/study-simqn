"""원격 프로토콜의 상태·메시지 인과관계·실패 처리를 검증함."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(name, *args):
    return subprocess.run([sys.executable, str(ROOT / 'examples' / name), *map(str, args)],
                          capture_output=True, text=True, timeout=60, cwd=ROOT)


class DistributedComputingTests(unittest.TestCase):
    def result(self, name, *args):
        p = execute(name, *args)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_teleportation_preserves_six_input_states_and_waits_for_messages(self):
        r = self.result('17_network_teleportation.py', '--shots', 96)
        self.assertEqual(r['completed'], 96)
        self.assertEqual(len(r['by_input']), 6)
        self.assertAlmostEqual(r['minimum_fidelity'], 1)
        self.assertAlmostEqual(r['mean_completion_seconds'], 0.03)
        self.assertEqual(r['classical_payload_bits'], 192)
        self.assertEqual(set(r['measurement_branches']), {'00', '01', '10', '11'})
        events = {x['event']: x['time_seconds'] for x in r['first_trial_trace']}
        self.assertAlmostEqual(events['bell_measurement'], 0.02)
        self.assertAlmostEqual(events['bob_correction'], 0.03)
        self.assertAlmostEqual(events['alice_ack'], 0.04)

    def test_remote_cnot_matches_local_reference_for_complex_superpositions(self):
        r = self.result('18_remote_cnot.py', '--shots', 96)
        self.assertEqual(r['completed'], 96)
        self.assertEqual(len(r['by_input']), 16)
        self.assertAlmostEqual(r['minimum_fidelity'], 1)
        self.assertAlmostEqual(r['mean_completion_seconds'], 0.04)
        self.assertEqual(r['classical_payload_bits'], 192)
        self.assertEqual(r['bell_pairs_created'], 96)
        self.assertEqual(set(r['measurement_branches']), {'00', '01', '10', '11'})

    def test_quantum_loss_produces_no_fidelity_or_completed_operation(self):
        for name in ('17_network_teleportation.py', '18_remote_cnot.py'):
            r = self.result(name, '--shots', 12, '--drop-rate', 1)
            self.assertEqual(r['completed'], 0)
            self.assertEqual(r['failed'], 12)
            self.assertIsNone(r['mean_fidelity'])
            self.assertIsNone(r['mean_completion_seconds'])
            self.assertEqual(r['bell_pairs_created'], 12)
            self.assertEqual(r['classical_payload_bits'], 0)

    def test_low_pair_fidelity_and_memory_dephasing_degrade_state(self):
        r = self.result('17_network_teleportation.py', '--shots', 12, '--fidelity', 0.25)
        self.assertAlmostEqual(r['mean_fidelity'], 0.5)
        noisy = self.result('18_remote_cnot.py', '--shots', 16, '--t2', 0.005)
        self.assertLess(noisy['mean_fidelity'], 0.9)

    def test_seed_reproducibility_and_invalid_parameters(self):
        for name in ('17_network_teleportation.py', '18_remote_cnot.py'):
            self.assertEqual(self.result(name, '--shots', 12), self.result(name, '--shots', 12))
            for args in [('--shots', 0), ('--drop-rate', 1.1), ('--t2', -1),
                         ('--quantum-delay', 'nan'), ('--classical-delay', -1)]:
                p = execute(name, *args)
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertNotIn('Traceback', p.stderr)


if __name__ == '__main__':
    unittest.main()
