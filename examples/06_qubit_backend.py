"""06: 밀도행렬 backend와 QubitFactory의 비트 반전 잡음을 비교함."""

import argparse
import json

import numpy as np
from _cli import positive_int, probability, seed_value
from _noise import bit_flip_measure_error
from qns.models.qubit import H, Qubit
from qns.models.qubit.factory import QubitFactory
from qns.utils.rnd import set_seed


def run(shots=1000, flip_probability=0.2, seed=42):
    set_seed(seed)
    noisy = QubitFactory(measure_decoherence_rate=flip_probability,
                         measure_error_model=bit_flip_measure_error)
    counts = {k: {'0': 0, '1': 0} for k in ('ideal_zero', 'noisy_zero', 'plus', 'mixed')}
    mixed_rho = np.eye(2) / 2
    for _ in range(shots):
        plus = Qubit()
        H(plus)
        for name, qubit in [('ideal_zero', Qubit()), ('noisy_zero', noisy()),
                            ('plus', plus), ('mixed', Qubit(rho=mixed_rho.copy()))]:
            counts[name][str(qubit.measure())] += 1
    return {'shots': shots, 'seed': seed, 'flip_probability': flip_probability,
            'mixed_density_matrix': mixed_rho.tolist(), **counts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shots', type=positive_int, default=1000)
    parser.add_argument('--flip-probability', type=probability, default=0.2)
    parser.add_argument('--seed', type=seed_value, default=42)
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))
