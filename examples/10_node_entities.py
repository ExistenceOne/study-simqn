"""10: 노드에 메모리·operator·두 채널을 연결하고 수신→연산→ACK를 실행함."""

import argparse
import json

from qns.entity.cchannel.cchannel import (
    ClassicChannel,
    ClassicPacket,
    RecvClassicPacket,
)
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.operator.event import OperateRequestEvent, OperateResponseEvent
from qns.entity.operator.operator import QuantumOperator
from qns.entity.qchannel.qchannel import QuantumChannel, RecvQubitPacket
from qns.models.qubit import Qubit, X
from qns.simulator.simulator import Simulator


def flip_and_measure(qubit):
    X(qubit)
    return qubit.measure()


class ReceiverApp(Application):
    def __init__(self, peer, memory, operator, cchannel, observations):
        super().__init__()
        self.peer, self.memory, self.operator = peer, memory, operator
        self.cchannel, self.observations = cchannel, observations
        self.add_handler(self.receive_qubit, [RecvQubitPacket])
        self.add_handler(self.operation_done, [OperateResponseEvent])

    def receive_qubit(self, node, event):
        s = self.get_simulator()
        self.observations['quantum_arrival_seconds'] = s.tc.sec
        if not self.memory.write(event.qubit):
            raise RuntimeError('메모리에 수신 큐비트를 저장하지 못함')
        self.observations['memory_usage_after_write'] = self.memory.count
        qubit = self.memory.read(event.qubit)
        self.observations['memory_usage_after_read'] = self.memory.count
        # operate() 직접 호출과 달리 응답 이벤트에 operator 지연이 적용됨.
        s.add_event(OperateRequestEvent(operator=self.operator, qubits=[qubit], t=s.tc, by=self))
        return True

    def operation_done(self, node, event):
        self.observations['measurement'] = event.result
        self.observations['operation_response_seconds'] = self.get_simulator().tc.sec
        self.cchannel.send(ClassicPacket({'bit': event.result}, src=node, dest=self.peer), self.peer)
        return True


class AckApp(Application):
    def __init__(self, observations):
        super().__init__()
        self.observations = observations
        self.add_handler(self.receive, [RecvClassicPacket])

    def receive(self, node, event):
        self.observations['ack'] = event.packet.get()
        self.observations['ack_arrival_seconds'] = self.get_simulator().tc.sec
        return True


def run():
    s = Simulator(0, 0.1, accuracy=1_000_000)
    alice, bob = QNode('Alice'), QNode('Bob')
    quantum = QuantumChannel('quantum', delay=0.02, bandwidth=0)
    classical = ClassicChannel('classical', delay=0.01, bandwidth=0)
    for node in (alice, bob):
        node.add_qchannel(quantum)
        node.add_cchannel(classical)
        node.add_memory(QuantumMemory(f'{node.name}-memory', capacity=2))
        node.add_operator(QuantumOperator(f'{node.name}-operator', gate=flip_and_measure, delay=0.01))
    observations = {}
    alice.add_apps(AckApp(observations))
    bob.add_apps(ReceiverApp(alice, bob.memories[0], bob.operators[0], classical, observations))
    # install()는 등록된 entity와 앱도 설치함. 공유 채널은 양 끝 노드에 등록함.
    alice.install(s)
    bob.install(s)
    quantum.send(Qubit(name='payload'), next_hop=bob)
    s.run()
    return {'nodes': {n.name: {'memories': [m.name for m in n.memories],
                             'operators': [o.name for o in n.operators],
                             'qchannels': [q.name for q in n.qchannels],
                             'cchannels': [c.name for c in n.cchannels],
                             'apps': [type(a).__name__ for a in n.apps]} for n in (alice, bob)},
            **observations}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(run(), indent=2))
