# Fig. 6 Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 같은 선형 얽힘 분배 workload에서 SimQN 큐비트/Werner 백엔드와 1/4-worker 실행 비용을 측정하고 Fig. 6 형태의 그래프·원시 결과를 생성함.

**Architecture:** 동일 이벤트 스케줄과 프로토콜을 공유하고 물리 연산만 backend adapter로 분리함. 별도 `evaluations.run_fig6` CLI로 기존 Fig. 3·5 config와 결과의 호환성을 유지함. 성능 측정에 앞서 두 backend의 완료 수·충실도 동등성을 검증함.

**Tech Stack:** 기존 Python 3.11/3.12, qns 0.2.3, NumPy, pandas, Matplotlib; 표준 multiprocessing/process timing. 새 필수 의존성 없음.

**Spec:** 이 문서의 실험 명세; 원본 `docs/SimQN_A_Network-Layer_Simulator_for_the_Quantum_Network_Investigation.pdf` PDF 7쪽, Fig. 6 및 Performance Analysis. 기존 참고: `evaluations/README.md`, `docs/cython-build.md`.

## 실험 명세와 범위

최초 요청은 Fig. 6 구현 계획 작성이었음. 이후 NetSquid 사용 가능 여부를 확인하고
사용자의 구현 지시에 따라 아래 명세를 구현·검증했음. 원래 계획의 2차 NetSquid 범위는
아래 구현 결정에 따라 1차에 포함했음.

| 항목 | 원문 근거 / 계획값 |
| --- | --- |
| x축 | 그림의 5, 10, 15, …, 50노드; 0은 축 원점으로 보고 실행 조건에서 제외 |
| 본문 토폴로지 | 10노드 선형; 전체 sweep과 별도로 10노드 검증 조건을 유지 |
| 인접 링크 거리·전파 속도 | 10 km, 200,000 km/s → 링크당 50 μs |
| 링크 생성 | 모든 인접 링크에서 1,000 Hz |
| 분배 프로토콜 | 중계기 Bell 측정, 결과를 목적지로 보내 종단 간 쌍 완성 |
| 큐비트 잡음 | 본문의 depolarizing rate 200 Hz; 구체적인 확률식은 미명시 |
| 비교 | Qubit/Werner × 1/4 worker; NetSquid는 별도 2차 |
| 실행 시간·반복 | 추가 가정: simulated duration 1초, 반복 8회, unmeasured warmup 1회/backend/node |
| 초기 상태 | 추가 가정: fidelity 1인 Bell 쌍 |
| 채널·메모리 | 추가 가정: 손실 0, 무제한 대역폭, 라운드별 독립 메모리; 정제·재시도 없음 |
| 고전 통지 | 추가 가정: 선형 경로의 홉 수 × 50 μs, 손실·추가 처리 지연 0 |
| 생성 위치 | 추가 가정: 링크 왼쪽에서 쌍 생성, 오른쪽 절반을 50 μs 지연으로 전달 |

본문의 CPU 정보 Intel i5-9400/32 GB는 바로 앞 대규모 실험 설명에 있음.
Fig. 6에서도 같은 장비를 썼는지 확정하지 않으며 실제 장비를 기록함.
원문의 11.1%, 2.68배, 3.07배, 2.60배, 8.02배를 목표값·합격 기준으로 쓰지 않음.

### 권장 접근과 대안

1. **권장: 동일 스케줄 + backend adapter.** 직접 프로토콜 구현이 필요하지만 이벤트량·완료 수·물리 모델을 대조할 수 있음.
2. 기존 Fig. 5 `EntanglementDistributionApp`을 재사용하면 빠르지만 순차 분배 동작이 Fig. 6의 링크별 동시 생성·측정과 달라 기본 benchmark로 부적합함.
3. 오래된 benchmark 전체 소스를 복원하면 당시 환경에 가까워질 수 있지만 현재 qns/API와 의존성 차이가 큼. 정확한 공개 소스를 확보한 경우 별도 historical preset으로 추가함.

### 동일 프로토콜

라운드 `r`의 생성 시각은 `r / 1000`, 처음은 0초이며 duration 미만까지만 생성함.
각 라운드의 링크 쌍은 독립적이고 인접 링크 쌍을 모두 준비한 뒤 각 중계기의 두 로컬 큐비트에 Bell 측정을 수행함.
동일 시각 이벤트는 중계기 노드 index 순서로 처리함. 프로토콜 시간상 동시이며 CPU 병렬 처리를 뜻하지 않음.
측정 결과 두 bit를 목적지로 전송하고, 모든 결과가 도착했을 때 XOR parity에 따른 X/Z 보정을 적용함.
완료 시각이 duration 이내인 쌍만 세고, 완료 순간의 충실도 값을 복사해 기록함.

