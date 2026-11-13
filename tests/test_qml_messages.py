"""화면·팝업을 한 번씩 열어 보고 QML 이 투덜대는지 본다.

바인딩은 visible 과 상관없이 계산되므로, '아직 아무것도 안 읽은' 팝업이
없는 값을 건드리면 그 자리에서 TypeError 가 난다 (가져오기 팝업이 그랬다).
눈으로는 멀쩡해 보여서 이런 건 이렇게 잡아 두는 게 낫다.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QMetaObject, QObject, QUrl, Q_ARG, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from capital_calc.backend import Backend  # noqa: E402

BAD = ("TypeError", "ReferenceError", "is not a function",
       "Unable to assign", "overrides a member")


def test_no_qml_complaints_while_opening_everything():
    QQuickStyle.setStyle("Material")
    app = QGuiApplication.instance() or QGuiApplication([])
    msgs: list[str] = []
    qInstallMessageHandler(lambda mode, ctx, text: msgs.append(text))
    try:
        backend = Backend()
        backend.loadSample()
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(ROOT))
        engine.rootContext().setContextProperty("backend", backend)
        engine.load(QUrl.fromLocalFile(str(ROOT / "qml" / "Main.qml")))
        assert engine.rootObjects(), "QML 로드 실패"
        win = engine.rootObjects()[0]
        app.processEvents()

        def child(name):
            obj = win.findChild(QObject, name)
            assert obj is not None, f"{name} 을 못 찾음"
            return obj

        ledger = child("ledgerView")
        for mode in ("ledger", "overview", "plan"):
            win.setProperty("mode", mode)
            app.processEvents()

        win.setProperty("mode", "ledger")
        for method in ("openImport", "openFixed", "openBudget", "openAdd"):
            QMetaObject.invokeMethod(ledger, method)
            app.processEvents()
        for name in ("importDialog", "fixedDialog", "budgetDialog", "entryDialog"):
            child(name).setProperty("visible", False)
            app.processEvents()

        ledger.setProperty("viewMode", "calendar")
        app.processEvents()

        win.setProperty("mode", "plan")
        QMetaObject.invokeMethod(win, "openAddDialog")
        app.processEvents()
        child("itemDialog").setProperty("visible", False)
        QMetaObject.invokeMethod(win, "openEditDialog", Q_ARG("QVariant", 2))
        app.processEvents()
        child("itemDialog").setProperty("visible", False)
        child("goalsDialog").setProperty("visible", True)
        app.processEvents()
    finally:
        qInstallMessageHandler(None)

    bad = [m for m in msgs if any(w in m for w in BAD)]
    assert not bad, "QML 이 투덜댑니다:\n" + "\n".join(bad)
