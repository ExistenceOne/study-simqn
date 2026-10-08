"""19·20 공통 이벤트 엔진. GHZ/독립 상태 준비 외에는 동일한 센서·채널 사용."""
import argparse
import math

import numpy as np
from _cli import nonnegative_float, positive_int, probability, seed_value
from _distributed import t2_storage_error, validate
from qns.entity.cchannel.cchannel import ClassicChannel, ClassicPacket, RecvClassicPacket
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel, RecvQubitPacket
from qns.models.qubit import CNOT, H, RZ
from qns.models.qubit.factory import QubitFactory
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed


class SensorApp(Application):
    def __init__(self, index, source, memory, classical, phase, bias, rounds, trace):
        super().__init__()
        self.index, self.source, self.memory, self.classical = index, source, memory, classical
        self.phase, self.bias, self.rounds, self.trace = phase, bias, rounds, trace
        self.packets = 0
        self.add_handler(self.receive_qubit, [RecvQubitPacket])
        self.add_handler(self.receive_result, [RecvClassicPacket])

    def note(self, round_id, event):
        if round_id == 0:
            self.trace.append({'node': self.get_node().name, 'event': event,
                               'time_seconds': self.get_simulator().tc.sec})

    def accept(self, qubit):
        if not self.memory.write(qubit):
            raise RuntimeError('센서 메모리 용량 부족')
        self.note(qubit.round_id, 'probe_arrival')
        s = self.get_simulator()
        s.add_event(func_to_event(qubit.measure_at, self.measure, probe_name=qubit.name, round_id=qubit.round_id))

    def receive_qubit(self, node, event):
        self.accept(event.qubit)
        return True

    def measure(self, probe_name, round_id):
        qubit = self.memory.read(probe_name)
        RZ(qubit, self.phase + self.bias)
        bit = qubit.measureX()
        self.note(round_id, 'sensor_measurement')
        if self.index == 0:
            self.rounds[round_id][self.index] = bit
        else:
            self.packets += 1
            self.classical.send(ClassicPacket({'round': round_id, 'sensor': self.index, 'bit': bit},
                                src=self.get_node(), dest=self.source), self.source)

    def receive_result(self, node, event):
        if self.index != 0:
            return False
        payload = event.packet.get()
        self.rounds[payload['round']][payload['sensor']] = payload['bit']
        self.note(payload['round'], 'result_arrival')
        return True


def sensor_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--nodes', type=positive_int, default=3)
    parser.add_argument('--shots', type=positive_int, default=200, help='반복당 준비 시도 수; 성공 횟수가 아님')
    parser.add_argument('--repeats', type=positive_int, default=8)
    parser.add_argument('--phase', type=float, default=0.1, help='모든 센서에 동일한 위상, rad')
    parser.add_argument('--quantum-delay', type=nonnegative_float, default=0.01)
    parser.add_argument('--classical-delay', type=nonnegative_float, default=0.01)
    parser.add_argument('--interrogation', type=nonnegative_float, default=0.005)
    parser.add_argument('--drop-rate', type=probability, default=0)
    parser.add_argument('--t2', type=nonnegative_float, default=0, help='초 단위; 0은 잡음 비활성화')
    parser.add_argument('--seed', type=seed_value, default=42)
    return parser


def check_settings(nodes, shots, repeats, phase, quantum_delay, classical_delay, interrogation, drop_rate, t2):
    validate(shots, quantum_delay, classical_delay, drop_rate, t2)
    if not isinstance(nodes, int) or not 2 <= nodes <= 6:
        raise ValueError('nodes는 2부터 6까지 가능함; 공동 밀도행렬 크기 제한')
    if not isinstance(repeats, int) or repeats < 1:
        raise ValueError('repeats는 1 이상의 정수여야 함')
    if not math.isfinite(phase) or abs(phase) >= math.pi / (2 * nodes):
        raise ValueError('위상은 알려진 국소 범위 abs(phase) < pi/(2*nodes)여야 함')
    if not math.isfinite(interrogation) or interrogation < 0:
        raise ValueError('interrogation은 0 이상의 유한한 숫자여야 함')


