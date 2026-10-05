"""07: Werner 쌍의 저장 디코히런스·교환·확률적 정제를 관찰함."""

import argparse
import json
from statistics import mean

from _cli import nonnegative_float, positive_int, probability, seed_value
from qns.models.epr.werner import WernerStateEntanglement
from qns.utils.rnd import set_seed


def run(fidelity=0.9, shots=1000, storage_time=1, decoherence_rate=0.2, seed=42):
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
            'mean_distilled_fidelity': mean(distilled) if distilled else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fidelity', type=probability, default=0.9)
    parser.add_argument('--shots', type=positive_int, default=1000)
    parser.add_argument('--storage-time', type=nonnegative_float, default=1)
    parser.add_argument('--decoherence-rate', type=nonnegative_float, default=0.2)
    parser.add_argument('--seed', type=seed_value, default=42)
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))
