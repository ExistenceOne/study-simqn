# Fig. 3·5 재현 설계

대상: 저장소의 SimQN 논문 PDF 6–7쪽. 원본 그림 수치의 완전 일치가 아니라,
실제 SimQN 시뮬레이션으로 실험을 다시 실행하고 가정을 추적할 수 있도록 함.

- Fig. 3: 선형 BB84 링크를 병렬로 실행하고 링크별 correct-sifted bit 수의
  최솟값/실험 시간을 신뢰 중계의 병목 지표로 사용함. 이는 종단 간 키 전달
  구현이나 안전한 최종 비밀키율이 아님. 원본 공개 예제와 동일한 집계임.
- 2023년 공개 예제의 BB84를 GPL-3.0 출처와 커밋을 명시하여 보존함.
  최신 qns 0.2.3의 이벤트·물리 모델을 사용하되 새 후처리 코드와 혼합하지 않음.
- historical 설정은 공개 예제의 exp(-L/50 km) 손실과 collective rotation 사용.
  paper-stated 설정은 본문 0.2 dB/km 손실과 명시적으로 가정한 비트 반전 모델 사용.
- Fig. 5: RandomTopology, Dijkstra, 내장 EntanglementDistributionApp,
  Werner fidelity 0.99, 메모리 50, decoherence rate 1/5 s^-1.
  반복마다 토폴로지·요청을 고정하고 rate별 새 네트워크 복사본을 실행함.
- Fig. 5는 세션당/전체 EDR와 평균 완료 수를 모두 저장함. 기본 그림은
  세션당 EDR(pair/s)이며 원본의 모호한 throughput 축을 임의 배율로 맞추지 않음.
- JSON config: full/historical, full/paper-stated, smoke. 가정은 문서와 metadata에 저장.
- CLI: 선택한 그림의 반복별 CSV, 평균·표준편차·SEM CSV, PNG와 metadata 생성.
- 검증: 물리 기대값, 잡음 on/off, seed 재현, 세션·요청 고정, 완료 집계,
  통계 집계 및 실제 CLI/그래프 출력. 사용자 기존 변경·PDF는 커밋하지 않음.