def experiment(mode, nodes=3, shots=200, repeats=8, phase=0.1, quantum_delay=0.01,
               classical_delay=0.01, interrogation=0.005, drop_rate=0, t2=0, seed=42):
    check_settings(nodes, shots, repeats, phase, quantum_delay, classical_delay, interrogation, drop_rate, t2)
    if mode not in ('independent', 'ghz'):
        raise ValueError('mode는 independent 또는 ghz여야 함')
    # 보정 모델도 실제 SimQN 슬롯에 맞춤. 각 지연을 따로 양자화한 뒤 합산함.
    clock = Simulator(0, 0, accuracy=1_000_000)
    quantum_duration = clock.time(sec=quantum_delay)
    classical_duration = clock.time(sec=classical_delay)
    interrogation_duration = clock.time(sec=interrogation)
    # source는 준비 때부터 보관, 원격 센서는 도착 후 보관함. 비행 중 탈위상은 제외함.
    storage_times = np.array([(quantum_duration + interrogation_duration).sec]
                             + [interrogation_duration.sec] * (nodes - 1))
    visibilities = np.exp(-storage_times / t2) if t2 else np.ones(nodes)
    survival = np.array([1] + [1 - drop_rate] * (nodes - 1))
    visibility = float(np.prod(visibilities)) if mode == 'ghz' else float(survival @ visibilities / survival.sum())
    multiplier = nodes if mode == 'ghz' else 1
    expected_signal = -visibility * math.sin(multiplier * phase)
    estimates, signals, completed, received, packets = [], [], 0, 0, 0
    trace = []
    completion_duration = quantum_duration + interrogation_duration + classical_duration
    slot_duration = completion_duration + clock.time(time_slot=10)
    slot = slot_duration.sec
    first_completion = completion_duration.sec
    factory = QubitFactory(store_error_model=t2_storage_error)
    for repeat in range(repeats):
        set_seed((seed + repeat) % 2**32)
        s = Simulator(0, shots * slot, accuracy=1_000_000)
        sensors = [QNode(f'Sensor{i}') for i in range(nodes)]
        rounds = [{} for _ in range(shots)]
        apps, quantum_links = [], []
        for index, node in enumerate(sensors):
            quantum = classical = None
            if index:
                quantum = QuantumChannel(f'probe-{index}', bandwidth=0, delay=quantum_delay, drop_rate=drop_rate)
                classical = ClassicChannel(f'result-{index}', delay=classical_delay)
                for endpoint in (sensors[0], node):
                    endpoint.add_qchannel(quantum)
                    endpoint.add_cchannel(classical)
            quantum_links.append(quantum)
            memory = QuantumMemory(f'memory-{index}', capacity=1, decoherence_rate=1/t2 if t2 else 0)
            node.add_memory(memory)
            app = SensorApp(index, sensors[0], memory, classical, phase,
                            math.pi / (2 * multiplier), rounds, trace if repeat == 0 else [])
            node.add_apps(app)
            apps.append(app)
        for node in sensors:
            node.install(s)

        def prepare(round_id):
            probes = [factory(name=f'probe-{round_id}-{i}') for i in range(nodes)]
            if mode == 'ghz':
                H(probes[0])
                for probe in probes[1:]:
                    CNOT(probes[0], probe)
            else:
                for probe in probes:
                    H(probe)
            for index, probe in enumerate(probes):
                probe.round_id = round_id
                # 동시 측정을 위한 공유 시계. 지연은 simulator 슬롯 단위로 양자화됨.
                probe.measure_at = s.tc + quantum_duration + interrogation_duration
                if index == 0:
                    apps[0].accept(probe)
                else:
                    quantum_links[index].send(probe, sensors[index])

        for round_id in range(shots):
            s.add_event(func_to_event(s.time(time_slot=round_id * slot_duration.time_slot), prepare, round_id=round_id))
        s.run()
        complete_rounds = [row for row in rounds if len(row) == nodes]
        completed += len(complete_rounds)
        received += sum(len(row) for row in rounds)
        packets += sum(app.packets for app in apps)
        if mode == 'ghz':
            values = [(-1)**sum(row.values()) for row in complete_rounds]
            raw = float(np.mean(values)) if values else None
            scaled = raw / visibility if raw is not None and visibility > 1e-12 else None
        else:
            values = [1 - 2 * bit for row in rounds for bit in row.values()]
            raw = float(np.mean(values)) if values else None
            # 수신한 센서별 알려진 visibility로 보정해서 부분 손실의 가중치 편향을 피함.
            calibrated = [(1 - 2 * bit) / visibilities[i] for row in rounds for i, bit in row.items()
                          if visibilities[i] > 1e-12]
            scaled = float(np.mean(calibrated)) if calibrated else None
        signals.append(raw)
        estimates.append(float(math.asin(np.clip(-scaled, -1, 1)) / multiplier) if scaled is not None else None)
    errors = [estimate - phase for estimate in estimates if estimate is not None]
    if mode == 'ghz':
        v, angle = visibility, nodes * phase
        numerator = v**2 * math.cos(angle)**2
        # sin(angle)≈1일 때 1 - sin²의 수치 소거를 피함.
        fisher = (1 - drop_rate)**(nodes - 1) * nodes**2 * numerator / ((1 - v**2) + numerator)
    else:
        numerator = visibilities**2 * math.cos(phase)**2
        fisher = float(np.sum(survival * numerator / ((1 - visibilities**2) + numerator)))
    return {
        'mode': mode, 'seed': seed, 'nodes': nodes, 'phase_radians': phase,
        'shots_per_repeat': shots, 'repeats': repeats, 'attempted_rounds': shots * repeats,
        'completed_rounds': completed, 'complete_round_rate': completed / (shots * repeats),
        'sensor_uses': nodes * shots * repeats, 'quantum_transmissions': (nodes - 1) * shots * repeats,
        'received_measurements': received, 'classical_packets_sent': packets,
        'estimates': estimates, 'observed_signals': signals,
        'valid_estimate_repeats': len(errors),
        'estimate_std': float(np.std(errors, ddof=1)) if len(errors) > 1 else None,
        'estimate_mean_standard_error': float(np.std(errors, ddof=1) / np.sqrt(len(errors))) if len(errors) > 1 else None,
        'rmse': float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
        'bias': float(np.mean(errors)) if errors else None,
        'visibility': visibility, 'per_sensor_visibility': visibilities.tolist(), 'expected_signal': expected_signal,
        'expected_fisher_information_per_attempt': fisher,
        'first_complete_round_seconds_if_successful': first_completion,
        'total_simulated_seconds': repeats * shots * slot, 'slot_seconds': slot,
        'first_trial_trace': trace, 'time_resolution_seconds': 0.000001,
        'effective_delays_seconds': dict(quantum=quantum_duration.sec, classical=classical_duration.sec,
                                        interrogation=interrogation_duration.sec),
        'storage_times_seconds': storage_times.tolist(),
        'settings': dict(quantum_delay=quantum_delay, classical_delay=classical_delay,
                         interrogation=interrogation, drop_rate=drop_rate, t2=t2),
        'calibration': 'known T2 and delays; quadrature bias; local arcsin branch',
        'resource_accounting': 'attempted probes include losses; no retries; preparation gates ideal and instantaneous',
    }