큐비트 backend는 실제 QState/Bell 상태, CNOT/H/측정/X/Z 연산을 수행함.
측정 직후 중계기 큐비트를 상태에서 제거해야 함. 체인 전체를 미리 하나의 밀도행렬로 합치지 않음.
Werner backend는 같은 링크 준비·측정·메시지·완료 이벤트를 거치며, swapping에서 `w_out=w_left*w_right`를 계산함.
측정 bit는 이상적 Werner swapping의 네 branch를 동일 확률로 선택함.
두 backend의 RNG 소비량은 같다고 가정하지 않음. 동일 seed의 branch bit 완전 일치 대신 완료 수와 보정 후 충실도로 동등성을 검증함.

### 잡음 동등성

설치 qns의 `DepolarError`는 Pauli 각각에 `p`를 주고, `p >= 1/3`이면 별도 분기로 바뀜.
`DepolarStorageErrorModel`은 `p=1-exp(-rate*t)`를 전달함.
Werner 기본 감쇠 `w*=exp(-rate*t)`와는 같은 rate를 넣어도 일치하지 않음.

주 비교에는 명시적인 **추가 가정**으로 한 큐비트의 Bloch 수축을 `exp(-200*t)`로 정의함.
Pauli I/X/Y/Z 확률은 각각 `1-3p, p, p, p`, `p=(1-exp(-200*t))/4`로 구현함.
Werner는 쌍의 두 절반에 실제 누적된 저장 시간 `t_left+t_right`로 `w*=exp(-200*(t_left+t_right))`를 적용함.
양자 채널 이동 시간에도 같은 local depolarization을 적용하는 설정은 `noise_during_transit=true`로 명시함.
읽기/측정에서 이미 적용한 시간을 다시 적용하지 않도록 각 절반의 last-noise timestamp를 관리함.
위 규칙은 논문의 정확한 숨은 오류 함수를 복원한 것이 아님.
원래 qns 함수 그대로의 결과를 원한다면 별도 `native-qns` preset으로 추가하고 모델 비동등성을 표시해야 함; 1차 범위에는 넣지 않음.

### 시간 지표

- `setup_seconds`: 네트워크·상태·이벤트 구성 시간.
- `simulation_seconds`: 이벤트 실행 시작부터 완료까지 `perf_counter_ns` wall time.
- `job_seconds`: setup + simulation; warmup·결과 저장·plot 제외.
- `batch_seconds`: 동일 backend/node의 반복 8개를 모두 끝내는 wall time. 프로세스 시작·통신 비용 포함.
- `amortized_seconds`: batch_seconds / 완료한 job 수. Fig. 6 형태의 주 그래프 y축.
- `speedup`: 동일 backend/node/job seed 목록의 1-worker batch_seconds / 4-worker batch_seconds.

1 worker도 같은 process-pool 경로를 사용해 비교함. BLAS/OpenMP thread 수는 worker 시작 전 1로 제한함. 각 batch의 모든 process에서 warmup 1회를 완료한 뒤 barrier를 해제하고 measured job을 실행함. batch 타이머에서는 warmup 구간만 제외하되 process 시작·통신 비용은 포함함.
4 worker는 독립 실험 4개를 병렬 실행함. 단일 실험을 4개 조각으로 분할하지 않음.
개별 job latency가 4배 줄었다고 주장하지 않음. 워커 수는 OS 프로세스 수이며 물리 코어 독점을 보장하지 않음.
한 batch의 job 8개에서 얻은 SEM을 batch 시간의 SEM으로 쓰지 않음.
전체 실행은 batch 3회로 batch 평균·표본 SD·SEM을 계산하고, 개별 job 분포는 별도 요약함.

## Global Constraints

- 기존 Fig. 3·5 CLI/config 및 사용자 수정 파일 유지. 사용자의 후속 구현·publish 지시에 따라 공개함.
- 필수 패키지 버전은 기존 requirements를 그대로 사용함.
- figure의 0노드 조건을 만들지 않으며 최소 노드는 2임.
- RNG seed는 backend/node/batch/job 식별자로 결정하고 PID·실행 순서에 의존하지 않음.
- 출력은 빈 폴더에만 생성; running/complete/failed metadata와 실패한 job 식별자 유지.
- 성능 수치를 curve fitting하거나 강제로 원문 배율에 맞추지 않음.
- Cython 측정은 별도 build 환경/실제 로딩 경로를 기록; Python 코어 결과와 섞지 않음.
- NetSquid가 없으면 skipped 사유 기록. 원문 곡선이나 추정값으로 빈 곡선을 채우지 않음.

