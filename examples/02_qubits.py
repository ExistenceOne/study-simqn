"""02: 독립적으로 준비한 큐비트를 측정하고 Bell 쌍의 상관관계를 확인함."""

import argparse
import json

from _cli import positive_int, seed_value
from qns.models.qubit import CNOT, H, Qubit, X
from qns.utils.rnd import set_seed


def run(shots=1000, seed=42):
    set_seed(seed)
    counts = {name: {"0": 0, "1": 0} for name in
              ["zero_state", "one_state", "plus_state"]}
    bell_counts = {"00": 0, "01": 0, "10": 0, "11": 0}

    for _ in range(shots):
        # 매번 새 큐비트를 준비함. 같은 큐비트를 반복 측정하는 실험이 아님.
        zero, one, plus = Qubit(), Qubit(), Qubit()
        X(one)       # |0> -> |1>
        H(plus)      # |0> -> |+>
        for name, qubit in [("zero_state", zero), ("one_state", one),
                            ("plus_state", plus)]:
            counts[name][str(qubit.measure())] += 1  # 기본 측정 기저는 Z

        alice, bob = Qubit(), Qubit()
        H(alice)
        CNOT(alice, bob)  # (|00> + |11>) / sqrt(2)
        bits = f"{alice.measure()}{bob.measure()}"
        bell_counts[bits] += 1

    return {"shots": shots, "seed": seed, **counts, "bell_pairs": bell_counts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=positive_int, default=1000, help="각 실험의 반복 횟수")
    parser.add_argument("--seed", type=seed_value, default=42)
    args = parser.parse_args()
    print(json.dumps(run(args.shots, args.seed), indent=2))
