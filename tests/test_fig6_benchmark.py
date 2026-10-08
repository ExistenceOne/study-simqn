"""Independent process trials, timing accounting and optional CLI regression."""

import importlib.util
import unittest

SETTINGS = {
    "duration": 0.002,
    "send_rate": 1000,
    "link_length_km": 10,
    "speed_km_s": 200000,
    "depolar_rate": 200,
    "noise_during_transit": True,
    "initial_fidelity": 1,
    "warmup_jobs": 1,
}


class Fig6BenchmarkTests(unittest.TestCase):
    def runner(self):
        self.assertIsNotNone(
            importlib.util.find_spec("evaluations.fig6_benchmark"),
            "Fig. 6 benchmark is not implemented",
        )
        from evaluations.fig6_benchmark import run_batch

        return run_batch

    def test_amortized_accounting(self):
        self.runner()
        from evaluations.fig6_benchmark import batch_metrics

        row = batch_metrics(workers=4, jobs=4, elapsed=10, warmup=2, startup=1)
        self.assertEqual(row["batch_seconds"], 8)
        self.assertEqual(row["amortized_seconds"], 2)
        self.assertEqual(row["warmup_seconds"], 2)

    def test_spawn_1_and_4_workers_agree(self):
        run = self.runner()
        one, a = run("qubit", 4, SETTINGS, [1, 2, 3, 4], 1)
        four, b = run("qubit", 4, SETTINGS, [1, 2, 3, 4], 4)
        self.assertEqual([r["seed"] for r in a], [1, 2, 3, 4])
        self.assertEqual([r["job_index"] for r in b], [0, 1, 2, 3])
        for x, y in zip(a, b):
            self.assertEqual(x["completed_pairs"], y["completed_pairs"])
            self.assertAlmostEqual(x["mean_fidelity"], y["mean_fidelity"], places=10)
            self.assertEqual(x["event_count"], y["event_count"])
        for row in [one, four]:
            self.assertAlmostEqual(row["amortized_seconds"], row["batch_seconds"] / 4)
            self.assertGreater(row["startup_seconds"], 0)

    def test_worker_exception_is_reported(self):
        run = self.runner()
        with self.assertRaisesRegex(RuntimeError, "job|worker"):
            run("unknown-backend", 4, {**SETTINGS, "warmup_jobs": 0}, [1], 1)

    def test_missing_or_duplicate_job_rejected(self):
        self.runner()
        from evaluations.fig6_benchmark import ordered_jobs

        with self.assertRaisesRegex(RuntimeError, "missing|duplicate"):
            ordered_jobs([{"job_index": 0}, {"job_index": 0}], 2)
        with self.assertRaisesRegex(RuntimeError, "missing|duplicate"):
            ordered_jobs([{"job_index": 0}], 2)

    def test_unknown_backend_warmup_failure_does_not_hang(self):
        run = self.runner()
        with self.assertRaisesRegex(RuntimeError, "worker|warmup"):
            run("unknown-backend", 4, SETTINGS, [1], 1)


class Fig6CliTests(unittest.TestCase):
    def config(self):
        self.assertIsNotNone(
            importlib.util.find_spec("evaluations.run_fig6"),
            "Fig. 6 CLI is not implemented",
        )
        import json
        from pathlib import Path

        from evaluations.run_fig6 import validate

        cfg = json.loads(Path("evaluations/configs/fig6-smoke.json").read_text())
        cfg.update(
            nodes=[2],
            backends=["qubit", "werner"],
            workers=[1],
            jobs_per_batch=1,
            batch_repeats=1,
            warmup_jobs=0,
        )
        validate(cfg)
        return cfg

    def test_invalid_settings(self):
        cfg = self.config()
        from evaluations.run_fig6 import validate

        for key, value in [
            ("nodes", [2.0]),
            ("nodes", [True]),
            ("duration", float("nan")),
            ("jobs_per_batch", 0),
            ("warmup_jobs", -1),
            ("workers", [4]),
            ("noise_during_transit", "true"),
            ("send_rate", 0),
            ("seed", -1),
        ]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate({**cfg, key: value})

    def test_cli_outputs_single_batch_null_sem_and_no_overwrite(self):
        cfg = self.config()
        import csv
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(json.dumps(cfg))
            command = [
                sys.executable,
                "-m",
                "evaluations.run_fig6",
                "--config",
                str(config),
                "--output",
                str(root / "out"),
            ]
            r = subprocess.run(
                command, capture_output=True, text=True, timeout=60, check=False
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            metadata = json.loads((root / "out/metadata.json").read_text())
            self.assertEqual(metadata["status"], "complete")
            self.assertTrue(metadata["quality_validation"]["passed"])
            for name in ["fig6.png", "fig6_job_latency.png"]:
                self.assertTrue(
                    (root / "out" / name).read_bytes().startswith(b"\x89PNG")
                )
            with (root / "out/fig6_summary.csv").open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["amortized_seconds_sem"], "")
            self.assertNotEqual(
                subprocess.run(command, capture_output=True, check=False).returncode, 0
            )

    def test_failure_status_preserves_condition(self):
        cfg = self.config()
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from evaluations.run_fig6 import run

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch(
                    "evaluations.run_fig6.run_batch",
                    side_effect=RuntimeError("job 0 failed"),
                ),
                self.assertRaises(RuntimeError),
            ):
                run(cfg, Path(directory))
            d = json.loads((Path(directory) / "metadata.json").read_text())
            self.assertEqual(d["status"], "failed")
            self.assertEqual(d["current_condition"]["nodes"], 2)
            self.assertIn("job 0 failed", d["error"])

    def test_interruption_is_recorded_as_failed(self):
        cfg = self.config()
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from evaluations.run_fig6 import run

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("evaluations.run_fig6.run_batch", side_effect=KeyboardInterrupt),
                self.assertRaises(KeyboardInterrupt),
            ):
                run(cfg, Path(directory))
            d = json.loads((Path(directory) / "metadata.json").read_text())
            self.assertEqual(d["status"], "failed")
            self.assertIn("KeyboardInterrupt", d["error"])
