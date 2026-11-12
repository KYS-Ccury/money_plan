"""수정 팝업이 항상 선택한 행의 값을 보여주는지 (슬라이더로 값을 바꾼 뒤에도) 확인."""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QMetaObject, QObject, QUrl, Q_ARG, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from capital_calc.backend import Backend  # noqa: E402
from capital_calc.model import Category, Item, Plan  # noqa: E402


def _load():
    QQuickStyle.setStyle("Material")
    app = QGuiApplication.instance() or QGuiApplication([])
    plan = Plan(months=12, target=1_000_000)
    plan.add(Item("보유 현금", Category.CASH, 60_000_000))
    plan.add(Item("관리비", Category.MAINT, 150_000))
    plan.add(Item("대출", Category.LOAN, 12_000_000, rate=10.0, start_date="2026-04-01", end_date="2026-10-01",
                  repayments=[{"date": "2026-07-01", "amount": 6_000_000}], monthly_repay_rate=2.5))
    backend = Backend(plan)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(ROOT))
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qml" / "Main.qml")))
    assert engine.rootObjects(), "QML 로드 실패"
    win = engine.rootObjects()[0]
    return app, engine, backend, win


def test_edit_dialog_shows_selected_row_after_slider_edit():
    app, engine, backend, win = _load()
    dlg = win.findChild(QObject, "itemDialog")
    amount_input = dlg.findChild(QObject, "amountInput")
    assert dlg is not None and amount_input is not None

    # 1) 관리비(150,000) 수정 팝업을 열고 슬라이더로 값을 바꾼다 (commit 호출 = 드래그와 동일 경로)
    QMetaObject.invokeMethod(win, "openEditDialog", Q_ARG("QVariant", 1))
    app.processEvents()
    assert dlg.property("amount") == 150_000
    QMetaObject.invokeMethod(amount_input, "commit", Q_ARG("QVariant", 200_000))
    app.processEvents()
    assert dlg.property("amount") == 200_000
    assert amount_input.property("value") == 200_000
    QMetaObject.invokeMethod(dlg, "close")
    app.processEvents()

    # 2) 다른 행(보유 현금 60,000,000)을 열면 그 행의 값이 보여야 한다
    QMetaObject.invokeMethod(win, "openEditDialog", Q_ARG("QVariant", 0))
    app.processEvents()
    assert dlg.property("amount") == 60_000_000
    assert amount_input.property("value") == 60_000_000, "이전 값이 남아 있음 (바인딩 끊김)"

    engine.deleteLater()


def test_edit_dialog_loads_dates_and_repayments_and_saves():
    from PySide6.QtCore import Q_RETURN_ARG
    app, engine, backend, win = _load()
    dlg = win.findChild(QObject, "itemDialog")

    QMetaObject.invokeMethod(win, "openEditDialog", Q_ARG("QVariant", 2))
    app.processEvents()
    assert dlg.property("startDate") == "2026-04-01"
    assert dlg.property("endDate") == "2026-10-01"
    assert dlg.property("monthlyRepayRate") == 2.5
    reps = QMetaObject.invokeMethod(dlg, "repaymentsJson", Qt.ConnectionType.DirectConnection, Q_RETURN_ARG("QVariant"))
    assert json.loads(reps) == [{"date": "2026-07-01", "amount": 6_000_000}]

    # 종료일을 비우고 저장 → 무기한
    dlg.setProperty("endDate", "")
    QMetaObject.invokeMethod(dlg, "submit")
    app.processEvents()
    m = backend.items
    idx = m.index(2)
    assert m.data(idx, m.EndDateRole) == ""
    assert m.data(idx, m.StartDateRole) == "2026-04-01"
    assert m.data(idx, m.RepaymentsRole) == [{"date": "2026-07-01", "amount": 6_000_000.0}]
    assert m.data(idx, m.MonthlyRepayRateRole) == 2.5                # 저장 후에도 유지
    engine.deleteLater()


