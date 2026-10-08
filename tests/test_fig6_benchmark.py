"""Independent process trials, timing accounting and optional CLI regression."""
import importlib.util
import unittest

SETTINGS = dict(duration=.002, send_rate=1000, link_length_km=10,
                speed_km_s=200000, depolar_rate=200, noise_during_transit=True,
                initial_fidelity=1, warmup_jobs=1)


class Fig6BenchmarkTests(unittest.TestCase):
    def runner(self):
        self.assertIsNotNone(importlib.util.find_spec('evaluations.fig6_benchmark'),
                             'Fig. 6 benchmark is not implemented')
        from evaluations.fig6_benchmark import run_batch
        return run_batch

    def test_amortized_accounting(self):
        self.runner()
        from evaluations.fig6_benchmark import batch_metrics
        row = batch_metrics(workers=4, jobs=4, elapsed=10, warmup=2, startup=1)
        self.assertEqual(row['batch_seconds'], 8)
        self.assertEqual(row['amortized_seconds'], 2)
        self.assertEqual(row['warmup_seconds'], 2)

    def test_spawn_1_and_4_workers_agree(self):
        run = self.runner()
        one, a = run('qubit', 4, SETTINGS, [1, 2, 3, 4], 1)
        four, b = run('qubit', 4, SETTINGS, [1, 2, 3, 4], 4)
        self.assertEqual([r['seed'] for r in a], [1, 2, 3, 4])
        self.assertEqual([r['job_index'] for r in b], [0, 1, 2, 3])
        for x, y in zip(a, b):
            self.assertEqual(x['completed_pairs'], y['completed_pairs'])
            self.assertAlmostEqual(x['mean_fidelity'], y['mean_fidelity'], places=10)
            self.assertEqual(x['event_count'], y['event_count'])
        for row in [one, four]:
            self.assertAlmostEqual(row['amortized_seconds'], row['batch_seconds']/4)
            self.assertGreater(row['startup_seconds'], 0)

    def test_worker_exception_is_reported(self):
        run = self.runner()
        with self.assertRaisesRegex(RuntimeError, 'job|worker'):
            run('unknown-backend', 4, {**SETTINGS, 'warmup_jobs': 0}, [1], 1)

    def test_missing_or_duplicate_job_rejected(self):
        self.runner()
        from evaluations.fig6_benchmark import ordered_jobs
        with self.assertRaisesRegex(RuntimeError, 'missing|duplicate'):
            ordered_jobs([{'job_index': 0}, {'job_index': 0}], 2)
        with self.assertRaisesRegex(RuntimeError, 'missing|duplicate'):
            ordered_jobs([{'job_index': 0}], 2)

    def test_unknown_backend_warmup_failure_does_not_hang(self):
        run = self.runner()
        with self.assertRaisesRegex(RuntimeError, 'worker|warmup'):
            run('unknown-backend', 4, SETTINGS, [1], 1)
