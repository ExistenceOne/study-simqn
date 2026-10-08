"""분산 예제 공통 상태·T2 잡음·CLI 도구. 프로토콜은 각 예제에 있음."""
import argparse
import contextlib
import io
import math
from types import MethodType

import numpy as np
from _cli import nonnegative_float, positive_int, probability, seed_value
from qns.models.epr.werner import WernerStateEntanglement
from qns.models.qubit.const import OPERATOR_PAULI_I, OPERATOR_PAULI_Z

STATES = {
    '0': np.array([[1], [0]], dtype=complex),
    '1': np.array([[0], [1]], dtype=complex),
    '+': np.array([[1], [1]], dtype=complex) / np.sqrt(2),
    '-': np.array([[1], [-1]], dtype=complex) / np.sqrt(2),
    '+i': np.array([[1], [1j]], dtype=complex) / np.sqrt(2),
    '-i': np.array([[1], [-1j]], dtype=complex) / np.sqrt(2),
}


def t2_storage_error(self, t=0, decoherence_rate=0, **kwargs):
    # decoherence_rate = 1/T2; t가 커져도 p는 1/2를 넘지 않음.
    p = -math.expm1(-decoherence_rate * t) / 2
    self.stochastic_operate([OPERATOR_PAULI_I, OPERATOR_PAULI_Z], [1 - p, p])


def attach_storage_noise(qubit):
    qubit.store_error_model = MethodType(t2_storage_error, qubit)
    return qubit


def bell_qubits(fidelity):
    with contextlib.redirect_stdout(io.StringIO()):
        pair = WernerStateEntanglement(fidelity).to_qubits()
    return [attach_storage_noise(q) for q in pair]


def ordered_rho(qubits):
    state = qubits[0].state
    if any(q.state is not state for q in qubits) or len(state.qubits) != len(qubits):
        raise ValueError('관측할 큐비트만 남은 공동 상태가 필요함')
    order = [state.qubits.index(q) for q in qubits]
    n = len(qubits)
    return state.rho.reshape([2] * (2 * n)).transpose(order + [n + i for i in order]).reshape(2**n, 2**n)


def overlap(qubits, target):
    value = (target.conj().T @ ordered_rho(qubits) @ target).item().real
    return float(np.clip(value, 0, 1))


def validate(shots, quantum_delay, classical_delay, drop_rate, t2, fidelity=1):
    if not isinstance(shots, int) or shots < 1:
        raise ValueError('shots는 1 이상의 정수여야 함')
    for name, x in [('quantum_delay', quantum_delay), ('classical_delay', classical_delay), ('t2', t2)]:
        if not math.isfinite(x) or x < 0:
            raise ValueError(f'{name}은 0 이상의 유한한 숫자여야 함')
    if not 0 <= drop_rate <= 1 or not 0 <= fidelity <= 1:
        raise ValueError('drop_rate와 fidelity는 0부터 1까지여야 함')


def computing_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--shots', type=positive_int, default=120)
    parser.add_argument('--quantum-delay', type=nonnegative_float, default=0.01)
    parser.add_argument('--classical-delay', type=nonnegative_float, default=0.01)
    parser.add_argument('--drop-rate', type=probability, default=0)
    parser.add_argument('--fidelity', type=probability, default=1)
    parser.add_argument('--t2', type=nonnegative_float, default=0, help='초 단위; 0은 메모리 잡음 비활성화')
    parser.add_argument('--seed', type=seed_value, default=42)
    return parser


def summarize(trials, seed, settings):
    successful = [r for r in trials if r['fidelity'] is not None]
    by_input = {}
    branches = {}
    for row in trials:
        group = by_input.setdefault(row['input'], {'attempted': 0, 'completed': 0, 'fidelities': []})
        group['attempted'] += 1
        if row['fidelity'] is not None:
            group['completed'] += 1
            group['fidelities'].append(row['fidelity'])
            key = row['branch']
            branches[key] = branches.get(key, 0) + 1
    for group in by_input.values():
        values = group.pop('fidelities')
        group['mean_fidelity'] = float(np.mean(values)) if values else None
    return {
        'seed': seed, 'settings': settings, 'attempted': len(trials),
        'completed': len(successful), 'failed': len(trials) - len(successful),
        'success_rate': len(successful) / len(trials),
        'bell_pairs_created': len(trials), 'quantum_transmissions': len(trials),
        'classical_packets_sent': sum(r['packets'] for r in trials),
        'classical_payload_bits': sum(r['bits'] for r in trials),
        'mean_fidelity': float(np.mean([r['fidelity'] for r in successful])) if successful else None,
        'minimum_fidelity': min((r['fidelity'] for r in successful), default=None),
        'mean_completion_seconds': float(np.mean([r['completion'] for r in successful])) if successful else None,
        'mean_ack_seconds': float(np.mean([r['ack'] for r in successful if r.get('ack') is not None]))
        if any(r.get('ack') is not None for r in successful) else None,
        'measurement_branches': branches, 'by_input': by_input,
        'first_trial_trace': trials[0]['trace'],
        'timeout_seconds': trials[0]['timeout'],
        'gate_model': 'instantaneous ideal local gates',
    }