def test_edit_dialog_repay_method_requires_end_date():
    from PySide6.QtCore import Q_RETURN_ARG
    app, engine, backend, win = _load()
    dlg = win.findChild(QObject, "itemDialog")

    QMetaObject.invokeMethod(win, "openEditDialog", Q_ARG("QVariant", 2))
    app.processEvents()
    assert dlg.property("repayMethod") == "rate"            # 상환율만 있던 예전 항목

    # 원리금 균등으로 바꾸고 종료일을 비우면 저장이 막힌다
    QMetaObject.invokeMethod(dlg, "setRepayMethod", Q_ARG("QVariant", "equal_payment"))
    dlg.setProperty("endDate", "")
    app.processEvents()
    assert dlg.property("loanInfo")["needsEnd"] is True
    valid = QMetaObject.invokeMethod(dlg, "datesValid", Qt.ConnectionType.DirectConnection, Q_RETURN_ARG("QVariant"))
    assert valid is False

    dlg.setProperty("endDate", "2027-04-01")                # 12개월 만기
    app.processEvents()
    info = dlg.property("loanInfo")
    assert not info["needsEnd"] and info["months"] == 12
    assert "원리금 균등" in info["text"] and info["first"] > 0

    QMetaObject.invokeMethod(dlg, "submit")
    app.processEvents()
    m = backend.items
    idx = m.index(2)
    assert m.data(idx, m.RepayMethodRole) == "equal_payment"
    assert m.data(idx, m.MonthlyRepayRateRole) == 0.0       # rate 방식이 아니면 상환율은 버린다
    engine.deleteLater()


def test_ledger_delete_asks_first():
    """가계부의 ✕ 는 바로 지우지 않고 확인 팝업을 띄운다 (되돌릴 수 없으므로)."""
    from capital_calc.ledger import Entry, Ledger
    from capital_calc.model import Workspace

    QQuickStyle.setStyle("Material")
    app = QGuiApplication.instance() or QGuiApplication([])
    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger([
        Entry("2026-11-05", "식비", 30_000, "점심"),
        Entry("2026-11-06", "교통", 1_500, "버스"),
    ])
    backend = Backend(ws)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(ROOT))
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qml" / "Main.qml")))
    assert engine.rootObjects(), "QML 로드 실패"
    win = engine.rootObjects()[0]
    win.setProperty("mode", "ledger")
    app.processEvents()

    view = win.findChild(QObject, "ledgerView")
    dlg = view.findChild(QObject, "removeEntryDialog")
    assert view is not None and dlg is not None
    assert not dlg.property("visible")

    before = len(ws.ledger.entries)
    QMetaObject.invokeMethod(view, "confirmRemove",
                             Q_ARG("QVariant", 0), Q_ARG("QVariant", "11월 5일"),
                             Q_ARG("QVariant", "점심"), Q_ARG("QVariant", "식비"),
                             Q_ARG("QVariant", "-30,000원"))
    app.processEvents()
    assert dlg.property("visible"), "확인 팝업이 안 떴다"
    assert "점심" in dlg.property("message")
    assert len(ws.ledger.entries) == before, "묻기도 전에 지워졌다"

    # 확인을 눌러야 지워진다
    QMetaObject.invokeMethod(dlg, "accepted")
    app.processEvents()
    assert len(ws.ledger.entries) == before - 1


def test_entry_dialog_can_make_a_category():
    """팝업의 ＋ 로 분류를 만들면 바로 그 분류가 골라지고, 수입/지출 표시도 따라간다."""
    from capital_calc.ledger import Ledger
    from capital_calc.model import Workspace

    QQuickStyle.setStyle("Material")
    app = QGuiApplication.instance() or QGuiApplication([])
    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    backend = Backend(ws)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(ROOT))
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qml" / "Main.qml")))
    assert engine.rootObjects(), "QML 로드 실패"
    win = engine.rootObjects()[0]
    win.setProperty("mode", "ledger")
    app.processEvents()

    dlg = win.findChild(QObject, "entryDialog")
    QMetaObject.invokeMethod(dlg, "openForAdd", Q_ARG("QVariant", "2026-11-11"))
    app.processEvents()
    assert dlg.property("kind") == "cost"
    assert dlg.property("categoryIsCustom") is False

    name = dlg.findChild(QObject, "newCategoryName")
    toggle = dlg.findChild(QObject, "newCategoryToggle")
    assert name is not None and toggle is not None

    # 수입으로 '부모님 용돈' 을 만든다
    toggle.setProperty("checked", True)
    dlg.setProperty("newCatKind", "income")
    name.setProperty("text", "부모님 용돈")
    QMetaObject.invokeMethod(dlg, "createCategory")
    app.processEvents()

    assert "부모님 용돈" in ws.ledger.income_categories()
    assert dlg.property("category") == "부모님 용돈", "만든 분류가 바로 골라져야 한다"
    assert dlg.property("kind") == "income", "수입으로 기록된다고 보여야 한다"
    assert dlg.property("categoryIsCustom") is True
    assert not toggle.property("checked"), "만들고 나면 입력칸이 닫힌다"

    # 그 분류로 적으면 수입으로 들어간다
    backend.addEntry("2026-11-11", "부모님 용돈", 300_000, "엄마")
    assert ws.ledger.summary("")["income"] == 300_000

    # 쓰고 있는 분류는 못 지운다
    assert backend.removeLedgerCategory("부모님 용돈") != ""
    assert "부모님 용돈" in ws.ledger.income_categories()


