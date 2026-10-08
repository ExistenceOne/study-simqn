"""19: 각 센서의 독립 Ramsey 측정과 고전 채널을 통한 결과 수집."""
import json

from _sensor_network import experiment, sensor_parser


def run(nodes=3, shots=200, repeats=8, phase=0.1, quantum_delay=0.01,
        classical_delay=0.01, interrogation=0.005, drop_rate=0, t2=0, seed=42):
    # 각 센서는 + 상태를 준비하고 RZ(phase + pi/2) 이후 X 측정함.
    # 공통 위상은 사전에 알려진 좁은 범위로 제한함. RMSE를 구하려고 독립 반복함.
    return experiment('independent', nodes, shots, repeats, phase, quantum_delay,
                      classical_delay, interrogation, drop_rate, t2, seed)


if __name__ == '__main__':
    parser = sensor_parser(__doc__)
    args = vars(parser.parse_args())
    try:
        result = run(**args)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
