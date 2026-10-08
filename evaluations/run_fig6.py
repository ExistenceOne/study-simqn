"""Fig. 6 wall-time benchmark; python -m evaluations.run_fig6 --config PATH."""

import argparse
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evaluations.fig6_benchmark import THREAD_VARS, run_batch
from evaluations.plotting import plot_fig6
from evaluations.reporting import summarize, write_csv

ASSUMPTIONS = {
    "reproduction": "Source-informed workload, not exact paper timing reproduction.",
    "nodes": "Figure sweep 5..50. Paper text separately says 10-node chain.",
    "generation": "Left endpoint generates a Bell pair; right half arrives after distance/speed.",
    "swapping": "All repeaters BSM at link-ready time; deterministic node-order callbacks, no processing delay.",
    "classical": "One logical routed BSM message per repeater, delay=remaining hops*link delay; no per-hop forwarding events.",
    "noise": "Assumed local Bloch contraction exp(-200*t). Both halves accumulate actual transit/storage time. Same DM channel in both simulators.",
    "werner": "Scalar Werner states in corrected Pauli frame; BSM bits sampled uniformly. No gates simulated on the scalar state.",
    "resources": "Unlimited round memory, lossless/unlimited channels, no distillation, capacity congestion or retries.",
    "time": "Main y=batch wall time/job count, subtract warmup barrier span only; startup/IPC/teardown included. Job latency separately reported.",
    "parallel": "Spawn processes run independent trials; one trial is never partitioned among cores. Native math thread count=1.",
    "netsquid": "One-worker DM benchmark; optional proprietary dependency. Absent package is skipped, installed import/runtime failure is an error.",
    "duration": "1s full simulated duration, 8 jobs/batch and 3 batches are assumptions, not paper values.",
    "uncertainty": "Batch sample SEM for amortized time; per-job latency uses separately labeled job samples.",
}


def validate(config):
    keys = (
        "name",
        "seed",
        "nodes",
        "backends",
        "workers",
        "duration",
        "send_rate",
        "link_length_km",
        "speed_km_s",
        "depolar_rate",
        "noise_during_transit",
        "jobs_per_batch",
        "batch_repeats",
        "warmup_jobs",
        "initial_fidelity",
    )
    if not isinstance(config, dict) or any(k not in config for k in keys):
        raise ValueError(f"Required config keys: {keys}")

    def number(key, lo, hi, integer=False, value=None):
        v = config[key] if value is None else value
        if (
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not lo <= v <= hi
            or (integer and not isinstance(v, int))
        ):
            raise ValueError(
                f"{key}: expected {'integer' if integer else 'finite number'} in [{lo}, {hi}]"
            )

    if not isinstance(config["name"], str) or not config["name"]:
        raise ValueError("name: nonempty string required")
    number("seed", 0, 2**32 - 1, True)
    for key, lo, hi in [
        ("duration", 1e-6, 100),
        ("send_rate", 1, 1e6),
        ("link_length_km", 1e-6, 10000),
        ("speed_km_s", 1, 1e9),
        ("depolar_rate", 0, 1e6),
        ("initial_fidelity", 0.25, 1),
    ]:
        number(key, lo, hi)
    for key, lo, hi in [
        ("jobs_per_batch", 1, 1000),
        ("batch_repeats", 1, 100),
        ("warmup_jobs", 0, 10),
    ]:
        number(key, lo, hi, True)
    if not isinstance(config["noise_during_transit"], bool):
        raise ValueError("noise_during_transit: boolean required")  # noqa: TRY004
    for key in ["nodes", "workers", "backends"]:
        values = config[key]
        if not isinstance(values, list) or not values:
            raise ValueError(f"{key}: nonempty list required")
        if key == "backends":
            if any(
                not isinstance(v, str) or v not in ["qubit", "werner", "netsquid"]
                for v in values
            ):
                raise ValueError("backends: qubit, werner, netsquid only")
        else:
            for value in values:
                number(
                    key,
                    2 if key == "nodes" else 1,
                    50 if key == "nodes" else 4,
                    True,
                    value=value,
                )
        if len(set(values)) != len(values):
            raise ValueError(f"{key}: distinct entries required")
    if max(config["workers"]) > config["jobs_per_batch"]:
        raise ValueError("jobs_per_batch must be at least max workers")
    if "netsquid" in config["backends"] and 1 not in config["workers"]:
        raise ValueError("NetSquid comparison requires workers=1")
    if round(config["link_length_km"] / config["speed_km_s"] * 1e9) < 1:
        raise ValueError("link delay must be at least 1 ns")


def environment():
    versions = {}
    for package in [
        "qns",
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
        "netsquid",
        "pydynaa",
        "cysignals",
    ]:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    from qns.simulator import pool, simulator, ts

    core = {}
    for module in [simulator, ts, pool]:
        path = str(module.__file__)
        core[module.__name__] = {
            "path": path,
            "compiled": path.endswith((".so", ".pyd")),
        }
    model = platform.processor()
    if sys.platform == "darwin":
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=False,
        )
        model = result.stdout.strip() or model
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "cpu_model": model,
        "logical_cpus": os.cpu_count(),
        "packages": versions,
        "qns_core": core,
        "start_method": "spawn",
        "worker_thread_limits": dict.fromkeys(THREAD_VARS, "1"),
    }


