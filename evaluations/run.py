"""논문 Fig. 3·5 실행: python -m evaluations.run --config ... --output ..."""

import argparse
import importlib.metadata
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evaluations import fig3, fig5
from evaluations.plotting import plot_fig3, plot_fig5
from evaluations.reporting import summarize, write_csv

ASSUMPTIONS = {
    "reproduction": "Source-informed rerun; not an exact numerical reproduction or curve fit.",
    "fig3_metric": "Minimum link correct-sifted bits / duration. Historical diagnostic; not secure secret key rate or an implemented relay transport.",
    "fig3_legacy_source": "QNLab-USTC/SimQN@3902842032db74e14a10ea72360264697a79fe3a:qns/network/protocol/bb84.py",
    "fig3_loss": "Paper specifies 0.2 dB/km; public examples instead used exp(-L_km/50). Config selects the convention.",
    "fig3_noise": "Historical public code uses collective rotation. Paper-stated preset assumes p_X=min(1, bit_flip_per_km*L_km); coefficient is not from the paper.",
    "fig3_relays": "Equal hop lengths, unlimited bandwidth, min link count; no extra relay processing delay. Duration comes from the public examples.",
    "fig5_missing": "Exact node/link count, delays, bandwidth, duration, seeds and repeats are not fully specified in the paper. They are explicit configurable assumptions.",
    "fig5_classical": "All-pairs classical channels for direct success notification in the built-in protocol; quantum graph is random.",
    "fig5_sessions": "Unique endpoints, disjoint source/destination pairs; prefixes shared across session counts within a trial.",
    "fig5_metric": "Destination completions in [warmup,duration], divided by duration-warmup. Report total and per-session pair/s plus mean counts; paper throughput normalization unclear.",
    "fig5_quality": "Protocol completions are counted without a fidelity threshold. Mean fidelity is snapshotted at destination completion, before later source ACK mutations.",
    "uncertainty": "Sample standard deviation and SEM across independent seeds. Single-trial uncertainty is null, not a zero-error estimate.",
}


def validate(config):
    def numeric(value, label, minimum=0, maximum=1e12, integer=False):
        try:
            valid = (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and minimum <= value <= maximum
                and (not integer or isinstance(value, int))
            )
        except (ValueError, OverflowError):
            valid = False
        if not valid:
            raise ValueError(
                f"{label}: expected {'integer' if integer else 'finite number'} in [{minimum}, {maximum}]"
            )

    def required(section, keys):
        if not isinstance(section, dict) or set(keys) - section.keys():
            raise ValueError(f"Missing config keys: {keys}")

    def sequence(values, label):
        if (
            not isinstance(values, list)
            or not values
            or len(set(values)) != len(values)
        ):
            raise ValueError(f"{label}: nonempty list of distinct values required")

    required(config, ["name", "seed", "fig3", "fig5"])
    if not isinstance(config["name"], str) or not config["name"]:
        raise ValueError("name: nonempty string required")
    numeric(config["seed"], "seed", maximum=2**32 - 10000, integer=True)
    three, five = config["fig3"], config["fig5"]
    required(
        three,
        [
            "duration",
            "repeats",
            "send_rate",
            "lengths_km",
            "relays",
            "relay_total_length_km",
            "loss_model",
            "attenuation_db_km",
            "noise",
            "bit_flip_per_km",
            "light_speed_m_s",
        ],
    )
    required(
        five,
        [
            "nodes",
            "links",
            "duration",
            "warmup",
            "repeats",
            "sessions",
            "send_rates",
            "memory",
            "fidelity",
            "coherence_time",
            "quantum_delay",
            "classical_delay",
            "quantum_bandwidth",
            "classical_bandwidth",
        ],
    )
    for section in [three, five]:
        numeric(section["duration"], "duration", minimum=1e-6)
        numeric(section["repeats"], "repeats", minimum=1, maximum=1000, integer=True)
    numeric(three["send_rate"], "send_rate", minimum=1e-6, maximum=1e6)
    numeric(three["attenuation_db_km"], "attenuation_db_km", maximum=100)
    numeric(three["bit_flip_per_km"], "bit_flip_per_km", maximum=1)
    numeric(three["light_speed_m_s"], "light_speed_m_s", minimum=1)
    numeric(three["relay_total_length_km"], "relay_total_length_km", minimum=0)
    if three["loss_model"] not in ["paper-db", "historical-exp"]:
        raise ValueError("loss_model: paper-db or historical-exp required")
    if three["noise"] not in ["bit-flip", "historical-rotation"]:
        raise ValueError("noise: bit-flip or historical-rotation required")
    sequence(three["lengths_km"], "lengths_km")
    sequence(three["relays"], "relays")
    for length in three["lengths_km"]:
        numeric(length, "lengths_km", maximum=10000)
    for relays in three["relays"]:
        numeric(relays, "relays", maximum=100, integer=True)
    numeric(five["nodes"], "nodes", minimum=2, maximum=400, integer=True)
    numeric(
        five["links"],
        "links",
        minimum=five["nodes"] - 1,
        maximum=five["nodes"] * (five["nodes"] - 1) // 2,
        integer=True,
    )
    numeric(five["memory"], "memory", minimum=2, integer=True)
    numeric(five["fidelity"], "fidelity", minimum=0.25, maximum=1)
    numeric(five["coherence_time"], "coherence_time", minimum=1e-6)
    numeric(five["warmup"], "warmup", maximum=five["duration"])
    if five["duration"] - five["warmup"] < 1e-6:
        raise ValueError("duration - warmup must be at least 1 us")
    for name in ["quantum_delay", "classical_delay"]:
        numeric(five[name], name)
    for name in ["quantum_bandwidth", "classical_bandwidth"]:
        numeric(five[name], name, maximum=1e6, integer=True)
    sequence(five["sessions"], "sessions")
    sequence(five["send_rates"], "send_rates")
    for sessions in five["sessions"]:
        numeric(
            sessions, "sessions", minimum=1, maximum=five["nodes"] // 2, integer=True
        )
    for rate in five["send_rates"]:
        numeric(rate, "send_rates", minimum=1e-6, maximum=1e6)


