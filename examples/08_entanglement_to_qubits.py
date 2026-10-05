"""08: to_qubits()로 Werner 쌍을 공유 밀도행렬을 가진 큐비트로 변환함."""

import argparse
import contextlib
import io
import json

import numpy as np
from _cli import positive_int, probability, seed_value
from qns.models.epr.werner import WernerStateEntanglement
from qns.models.qubit import X
from qns.utils.rnd import set_seed


def convert(pair):
    # qns 0.2.3의 Werner.to_qubits는 rho를 stdout에 출력함.
    # JSON 출력이 깨지지 않게 해당 출력만 캡처하고 실제 반환값을 사용함.
    with contextlib.redirect_stdout(io.StringIO()):
        return pair.to_qubits()


def run(shots=1000, fidelities=(0.25, 0.9, 1), seed=42):
    set_seed(seed)
    experiments = []
    phi_plus = np.array([1, 0, 0, 1]) / np.sqrt(2)
    for fidelity in fidelities:
        pair = WernerStateEntanglement(fidelity)
        alice, bob = convert(pair)
        rho = alice.state.rho.copy()  # 측정 전에 공동 상태를 기록함.
        counts = {mode: dict.fromkeys(('00', '01', '10', '11'), 0)
                  for mode in ('z_counts', 'after_x_counts')}
        for mode, mode_counts in counts.items():
            for _ in range(shots):
                a, b = convert(WernerStateEntanglement(fidelity))
                if mode == 'after_x_counts':
                    X(a)
                mode_counts[f'{a.measure()}{b.measure()}'] += 1
        w = (4 * fidelity - 1) / 3
        experiments.append({
            'input_fidelity': fidelity, 'bell_overlap': float(np.real(phi_plus @ rho @ phi_plus)),
            'shared_state': alice.state is bob.state,
            'entanglement_consumed': pair.is_decoherenced,
            'density_matrix_real': rho.real.tolist(), 'density_matrix_imag': rho.imag.tolist(),
            'expected_z_agreement': (1 + w) / 2,
            'observed_z_agreement': (counts['z_counts']['00'] + counts['z_counts']['11']) / shots,
            **counts,
        })
    return {'seed': seed, 'shots_per_condition': shots, 'experiments': experiments}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shots', type=positive_int, default=1000)
    parser.add_argument('--fidelities', type=probability, nargs='+', default=[0.25, 0.9, 1])
    parser.add_argument('--seed', type=seed_value, default=42)
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))
