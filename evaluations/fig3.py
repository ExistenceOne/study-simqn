"""Fig. 3: 공개 예제 방식의 correct-sifted bit 병목율 측정."""

import math
from functools import partial

from qns.models.qubit import Qubit, X
from qns.network import QuantumNetwork
from qns.network.topology import LineTopology
from qns.network.topology.topo import ClassicTopology
from qns.simulator.simulator import Simulator
from qns.utils.rnd import get_rand, set_seed

from evaluations.vendor.legacy_bb84 import BB84RecvApp, BB84SendApp, QubitWithError


def transmission(length_km, loss_model, attenuation_db_km):
    if loss_model == "paper-db":
        return 10 ** (-attenuation_db_km * length_km / 10)
    if loss_model == "historical-exp":
        return math.exp(-length_km / 50)
    raise ValueError(f"Unknown loss model: {loss_model}")


class ExperimentQubit(Qubit):
    def __init__(self, state, noise, bit_flip_per_km):
        super().__init__(state=state)
        self.noise = noise
        self.bit_flip_per_km = bit_flip_per_km

    def transfer_error_model(self, length, decoherence_rate=0, **kwargs):
        if self.noise == "historical-rotation":
            QubitWithError.transfer_error_model(
                self, length, decoherence_rate, **kwargs
            )
        elif self.noise == "bit-flip":
            # 가정: p_X = min(1, alpha * L_km). 논문에 없는 함수는 명시 설정함.
            if get_rand() < min(1, self.bit_flip_per_km * length / 1000):
                X(self)
        elif self.noise != "none":
            raise ValueError(f"Unknown noise model: {self.noise}")


def simulate(total_length_km, relays, noise, settings, seed):
    set_seed(seed)
    duration = settings["duration"]
    hop_length = total_length_km / (relays + 1)
    length_m = hop_length * 1000
    delay = length_m / settings["light_speed_m_s"]
    simulator = Simulator(0, duration, accuracy=10_000_000_000)
    topology = LineTopology(
        relays + 2,
        qchannel_args={
            "length": length_m,
            "delay": delay,
            "bandwidth": 0,
            "drop_rate": 1
            - transmission(
                hop_length, settings["loss_model"], settings["attenuation_db_km"]
            ),
        },
        cchannel_args={"delay": delay, "bandwidth": 0},
    )
    network = QuantumNetwork(topo=topology, classic_topo=ClassicTopology.Follow)
    receivers = []
    for channel, classical in zip(network.qchannels, network.cchannels):
        source, destination = channel.node_list
        sender = BB84SendApp(
            destination,
            channel,
            classical,
            settings["send_rate"],
            qubit_factory=partial(
                ExperimentQubit,
                noise=noise,
                bit_flip_per_km=settings["bit_flip_per_km"],
            ),
        )
        receiver = BB84RecvApp(source, channel, classical)
        source.add_apps(sender)
        destination.add_apps(receiver)
        receivers.append(receiver)
    network.install(simulator)
    simulator.run()
    correct = [len(receiver.succ_key_pool) for receiver in receivers]
    sifted = [receiver.sifted_count for receiver in receivers]
    errors = sum(receiver.error_count for receiver in receivers)
    return {
        "total_length_km": total_length_km,
        "relays": relays,
        "noise": noise,
        "seed": seed,
        "duration_seconds": duration,
        "hop_length_km": hop_length,
        "loss_model": settings["loss_model"],
        "correct_bits": min(correct),
        "sifted_bits": min(sifted),
        "correct_sifted_bps": min(correct) / duration,
        "sifted_bps": min(sifted) / duration,
        "qber": errors / sum(sifted) if sum(sifted) else None,
        "link_correct_bits": correct,
        "link_sifted_bits": sifted,
    }
