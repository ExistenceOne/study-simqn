"""03: 실제 QuantumChannel로 큐비트를 보내 손실률별 수신 건수를 비교함."""

import argparse
import json

from _cli import nonnegative_float, positive_int, probability, seed_value
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel, RecvQubitPacket
from qns.models.qubit import Qubit
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed


class Receiver(Application):
    def __init__(self):
        super().__init__()
        self.arrivals = []
        self.add_handler(self.receive, [RecvQubitPacket])

    def receive(self, node, event):
        self.arrivals.append(event.t.sec)
        return True


def run(count=1000, delay=0.01, drop_rates=(0, 0.3, 0.7, 1), seed=42):
    experiments = []
    for drop_rate in drop_rates:
        set_seed(seed)
        interval = 0.001  # 큐비트를 1 ms마다 생성함.
        # 마지막 송신 + 지연보다 늦게 종료하여 진행 중인 큐비트를 손실로 세지 않음.
        simulator = Simulator(0, count * interval + delay + interval, accuracy=1_000_000)
        alice, bob = QNode("Alice"), QNode("Bob")
        channel = QuantumChannel("link", delay=delay, drop_rate=drop_rate, bandwidth=0)
        # bandwidth=0은 무제한임. 이 예제에서는 큐 대기/버퍼 손실을 제외함.
        alice.add_qchannel(channel)
        bob.add_qchannel(channel)
        receiver = Receiver()
        bob.add_apps(receiver)
        alice.install(simulator)
        bob.install(simulator)

        def send(link=channel, destination=bob):
            link.send(Qubit(), destination)

        for index in range(count):
            simulator.add_event(func_to_event(simulator.time(sec=index * interval), send))
        simulator.run()
        received = len(receiver.arrivals)
        experiments.append({
            "drop_rate": drop_rate, "sent": count, "received": received,
            "lost": count - received, "observed_loss_rate": (count - received) / count,
            "first_arrival_seconds": receiver.arrivals[0] if received else None,
            "last_arrival_seconds": receiver.arrivals[-1] if received else None,
        })
    return {"seed": seed, "delay_seconds": delay, "experiments": experiments}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=positive_int, default=1000, help="송신 큐비트 수")
    parser.add_argument("--delay", type=nonnegative_float, default=0.01, help="채널 지연, 초")
    parser.add_argument("--drop-rates", nargs="+", type=probability, default=[0, 0.3, 0.7, 1])
    parser.add_argument("--seed", type=seed_value, default=42)
    args = parser.parse_args()
    print(json.dumps(run(args.count, args.delay, args.drop_rates, args.seed), indent=2))
