"""14: Monitor로 가상 시간별 완료 count를 관측하고 CSV로 저장함."""

import argparse
import json
from pathlib import Path

from qns.entity.monitor.monitor import Monitor
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator


def run(output=None):
    s = Simulator(0, 1, accuracy=1_000_000)
    state = {'count': 0}

    def complete():
        state['count'] += 1

    for time in (0.1, 0.4, 0.7):
        s.add_event(func_to_event(s.time(sec=time), complete))
    monitor = Monitor('completion-counter')
    monitor.add_attribution('count', lambda simulator, network, event: state['count'])
    monitor.add_attribution('completed_per_second',
                            lambda simulator, network, event: state['count'] / simulator.tc.sec
                            if simulator.tc.sec > 0 else 0.0)
    monitor.at_start()
    monitor.at_period(0.25)
    # 주기 관측이 이미 1초를 포함하므로 at_finish() 중복 등록은 하지 않음.
    monitor.install(s)
    s.run()
    data = monitor.get_date()  # qns API의 실제 메서드 이름임.
    if output is not None:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(path, index=False, lineterminator='\n')
    return {'duration_seconds': 1, 'period_seconds': 0.25,
            'records': data.to_dict(orient='records'), 'csv_path': str(output) if output else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='CSV 저장 경로. 생략하면 JSON만 출력함')
    args = parser.parse_args()
    if args.output and Path(args.output).exists():
        parser.error('기존 CSV를 덮어쓰지 않음. 새 경로를 지정해야 함')
    print(json.dumps(run(**vars(args)), indent=2))
