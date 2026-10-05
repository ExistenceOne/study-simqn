# Cython 코어 빌드와 비교

15번은 Python 코어에서도 실행 가능함. 실제 Cython 확장 모듈로 비교하려면
별도 환경에서 현재 설치한 qns의 `ts.py`, `pool.py`, `simulator.py`를 컴파일함.
나머지 물리 모델·entity 모듈은 Python 상태로 유지함.
원본 저장소의 오래된 `.pyx` 구현으로 바꾸는 방식과는 다름.

원본 [setup-cython.py](https://github.com/QNLab-USTC/SimQN/blob/main/setup-cython.py)는
현재 배포판과 맞지 않는 버전·파일명도 포함함. 이 저장소의
[build_cython_core.py](../scripts/build_cython_core.py)는 설치 패키지를 새 폴더로 복사해서
세 모듈의 현재 `.py` 소스만 컴파일함. 기존 가상환경과 소스는 변경하지 않음.
`annotation_typing=False`로 Python 타입 힌트에서 Cython이 추가 타입 제약을 만들지 않게 함.

## macOS·Linux

C 컴파일러와 Python 개발 헤더 필요함. macOS는 Xcode Command Line Tools,
Linux는 C 컴파일러와 해당 Python의 개발 헤더를 준비함.

저장소 루트에서 실행함. `.venv-cython`은 아직 없는 별도 환경 이름을 사용함.

```bash
python3.12 -m venv .venv-cython
source .venv-cython/bin/activate
python -m pip install -r requirements-cython.txt

# 동일 Python·의존성에서 먼저 Python 코어 측정
python examples/15_cython_acceleration.py --events 100000 --repeats 5

# output은 아직 존재하지 않는 경로여야 함
python scripts/build_cython_core.py --output /tmp/study-simqn-cython-core

# 새 프로세스에서 복사한 qns를 먼저 로딩함
PYTHONPATH=/tmp/study-simqn-cython-core python examples/15_cython_acceleration.py \
  --events 100000 --repeats 5 --require-compiled
```

`uv` 사용 시 환경 생성·설치 명령은 아래로 대체할 수 있음.

```bash
uv venv --python 3.12 .venv-cython
uv pip install --python .venv-cython/bin/python -r requirements-cython.txt
source .venv-cython/bin/activate
```

## Windows PowerShell

해당 Python을 지원하는 MSVC C/C++ Build Tools 필요함.

```powershell
py -3.12 -m venv .venv-cython
.venv-cython\Scripts\Activate.ps1
python -m pip install -r requirements-cython.txt
python examples/15_cython_acceleration.py --events 100000 --repeats 5
python scripts/build_cython_core.py --output "$env:TEMP\study-simqn-cython-core"
$env:PYTHONPATH = "$env:TEMP\study-simqn-cython-core"
python examples/15_cython_acceleration.py --events 100000 --repeats 5 --require-compiled
Remove-Item Env:PYTHONPATH
```

Windows 빌드는 로컬에서 검증하지 않았음. macOS Python 3.12 빌드와 실행은 검증했으며
GitHub Actions에서는 Linux Python 3.11·3.12로 빌드·검증함.

## 결과 해석

- 세 `modules` 항목이 모두 `compiled_extension=true`인지 확인함.
- `invoked=events`, `checksum=events*(events-1)/2`인지 확인함.
- 같은 events·repeats·Python·패키지 버전·장비에서 median wall time을 비교함.
- Python median / Cython median이 관측 speedup임. 1보다 작으면 해당 실험에서는 느려진 것임.

Python 코드를 Cython으로 컴파일했다고 모든 작업이 빨라지는 것은 아님.
이벤트 래핑·Python 객체 호출·힙 비교 비용도 포함됨. 오래된 수동 최적화 `.pyx`의
성능을 측정하는 예제가 아니며, 논문의 가속 수치를 재현한다고 주장하지 않음.
컴파일러 경고와 빌드 로그는 빌드 명령에 출력됨. 성공 여부는 종료 코드와
output의 `build-metadata.json`, 실제 확장 모듈 로딩으로 확인함.
호환되지 않는 Python 버전이나 운영체제로 `.so/.pyd`를 복사해서 사용하면 안 됨.

빌드 결과·C 파일·가상환경은 GitHub에 올릴 필요 없음.
[module-sample-results.json](module-sample-results.json)에 실제 Python/Cython 비교 결과를 보존함.

2026-10-05 macOS ARM64·Python 3.12에서 100,000이벤트를 5회 측정한 median은
Python 약 1.317초, Cython 약 1.362초였음. 관측 speedup은 약 0.967로,
이 실행에서는 Cython이 조금 느렸음. 다른 장비·workload의 결과로 일반화하면 안 됨.
