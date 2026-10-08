"""20: 동일한 시도 수로 독립 센서와 GHZ 센서의 위상 추정 성능을 비교함."""
import json

from _sensor_network import experiment, sensor_parser


def run(nodes=3, shots=200, repeats=8, phase=0.1, quantum_delay=0.01,
        classical_delay=0.01, interrogation=0.005, drop_rate=0, t2=0, seed=42):
    settings = dict(nodes=nodes, shots=shots, repeats=repeats, phase=phase,
                    quantum_delay=quantum_delay, classical_delay=classical_delay,
                    interrogation=interrogation, drop_rate=drop_rate, t2=t2, seed=seed)
    # GHZ 준비 → 실제 quantum channel 분배 → 각 노드 RZ → X 측정 → parity.
    # 독립 방식에도 같은 채널·지연·시도 수를 적용. 손실된 시도도 비용에 포함함.
    independent = experiment('independent', **settings)
    ghz = experiment('ghz', **settings)
    a, b = independent['rmse'], ghz['rmse']
    ia = independent['expected_fisher_information_per_attempt']
    return {'independent': independent, 'ghz': ghz,
            'ideal_local_information_gain': nodes,
            'expected_information_gain': ghz['expected_fisher_information_per_attempt'] / ia if ia else None,
            'observed_rmse_ratio_independent_over_ghz': a / b if a is not None and b else None}


if __name__ == '__main__':
    parser = sensor_parser(__doc__)
    try:
        result = run(**vars(parser.parse_args()))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
