"""Fig. 5: 같은 토폴로지/요청에서 세션 수·송신 속도별 실제 분배율 측정."""

from statistics import mean

from qns.entity.cchannel.cchannel import ClassicChannel
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel
from qns.network import QuantumNetwork
from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology import RandomTopology
from qns.network.topology.topo import ClassicTopology
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed


class MeasuredDistributionApp(EntanglementDistributionApp):
    def __init__(self, init_fidelity):
        super().__init__(init_fidelity=init_fidelity)
        self.completion_times = []
        self.completion_fidelities = []

    def handle_response(self, packet):
        before = self.success_count
        super().handle_response(packet)
        if self.success_count > before and self.success:
            # 목적지 success에만 쌍이 추가됨. 송신자 ACK 카운터는 별도로 둠.
            self.completion_times.append(self._simulator.current_time.sec)
            self.completion_fidelities.append(float(self.success[-1].fidelity))


def build_network(settings, topology_seed):
    set_seed(topology_seed)
    topology = RandomTopology(
        nodes_number=settings["nodes"],
        lines_number=settings["links"],
        qchannel_args={
            "delay": settings["quantum_delay"],
            # qns 0.2.3 연결성 검사에서는 0을 연결 없음으로 취급함.
            # 생성 중만 양수로 설정하고, 실제 채널 설정은 아래에서 복원함.
            "bandwidth": settings["quantum_bandwidth"] or 1,
            "drop_rate": 0,
        },
        cchannel_args={
            "delay": settings["classical_delay"],
            "bandwidth": settings["classical_bandwidth"],
        },
        memory_args=[
            {
                "capacity": settings["memory"],
                "decoherence_rate": 1 / settings["coherence_time"],
            }
        ],
        nodes_apps=[MeasuredDistributionApp(init_fidelity=settings["fidelity"])],
    )
    network = QuantumNetwork(
        topo=topology, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm()
    )
    for channel in network.qchannels:
        channel.bandwidth = settings["quantum_bandwidth"]
    network.build_route()
    return network  # install 전 템플릿임. 각 실험은 독립된 복사본을 사용함.


def simulate(
    base_network, sessions, send_rate, settings, request_seed, simulation_seed
):
    # 완전 고전 그래프는 객체 참조가 깊어서 deepcopy 시 재귀 한계를 넘음.
    # 엔티티는 새로 만들고 계산된 경로의 노드 참조만 새 노드로 매핑함.
    network = QuantumNetwork(route=DijkstraRouteAlgorithm())
    mapping = {}
    for old_node in base_network.nodes:
        node = QNode(old_node.name)
        network.add_node(node)
        mapping[old_node] = node
        node.add_apps(MeasuredDistributionApp(init_fidelity=settings["fidelity"]))
        node.add_memory(
            QuantumMemory(
                name=f"m-{node.name}",
                node=node,
                capacity=settings["memory"],
                decoherence_rate=1 / settings["coherence_time"],
            )
        )
    for old_channel in base_network.qchannels:
        channel = QuantumChannel(
            old_channel.name,
            delay=settings["quantum_delay"],
            bandwidth=settings["quantum_bandwidth"],
            drop_rate=0,
        )
        for old_node in old_channel.node_list:
            mapping[old_node].add_qchannel(channel)
        network.add_qchannel(channel)
    for old_channel in base_network.cchannels:
        channel = ClassicChannel(
            old_channel.name,
            delay=settings["classical_delay"],
            bandwidth=settings["classical_bandwidth"],
        )
        for old_node in old_channel.node_list:
            mapping[old_node].add_cchannel(channel)
        network.add_cchannel(channel)
    network.route.route_table = {
        mapping[source]: {
            mapping[dest]: [cost, [mapping[node] for node in path]]
            for dest, (cost, path) in destinations.items()
        }
        for source, destinations in base_network.route.route_table.items()
    }
    set_seed(request_seed)
    network.random_requests(
        sessions, allow_overlay=False, attr={"send_rate": send_rate}
    )
    set_seed(simulation_seed)
    simulator = Simulator(0, settings["duration"], accuracy=1_000_000)
    network.install(simulator)
    simulator.run()
    window = settings["duration"] - settings["warmup"]
    rows = []
    for index, request in enumerate(network.requests):
        source = request.src.get_apps(MeasuredDistributionApp)[0]
        destination = request.dest.get_apps(MeasuredDistributionApp)[0]
        fidelities = [
            fidelity
            for time, fidelity in zip(
                destination.completion_times, destination.completion_fidelities
            )
            if time >= settings["warmup"]
        ]
        rows.append(
            {
                "session": index,
                "source": request.src.name,
                "destination": request.dest.name,
                "hops": len(network.query_route(request.src, request.dest)[0][2]) - 1,
                "attempted_full_run": source.send_count,
                "completed": len(fidelities),
                "eps": len(fidelities) / window,
                "mean_fidelity": mean(fidelities) if fidelities else None,
            }
        )
    completed = sum(row["completed"] for row in rows)
    # rate와 count를 혼동하지 않도록 서로 다른 지표를 모두 저장함.
    result = {
        "sessions": sessions,
        "send_rate_hz": send_rate,
        "completed": completed,
        "mean_completed_per_session": completed / sessions,
        "total_eps": completed / window,
        "mean_session_eps": completed / window / sessions,
        "measurement_seconds": window,
        "request_seed": request_seed,
        "simulation_seed": simulation_seed,
    }
    return result, rows
