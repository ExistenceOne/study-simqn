"""17: Bell 측정 → 두 고전 비트 송신 → 수신 후 보정하는 네트워크 텔레포테이션."""
import json

from _distributed import (STATES, attach_storage_noise, bell_qubits, computing_parser,
                          overlap, summarize, validate)
from qns.entity.cchannel.cchannel import ClassicChannel, ClassicPacket, RecvClassicPacket
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel, RecvQubitPacket
from qns.models.qubit import CNOT, H, Qubit, X, Z
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed


class TeleportApp(Application):
    def __init__(self, role, peer, memory, classical, record, target):
        super().__init__()
        self.role, self.peer, self.memory = role, peer, memory
        self.classical, self.record, self.target = classical, record, target
        self.add_handler(self.receive_qubit, [RecvQubitPacket])
        self.add_handler(self.receive_classical, [RecvClassicPacket])

    def trace(self, event):
        self.record['trace'].append({'node': self.get_node().name, 'event': event,
                                     'time_seconds': self.get_simulator().tc.sec})

    def send(self, kind, **payload):
        self.record['packets'] += 1
        self.record['bits'] += 2 if kind == 'correction' else 0
        self.classical.send(ClassicPacket({'kind': kind, **payload},
                            src=self.get_node(), dest=self.peer), self.peer)

    def receive_qubit(self, node, event):
        if self.role != 'bob':
            return False
        if not self.memory.write(event.qubit):
            raise RuntimeError('Bob 메모리 용량 부족')
        self.trace('bob_bell_arrival')
        self.send('ready')
        return True

    def receive_classical(self, node, event):
        message = event.packet.get()
        if self.role == 'alice' and message['kind'] == 'ready':
            data, a = self.memory.read('data'), self.memory.read('a')
            CNOT(data, a)
            H(data)
            z_bit, x_bit = data.measure(), a.measure()
            self.record['branch'] = f'{z_bit}{x_bit}'
            self.trace('bell_measurement')
            self.send('correction', x=x_bit, z=z_bit)
        elif self.role == 'bob' and message['kind'] == 'correction':
            b = self.memory.read('b')  # 대기 시간의 T2 잡음은 read() 시 적용됨.
            if message['x']:
                X(b)
            if message['z']:
                Z(b)
            self.trace('bob_correction')
            # 공유 상태가 이후 바뀌기 전에 완료 시점의 fidelity를 기록함.
            self.record['fidelity'] = overlap([b], self.target)
            self.record['completion'] = self.get_simulator().tc.sec
            self.send('ack')
        elif self.role == 'alice' and message['kind'] == 'ack':
            self.trace('alice_ack')
            self.record['ack'] = self.get_simulator().tc.sec
        return True


def run(shots=120, quantum_delay=0.01, classical_delay=0.01,
        drop_rate=0, fidelity=1, t2=0, seed=42):
    validate(shots, quantum_delay, classical_delay, drop_rate, t2, fidelity)
    set_seed(seed)
    trials = []
    for trial in range(shots):
        label = list(STATES)[trial % len(STATES)]
        target = STATES[label]
        # 마지막 ACK까지 도착할 수 있는 시간. 매 시도는 독립적이며 재시도 안 함.
        timeout = quantum_delay + 3 * classical_delay + 0.00001
        s = Simulator(0, timeout, accuracy=1_000_000)
        alice, bob = QNode('Alice'), QNode('Bob')
        quantum = QuantumChannel('bell-link', bandwidth=0, delay=quantum_delay, drop_rate=drop_rate)
        classical = ClassicChannel('control-link', delay=classical_delay)
        record = {'input': label, 'fidelity': None, 'completion': None, 'ack': None,
                  'packets': 0, 'bits': 0, 'trace': [], 'timeout': timeout}
        for node, peer, role in ((alice, bob, 'alice'), (bob, alice, 'bob')):
            node.add_qchannel(quantum)
            node.add_cchannel(classical)
            memory = QuantumMemory(f'{role}-memory', capacity=2, decoherence_rate=1/t2 if t2 else 0)
            node.add_memory(memory)
            node.add_apps(TeleportApp(role, peer, memory, classical, record, target))
            node.install(s)
        a, b = bell_qubits(fidelity)
        a.name, b.name = 'a', 'b'
        alice.memories[0].write(a)
        alice.memories[0].write(attach_storage_noise(Qubit(state=target.copy(), name='data')))
        quantum.send(b, bob)
        s.run()
        trials.append(record)
    return summarize(trials, seed, dict(quantum_delay=quantum_delay, classical_delay=classical_delay,
                                       drop_rate=drop_rate, fidelity=fidelity, t2=t2))


if __name__ == '__main__':
    parser = computing_parser(__doc__)
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))
