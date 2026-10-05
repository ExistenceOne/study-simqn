"""13: 수동 요청과 endpoint 중복 허용/금지 무작위 요청을 비교함."""

import argparse
import json

from _cli import positive_int, seed_value
from qns.network import QuantumNetwork
from qns.network.topology import LineTopology
from qns.utils.rnd import set_seed


def snapshot(net):
    return [{'src': r.src.name, 'dest': r.dest.name, 'attr': r.attr.copy()} for r in net.requests]


def run(nodes=8, requests=3, seed=42):
    set_seed(seed)
    net = QuantumNetwork(topo=LineTopology(nodes, memory_args=[]))
    net.add_request(net.nodes[0], net.nodes[-1], attr={'send_rate': 5, 'kind': 'manual'})
    manual = snapshot(net)
    # random_requests()는 기존 network/node 요청 목록을 지우고 생성함.
    net.random_requests(requests, allow_overlay=False, attr={'send_rate': 10, 'kind': 'unique'})
    unique = snapshot(net)
    manual_replaced = all(r.attr['kind'] != 'manual' for n in net.nodes for r in n.requests)
    registrations = {n.name: len(n.requests) for n in net.nodes}
    # 노드 수보다 많은 endpoint를 선택하여 중복이 실제 발생하게 함.
    overlay_count = nodes
    net.random_requests(overlay_count, allow_overlay=True, attr={'send_rate': 10, 'kind': 'overlay'})
    overlay = snapshot(net)
    endpoints = [r[k] for r in overlay for k in ('src', 'dest')]
    return {'seed': seed, 'nodes': nodes, 'manual': manual, 'manual_replaced': manual_replaced,
            'unique_random': unique, 'unique_node_request_counts': registrations,
            'overlay_random': overlay, 'overlay_endpoint_reuses': len(endpoints) - len(set(endpoints))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nodes', type=positive_int, default=8)
    parser.add_argument('--requests', type=positive_int, default=3)
    parser.add_argument('--seed', type=seed_value, default=42)
    args = parser.parse_args()
    if args.nodes < 2 or args.requests * 2 > args.nodes:
        parser.error('nodes >= 2와 requests * 2 <= nodes 필요함')
    print(json.dumps(run(**vars(args)), indent=2))