## Review Focus

1. 동일 시각 이벤트 순서에 의한 잘못된 parity·중복 완료: 3/4노드 모든 branch와 완료 수 검증.
2. 큰 체인에서 전체 밀도행렬 병합: 50노드 실행의 최대 QState 큐비트 수 계측, 기본 순서에서 4 이하 요구.
3. 채널/메모리 오류 중복 적용: 분할 저장와 한 번 저장 결과가 같고 양쪽 절반 감쇠가 반영됨.
4. spawn·seed·worker 실패: 1/4 worker 결과 일치, 누락·예외는 실패로 보고; 부분 성공을 complete로 저장하지 않음.
5. duration 경계·비정상 config: 2노드 최소조건, 마지막 ACK 미도착, NaN/float node count/0 jobs 거부.

## 파일 구조

- Create `evaluations/fig6_protocol.py`: 공통 이벤트·라운드·통지·완료 계측.
- Create `evaluations/fig6_backends.py`: Qubit/Werner adapter와 matched depolarization.
- Create `evaluations/fig6_benchmark.py`: top-level worker, process-pool 실행·시간·seed·batch 통계.
- Create `evaluations/run_fig6.py`: 독립 config 검증·CLI·CSV·metadata.
- Create `evaluations/configs/fig6-smoke.json`, `fig6-full.json`.
- Modify `evaluations/plotting.py`: `plot_fig6`; `evaluations/README.md`: 실행·가정·시간 지표.
- Create `tests/test_fig6_protocol.py`, `tests/test_fig6_benchmark.py`.
- Create 실행 후 `evaluations/sample-results/fig6/`: 측정 CSV·PNG·metadata; 기존 results guide에 링크.
- Reuse `evaluations/reporting.py`, `examples/16_parallel_simulations.py`의 seed/누락 검증 패턴, `scripts/build_cython_core.py`.

## Task 1: 동등한 백엔드와 분배 프로토콜

**Files:** `fig6_backends.py`, `fig6_protocol.py`, `tests/test_fig6_protocol.py`.

**Interfaces:**
- `run_trial(backend: str, nodes: int, settings: dict, seed: int) -> dict`.
- 결과: completed_pairs, completion_times, completion_fidelities, scheduled_rounds, event_count, max_state_qubits.
- Adapter: create_link(round_id, link_id), apply_noise(handle, now), swap(left, right, now), correct(pair, x_bit, z_bit), fidelity(pair).
- 공통 handle은 link/round id, 양끝 노드, 각 절반 last-noise time을 포함함.

- [x] 먼저 실패 테스트 작성: noise=0의 2/3/4노드에서 보정 후 fidelity=1, 모든 Bell branch에서 parity 보정 확인, 중복 completion 없음.
- [x] 잡음 테스트 작성: 단일 쌍 양쪽에 시간 t를 적용하면 `F=(1+3*exp(-400*t))/4`; 분할 적용과 일괄 적용 일치. 3/4노드의 backend fidelity 차이 <1e-10.
- [x] `python -m unittest discover -s tests -p test_fig6_protocol.py -v` 실행해 미구현 실패 확인.
- [x] adapter와 공통 protocol 구현. 2노드는 중계 측정 없이 전달 완료, node50도 로컬 측정 즉시 상태 축소.
- [x] 경계 테스트: duration 전에 생성했지만 ACK가 늦은 round는 미완료; 완료 후 상태 변화가 기록 fidelity를 바꾸지 않음. 50노드·2라운드에서 max_state_qubits <=4.
- [x] 테스트 통과 확인 후 해당 파일만 commit.

## Task 2: 독립 실험 병렬 실행과 정직한 시간 측정

**Files:** `fig6_benchmark.py`, `tests/test_fig6_benchmark.py`.

**Interfaces:**
- `run_batch(backend: str, nodes: int, settings: dict, seeds: list[int], workers: int) -> tuple[dict, list[dict]]`.
- worker는 picklable top-level 함수; timing을 붙인 Task 1 결과 반환.
- batch 결과는 workers/jobs/batch_seconds/amortized_seconds; job은 seed와 세 시간 지표 포함.

- [x] 실패 테스트 작성: synthetic clock 결과로 batch 8초/4 jobs=2초 계산; 결과 순서를 job index로 복원; 중복/누락 job 거부.
- [x] 작은 실제 프로토콜의 1/4-worker 완료 수·충실도 일치 테스트 작성; spawn subprocess에서 import만 해도 pool이 실행되지 않음 확인.
- [x] narrow tests 실행해 실패 확인 후 process pool, wall timing, warmup, thread env 제한 구현.
- [x] worker 예외는 원인과 job id를 호출자에 전달하고 batch 실패 처리하는 테스트 추가.
- [x] narrow tests 통과 후 commit. CI에서 speedup >1 같은 성능 threshold는 검사하지 않음.

