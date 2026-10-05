"""11: 세 노드에 ClassicPacketForwardApp을 설치해 고전 패킷을 전달함."""

import argparse
import json

from _cli import positive_int
from qns.entity.cchannel.cchannel import ClassicPacket, RecvClassicPacket
from qns.entity.node.app import Application
from qns.network import QuantumNetwork
from qns.network.protocol.classicforward import ClassicPacketForwardApp
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology import LineTopology
from qns.network.topology.topo import ClassicTopology
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator


class PacketObserver(Application):
    def __init__(self, trace):
        super().__init__()
        self.trace = trace
        self.add_handler(self.receive, [RecvClassicPacket])

    def receive(self, node, event):
        self.trace.append({'node': node.name, 'time_seconds': self.get_simulator().tc.sec,
                           'sequence': event.packet.get()['sequence']})
        return False  # 다음 forwarding 앱이 패킷을 처리하도록 허용함.


class DestinationApp(Application):
    def __init__(self, received):
        super().__init__()
        self.received = received
        self.add_handler(self.receive, [RecvClassicPacket])

    def receive(self, node, event):
        if event.packet.dest is not node:
            return False
        self.received.append({'time_seconds': self.get_simulator().tc.sec, 'message': event.packet.get()})
        return True


def run(count=3):
    s = Simulator(0, count * 0.01 + 0.1, accuracy=1_000_000)
    net = QuantumNetwork(topo=LineTopology(3, memory_args=[], cchannel_args={'delay': 0.01}),
                         classic_topo=ClassicTopology.Follow)
    # 고전 채널로 경로를 구축함. 라우팅 알고리즘 비교는 하지 않음.
    route = DijkstraRouteAlgorithm()
    route.build(net.nodes, net.cchannels)
    trace, received = [], []
    for node in net.nodes:
        node.add_apps(PacketObserver(trace))
        node.add_apps(ClassicPacketForwardApp(route))
        node.add_apps(DestinationApp(received))
    net.install(s)
    source, relay, destination = net.nodes
    channel = source.get_cchannel(relay)
    for sequence in range(count):
        packet = ClassicPacket({'sequence': sequence, 'payload': 'hello'}, src=source, dest=destination)
        s.add_event(func_to_event(s.time(sec=sequence * 0.01), channel.send,
                                 packet=packet, next_hop=relay))
    s.run()
    return {'sent': count, 'received': received, 'packet_trace': trace,
            'apps': {n.name: [type(a).__name__ for a in n.apps] for n in net.nodes}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=positive_int, default=3)
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))