def check_quality(jobs, nodes, settings):
    """Independent analytic count and Werner contraction, not only pairwise agreement."""
    hop = round(settings["link_length_km"] / settings["speed_km_s"] * 1e9)
    end = round(settings["duration"] * 1e9)
    rounds = 0
    expected_count, checksum = 0, 0
    while True:
        tick = round(rounds / settings["send_rate"] * 1e9)
        if tick >= end:
            break
        if tick + (nodes - 1) * hop <= end:
            expected_count += 1
            checksum += rounds
        rounds += 1
    # Initial Werner parameters multiply across links. Each local half waits
    # hop seconds; retained endpoints also wait (nodes-2)*hop for BSM messages.
    half_time = 2 * hop if settings["noise_during_transit"] else hop
    total_time = ((nodes - 1) * half_time + 2 * (nodes - 2) * hop) / 1e9
    initial_w = (4 * settings["initial_fidelity"] - 1) / 3
    expected_fidelity = (
        1
        + 3
        * initial_w ** (nodes - 1)
        * math.exp(-settings["depolar_rate"] * total_time)
    ) / 4
    for job in jobs:
        if (
            job["completed_pairs"] != expected_count
            or job["completed_round_checksum"] != checksum
            or job["scheduled_rounds"] != rounds
            or job["max_state_qubits"] > 4
        ):
            raise RuntimeError(
                f"Protocol quality/count mismatch: job {job['job_index']}, nodes {nodes}"
            )
        if expected_count and abs(job["mean_fidelity"] - expected_fidelity) > 1e-9:
            raise RuntimeError(
                f"Backend fidelity mismatch: job {job['job_index']}, nodes {nodes}"
            )
    return {
        "expected_completed": expected_count,
        "expected_fidelity": expected_fidelity,
        "jobs_checked": len(jobs),
    }


def speedup_rows(batches):
    baselines = {
        (r["backend"], r["nodes"], r["batch"]): r for r in batches if r["workers"] == 1
    }
    rows = []
    for row in batches:
        base = baselines.get((row["backend"], row["nodes"], row["batch"]))
        if row["workers"] != 1 and base:
            rows.append(
                {
                    "backend": row["backend"],
                    "nodes": row["nodes"],
                    "workers": row["workers"],
                    "batch": row["batch"],
                    "speedup": base["batch_seconds"] / row["batch_seconds"],
                }
            )
    return rows


def run(config, output, require_netsquid=False):
    validate(config)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "status": "running",
        "config": config,
        "assumptions": ASSUMPTIONS,
        "environment": environment(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "skipped": [],
        "quality_validation": {"passed": False, "conditions": []},
    }
    batches, jobs = [], []
    started = time.perf_counter()

    def save():
        metadata["wall_seconds"] = time.perf_counter() - started
        (output / "metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )

    save()
    try:
        backends = list(config["backends"])
        if "netsquid" in backends and importlib.util.find_spec("netsquid") is None:
            if require_netsquid:
                raise RuntimeError(
                    "NetSquid not installed; use the separate NetSquid environment"
                )
            backends.remove("netsquid")
            metadata["skipped"].append(
                {"backend": "netsquid", "reason": "package not installed"}
            )
        if not backends:
            raise RuntimeError(
                "No executable backend; all requested backends were skipped"
            )
        for batch_index in range(config["batch_repeats"]):
            # Rotate backend order across batches to reduce fixed-order bias.
            order = (
                backends[batch_index % len(backends) :]
                + backends[: batch_index % len(backends)]
            )
            for nodes in config["nodes"]:
                seeds = [
                    (
                        config["seed"]
                        + nodes * 10000
                        + batch_index * config["jobs_per_batch"]
                        + i
                    )
                    % 2**32
                    for i in range(config["jobs_per_batch"])
                ]
                for backend in order:
                    worker_order = config["workers"][
                        :: 1 if batch_index % 2 == 0 else -1
                    ]
                    for workers in [1] if backend == "netsquid" else worker_order:
                        condition = {
                            "backend": backend,
                            "nodes": nodes,
                            "workers": workers,
                            "batch": batch_index,
                        }
                        metadata["current_condition"] = condition
                        save()
                        print(f"Fig6: {condition}", file=sys.stderr, flush=True)
                        batch, records = run_batch(
                            backend, nodes, config, seeds, workers
                        )
                        quality = check_quality(records, nodes, config)
                        metadata["quality_validation"]["conditions"].append(
                            {**condition, **quality}
                        )
                        batches.append({**condition, **batch})
                        jobs.extend({**condition, **record} for record in records)
                        write_csv(output / "fig6_batches.csv", batches)
                        write_csv(output / "fig6_jobs.csv", jobs)
                        save()
        summary = summarize(
            batches,
            ["backend", "nodes", "workers"],
            ["batch_seconds", "amortized_seconds", "startup_seconds", "warmup_seconds"],
        )
        latency = summarize(
            jobs,
            ["backend", "nodes", "workers"],
            ["setup_seconds", "simulation_seconds", "job_seconds"],
        )
        write_csv(output / "fig6_summary.csv", summary)
        write_csv(output / "fig6_job_latency_summary.csv", latency)
        ratios = speedup_rows(batches)
        if ratios:
            write_csv(output / "fig6_speedups.csv", ratios)
            write_csv(
                output / "fig6_speedup_summary.csv",
                summarize(ratios, ["backend", "nodes", "workers"], ["speedup"]),
            )
        plot_fig6(summary, output / "fig6.png", "amortized_seconds")
        plot_fig6(latency, output / "fig6_job_latency.png", "job_seconds")
        metadata["quality_validation"]["passed"] = True
        metadata["status"] = "complete"
        metadata.pop("current_condition", None)
    except BaseException as error:
        metadata["status"] = "failed"
        metadata["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        save()
    return output.resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="evaluations/configs/fig6-smoke.json")
    parser.add_argument("--output")
    parser.add_argument("--workers", nargs="+", type=int)
    parser.add_argument("--require-netsquid", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.workers:
        config["workers"] = args.workers
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = (
        Path(args.output)
        if args.output
        else Path("results/evaluations") / f"fig6-{stamp}"
    )
    try:
        print(run(config, output, args.require_netsquid))
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
