"""15: 실제 로드한 Python/Cython 모듈을 확인하고 이벤트 처리 시간을 측정함."""

import argparse
import importlib
import importlib.machinery
import json
import time
from statistics import median

from _cli import positive_int
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator


def loaded_modules():
    result = {}
    for name in ('qns.simulator.ts', 'qns.simulator.pool', 'qns.simulator.simulator'):
        module = importlib.import_module(name)
        path = str(module.__file__)
        compiled = any(path.endswith(suffix) for suffix in importlib.machinery.EXTENSION_SUFFIXES)
        result[name] = {'path': path, 'compiled_extension': compiled}
    return result


def run(events=10000, repeats=3):
    wall_seconds = []
    for _ in range(repeats):
        # 타이밍에 등록·실행 모두 포함함. 각 반복은 새 simulator를 사용함.
        started = time.perf_counter()
        s = Simulator(0, events / 1_000_000, accuracy=1_000_000)
        state = {'invoked': 0, 'checksum': 0}

        def count(index, state=state):
            state['invoked'] += 1
            state['checksum'] += index

        for index in range(events):
            s.add_event(func_to_event(s.time(time_slot=index), count, index=index))
        s.run()
        wall_seconds.append(time.perf_counter() - started)
        if state != {'invoked': events, 'checksum': events * (events - 1) // 2}:
            raise RuntimeError('이벤트 count/checksum 검증 실패')
    modules = loaded_modules()
    return {'events': events, 'repeats': repeats, **state, 'modules': modules,
            'all_core_modules_compiled': all(m['compiled_extension'] for m in modules.values()),
            'wall_seconds': wall_seconds, 'median_wall_seconds': median(wall_seconds),
            'events_per_wall_second': events / median(wall_seconds)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=positive_int, default=10000)
    parser.add_argument('--repeats', type=positive_int, default=3)
    parser.add_argument('--require-compiled', action='store_true', help='코어 세 모듈이 확장 모듈인지 검사함')
    args = parser.parse_args()
    if args.require_compiled and not all(m['compiled_extension'] for m in loaded_modules().values()):
        parser.error('Cython 코어가 로드되지 않았음. docs/cython-build.md 참조')
    print(json.dumps(run(args.events, args.repeats), indent=2))