## Task 3: CLI·결과·그래프 통합

**Files:** `run_fig6.py`, 두 JSON config, `plotting.py`, tests 두 파일, `evaluations/README.md`.

**Interfaces:**
- CLI: `python -m evaluations.run_fig6 --config PATH [--output EMPTY_DIR] [--workers 1 4]`.
- `plot_fig6(summary: list[dict], path: Path, metric: str) -> None`.
- config: name/seed/nodes/backends/workers/duration/send_rate/link_length_km/speed_km_s/depolar_rate/noise_during_transit/jobs_per_batch/batch_repeats/warmup_jobs/initial_fidelity.
- smoke: nodes=[2,5], duration=.01, jobs_per_batch=4, batch_repeats=2, warmup_jobs=1.
- full: nodes=[5,10,15,20,25,30,35,40,45,50], duration=1, jobs_per_batch=8, batch_repeats=3, warmup_jobs=1.
- 공통: backends=[qubit,werner], workers=[1,4]; 나머지는 실험 명세 표의 값.

- [x] config 테스트: nodes integer>=2, duration/rate 유한 양수, workers/jobs/batch_repeats 양의 정수, batch_repeats=1이면 SEM null. NaN/bool/float 노드 수와 비어 있지 않은 output 거부.
- [x] smoke CLI 통합 테스트에서 `fig6_jobs.csv`, `fig6_batches.csv`, `fig6_summary.csv`, `fig6.png`, `fig6_job_latency.png`, `metadata.json` 검증.
- [x] narrow tests로 미구현 실패 확인 후 CLI 구현: 조건별 checkpoint, 실패 metadata, 전체 config·seed·버전·OS/CPU·start_method·BLAS 환경·qns 모듈 실제 경로와 compiled flag 기록.
- [x] amortized와 job latency를 별도 그림으로 표시. 원문 초 단위 값·배율을 실측과 섞지 않고 legend에는 worker/process로 명시.
- [x] README에 실행법, 잡음·duration 추가 가정, 4-worker 의미, NetSquid/Cython 범위 기록.
- [x] narrow tests와 기존 전체 tests 통과 확인 후 commit.

## Task 4: 실기 검증과 결과 공개

- [x] smoke 실행 후 전 조건 complete와 PNG label 확인.
- [x] full 실행 전에 10/50노드 각 1 job의 메모리·시간 확인. 50노드에서 상태의 4qubit 상한을 넘으면 full 실행을 중단하고 Task 1 수정.
- [x] full: 노드 조건 10개 × 2 backend × 2 worker × 3 batch × 8 jobs = 960 measured jobs. 각 process에 warmup 1회를 수행하므로 worker 수까지 반영하면 총 300 warmup jobs이며 별도 기록. NetSquid 1-worker 곡선을 추가하면 measured jobs 240개와 warmup jobs 30개가 더해져 각각 총 1200·330개임.
- [x] 동일 job 종류에서 완료 수·fidelity 일치 확인. worker 수에 따라 simulation output이 변하면 성능 평가 보류.
- [x] Python 3.11/3.12 전체 tests, ruff, diff check. 빨라지는 것 자체는 합격 기준이 아님.
- [x] CSV/PNG/metadata를 sample-results에 저장하고 결과 guide 갱신. 사용자 미commit 변경은 포함하지 않음.
- [x] 구현 공개가 지시된 단계에서 commit/push하고 GitHub CI 확인.

## 2차: NetSquid·Cython 비교

- NetSquid 사용 가능 환경·버전 확인 후 같은 이벤트/잡음/완료 기준의 adapter 추가. 작은 회로의 fidelity와 event workload를 검증한 뒤 다섯 번째 곡선 측정.
- NetSquid 취득·인증·배포 조건 확인이 필요한 경우 사용자에게 필요한 정보 요청. 미측정은 skipped로 표시.
- Cython은 기존 build script의 별도 환경에서 동일 workload를 측정하고 core_kind별 그림 생성. 현재 Python 소스 컴파일 결과는 2023년 수동 최적화 pyx 재현과 구별.
- 논문 수치의 엄밀한 재현에는 당시 protocol source, duration, repeats, NetSquid version, timing 범위, hardware의 추가 정보가 필요함.

## 완료 기준

