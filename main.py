"""자본금 계산기 실행 파일 (PySide6 + QML).

    python main.py                          # 창 띄우기
    python main.py --screenshot shot.png    # 1초 후 스크린샷 저장하고 자동 종료 (테스트용)

예전 OpenGL(ImGui) 버전은 main_imgui.py 로 실행할 수 있습니다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QMetaObject, QTimer, QUrl, Q_ARG
from PySide6.QtGui import QGuiApplication, QFont
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from capital_calc.backend import Backend

QML_DIR = Path(__file__).resolve().parent / "qml"


def main() -> int:
    parser = argparse.ArgumentParser(description="자본금 계산기 (PySide6 + QML)")
    parser.add_argument("--screenshot", type=str, default=None, help="스크린샷 PNG 경로 (테스트용, 저장 후 종료)")
    parser.add_argument("--open-dialog", action="store_true", help="테스트용: 추가 팝업을 연 상태로 스크린샷")
    parser.add_argument("--size", type=str, default=None, help="테스트용: 창 크기 WxH (예: 1280x1100)")
    parser.add_argument("--open-edit", type=int, default=None, help="테스트용: 지정 행의 수정 팝업을 연 상태로 스크린샷")
    parser.add_argument("--demo-toast", action="store_true", help="테스트용: 저장 완료 토스트를 띄운 상태로 스크린샷")
    parser.add_argument("--demo-scenarios", action="store_true", help="테스트용: 시나리오 2개를 더 만들어 비교 화면으로 (저장하지 않음)")
    parser.add_argument("--demo-sample", action="store_true", help="테스트용: 예시 데이터로 띄우기 (저장하지 않음)")
    parser.add_argument("--ledger", action="store_true", help="테스트용: 가계부 화면으로 띄우기")
    args = parser.parse_args()

    QQuickStyle.setStyle("Material")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("자본금 계산기")
    app.setFont(QFont("Malgun Gothic", 10))

    backend = Backend()
    if args.demo_sample:
        backend.loadSample()
    if args.demo_scenarios:
        from capital_calc.model import Category, Item
        base = backend.activeScenario
        backend.duplicateScenario()
        backend.renameScenario(backend.activeScenario, "2번: 월세 ↓")
        for it in backend._plan.items:
            if it.category == Category.RENT:
                it.amount *= 0.7
        backend.duplicateScenario()
        backend.renameScenario(backend.activeScenario, "3번: 부업 수입")
        backend._plan.add(Item("부업", Category.INCOME, 600_000))
        backend.activeScenario = base
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR.parent))          # 'qml' 디렉터리를 모듈로 import 가능하게
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        print("QML 로드 실패", file=sys.stderr)
        return 1

    if args.ledger:
        engine.rootObjects()[0].setProperty("mode", "ledger")

    if args.size:
        w, h = (int(x) for x in args.size.lower().split("x"))
        engine.rootObjects()[0].setWidth(w)
        engine.rootObjects()[0].setHeight(h)

    if args.screenshot:
        win = engine.rootObjects()[0]

        def shoot() -> None:
            win.grabWindow().save(args.screenshot)
            app.quit()

        if args.open_dialog:
            QTimer.singleShot(400, lambda: QMetaObject.invokeMethod(win, "openAddDialog"))
        if args.demo_toast:
            QTimer.singleShot(600, lambda: QMetaObject.invokeMethod(
                win, "showToast", Q_ARG("QVariant", f"저장되었습니다  ·  {backend.dataPath}")))
        if args.open_edit is not None:
            QTimer.singleShot(400, lambda: QMetaObject.invokeMethod(win, "openEditDialog", Q_ARG("QVariant", args.open_edit)))
        QTimer.singleShot(1500, shoot)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