def run_fig3(settings, seed, output, profile):
    for panel in ["a", "b"]:
        conditions = (
            [(length, relay) for length in settings["lengths_km"] for relay in [0, 1]]
            if panel == "a"
            else [
                (settings["relay_total_length_km"], relay)
                for relay in settings["relays"]
            ]
        )
        rows = []
        for length, relay in conditions:
            for noise in ["none", settings["noise"]]:
                print(
                    f"Fig3{panel}: length={length}km relays={relay} noise={noise}",
                    file=sys.stderr,
                    flush=True,
                )
                for trial in range(settings["repeats"]):
                    row = fig3.simulate(length, relay, noise, settings, seed + trial)
                    rows.append({"trial": trial, **row})
                write_csv(output / f"fig3{panel}_trials.csv", rows)
        summary = summarize(
            rows,
            ["total_length_km", "relays", "noise"],
            ["correct_sifted_bps", "sifted_bps", "qber"],
        )
        write_csv(output / f"fig3{panel}_summary.csv", summary)
        plot_fig3(summary, panel, output / f"fig3{panel}.png", profile)


def run_fig5(settings, seed, output, profile):
    rows, session_rows = [], []
    for trial in range(settings["repeats"]):
        topology_seed = seed + 3 * trial
        print(
            f"Fig5: building {settings['nodes']} nodes, {settings['links']} links, trial={trial}",
            file=sys.stderr,
            flush=True,
        )
        base = fig5.build_network(settings, topology_seed)
        for sessions in settings["sessions"]:
            for rate in settings["send_rates"]:
                print(
                    f"Fig5: sessions={sessions} send_rate={rate}Hz trial={trial}",
                    file=sys.stderr,
                    flush=True,
                )
                result, details = fig5.simulate(
                    base, sessions, rate, settings, topology_seed + 1, topology_seed + 2
                )
                rows.append({"trial": trial, "topology_seed": topology_seed, **result})
                session_rows.extend(
                    {
                        "trial": trial,
                        "sessions": sessions,
                        "send_rate_hz": rate,
                        **detail,
                    }
                    for detail in details
                )
                write_csv(output / "fig5_trials.csv", rows)
                write_csv(output / "fig5_sessions.csv", session_rows)
    summary = summarize(
        rows,
        ["sessions", "send_rate_hz"],
        ["mean_session_eps", "total_eps", "mean_completed_per_session"],
    )
    write_csv(output / "fig5_summary.csv", summary)
    plot_fig5(summary, output / "fig5.png", profile)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("evaluations/configs/smoke.json")
    )
    parser.add_argument("--figures", nargs="+", choices=["3", "5"], default=["3", "5"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        validate(config)
    except (ValueError, TypeError, OSError) as error:
        parser.error(str(error))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = (
        args.output or Path("results/evaluations") / f"{args.config.stem}-{timestamp}"
    )
    if output.exists() and any(output.iterdir()):
        parser.error("output directory must be empty; use a new --output path")
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    metadata = {
        "status": "running",
        "config": config,
        "figures": args.figures,
        "assumptions": ASSUMPTIONS,
        "versions": {
            "python": platform.python_version(),
            **{
                name: importlib.metadata.version(name)
                for name in ["qns", "numpy", "pandas", "matplotlib"]
            },
        },
        "platform": platform.platform(),
        "started_utc": timestamp,
    }

    def save_metadata():
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    save_metadata()
    try:
        if "3" in args.figures:
            run_fig3(config["fig3"], config["seed"], output, config["name"])
        if "5" in args.figures:
            run_fig5(config["fig5"], config["seed"], output, config["name"])
        metadata["status"] = "complete"
    except Exception as error:
        metadata["status"] = "failed"
        metadata["error"] = str(error)
        raise
    finally:
        metadata["wall_seconds"] = time.perf_counter() - started
        save_metadata()
    print(output.resolve())


if __name__ == "__main__":
    main()