SimQN 네 곡선을 실측에서 생성하고 각 점을 job/batch CSV와 metadata에서 추적할 수 있을 것.
backend 품질·완료 수가 같은 조건에서 일치하고 기존 Fig. 3·5 검증을 유지할 것.
원문과의 차이·미측정 NetSquid·Cython 실행 종류를 설명할 수 있을 것.

## NetSquid 사용 가능 여부 사전 확인 (2026-10-09)

- macOS ARM64 / Python 3.11.16에서 NetSquid 1.1.8 설치 확인.
- 확인 환경: `/tmp/study-simqn-netsquid-check`; 임시 경로이므로 구현 시 재생성 가능한 별도 환경으로 관리해야 함.
- NumPy 2.4.6에서는 import 중 `correct_global_phase` 배열→스칼라 변환 TypeError 재현.
- NumPy만 1.26.4로 변경한 뒤 import, density-matrix Bell 생성(H/CNOT), fidelity 계산, depolarization, sim_run(duration=100) 통과.
- 초기 Bell fidelity ≈1, depolarization(prob=.1) 후 fidelity=.925, sim_time=100 확인.
- NetSquid 1.1.8 / NumPy 1.26.4 / SciPy 1.17.1 / pandas 3.0.6 / pydynaa 1.0.2 / cysignals 1.12.5; pip check 통과.
- 패키지 서버 인증은 사용자 로컬 입력으로 수행. 인증 정보를 저장소에 저장하지 않음.
- 따라서 NetSquid adapter 개발 환경은 사용 가능함. Fig. 6 비교 프로토콜의 동등성·성능 측정은 아직 미검증이며 2차 adapter 작업은 남아 있음.
- NumPy 변환 오류 근거: https://numpy.org/doc/2.4/release/2.4.0-notes.html

## 구현 시 결정

- NetSquid 사용 가능 확인 후 사용자 구현 지시에 따라 1차에 NetSquid DM adapter 포함.
- 동일시각 BSM은 하나의 callback에서 노드 index 순서로 수행. 실제 gate/measurement는 각각 실행하며 protocol 시간 지연은 없음.
- quantum link당 도착 event, repeater당 목적지 BSM 통지 event를 두 simulator에서 동일하게 수행. 물리 channel/entity queue와 고전 홉별 forwarding overhead는 추가하지 않음.
- 1-worker와 4-worker 모두 spawn pool을 사용. 프로세스 import/startup 비용 포함, 모든 process의 warmup barrier 구간만 제외.
- `run_fig6`의 full preset은 NetSquid 포함 150 batches/1200 measured jobs; SimQN만 실행하면 120 batches/960 jobs.
- 기존 Fig. 3·5 config를 변경하지 않고 별도 CLI로 제공.

## 실행 검증 기록 (2026-10-09)

- 최종 측정 코드: `17a9fdc` (QState 측정 후 밀도행렬 trace 안정화 포함).
- full: 150 batches / 1200 measured jobs / 330 unmeasured warmups 완료; NetSquid 포함 다섯 곡선 모두 실측.
- smoke: 20 batches / 80 measured jobs 완료. 실패·중단한 사전 측정 결과는 공개 결과에서 제외.
- 240개의 node/batch/job/seed 그룹에서 다섯 조건의 완료 수·round checksum·이벤트 수 일치; 평균 충실도 차이 <1e-10. 각 job은 별도 해석식 검증도 통과.
- batch/jobs 및 1-worker/4-worker speedup CSV를 독립 재계산해 확인. 두 full PNG의 축·범례·오류 막대 시각 검증 완료.
- Apple M4 / macOS ARM64 / Python 3.11.16 / NumPy 1.26.4 / NetSquid 1.1.8에서 동일 환경 비교.
- 평균 batch speedup 범위: qubit 3.03–3.16배, Werner 1.40–2.55배. 개별 job latency와 구별하며 논문 배율 재현으로 주장하지 않음.
- 67 tests: Python3.11 NumPy2, Python3.12 NumPy2, Cython3.12 compiled core, NetSquid3.11 NumPy1.26.4 모두 통과. NetSquid 없는 세 환경은 optional test 두 개 skip.
- 독립 리뷰의 import/startup 공정성, ns 경계, worker timeout 종료, 밀도행렬 trace 오류 지적 수정 및 재검증 완료. Ruff·diff check 통과.
- Cython 전체 성능 sweep은 이번 결과에 포함하지 않음; compiled core 호환성만 검증. 논문 미공개 duration·반복·잡음식·시간 집계 범위·하드웨어로 인해 정확한 원문 수치 재현은 여전히 추가 자료가 필요함.
