"""실제 실행 명령으로 예제의 학습 결과를 검증함. 외부 서비스는 필요 없음."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(name, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "examples" / name), *map(str, args)],
        capture_output=True, text=True, cwd=ROOT, timeout=30, check=False,
    )


class ExampleTests(unittest.TestCase):
    def result(self, name, *args):
        process = execute(name, *args)
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def test_events_are_time_ordered_and_canceled_event_is_absent(self):
        result = self.result("01_events.py")
        self.assertEqual(result["events"], [
            {"time_seconds": 0.1, "name": "first"},
            {"time_seconds": 0.2, "name": "second"},
            {"time_seconds": 0.3, "name": "third"},
        ])

    def test_qubit_preparation_and_bell_correlation(self):
        result = self.result("02_qubits.py", "--shots", 1000)
        self.assertEqual(result["zero_state"], {"0": 1000, "1": 0})
        self.assertEqual(result["one_state"], {"0": 0, "1": 1000})
        self.assertTrue(400 < result["plus_state"]["0"] < 600)
        self.assertEqual(sum(result["plus_state"].values()), 1000)
        self.assertEqual(result["bell_pairs"]["01"], 0)
        self.assertEqual(result["bell_pairs"]["10"], 0)
        self.assertEqual(sum(result["bell_pairs"].values()), 1000)
        self.assertTrue(400 < result["bell_pairs"]["00"] < 600)

    def test_seed_reproduces_measurement_counts(self):
        first = self.result("02_qubits.py", "--shots", 25, "--seed", 7)
        second = self.result("02_qubits.py", "--shots", 25, "--seed", 7)
        self.assertEqual(first, second)

    def test_channel_extreme_losses_and_arrival_times(self):
        result = self.result("03_channel_loss.py", "--count", 20,
                             "--delay", 0.02, "--drop-rates", 0, 1)
        no_loss, full_loss = result["experiments"]
        self.assertEqual(no_loss["received"], 20)
        self.assertEqual(no_loss["lost"], 0)
        self.assertAlmostEqual(no_loss["first_arrival_seconds"], 0.02)
        self.assertAlmostEqual(no_loss["last_arrival_seconds"], 0.039)
        self.assertEqual(full_loss["received"], 0)
        self.assertEqual(full_loss["lost"], 20)
        self.assertIsNone(full_loss["first_arrival_seconds"])

    def test_channel_sampled_loss_is_near_probability(self):
        result = self.result("03_channel_loss.py", "--drop-rates", 0.5)
        self.assertTrue(400 < result["experiments"][0]["received"] < 600)

    def test_route_metric_changes_the_selected_path(self):
        result = self.result("04_routing.py")
        self.assertEqual(result["fewest_hops"]["path"], ["Alice", "Bob"])
        self.assertEqual(result["fewest_hops"]["cost_hops"], 1)
        self.assertEqual(result["lowest_delay"]["path"],
                         ["Alice", "Relay1", "Relay2", "Bob"])
        self.assertAlmostEqual(result["lowest_delay"]["cost_seconds"], 0.03)

    def test_distribution_completes_with_valid_fidelity(self):
        result = self.result("05_entanglement_distribution.py")
        self.assertEqual(result["path"], ["n1", "n2", "n3", "n4"])
        self.assertGreater(result["completed"], 0)
        self.assertLessEqual(result["completed"], result["attempted"])
        self.assertTrue(0.25 < result["mean_fidelity"] < 0.99)
        self.assertAlmostEqual(result["pairs_per_second"], result["completed"] / 5)

    def test_distribution_before_first_delivery_has_null_fidelity(self):
        result = self.result("05_entanglement_distribution.py", "--duration", 0.001)
        self.assertEqual(result["completed"], 0)
        self.assertGreater(result["attempted"], 0)
        self.assertIsNone(result["mean_fidelity"])

    def test_invalid_inputs_are_cli_errors(self):
        cases = [
            ("02_qubits.py", "--shots", "0"),
            ("02_qubits.py", "--seed", "-1"),
            ("02_qubits.py", "--seed", "4294967296"),
            ("03_channel_loss.py", "--drop-rates", "1.1"),
            ("03_channel_loss.py", "--delay", "nan"),
            ("03_channel_loss.py", "--delay", "-1"),
            ("05_entanglement_distribution.py", "--nodes", "1"),
            ("05_entanglement_distribution.py", "--memory", "1"),
            ("05_entanglement_distribution.py", "--send-rate", "0"),
            ("05_entanglement_distribution.py", "--send-rate", "1e-320"),
            ("05_entanglement_distribution.py", "--duration", "inf"),
        ]
        for name, option, value in cases:
            with self.subTest(name=name, option=option, value=value):
                process = execute(name, option, value)
                self.assertEqual(process.returncode, 2)
                self.assertIn("error:", process.stderr)
                self.assertNotIn("Traceback", process.stderr)


if __name__ == "__main__":
    unittest.main()
