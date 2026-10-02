"""04: 같은 네트워크에서도 경로 비용의 정의에 따라 선택 경로가 달라짐."""

import json

from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel
from qns.network import QuantumNetwork
from qns.network.route.dijkstra import DijkstraRouteAlgorithm


def run():
    network = QuantumNetwork()
    alice, relay1, relay2, bob = [QNode(name) for name in
                                ["Alice", "Relay1", "Relay2", "Bob"]]
    for node in [alice, relay1, relay2, bob]:
        network.add_node(node)

    # 직접 링크는 100 ms, 우회 링크 3개는 각각 10 ms임.
    for name, left, right, delay in [
        ("direct", alice, bob, 0.1),
        ("via1", alice, relay1, 0.01),
        ("via2", relay1, relay2, 0.01),
        ("via3", relay2, bob, 0.01),
    ]:
        channel = QuantumChannel(name, delay=delay)
        left.add_qchannel(channel)
        right.add_qchannel(channel)
        network.add_qchannel(channel)

    network.build_route()  # 기본 비용은 링크당 1, 즉 홉 수임.
    hops_cost, _, hops_path = network.query_route(alice, bob)[0]

    network.route = DijkstraRouteAlgorithm(
        metric_func=lambda channel: channel.delay_model.calculate(),
    )
    network.build_route()
    delay_cost, _, delay_path = network.query_route(alice, bob)[0]
    return {
        "fewest_hops": {"path": [node.name for node in hops_path], "cost_hops": hops_cost},
        "lowest_delay": {"path": [node.name for node in delay_path], "cost_seconds": delay_cost},
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
