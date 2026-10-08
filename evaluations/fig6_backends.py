"""Matched local depolarization and destructive Bell swapping for Fig. 6.

Each half's Bloch vector contracts by exp(-rate * elapsed). This explicitly
chosen model is not the same as qns's built-in DepolarStorageErrorModel.
"""

from dataclasses import dataclass

import numpy as np
from qns.models.epr.werner import WernerStateEntanglement
from qns.models.qubit import CNOT, H, I, Qubit, X, Y, Z
from qns.models.qubit.qubit import QState
from qns.utils.rnd import set_seed

PHI = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)


@dataclass
class Pair:
    state: object
    last: list[float]


class Backend:
    def __init__(self, name, settings, seed):
        self.name = name
        self.settings = settings
        self.rng = np.random.default_rng(seed)
        self.max_state_qubits = 2
        if name == "netsquid":
            import netsquid as ns
            from netsquid.qubits import qubitapi

            self.ns, self.api = ns, qubitapi
            ns.set_qstate_formalism(ns.QFormalism.DM)
            ns.set_random_state(seed=seed)
        else:
            set_seed(seed)

    def create_link(self, now, transit_seconds=0):
        f = self.settings["initial_fidelity"]
        w = (4 * f - 1) / 3
        if self.name == "werner":
            state = WernerStateEntanglement(fidelity=f)
        else:
            rho = w * np.outer(PHI, PHI.conj()) + (1 - w) * np.eye(4) / 4
            if self.name == "qubit":
                a, b = Qubit(), Qubit()
                joint = QState([a, b], rho=rho)
                a.state = b.state = joint
            else:
                a, b = self.api.create_qubits(2)
                self.api.assign_qstate([a, b], rho)
            state = (a, b)
        right_start = (
            now if self.settings["noise_during_transit"] else now + transit_seconds
        )
        return Pair(state, [now, right_start])

    def apply_noise(self, pair, now):
        elapsed = [max(0, now - t) for t in pair.last]
        rate = self.settings["depolar_rate"]
        if self.name == "werner":
            pair.state.w *= np.exp(-rate * sum(elapsed))
        else:
            for qubit, t in zip(pair.state, elapsed):
                contraction = np.exp(-rate * t)
                if self.name == "qubit":
                    p = (1 - contraction) / 4
                    qubit.stochastic_operate([I, X, Y, Z], [1 - 3 * p, p, p, p])
                else:
                    # NetSquid's prob mixes the entire single-qubit state with I/2.
                    self.api.depolarize(qubit, prob=1 - contraction)
        pair.last = [max(t, now) for t in pair.last]

    def swap(self, left, right, now):
        self.apply_noise(left, now)
        self.apply_noise(right, now)
        if self.name == "werner":
            state = left.state.swapping(right.state)
            x, z = map(int, self.rng.integers(0, 2, size=2))
        else:
            a, middle_left = left.state
            middle_right, b = right.state
            if self.name == "qubit":
                CNOT(middle_left, middle_right)
                self.max_state_qubits = max(
                    self.max_state_qubits, middle_left.state.num
                )
                H(middle_left)
                z, x = middle_left.measure(), middle_right.measure()
            else:
                from netsquid.qubits.operators import CNOT as NCNOT
                from netsquid.qubits.operators import H as NH

                self.api.operate([middle_left, middle_right], NCNOT)
                self.max_state_qubits = max(
                    self.max_state_qubits, middle_left.qstate.num_qubits
                )
                self.api.operate(middle_left, NH)
                z = self.api.measure(middle_left, discard=True)[0]
                x = self.api.measure(middle_right, discard=True)[0]
            state = (a, b)
        return Pair(state, [now, now]), int(x), int(z)

    def correct(self, pair, x, z):
        if self.name == "qubit":
            if x:
                X(pair.state[1])
            if z:
                Z(pair.state[1])
        elif self.name == "netsquid":
            from netsquid.qubits.operators import X as NX
            from netsquid.qubits.operators import Z as NZ

            if x:
                self.api.operate(pair.state[1], NX)
            if z:
                self.api.operate(pair.state[1], NZ)
        # Werner represents the state in the corrected Pauli frame.

    def fidelity(self, pair):
        if self.name == "werner":
            return float(pair.state.fidelity)
        if self.name == "qubit":
            a, b = pair.state
            rho = a.state.rho
            if a.state.qubits != [a, b]:
                rho = rho.reshape(2, 2, 2, 2).transpose(1, 0, 3, 2).reshape(4, 4)
            return float(np.real(PHI.conj() @ rho @ PHI))
        from netsquid.qubits.ketstates import b00

        return float(self.api.fidelity(list(pair.state), b00, squared=True))


def make_backend(name, settings, seed):
    if name not in ("qubit", "werner", "netsquid"):
        raise ValueError(f"Unknown backend: {name}")
    return Backend(name, settings, seed)
