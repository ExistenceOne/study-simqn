"""설치된 qns를 새 폴더에 복사하고 현재 버전의 코어 Python 소스만 Cython 빌드함."""

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

SETUP_SOURCE = '''from setuptools import Extension, setup
from Cython.Build import cythonize

modules = ['qns.simulator.ts', 'qns.simulator.pool', 'qns.simulator.simulator']
extensions = [Extension(name, [name.replace('.', '/') + '.py']) for name in modules]
setup(name='study-simqn-cython-core',
      ext_modules=cythonize(extensions, compiler_directives={
          'language_level': 3, 'annotation_typing': False}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='아직 존재하지 않는 새 폴더')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('기존 폴더를 덮어쓰지 않음. 새 output 경로를 지정해야 함')
    if importlib.util.find_spec('Cython') is None or importlib.util.find_spec('setuptools') is None:
        parser.error('requirements-cython.txt 설치 필요함')
    import qns

    source = Path(qns.__file__).parent
    shutil.copytree(source, output / 'qns',
                    ignore=shutil.ignore_patterns('__pycache__', '*.so', '*.pyd', '*.c', '*.pyc'))
    setup_file = output / 'setup_core.py'
    setup_file.write_text(SETUP_SOURCE, encoding='utf-8')
    # 기존 가상환경의 qns와 소스 파일은 수정하지 않음.
    process = subprocess.run([sys.executable, str(setup_file), 'build_ext', '--inplace'],
                             cwd=output, check=False)
    metadata = {'qns_version': version('qns'), 'cython_version': version('Cython'),
                'python': sys.version, 'source_package': str(source),
                'output': str(output), 'status': 'complete' if process.returncode == 0 else 'failed',
                'compiled_modules': ['qns.simulator.ts', 'qns.simulator.pool', 'qns.simulator.simulator'],
                'approach': 'Cython compile installed .py sources; historical .pyx not used'}
    (output / 'build-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(main())
