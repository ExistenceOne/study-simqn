"""07: Werner·이상적 Bell·Bell 대각 Mixed 쌍의 저장·교환·정제를 비교함."""

import argparse
import json
import math
from statistics import mean

from _cli import nonnegative_float, positive_int, probability, seed_value
from qns.models.epr.bell import BellStateEntanglement
from qns.models.epr.mixed import MixedStateEntanglement
from qns.models.epr.werner import WernerStateEntanglement
from qns.utils.rnd import set_seed


def run(
    fidelity=0.9,
    shots=1000,
    storage_time=1,
    decoherence_rate=0.2,
    seed=42,
    bell_swap_probability=0.5,
    mixed_weights=(0.9, 0.05, 0.03, 0.02),
):
    # Werner: 충실도 한 값으로 표현하는 저장·교환·정제
    set_seed(seed)
    stored = WernerStateEntanglement(fidelity)
    stored.store_error_model(t=storage_time, decoherence_rate=decoherence_rate)
    left, right = WernerStateEntanglement(fidelity), WernerStateEntanglement(fidelity)
    swapped = left.swapping(right)
    distilled = []
    for _ in range(shots):
        # 교환·정제는 두 입력을 소비하므로 매번 새 쌍을 준비함.
        a, b = WernerStateEntanglement(fidelity), WernerStateEntanglement(fidelity)
        result = a.distillation(b)
        if result is not None:
            distilled.append(float(result.fidelity))
    werner_result = {
        "seed": seed,
        "initial_fidelity": fidelity,
        "storage_time_seconds": storage_time,
        "decoherence_rate_per_second": decoherence_rate,
        "stored_fidelity": float(stored.fidelity),
        "swapped_fidelity": float(swapped.fidelity),
        "swap_inputs_consumed": left.is_decoherenced and right.is_decoherenced,
        "distillation_attempts": shots,
        "distillation_successes": len(distilled),
        "distillation_success_fraction": len(distilled) / shots,
        "mean_distilled_fidelity": mean(distilled) if distilled else None,
    }

    # Bell: 이상적 상태와 확률적 교환
    set_seed((seed + 1) % 2**32)
    stored = BellStateEntanglement(p_swap=bell_swap_probability)
    stored.store_error_model(t=storage_time, decoherence_rate=decoherence_rate)
    successful = []
    inputs_consumed = True
    for _ in range(shots):
        left, right = (
            BellStateEntanglement(p_swap=bell_swap_probability),
            BellStateEntanglement(p_swap=bell_swap_probability),
        )
        result = left.swapping(right)
        inputs_consumed &= left.is_decoherenced and right.is_decoherenced
        # Bell swapping은 실패해도 객체를 반환하므로 flag를 검사함.
        if not result.is_decoherenced:
            successful.append(float(result.fidelity))
    left, right = BellStateEntanglement(), BellStateEntanglement()
    distilled = left.distillation(right)
    bell_result = {
        "initial_fidelity": 1.0,
        "stored_fidelity": float(stored.fidelity),
        "p_swap": bell_swap_probability,
        "swap_attempts": shots,
        "swap_successes": len(successful),
        "swap_success_fraction": len(successful) / shots,
        "mean_successful_swap_fidelity": mean(successful) if successful else None,
        "swap_inputs_consumed": bool(inputs_consumed),
        "distilled_fidelity": float(distilled.fidelity),
        "distillation_inputs_consumed": left.is_decoherenced and right.is_decoherenced,
    }

    # Mixed: 비대칭 Bell 가중치와 내장 교환식 비교
    set_seed((seed + 2) % 2**32)
    mixed_args = {
        "fidelity": mixed_weights[0],
        "b": mixed_weights[1],
        "c": mixed_weights[2],
        "d": mixed_weights[3],
    }
    stored = MixedStateEntanglement(**mixed_args)
    stored.store_error_model(t=storage_time, decoherence_rate=decoherence_rate)
    left, right = (
        MixedStateEntanglement(**mixed_args),
        MixedStateEntanglement(**mixed_args),
    )
    initial = [float(left.a), float(left.b), float(left.c), float(left.d)]
    swapped = left.swapping(right)
    # Bell 상태의 Pauli 라벨은 XOR로 합성됨.
    # 내장 식과 비교하는 기준값이며 라이브러리 출력을 덮어쓰지 않음.
    reference = [sum(initial[i] * initial[i ^ k] for i in range(4)) for k in range(4)]
    actual = [float(swapped.a), float(swapped.b), float(swapped.c), float(swapped.d)]
    distilled = []
    for _ in range(shots):
        result = MixedStateEntanglement(**mixed_args).distillation(
            MixedStateEntanglement(**mixed_args)
        )
        if result is not None and not result.is_decoherenced:
            distilled.append(
                [float(result.a), float(result.b), float(result.c), float(result.d)]
            )
    mixed_result = {
        "weight_order": ["Phi+", "Psi+", "Psi-", "Phi-"],
        "initial_weights": initial,
        "stored_weights": [
            float(stored.a),
            float(stored.b),
            float(stored.c),
            float(stored.d),
        ],
        "swapped_weights": actual,
        "reference_swapped_weights": reference,
        "swap_max_abs_error": max(abs(a - b) for a, b in zip(actual, reference)),
        "swap_matches_bell_convolution": all(
            math.isclose(a, b, abs_tol=1e-12, rel_tol=1e-12)
            for a, b in zip(actual, reference)
        ),
        "swap_inputs_consumed": left.is_decoherenced and right.is_decoherenced,
        "distillation_attempts": shots,
        "distillation_successes": len(distilled),
        "distillation_success_fraction": len(distilled) / shots,
        "mean_distilled_fidelity": mean(v[0] for v in distilled) if distilled else None,
        "mean_distilled_weights": [mean(v[i] for v in distilled) for i in range(4)]
        if distilled
        else None,
    }

    return {**werner_result, "bell": bell_result, "mixed": mixed_result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fidelity", type=probability, default=0.9)
    parser.add_argument("--shots", type=positive_int, default=1000)
    parser.add_argument("--storage-time", type=nonnegative_float, default=1)
    parser.add_argument("--decoherence-rate", type=nonnegative_float, default=0.2)
    parser.add_argument("--seed", type=seed_value, default=42)
    parser.add_argument("--bell-swap-probability", type=probability, default=0.5)
    parser.add_argument(
        "--mixed-weights",
        type=probability,
        nargs=4,
        default=[0.9, 0.05, 0.03, 0.02],
        metavar=("A", "B", "C", "D"),
    )
    args = parser.parse_args()
    if not math.isclose(sum(args.mixed_weights), 1.0, rel_tol=0, abs_tol=1e-9):
        parser.error("mixed-weights의 합은 1이어야 함")
    print(json.dumps(run(**vars(args)), indent=2))
