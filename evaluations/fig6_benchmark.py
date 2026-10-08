"""Spawned independent experiments; startup and warmup are measured separately."""

import multiprocessing as mp
import os
import queue
import time
from concurrent.futures import ProcessPoolExecutor
from statistics import mean

THREAD_VARS = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def batch_metrics(*, workers, jobs, elapsed, warmup, startup):
    seconds = elapsed - warmup
    return {
        "workers": workers,
        "jobs": jobs,
        "batch_seconds": seconds,
        "amortized_seconds": seconds / jobs,
        "startup_seconds": startup,
        "warmup_seconds": warmup,
    }


def ordered_jobs(rows, expected):
    indexes = [row["job_index"] for row in rows]
    if len(indexes) != expected or set(indexes) != set(range(expected)):
        raise RuntimeError(
            f"missing or duplicate job: expected={expected}, indexes={indexes}"
        )
    return sorted(rows, key=lambda row: row["job_index"])


def _initialize(backend, nodes, settings, signals, start_warmup, start_jobs):
    # Every process warms up once before any measured job starts. Import costs
    # for every backend belong to startup, before the warmup barrier.
    from evaluations.fig6_backends import make_backend
    from evaluations.fig6_protocol import run_trial

    make_backend(backend, settings, seed=0)
    signals.put(("ready", None))
    start_warmup.wait()
    try:
        for index in range(settings["warmup_jobs"]):
            run_trial(backend, nodes, settings, index)
    except Exception as error:
        signals.put(("error", f"worker warmup failed: {type(error).__name__}: {error}"))
        raise
    signals.put(("warm", None))
    start_jobs.wait()


def _job(backend, nodes, settings, seed, index):
    from evaluations.fig6_protocol import run_trial

    try:
        trial = run_trial(backend, nodes, settings, seed)
    except Exception as error:
        raise RuntimeError(
            f"job {index}, seed {seed}: {type(error).__name__}: {error}"
        ) from error
    return {
        "job_index": index,
        "seed": seed,
        "completed_pairs": trial["completed_pairs"],
        "mean_fidelity": mean(trial["completion_fidelities"])
        if trial["completion_fidelities"]
        else None,
        "completed_round_checksum": sum(trial["completed_rounds"]),
        "scheduled_rounds": trial["scheduled_rounds"],
        "event_count": trial["event_count"],
        "max_state_qubits": trial["max_state_qubits"],
        "setup_seconds": trial["setup_seconds"],
        "simulation_seconds": trial["simulation_seconds"],
        "job_seconds": trial["job_seconds"],
    }


def _wait_signals(signals, futures, kind, count, timeout=600):
    deadline = time.monotonic() + timeout
    for _ in range(count):
        while True:
            if time.monotonic() > deadline:
                raise RuntimeError(f"worker {kind} barrier timed out")
            try:
                label, detail = signals.get(timeout=0.1)
            except queue.Empty:
                for future in futures:
                    if future.done() and future.exception() is not None:
                        raise RuntimeError(
                            f"worker initialization failed: {future.exception()}"
                        )
                continue
            if label == "error":
                raise RuntimeError(detail)
            if label != kind:
                raise RuntimeError(f"worker barrier: expected {kind}, got {label}")
            break


def _abort_pool(pool):
    # Python 3.11/3.12 have no public terminate_workers API. Capture the
    # multiprocessing.Process objects before shutdown clears the mapping.
    processes = list((pool._processes or {}).values())
    for process in processes:
        if process.is_alive():
            process.terminate()
    pool.shutdown(wait=False, cancel_futures=True)
    for process in processes:
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)


def run_batch(
    backend: str, nodes: int, settings: dict, seeds: list[int], workers: int
) -> tuple[dict, list[dict]]:
    if not seeds or workers < 1:
        raise ValueError("positive workers and nonempty seeds required")
    if len(seeds) < workers:
        raise ValueError("jobs must be at least the number of workers")
    previous = {name: os.environ.get(name) for name in THREAD_VARS}
    for name in THREAD_VARS:
        os.environ[name] = "1"
    context = mp.get_context("spawn")
    signals = context.Queue()
    start_warmup, start_jobs = context.Event(), context.Event()
    pool = None
    try:
        start = time.perf_counter_ns()
        pool = ProcessPoolExecutor(
            max_workers=workers,
            mp_context=context,
            initializer=_initialize,
            initargs=(backend, nodes, settings, signals, start_warmup, start_jobs),
        )
        futures = [
            pool.submit(_job, backend, nodes, settings, seed, index)
            for index, seed in enumerate(seeds)
        ]
        timeout = settings.get("worker_timeout_seconds", 600)
        _wait_signals(signals, futures, "ready", workers, timeout)
        warmup_start = time.perf_counter_ns()
        start_warmup.set()
        _wait_signals(signals, futures, "warm", workers, timeout)
        warmup_end = time.perf_counter_ns()
        start_jobs.set()
        deadline = time.monotonic() + timeout
        records = []
        for index, future in enumerate(futures):
            try:
                records.append(
                    future.result(timeout=max(0, deadline - time.monotonic()))
                )
            except TimeoutError as error:
                raise RuntimeError(
                    f"job batch timed out waiting for job {index}"
                ) from error
        rows = ordered_jobs(records, len(seeds))
        pool.shutdown(wait=True)
        pool = None
        stop = time.perf_counter_ns()
        batch = batch_metrics(
            workers=workers,
            jobs=len(seeds),
            elapsed=(stop - start) / 1e9,
            warmup=(warmup_end - warmup_start) / 1e9,
            startup=(warmup_start - start) / 1e9,
        )
        batch["start_method"] = "spawn"
        return batch, rows
    finally:
        # Release both barriers before shutdown, including initializer failure.
        start_warmup.set()
        start_jobs.set()
        if pool is not None:
            _abort_pool(pool)
        signals.close()
        signals.join_thread()
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
