"""논문 재실행 코드의 물리적 결과, 통계와 CLI 계약을 검증함."""

import csv
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class EvaluationTests(unittest.TestCase):
    def test_attenuation_formulas_are_not_confused(self):
        m = importlib.import_module("evaluations.fig3")
        self.assertAlmostEqual(m.transmission(50, "paper-db", 0.2), 0.1)
        self.assertAlmostEqual(
            m.transmission(50, "historical-exp", 0.2), 0.36787944117144233
        )
        self.assertEqual(m.transmission(0, "paper-db", 0.2), 1)

    def test_bb84_noise_free_and_full_bit_flip_are_distinct(self):
        m = importlib.import_module("evaluations.fig3")
        settings = {
            "duration": 0.5,
            "send_rate": 1000,
            "loss_model": "paper-db",
            "attenuation_db_km": 0,
            "light_speed_m_s": 299792458,
            "bit_flip_per_km": 1,
        }
        clean = m.simulate(1, 0, "none", settings, 42)
        noisy = m.simulate(1, 0, "bit-flip", settings, 42)
        self.assertTrue(150 < clean["sifted_bits"] < 350)
        self.assertEqual(clean["correct_bits"], clean["sifted_bits"])
        self.assertEqual(clean["qber"], 0)
        self.assertTrue(0.3 < noisy["qber"] < 0.7)  # X flips Z bits, not X bits.
        self.assertLess(noisy["correct_sifted_bps"], noisy["sifted_bps"])
        self.assertEqual(clean, m.simulate(1, 0, "none", settings, 42))

    def test_fig5_rate_accounting_and_seed_reproducibility(self):
        m = importlib.import_module("evaluations.fig5")
        settings = {
            "nodes": 8,
            "links": 12,
            "duration": 1,
            "warmup": 0,
            "memory": 50,
            "fidelity": 0.99,
            "coherence_time": 5,
            "quantum_delay": 0.01,
            "classical_delay": 0.01,
            "quantum_bandwidth": 0,
            "classical_bandwidth": 0,
        }
        base = m.build_network(settings, 42)
        self.assertTrue(all(channel.bandwidth == 0 for channel in base.qchannels))
        first, sessions = m.simulate(base, 2, 5, settings, 43, 44)
        second, other = m.simulate(base, 2, 5, settings, 43, 44)
        self.assertEqual(first, second)
        self.assertEqual(sessions, other)
        self.assertEqual(len(sessions), 2)
        self.assertGreater(first["completed"], 0)
        self.assertEqual(first["total_eps"], first["completed"])
        self.assertEqual(first["mean_session_eps"], first["total_eps"] / 2)
        self.assertEqual(first["completed"], sum(s["completed"] for s in sessions))
        self.assertEqual(
            len({s[k] for s in sessions for k in ["source", "destination"]}), 4
        )
        self.assertTrue(all(0.25 < s["mean_fidelity"] <= 0.99 for s in sessions))

    def test_summary_uses_sample_std_and_sem_and_keeps_single_trial_null(self):
        m = importlib.import_module("evaluations.reporting")
        grouped = m.summarize(
            [{"x": 1, "rate": 2}, {"x": 1, "rate": 4}], ["x"], ["rate"]
        )
        self.assertEqual(grouped[0]["rate_mean"], 3)
        self.assertAlmostEqual(grouped[0]["rate_std"], 1.4142135623730951)
        self.assertAlmostEqual(grouped[0]["rate_sem"], 1)
        singleton = m.summarize([{"x": 1, "rate": 2}], ["x"], ["rate"])[0]
        self.assertIsNone(singleton["rate_sem"])

    def test_dense_network_can_be_reinstantiated_without_recursive_copy(self):
        m = importlib.import_module("evaluations.fig5")
        settings = json.loads(Path("evaluations/configs/smoke.json").read_text())[
            "fig5"
        ]
        settings.update(nodes=150, links=450, duration=0.05)
        base = m.build_network(settings, 42)
        result, sessions = m.simulate(base, 2, 5, settings, 43, 44)
        self.assertEqual(len(sessions), 2)
        self.assertEqual(result["completed"], 0)

    def test_completed_fidelity_does_not_change_after_source_ack(self):
        m = importlib.import_module("evaluations.fig5")
        settings = json.loads(Path("evaluations/configs/smoke.json").read_text())[
            "fig5"
        ]
        settings.update(nodes=2, links=1, duration=0.18)
        base = m.build_network(settings, 42)
        _, before_ack = m.simulate(base, 1, 1, settings, 43, 44)
        settings["duration"] = 0.3
        _, after_ack = m.simulate(base, 1, 1, settings, 43, 44)
        self.assertEqual(before_ack[0]["completed"], 1)
        self.assertEqual(after_ack[0]["completed"], 1)
        self.assertAlmostEqual(
            before_ack[0]["mean_fidelity"], after_ack[0]["mean_fidelity"]
        )

    def test_cli_writes_csv_metadata_and_real_pngs(self):
        with tempfile.TemporaryDirectory() as directory:
            p = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "evaluations.run",
                    "--config",
                    "evaluations/configs/smoke.json",
                    "--output",
                    directory,
                ],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            for figure in ["fig3a", "fig3b", "fig5"]:
                with open(Path(directory) / f"{figure}_summary.csv") as stream:
                    rows = list(csv.DictReader(stream))
                self.assertGreater(len(rows), 0)
                self.assertEqual(
                    (Path(directory) / f"{figure}.png").read_bytes()[:8],
                    b"\x89PNG\r\n\x1a\n",
                )
            metadata = json.loads((Path(directory) / "metadata.json").read_text())
            self.assertEqual(metadata["versions"]["qns"], "0.2.3")
            self.assertIn("assumptions", metadata)

    def test_bad_topology_config_is_rejected_before_simulation(self):
        m = importlib.import_module("evaluations.run")
        config = json.loads(Path("evaluations/configs/smoke.json").read_text())
        config["fig5"]["links"] = 100000
        with self.assertRaises(ValueError):
            m.validate(config)

    def test_float_counts_and_zero_measurement_window_are_rejected(self):
        m = importlib.import_module("evaluations.run")
        for field, value in [("nodes", 20.0), ("warmup", 2)]:
            with self.subTest(field=field):
                config = json.loads(Path("evaluations/configs/smoke.json").read_text())
                config["fig5"][field] = value
                with self.assertRaises(ValueError):
                    m.validate(config)


if __name__ == "__main__":
    unittest.main()
