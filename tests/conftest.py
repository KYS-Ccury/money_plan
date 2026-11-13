"""테스트는 진짜 데이터 파일(capital_data.json)을 건드리지 않는다.

Backend 는 기본 경로의 파일을 열고, 자동 저장도 거기에 한다. 테스트가 그
경로를 그대로 쓰면 **사용자의 실제 재무 데이터를 덮어쓴다** (실제로 그런 일이
있었다). 그래서 모듈을 불러오기 전에 임시 폴더로 돌려놓는다.
"""
import os
import tempfile
from pathlib import Path

# capital_calc.backend 가 import 될 때 읽으므로, 그 전에 세워 두어야 한다
_TMP = Path(tempfile.mkdtemp(prefix="capital_test_")) / "capital_data.json"
os.environ["CAPITAL_DATA_FILE"] = str(_TMP)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_configure(config):
    from capital_calc import backend

    assert backend.DATA_FILE == _TMP, (
        f"테스트가 진짜 데이터 파일을 가리키고 있습니다: {backend.DATA_FILE}")
