# SimQN 논문 Fig. 3·5 재실행

작은 실행 검증부터 전체 sweep까지 같은 코드로 수행함.
**원본 공개 예제에 기반한 재실행이며, 원본 그림 수치의 완전 일치 재현은 아님.**
누락된 설정을 곡선에 맞춰 추정하지 않고 JSON config와 metadata에 남김.

실제로 실행한 [전체 결과와 그래프](sample-results/README.md)도 저장했음.

## 실행

저장소 루트에서 가상환경 활성화 후 실행함.

```bash
python -m pip install -r requirements-evaluation.txt

# 짧은 확인: Fig. 3(a), 3(b), 5 모두 실행
python -m evaluations.run --config evaluations/configs/smoke.json

# Fig. 3: 당시 공개 예제의 모델, 조건별 10회 반복
python -m evaluations.run --config evaluations/configs/historical.json --figures 3

# Fig. 3: 본문에 적힌 0.2 dB/km 손실 + 명시적인 오류 함수 가정
python -m evaluations.run --config evaluations/configs/paper-stated.json --figures 3

# Fig. 5: 400노드, 10·20·30·40세션, 10–100 Hz
python -m evaluations.run --config evaluations/configs/historical.json --figures 5
```

기본 출력 폴더는 `results/evaluations/<config 이름>-<UTC 실행 시각>`임.
`--output /원하는/빈/폴더`로 바꿀 수 있음. 기존 결과가 있는 폴더에는 덮어쓰지 않음.
진행 상황은 stderr, 최종 출력 경로는 stdout에 출력함.
CSV는 조건별로 저장하므로 중간에 중단돼도 완료된 조건의 데이터를 확인할 수 있음.
metadata의 `status=complete`인 실행만 전체 완료된 결과임.

## 출력 파일

| 파일 | 내용 |
| --- | --- |
| `fig3a_trials.csv`, `fig3b_trials.csv` | 각 조건·seed의 correct/sifted bit 수, 비율, QBER, 링크별 count |
| `fig3a_summary.csv`, `fig3b_summary.csv` | 평균·표본 표준편차·평균의 표준오차(SEM) |
| `fig5_trials.csv` | 전체·세션당 EDR와 평균 완료 수 |
| `fig5_sessions.csv` | 세션별 출발지·목적지·홉 수·완료 수·EDR·평균 충실도 |
| `fig5_summary.csv` | 각 세션 수·송신 rate 조건의 반복 통계 |
| `fig3a.png`, `fig3b.png`, `fig5.png` | 평균과 SEM을 표시한 그래프 |
| `metadata.json` | 실제 config, 가정, 패키지 버전, 플랫폼, 실행 시간, 완료 상태 |

SEM은 표본 표준편차를 반복 수의 제곱근으로 나눈 값임. 95% 신뢰구간이 아님.
반복 1회면 표준편차·SEM은 CSV에서 빈 값으로 저장함. 오류 막대를 그리지 않으며
이를 불확실성 0으로 해석하면 안 됨. QBER를 측정할 sifted bit가 없으면 QBER도 빈 값임.
Fig. 3(a)의 로그 축에서는 완료 0건을 임의의 작은 양수로 치환하지 않음.

## Fig. 3: 무엇을 재실행하는가

본문 설정은 송신 1 kHz, 거리 1–150 km, 조건별 10회 반복임.
3(a)는 직접 링크와 신뢰 중계기 1개, 각각 오류 유무를 비교함.
3(b)는 전체 거리 100 km에서 신뢰 중계기를 0–4개 넣음.
중계가 있으면 거리를 동일한 길이의 인접 링크로 나눔.

현재 `qns==0.2.3`의 BB84는 2025년에 후처리가 추가된 버전이라
논문 시기의 `succ_key_pool`과 지표가 다름. 이 실험은 다음 공개 스냅샷의
BB84 코드를 [vendor/legacy_bb84.py](vendor/legacy_bb84.py)에 보존함.

