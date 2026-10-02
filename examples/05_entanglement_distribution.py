"""05: 선형 네트워크의 중계 노드를 거쳐 얽힘을 분배함."""

import argparse
import json
import math
from statistics import mean

from _cli import (
    nonnegative_float,
    positive_float,
    positive_int,
    probability,
    seed_value,
)
from qns.network import QuantumNetwork
from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology import LineTopology
from qns.network.topology.topo import ClassicTopology
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed


def run(nodes=4, duration=5, send_rate=5, delay=0.01, memory=20, fidelity=0.99, seed=42):
    set_seed(seed)
    simulator = Simulator(0, duration, accuracy=1_000_000)
    topology = LineTopology(
        nodes_number=nodes,
        qchannel_args={"delay": delay, "bandwidth": 0, "drop_rate": 0},
        cchannel_args={"delay": delay, "bandwidth": 0},
        memory_args=[{"capacity": memory, "decoherence_rate": 0}],
        nodes_apps=[EntanglementDistributionApp(init_fidelity=fidelity)],
    )
    # 내장 프로토콜은 목적지에서 송신자로 직접 성공 통지를 보냄.
    # 이를 위해 고전 채널은 모든 노드 쌍을 연결함.
    network = QuantumNetwork(topo=topology, classic_topo=ClassicTopology.All,
                             route=DijkstraRouteAlgorithm())
    network.build_route()
    source, destination = network.nodes[0], network.nodes[-1]
    path = network.query_route(source, destination)[0][2]
    network.add_request(source, destination, attr={"send_rate": send_rate})
    network.install(simulator)
    simulator.run()

    sender = source.get_apps(EntanglementDistributionApp)[0]
    receiver = destination.get_apps(EntanglementDistributionApp)[0]
    # sender.success_count는 성공 통지가 도착한 수임. 완료 수는 목적지 기준으로 셈.
    fidelities = [pair.fidelity for pair in receiver.success]
    return {
        "seed": seed, "nodes": nodes, "path": [node.name for node in path],
        "duration_seconds": duration, "attempted": sender.send_count,
        "completed": receiver.success_count,
        "acknowledged_at_source": sender.success_count,
        "pairs_per_second": receiver.success_count / duration,
        "mean_fidelity": mean(fidelities) if fidelities else None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes", type=positive_int, default=4, help="노드 수, 최소 2")
    parser.add_argument("--duration", type=positive_float, default=5, help="가상 실험 시간, 초")
    parser.add_argument("--send-rate", type=positive_float, default=5, help="초당 분배 시도 수")
    parser.add_argument("--delay", type=nonnegative_float, default=0.01, help="각 채널 지연, 초")
    parser.add_argument("--memory", type=positive_int, default=20, help="노드별 메모리 용량, 최소 2")
    parser.add_argument("--fidelity", type=probability, default=0.99, help="초기 Werner 상태 충실도")
    parser.add_argument("--seed", type=seed_value, default=42)
    args = parser.parse_args()
    if args.nodes < 2 or args.memory < 2:
        parser.error("nodes와 memory는 각각 2 이상이어야 함")
    if args.duration < 0.000001 or args.send_rate > 1_000_000:
        parser.error("1 us 시간 해상도 기준 duration >= 1e-6, send-rate <= 1e6 필요함")
    if not math.isfinite(1_000_000 / args.send_rate):
        parser.error("send-rate가 너무 작아서 이벤트 시각을 표현할 수 없음")
    print(json.dumps(run(args.nodes, args.duration, args.send_rate, args.delay,
                         args.memory, args.fidelity, args.seed), indent=2))
