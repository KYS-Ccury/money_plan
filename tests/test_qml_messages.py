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


def _settle(app, ms: int = 400):
    """'잠깐 기다렸다 한 번만' 갱신하는 타이머가 지나가도록 기다린다."""
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


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
        child("goalsDialog").setProperty("visible", False)

        # 계획 가져오기: 아직 아무것도 안 읽은 채로 열어 본다 (info 가 {} 인 상태)
        plan_import = child("planImportDialog")
        QMetaObject.invokeMethod(plan_import, "start")
        app.processEvents()
        QMetaObject.invokeMethod(plan_import, "readPasted")
        app.processEvents()
        plan_import.setProperty("visible", False)
        app.processEvents()
    finally:
        qInstallMessageHandler(None)

    bad = [m for m in msgs if any(w in m for w in BAD)]
    assert not bad, "QML 이 투덜댑니다:\n" + "\n".join(bad)


def test_export_buttons_exist():
    """그림·PDF 단추가 달려 있고, 그림 단추는 계획 화면에서만 보인다."""
    QQuickStyle.setStyle("Material")
    app = QGuiApplication.instance() or QGuiApplication([])
    backend = Backend()
    backend.loadSample()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(ROOT))
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qml" / "Main.qml")))
    assert engine.rootObjects(), "QML 로드 실패"
    win = engine.rootObjects()[0]
    app.processEvents()

    png = win.findChild(QObject, "pngButton")
    pdf = win.findChild(QObject, "pdfButton")
    card = win.findChild(QObject, "chartCard")
    assert png is not None and pdf is not None and card is not None
    assert png.property("visible") is True and pdf.property("visible") is True

    win.setProperty("mode", "ledger")
    app.processEvents()
    assert png.property("visible") is False      # 그래프가 없는 화면에서는 숨긴다
    assert pdf.property("visible") is True       # PDF 는 어디서든 (요약은 늘 있다)


def test_ledger_can_be_popped_out_into_its_own_window():
    """가계부를 따로 띄우고 본 창으로 되돌리는 동안 QML 이 투덜대지 않는지."""
    QQuickStyle.setStyle("Material")
    app = QGuiApplication.instance() or QGuiApplication([])
    msgs: list[str] = []
    qInstallMessageHandler(lambda mode, ctx, text: msgs.append(text))
    try:
        backend = Backend()
        backend.loadSample()
        backend.saveLedgerWindowState(-1, -1, -1, -1, False)   # 닫힌 상태에서 시작
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(ROOT))
        engine.rootContext().setContextProperty("backend", backend)
        engine.load(QUrl.fromLocalFile(str(ROOT / "qml" / "Main.qml")))
        assert engine.rootObjects(), "QML 로드 실패"
        win = engine.rootObjects()[0]
        app.processEvents()

        pane = win.findChild(QObject, "ledgerView")
        assert pane is not None
        assert win.property("ledgerPopped") is False
        assert win.findChild(QObject, "ledgerWindow") is None

        QMetaObject.invokeMethod(win, "popLedgerOut")
        app.processEvents()
        assert win.property("ledgerPopped") is True
        popped = win.findChild(QObject, "ledgerWindow")
        assert popped is not None, "따로 띄운 가계부 창을 못 찾음"
        assert popped.findChild(QObject, "ledgerWindowView") is not None
        assert pane.property("visible") is False          # 본 창 안에서는 숨는다
        assert backend.ledgerWindowState()["popped"] is True

        # 띄워 둔 채로 화면을 돌려 본다 (바인딩이 둘이 되는 자리다)
        for mode in ("plan", "overview", "ledger"):
            win.setProperty("mode", mode)
            app.processEvents()

        QMetaObject.invokeMethod(win, "popLedgerIn")
        app.processEvents()
        assert win.property("ledgerPopped") is False
        assert win.property("mode") == "ledger"
        assert pane.property("visible") is True
        assert backend.ledgerWindowState()["popped"] is False

        QMetaObject.invokeMethod(win, "toggleLedgerWindow")   # 단축키가 쓰는 길
        app.processEvents()
        assert win.property("ledgerPopped") is True
        QMetaObject.invokeMethod(win, "toggleLedgerWindow")
        app.processEvents()
        assert win.property("ledgerPopped") is False
    finally:
        qInstallMessageHandler(None)
        backend.saveLedgerWindowState(-1, -1, -1, -1, False)

    bad = [m for m in msgs if any(w in m for w in BAD)]
    assert not bad, "QML 이 투덜댑니다:\n" + "\n".join(bad)


