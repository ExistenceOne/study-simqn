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


def bell_example(shots, storage_time, decoherence_rate, p_swap, seed):
    set_seed(seed)
    stored = BellStateEntanglement(p_swap=p_swap)
    stored.store_error_model(t=storage_time, decoherence_rate=decoherence_rate)
    successful = []
    inputs_consumed = True
    for _ in range(shots):
        left, right = BellStateEntanglement(p_swap=p_swap), BellStateEntanglement(p_swap=p_swap)
        result = left.swapping(right)
        inputs_consumed &= left.is_decoherenced and right.is_decoherenced
        # Bell swapping은 실패해도 객체를 반환하므로 flag를 검사함.
        if not result.is_decoherenced:
            successful.append(float(result.fidelity))
    left, right = BellStateEntanglement(), BellStateEntanglement()
    distilled = left.distillation(right)
    return {'initial_fidelity': 1.0, 'stored_fidelity': float(stored.fidelity),
            'p_swap': p_swap, 'swap_attempts': shots, 'swap_successes': len(successful),
            'swap_success_fraction': len(successful) / shots,
            'mean_successful_swap_fidelity': mean(successful) if successful else None,
            'swap_inputs_consumed': bool(inputs_consumed),
            'distilled_fidelity': float(distilled.fidelity),
            'distillation_inputs_consumed': left.is_decoherenced and right.is_decoherenced}


def mixed_weights(pair):
    return [float(pair.a), float(pair.b), float(pair.c), float(pair.d)]


def mixed_example(weights, shots, storage_time, decoherence_rate, seed):
    def fresh():
        return MixedStateEntanglement(fidelity=weights[0], b=weights[1], c=weights[2], d=weights[3])

    set_seed(seed)
    stored = fresh()
    stored.store_error_model(t=storage_time, decoherence_rate=decoherence_rate)
    left, right = fresh(), fresh()
    initial = mixed_weights(left)
    swapped = left.swapping(right)
    # Bell 상태의 Pauli 라벨은 XOR로 합성됨.
    # 내장 식과 비교하는 기준값이며 라이브러리 출력을 덮어쓰지 않음.
    reference = [sum(initial[i] * initial[i ^ k] for i in range(4)) for k in range(4)]
    actual = mixed_weights(swapped)
    distilled = []
    for _ in range(shots):
        result = fresh().distillation(fresh())
        if result is not None and not result.is_decoherenced:
            distilled.append(mixed_weights(result))
    return {'weight_order': ['Phi+', 'Psi+', 'Psi-', 'Phi-'], 'initial_weights': initial,
            'stored_weights': mixed_weights(stored), 'swapped_weights': actual,
            'reference_swapped_weights': reference,
            'swap_max_abs_error': max(abs(a - b) for a, b in zip(actual, reference)),
            'swap_matches_bell_convolution': all(math.isclose(a, b, abs_tol=1e-12, rel_tol=1e-12)
                                                for a, b in zip(actual, reference)),
            'swap_inputs_consumed': left.is_decoherenced and right.is_decoherenced,
            'distillation_attempts': shots, 'distillation_successes': len(distilled),
            'distillation_success_fraction': len(distilled) / shots,
            'mean_distilled_fidelity': mean(v[0] for v in distilled) if distilled else None,
            'mean_distilled_weights': [mean(v[i] for v in distilled) for i in range(4)]
                                     if distilled else None}


def run(fidelity=0.9, shots=1000, storage_time=1, decoherence_rate=0.2, seed=42,
        bell_swap_probability=0.5, mixed_weights=(0.9, 0.05, 0.03, 0.02)):
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
    return {'seed': seed, 'initial_fidelity': fidelity,
            'storage_time_seconds': storage_time, 'decoherence_rate_per_second': decoherence_rate,
            'stored_fidelity': float(stored.fidelity), 'swapped_fidelity': float(swapped.fidelity),
            'swap_inputs_consumed': left.is_decoherenced and right.is_decoherenced,
            'distillation_attempts': shots, 'distillation_successes': len(distilled),
            'distillation_success_fraction': len(distilled) / shots,
            'mean_distilled_fidelity': mean(distilled) if distilled else None,
            'bell': bell_example(shots, storage_time, decoherence_rate,
                                 bell_swap_probability, (seed + 1) % 2**32),
            'mixed': mixed_example(mixed_weights, shots, storage_time, decoherence_rate,
                                   (seed + 2) % 2**32)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fidelity', type=probability, default=0.9)
    parser.add_argument('--shots', type=positive_int, default=1000)
    parser.add_argument('--storage-time', type=nonnegative_float, default=1)
    parser.add_argument('--decoherence-rate', type=nonnegative_float, default=0.2)
    parser.add_argument('--seed', type=seed_value, default=42)
    parser.add_argument('--bell-swap-probability', type=probability, default=0.5)
    parser.add_argument('--mixed-weights', type=probability, nargs=4,
                        default=[0.9, 0.05, 0.03, 0.02], metavar=('A', 'B', 'C', 'D'))
    args = parser.parse_args()
    if not math.isclose(sum(args.mixed_weights), 1.0, rel_tol=0, abs_tol=1e-9):
        parser.error('mixed-weights의 합은 1이어야 함')
    print(json.dumps(run(**vars(args)), indent=2))
