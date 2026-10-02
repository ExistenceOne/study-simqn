# SimQN 입문 예제 설계

## 목표

SimQN을 처음 접하는 사람이 작은 Python 스크립트를 실행하고 파라미터를
바꾸며 이벤트, 큐비트, 채널, 라우팅, 얽힘 분배를 순서대로 이해함.
결과물은 `ExistenceOne/study-simqn`에 게시함.

## 구성

- `examples/01_events.py`: 시간순 이벤트 실행과 취소.
- `examples/02_qubits.py`: X/H 게이트, Z 측정, Bell 쌍의 측정 상관관계.
- `examples/03_channel_loss.py`: 두 노드의 실제 QuantumChannel 송수신과 손실률 비교.
- `examples/04_routing.py`: 같은 그래프의 최소 홉 경로와 최소 지연 경로 비교.
- `examples/05_entanglement_distribution.py`: 작은 LineTopology에서 내장 프로토콜 실행.
- `examples/_cli.py`: 숫자 인자 검증만 공유함.
- `README.md`: 설치, 실행, 결과 해석, 추가 실험, 모델의 가정 설명.
- `tests/test_examples.py`: 실제 CLI를 실행해 물리적 결과와 입력 오류 검증.

## 실행·검증 기준

Python 3.11 이상과 PyPI `qns==0.2.3` 사용. NumPy/Pandas 버전도 고정함.
각 스크립트는 독립 실행 가능하며 JSON으로 결과 출력함.
확률 실험은 기본 seed 42 사용. 수치는 샘플링 오차가 있음을 설명함.
채널 손실 실험은 모든 수신 이벤트가 끝나도록 시뮬레이션 종료 시각 설정함.
얽힘 성공 0건이면 평균 충실도는 null, 성공 건수는 목적지 기준으로 집계함.
시간 종료 시 진행 중인 요청은 실패와 구분해 설명함.
외부 장치, API, 인증 없이 로컬 실행 가능해야 함.