def test_overview_is_kept_alive_but_goes_quiet_while_hidden():
    """한눈에 보기가 (1) 미리 만들어지고 (2) 안 보이는 동안 값을 새로 뜨지 않는지.

    들어갈 때마다 다시 만들면 한 프레임에 카드·그래프를 다 만들어 창이 멈춘다.
    그렇다고 숨겨만 두면 안 보이는 값이 계속 다시 계산돼 슬라이더가 느려진다.
    둘 다 아니어야 한다 — 만들어는 두고, 안 보이면 셈하지 않는다.
    """
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

        def overview():
            return win.findChild(QObject, "overviewView")

        QMetaObject.invokeMethod(win, "openOverview")
        for _ in range(60):                     # asynchronous 로 만들어지는 것을 기다린다
            app.processEvents()
            if overview() is not None:
                break
        view = overview()
        assert view is not None, "한눈에 보기가 만들어지지 않음"
        assert win.property("overviewReady") is True
        assert view.property("visible") is True
        assert view.property("stale") is False          # 보이는 동안에는 값이 새것이다

        # 다른 화면으로 가도 **지워지지 않는다** (다시 들어갈 때 바로 떠야 한다)
        win.setProperty("mode", "plan")
        app.processEvents()
        assert overview() is view
        assert view.property("visible") is False

        # 안 보이는 동안 계획이 바뀌어도 그 자리에서 셈하지 않고 '나중에' 로 둔다
        backend.months = backend.months + 1
        for _ in range(3):
            app.processEvents()
        _settle(app, 400)                               # 250ms 타이머가 지나가도록
        assert view.property("stale") is True, "안 보이는데 값을 새로 떴다"

        # 다시 들어가면 그때 한 번 새로 뜬다
        win.setProperty("mode", "overview")
        app.processEvents()
        assert view.property("stale") is False
    finally:
        qInstallMessageHandler(None)

    bad = [m for m in msgs if any(w in m for w in BAD)]
    assert not bad, "QML 이 투덜댑니다:\n" + "\n".join(bad)


def test_header_keeps_its_room_and_rearranges_when_the_window_is_small():
    """창을 줄여도 상단 바가 눌려 잘리지 않고, 설정 줄이 나뉘어 내려앉는지.

    목표 자본금 칸이 창 아래쪽에서 잘려 보이던 일이 있었다 — 상단 카드에
    최소 높이가 없어서 세로로 눌렸기 때문이다.
    """
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

        card = win.findChild(QObject, "headerCard")
        grid = win.findChild(QObject, "settingsGrid")
        bar = win.findChild(QObject, "toolbarFlow")
        assert card is not None and grid is not None and bar is not None

        win.setProperty("width", 1400)
        app.processEvents()
        wide_bar = bar.property("height")
        win.setProperty("width", 700)
        app.processEvents()
        # 단추 줄은 좁아지면 아래로 접힌다 (창 밖으로 밀려 나가지 않는다)
        assert bar.property("height") > wide_bar, "단추 줄이 줄바꿈되지 않았다"
        assert bar.property("width") <= card.property("width")

        for w, h, cols in ((1400, 900, 4), (1000, 700, 2), (760, 560, 1)):
            win.setProperty("width", w)
            win.setProperty("height", h)
            app.processEvents()
            assert grid.property("columns") == cols, f"{w}px 에서 {cols}줄이 아니다"
            # 눌려서 안의 내용보다 작아지면 아랫줄이 잘린다
            inner = grid.property("y") + grid.property("height")
            assert card.property("height") >= inner, f"{w}x{h} 에서 상단 바가 눌렸다"
    finally:
        qInstallMessageHandler(None)

    bad = [m for m in msgs if any(w in m for w in BAD)]
    assert not bad, "QML 이 투덜댑니다:\n" + "\n".join(bad)


def test_item_row_folds_its_narrow_columns_instead_of_pushing_the_delete_button_out():
    """줄이 좁아지면 연이율·▲▼ 가 접히고, ✕(삭제) 는 줄 안에 남는지.

    예전에는 칸들이 줄보다 넓어져 오른쪽 끝의 ✕ 가 잘려 나갔다 (줄은 clip 이다).
    """
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

        def a_row():
            """항목 줄 하나 (roomy 를 가진 것이 줄이다)."""
            for obj in win.findChildren(QObject):
                if obj.property("roomy") is not None and obj.property("name") is not None:
                    return obj
            return None

        for w, roomy in ((1500, True), (820, False)):
            win.setProperty("width", w)
            app.processEvents()
            row = a_row()
            assert row is not None, "항목 줄을 못 찾음"
            assert row.property("roomy") is roomy, f"{w}px 에서 roomy={roomy} 가 아니다"
            # 칸들이 줄보다 넓으면 ✕ 가 밖으로 밀린다
            inner = row.findChildren(QObject)
            wide = [c for c in inner
                    if c.property("x") is not None and c.property("width") is not None
                    and c.property("visible") is True
                    and c.property("x") + c.property("width") > row.property("width") + 1]
            assert not wide, f"{w}px 에서 줄 밖으로 삐져나온 것이 있다 ({len(wide)}개)"
    finally:
        qInstallMessageHandler(None)

    bad = [m for m in msgs if any(w in m for w in BAD)]
    assert not bad, "QML 이 투덜댑니다:\n" + "\n".join(bad)
