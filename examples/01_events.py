"""01: 이벤트는 등록 순서가 아니라 시뮬레이션 시각 순서대로 실행됨."""

import json

from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator


def run():
    simulator = Simulator(0, 1, accuracy=1_000_000)
    events = []

    def record(label):
        events.append({"time_seconds": simulator.current_time.sec, "name": label})

    # 일부러 역순으로 등록함. sec는 실제 대기 시간이 아니라 가상 시간임.
    for seconds, name in [(0.3, "third"), (0.2, "second"), (0.1, "first")]:
        # name은 이벤트 메타데이터, label은 record 함수에 전달할 인자임.
        simulator.add_event(func_to_event(
            simulator.time(sec=seconds), record, name=name, label=name,
        ))
    canceled = func_to_event(simulator.time(sec=0.15), lambda: record("canceled"))
    canceled.cancel()
    simulator.add_event(canceled)
    simulator.run()
    return {"events": events}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
