"""18: 두 노드가 공유 Bell 쌍과 양방향 고전 비트로 원격 CNOT을 실행함."""
import json

import numpy as np
from _distributed import (STATES, attach_storage_noise, bell_qubits, computing_parser,
                          overlap, summarize, validate)
from qns.entity.cchannel.cchannel import ClassicChannel, ClassicPacket, RecvClassicPacket
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel, RecvQubitPacket
from qns.models.qubit import CNOT, H, Qubit, X, Z
from qns.models.qubit.const import OPERATOR_CNOT
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed


class RemoteCNOTApp(Application):
    def __init__(self, role, peer, memory, classical, record, classical_delay):
        super().__init__()
        self.role, self.peer, self.memory = role, peer, memory
        self.classical, self.record, self.classical_delay = classical, record, classical_delay
        self.output = None
        self.add_handler(self.receive_qubit, [RecvQubitPacket])
        self.add_handler(self.receive_classical, [RecvClassicPacket])

    def trace(self, event):
        self.record['trace'].append({'node': self.get_node().name, 'event': event,
                                     'time_seconds': self.get_simulator().tc.sec})

    def send(self, kind, **payload):
        self.record['packets'] += 1
        self.record['bits'] += int('bit' in payload)
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

    def release_target(self):
        # Alice가 phase 비트를 받는 시각까지 Bob의 target도 메모리에 대기함.
        self.output = self.memory.read('target')
        self.trace('bob_target_released')

    def receive_classical(self, node, event):
        message = event.packet.get()
        if self.role == 'alice' and message['kind'] == 'ready':
            control, a = self.memory.read('control'), self.memory.read('a')
            CNOT(control, a)
            bit = a.measure()
            self.memory.write(control)
            self.record['control_bit'] = bit
            self.trace('alice_control_measurement')
            self.send('control', bit=bit)
        elif self.role == 'bob' and message['kind'] == 'control':
            b, target = self.memory.read('b'), self.memory.read('target')
            if message['bit']:
                X(b)
            CNOT(b, target)
            H(b)
            bit = b.measure()
            self.memory.write(target)
            self.record['phase_bit'] = bit
            self.trace('bob_local_cnot')
            self.send('phase', bit=bit)
            s = self.get_simulator()
            s.add_event(func_to_event(s.tc + s.time(sec=self.classical_delay), self.release_target))
        elif self.role == 'alice' and message['kind'] == 'phase':
            self.output = self.memory.read('control')
            if message['bit']:
                Z(self.output)
            self.trace('alice_phase_correction')
            self.record['completion'] = self.get_simulator().tc.sec
        return True


def run(shots=120, quantum_delay=0.01, classical_delay=0.01,
        drop_rate=0, fidelity=1, t2=0, seed=42):
    validate(shots, quantum_delay, classical_delay, drop_rate, t2, fidelity)
    set_seed(seed)
    trials = []
    inputs = [(a, b) for a in ('0', '1', '+', '+i') for b in ('0', '1', '+', '+i')]
    for trial in range(shots):
        c_label, t_label = inputs[trial % len(inputs)]
        reference = OPERATOR_CNOT @ np.kron(STATES[c_label], STATES[t_label])
        timeout = quantum_delay + 3 * classical_delay + 0.00001
        s = Simulator(0, timeout, accuracy=1_000_000)
        alice, bob = QNode('Alice'), QNode('Bob')
        quantum = QuantumChannel('bell-link', bandwidth=0, delay=quantum_delay, drop_rate=drop_rate)
        classical = ClassicChannel('control-link', delay=classical_delay)
        record = {'input': f'{c_label},{t_label}', 'fidelity': None, 'completion': None,
                  'packets': 0, 'bits': 0, 'trace': [], 'timeout': timeout}
        apps = []
        for node, peer, role in ((alice, bob, 'alice'), (bob, alice, 'bob')):
            node.add_qchannel(quantum)
            node.add_cchannel(classical)
            memory = QuantumMemory(f'{role}-memory', capacity=2, decoherence_rate=1/t2 if t2 else 0)
            node.add_memory(memory)
            app = RemoteCNOTApp(role, peer, memory, classical, record, classical_delay)
            apps.append(app)
            node.add_apps(app)
            node.install(s)
        a, b = bell_qubits(fidelity)
        a.name, b.name = 'a', 'b'
        alice.memories[0].write(a)
        alice.memories[0].write(attach_storage_noise(Qubit(state=STATES[c_label].copy(), name='control')))
        bob.memories[0].write(attach_storage_noise(Qubit(state=STATES[t_label].copy(), name='target')))
        quantum.send(b, bob)
        s.run()
        if all(app.output is not None for app in apps):
            # observer만 전체 상태를 읽음. 프로토콜 앱은 상대 노드 큐비트를 조작하지 않음.
            record['fidelity'] = overlap([app.output for app in apps], reference)
            record['branch'] = f"{record['control_bit']}{record['phase_bit']}"
        trials.append(record)
    return summarize(trials, seed, dict(quantum_delay=quantum_delay, classical_delay=classical_delay,
                                       drop_rate=drop_rate, fidelity=fidelity, t2=t2))


if __name__ == '__main__':
    parser = computing_parser(__doc__)
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))
