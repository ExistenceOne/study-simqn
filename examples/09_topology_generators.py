"""09: 같은 노드 수로 linear/grid/Waxman의 링크·차수·연결성을 비교함."""

import argparse
import json
import math

from _cli import positive_int, seed_value
from qns.network.topology import GridTopology, LineTopology, WaxmanTopology
from qns.utils.rnd import set_seed


def describe(topology):
    nodes, links = topology.build()
    adjacency = {node: set() for node in nodes}
    for link in links:
        a, b = link.node_list
        adjacency[a].add(b)
        adjacency[b].add(a)
    visited, pending = set(), [nodes[0]]
    while pending:
        node = pending.pop()
        if node not in visited:
            visited.add(node)
            pending.extend(adjacency[node] - visited)
    return {'nodes': len(nodes), 'links': len(links), 'connected': len(visited) == len(nodes),
            'degrees': {n.name: len(adjacency[n]) for n in nodes},
            'edges': [{'nodes': [n.name for n in link.node_list], 'length_m': float(link.length)}
                      for link in links]}


def run(nodes=9, seed=42):
    set_seed(seed)
    args = {'nodes_number': nodes, 'memory_args': [], 'qchannel_args': {'bandwidth': 1}}
    # Waxman 연결성 검사에서 bandwidth=0은 연결되지 않은 링크로 취급됨.
    # 이 예제는 생성만 비교하므로 양수 대역폭을 사용함.
    return {'seed': seed, 'linear': describe(LineTopology(**args)),
            'grid': describe(GridTopology(**args)),
            'waxman': describe(WaxmanTopology(size=1000, alpha=0.8, beta=0.5, **args))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nodes', type=positive_int, default=9)
    parser.add_argument('--seed', type=seed_value, default=42)
    args = parser.parse_args()
    if args.nodes < 4 or math.isqrt(args.nodes) ** 2 != args.nodes:
        parser.error('grid 비교를 위해 nodes는 4 이상의 완전제곱수여야 함')
    print(json.dumps(run(**vars(args)), indent=2))
