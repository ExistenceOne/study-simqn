"""12: 내장 BB84 송수신 앱을 두 노드에 설치하고 후처리 key pool을 비교함."""

import argparse
import json

from _cli import positive_float, seed_value
from qns.entity.cchannel.cchannel import ClassicChannel
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel
from qns.network.protocol.bb84 import BB84RecvApp, BB84SendApp
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed


def run(duration=5, seed=42):
    set_seed(seed)
    s = Simulator(0, duration, accuracy=1_000_000)
    alice, bob = QNode('Alice'), QNode('Bob')
    quantum = QuantumChannel('quantum', delay=0.001, bandwidth=0, drop_rate=0)
    classical = ClassicChannel('classical', delay=0.001, bandwidth=0)
    for node in (alice, bob):
        node.add_qchannel(quantum)
        node.add_cchannel(classical)
    # 설치된 qns 0.2.3 그대로 사용함. evaluation의 역사적 BB84와 다른 코드임.
    sender = BB84SendApp(dest=bob, qchannel=quantum, cchannel=classical, send_rate=1000)
    receiver = BB84RecvApp(src=alice, qchannel=quantum, cchannel=classical)
    alice.add_apps(sender)
    bob.add_apps(receiver)
    alice.install(s)
    bob.install(s)
    s.run()
    common = sorted(sender.key_pool.keys() & receiver.key_pool.keys())
    equal = all(sender.key_pool[k] == receiver.key_pool[k] for k in common)
    return {'seed': seed, 'duration_seconds': duration, 'send_rate_hz': 1000,
            'sender_app': type(sender).__name__, 'receiver_app': type(receiver).__name__,
            'sender_key_blocks': len(sender.key_pool), 'receiver_key_blocks': len(receiver.key_pool),
            'common_key_blocks': len(common), 'common_blocks_equal': equal if common else None,
            'matched_key_bits': sum(len(sender.key_pool[k]) for k in common
                                    if sender.key_pool[k] == receiver.key_pool[k]),
            'sender_remaining_raw_bits': len(sender.raw_key_pool),
            'receiver_remaining_raw_bits': len(receiver.raw_key_pool)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=positive_float, default=5)
    parser.add_argument('--seed', type=seed_value, default=42)
    args = parser.parse_args()
    if args.duration < 1e-6:
        parser.error('duration은 1 us 이상의 값이어야 함')
    print(json.dumps(run(**vars(args)), indent=2))