- [2023-06-14 BB84 소스](https://github.com/QNLab-USTC/SimQN/blob/3902842032db74e14a10ea72360264697a79fe3a/qns/network/protocol/bb84.py)
- [당시 직접 BB84 예제](https://github.com/QNLab-USTC/SimQN/blob/3902842032db74e14a10ea72360264697a79fe3a/examples/simple_bb84.py)
- [당시 신뢰 중계 예제](https://github.com/QNLab-USTC/SimQN/blob/3902842032db74e14a10ea72360264697a79fe3a/examples/trusted_relay_bb84.py)

원본에 qubit factory 선택과 sifted/error count 계측만 추가했음.
현재 qns의 이벤트·채널·큐비트 모델 위에서 실행하므로 2023 환경과 완전히 같지는 않음.
현대 BB84 모듈의 전역 변수나 설치된 라이브러리 코드는 수정하지 않음.

### 지표의 의미

당시 수신기는 기저가 같고 측정 bit까지 같은 경우만 `succ_key_pool`에 넣음.
발신 bit를 고전 메시지로 공개해서 비교하므로 이 값은 **진단용 correct-sifted bit 수**임.
오류 정정·privacy amplification을 거친 안전한 최종 비밀키 수가 아님.

`correct_sifted_bps`는 인접 링크별 correct-sifted bit 수의 최솟값을 실험 시간으로 나눈 값임.
이는 공개 trusted relay 예제의 병목 집계 방식임. 참고문헌 [14]의 종단 간 중계 프로토콜이나
실제 키 운반을 구현한 것은 아니며 추가 중계 계산 지연도 넣지 않았음.
따라서 그림의 y축에도 secret-key rate 대신 correct-sifted bottleneck rate를 표시함.
`sifted_bps`는 bit 일치 여부와 무관한 기저 일치 bit의 병목율임.
`qber`는 모든 링크에서 확인한 sifted bit 중 오류 bit 비율임.

### 손실·잡음의 두 기준

| config | 손실 모델 | 오류 있음 조건 |
| --- | --- | --- |
| `historical.json` | 공개 예제의 `exp(-L_km / 50)` 투과율 | 당시 collective-rotation 오류 모델 |
| `paper-stated.json` | 본문의 `10 ** (-0.2 * L_km / 10)` 투과율 | 가정한 `p_X = min(1, 0.001 * L_km)` 비트 반전 |

두 손실식은 같지 않음. 예를 들어 50 km의 투과율은 각각 약 0.3679와 0.1임.
공개 예제의 주석에는 0.2 dB/km라고 쓰였지만 구현된 수식은 해당 값과 다름.
어느 모델로 실행했는지 CSV와 metadata에 기록함.

논문에는 비트 반전 확률 함수가 없어서 `bit_flip_per_km=0.001`은 **추가 가정**임.
실제 X 오류는 Z 기저 bit를 뒤집지만 X 기저 bit는 뒤집지 않으므로
확률 함수와 측정 QBER를 동일시하면 안 됨.
`historical-rotation`도 본문의 비트 반전 모델과 동일한 잡음이 아님.

전파 속도는 `light_speed_m_s`, 실행 시간은 `duration`으로 조정함.
10초 실행은 당시 공개 예제에서 가져왔고, 각 채널의 대역폭은 무제한으로 명시함.
10 kHz 송신 대신 논문의 1 kHz를 그대로 유지함.

## Fig. 5: 다중 세션 얽힘 분배

논문에서 명시한 조건은 메모리 50, 초기 충실도 0.99,
결맞음 시간 5초, 10·20·30·40세션임. 원본 그림의 송신 rate는 10–100 Hz임.
내장 `EntanglementDistributionApp`, Werner backend, Dijkstra를 사용함.
메모리의 `decoherence_rate=1/5=0.2 s^-1`로 설정함.

정확한 토폴로지 크기·링크 수, 채널 지연, 대역폭, 실험 시간, 반복 수,
세션 중첩 여부와 평균의 분모가 모두 명시되어 있지는 않음.
현재 전체 config는 다음을 **추가 가정**으로 사용함.

| 항목 | 전체 실행 설정 |
| --- | --- |
| 노드·양자 링크 수 | 400·1200 |
| 실험 시간·warmup | 10초·0초 |
| 반복 수 | 3 |
| 양자·고전 채널 지연 | 각각 0.05초 |
| 채널 대역폭·손실 | 무제한·0 |
| 고전 네트워크 | 모든 노드 쌍 직접 연결 |
| 요청 선정 | 출발지·목적지 중복 없는 무작위 쌍 |

400은 본문의 최대 노드 수임. Fig. 5가 정확히 400노드였다고 확정한 것은 아님.
1200링크 등의 가정은 JSON을 복사해 쉽게 바꿀 수 있음.
무제한 대역폭에서도 제한된 메모리와 프로토콜 진행 시간 때문에 혼잡이 발생할 수 있음.

고전 전체 연결은 내장 프로토콜의 목적지→송신자 직접 성공 통지를 지원하기 위함임.
양자 링크는 임의 그래프임. 고전 메시지의 다중 홉 라우팅 실험은 아님.

### 반복과 집계

같은 반복 안에서는 토폴로지와 요청 seed를 유지함.
세션 수가 늘면 앞선 세션의 요청 쌍을 그대로 포함하는 prefix 구조임.
송신 rate가 달라질 때는 노드·메모리·앱·채널을 새로 만들고 라우팅 테이블의
노드 참조를 매핑하므로 직전 실험의 상태가 이어지지 않음.
큰 그래프를 `deepcopy`하지 않아서 400노드의 재귀 한계 오류도 피함.
qns의 무제한 대역폭 연결성 검사 문제는 생성 중에만 양수 대역폭을 사용하고 복원함.

완료는 목적지 기준으로 `[warmup, duration]` 구간에서 셈.
송신자에게 성공 통지가 도착한 수를 대신 사용하지 않음.

- `total_eps`: 전체 세션의 완료 합 / 측정 구간 시간.
- `mean_session_eps`: `total_eps / sessions`. 기본 그래프 지표임.
- `mean_completed_per_session`: 평균 완료 수. rate가 아니므로 단위가 pair임.

원본 Fig. 5는 축에 throughput (bps)를 쓰지만 본문은 얽힘 분배율이라고 설명하며
평균의 분모도 명확하지 않음. 이 코드는 원본 축 숫자를 맞추려고 임의로 10배 하지 않음.
CSV의 서로 다른 count/rate 지표를 사용해 원본과 비교할 수 있음.
완료 수는 충실도 임계값을 검사한 usable entanglement 수와 다름.
세션별 평균 충실도도 함께 확인해야 함.
충실도는 목적지 완료 순간에 숫자로 고정해서 저장함.
완료 후 송신자의 ACK 처리가 공유 Werner 객체를 바꾸어도 이 관측값은 변하지 않음.

## 작은 실행과 전체 실행의 차이

`smoke.json`은 Fig. 3을 1초·2회, Fig. 5를 20노드·2/4세션·2초·2회로 줄임.
빠른 동작 검증용이며 논문의 규모를 재현한 결과라고 해석하면 안 됨.
전체 config는 동일 코드로 긴 거리와 높은 부하까지 실행함.
증가하는 거리의 키율 감소, 중계에 따른 병목율 변화, rate·세션 수에 따른 혼잡을
관찰할 수 있지만 원본 숫자와 같다는 것은 별도 검증이 필요함.

## 코드·검증

| 파일 | 역할 |
| --- | --- |
| `fig3.py` | 손실식·잡음 설정과 선형 BB84 실행 |
| `fig5.py` | 토폴로지·독립 실험 생성, 목적지 완료 계측 |
| `reporting.py` | CSV와 표본 통계 |
| `plotting.py` | headless PNG 그래프 |
| `run.py` | config 검증, sweep, 진행 출력과 metadata |

```bash
python -m unittest discover -s tests -v
```

채널 손실식, noise-free/bit-flip 차이, seed 재현성, 독립 세션 집계,
150노드 회귀 테스트, 알려진 통계값, 잘못된 config와 실제 CLI 출력까지 검증함.
기존 입문 예제의 테스트도 함께 실행함. 보존한 코드는 원본 GPL-3.0-or-later이고
전체 저장소의 [LICENSE](../LICENSE)가 적용됨.