def test_fixed_dialog_creates_a_rule():
    """고정 팝업의 칸을 채우고 '추가' 를 누르면 규칙이 생기고 내역이 적힌다."""
    from datetime import date

    from capital_calc.ledger import Ledger, month_key
    from capital_calc.model import Workspace

    QQuickStyle.setStyle("Material")
    app = QGuiApplication.instance() or QGuiApplication([])
    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    backend = Backend(ws)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(ROOT))
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qml" / "Main.qml")))
    assert engine.rootObjects(), "QML 로드 실패"
    win = engine.rootObjects()[0]
    win.setProperty("mode", "ledger")
    app.processEvents()

    dlg = win.findChild(QObject, "fixedDialog")
    assert dlg is not None
    QMetaObject.invokeMethod(dlg, "openNew")
    app.processEvents()
    assert dlg.property("formOpen") is True

    this_month = month_key(date.today())
    dlg.findChild(QObject, "fixedName").setProperty("text", "월세")
    dlg.findChild(QObject, "fixedAmount").setProperty("text", "600000")
    dlg.findChild(QObject, "fixedDay").setProperty("value", 5)
    dlg.findChild(QObject, "fixedStart").setProperty("text", this_month)
    QMetaObject.invokeMethod(dlg, "save")
    app.processEvents()

    assert backend.fixedCount == 1
    row = backend.fixedRows[0]
    assert (row["name"], row["amount"], row["day"]) == ("월세", 600_000, 5)
    assert dlg.property("formOpen") is False               # 저장하면 칸이 닫힌다
    # 이번 달치가 바로 적혔고, 그 줄에 규칙 번호가 남는다
    assert [e.ym for e in ws.ledger.entries] == [this_month]
    assert ws.ledger.entries[0].rule == row["rid"]

    # 금액이 비면 거절하고 칸은 열린 채로 둔다
    QMetaObject.invokeMethod(dlg, "openNew")
    app.processEvents()
    dlg.findChild(QObject, "fixedAmount").setProperty("text", "")
    QMetaObject.invokeMethod(dlg, "save")
    app.processEvents()
    assert backend.fixedCount == 1
    assert dlg.property("formOpen") is True


def test_overview_page_loads_with_every_chart():
    """'한눈에' 화면이 뜨고, 추이·막대·도넛이 모두 값을 받는지."""
    app, engine, backend, win = _load()
    backend.loadSample()
    QMetaObject.invokeMethod(win, "openOverview")
    app.processEvents()
    assert win.property("mode") == "overview"

    view = win.findChild(QObject, "overviewView")
    assert view is not None and view.property("visible") is True

    trend = win.findChild(QObject, "overviewTrend")
    bars = win.findChild(QObject, "overviewBars")
    pie = win.findChild(QObject, "overviewPie")
    assert trend is not None and bars is not None and pie is not None

    assert len(trend.property("values")) == backend.months + 1
    rows = bars.property("rows")
    assert len(rows) == 12 and rows[-1]["isThis"]
    slices = pie.property("slices")
    assert slices and abs(sum(s["share"] for s in slices) - 1.0) < 1e-6

    # 계획을 바꾸면 그래프도 따라간다
    before = list(trend.property("values"))
    backend.setProperty("months", backend.months + 6)
    app.processEvents()
    assert len(trend.property("values")) == len(before) + 6


def test_undo_button_follows_the_stack():
    """되돌리기 단추는 되돌릴 게 있을 때만 켜지고, 다시 실행 단추는 그때만 보인다."""
    app, engine, backend, win = _load()
    undo = win.findChild(QObject, "undoButton")
    redo = win.findChild(QObject, "redoButton")
    assert undo is not None and redo is not None
    app.processEvents()
    assert undo.property("enabled") is False
    assert redo.property("visible") is False

    backend.addEntry("2026-11-11", "식비", 12_000, "점심", "")
    app.processEvents()
    assert undo.property("enabled") is True
    assert backend.undoLabel == "가계부 내역 추가"

    backend.undo()
    app.processEvents()
    assert undo.property("enabled") is False
    assert redo.property("visible") is True
