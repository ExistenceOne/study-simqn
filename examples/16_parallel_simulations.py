"""16: MPSimulations로 독립 잡음 실험을 병렬 실행하고 직렬 결과와 비교함."""

import argparse
import json
import logging
import multiprocessing

from _cli import positive_int, seed_value
from _noise import bit_flip_measure_error
from qns.models.qubit.factory import QubitFactory
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.utils.log import logger
from qns.utils.multiprocess import MPSimulations
from qns.utils.rnd import set_seed

# worker도 이 모듈을 import함. 라이브러리의 stdout 로그와 JSON을 분리함.
logger.setLevel(logging.WARNING)


class NoiseSweep(MPSimulations):
    def run(self, setting):
        # worker별로 seed를 다시 설정함. 실행 순서나 PID에 의존하지 않음.
        seed = (setting['seed'] + setting['_id']) % 2**32
        set_seed(seed)
        factory = QubitFactory(measure_decoherence_rate=setting['flip_probability'],
                               measure_error_model=bit_flip_measure_error)
        s = Simulator(0, setting['shots'] / 1_000_000, accuracy=1_000_000)
        observed = {'ones': 0}

        def measure():
            observed['ones'] += factory().measure()

        for shot in range(setting['shots']):
            s.add_event(func_to_event(s.time(time_slot=shot), measure))
        s.run()
        return {'experiment_seed': seed, 'ones': observed['ones'],
                'observed_flip_fraction': observed['ones'] / setting['shots']}


def run(shots=1000, repeats=3, cores=2, seed=42):
    sweep = NoiseSweep(settings={'flip_probability': [0.0, 0.2, 1.0], 'shots': [shots], 'seed': [seed]},
                       iter_count=repeats, aggregate=True, cores=cores)
    sweep.start()
    raw = sweep.get_raw_data().sort_values('_id')
    expected_count = 3 * repeats
    # 라이브러리는 worker 예외를 출력하고 누락할 수 있어 count를 명시적으로 검증함.
    if len(raw) != expected_count:
        raise RuntimeError(f'worker 결과 누락: expected={expected_count}, actual={len(raw)}')
    serial = NoiseSweep(settings=sweep.settings, iter_count=repeats, aggregate=False, cores=1)
    serial.prepare_setting()
    expected = [{**setting, **serial.run(setting)} for setting in serial._setting_list]
    records = raw.to_dict(orient='records')
    matches = records == expected
    if not matches:
        raise RuntimeError('직렬·병렬 결과 불일치')
    return {'cores': cores, 'start_method': multiprocessing.get_start_method(),
            'serial_matches_parallel': matches, 'raw': records,
            'summary': sweep.get_data().reset_index().to_dict(orient='records')}


if __name__ == '__main__':
    # Windows/macOS spawn에서도 앱 정의를 import만 하고 실행은 main 안에서 함.
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shots', type=positive_int, default=1000)
    parser.add_argument('--repeats', type=positive_int, default=3)
    parser.add_argument('--cores', type=positive_int, default=2)
    parser.add_argument('--seed', type=seed_value, default=42)
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error('표본 표준편차 집계를 위해 repeats >= 2 필요함')
    print(json.dumps(run(**vars(args)), indent=2))
