"""QML 브리지(Backend) 동작 검증. 화면 없이 offscreen 으로 실행."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from capital_calc.backend import Backend  # noqa: E402
from capital_calc.model import Plan, sample_plan  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])


def test_add_remove_move_and_summary():
    b = Backend(Plan(months=12, target=1_000_000))
    assert b.itemCount == 0
    b.addItem("현금", 0, 2_000_000, 0, True)          # 0 = 현금/자산
    b.addItem("월세", 5, 100_000, 0, True)            # 5 = 월세
    assert b.itemCount == 2
    assert b.capital == 2_000_000
    assert b.monthlyCost == 100_000
    assert b.net == 2_000_000 - 1_200_000
    assert b.gap == 800_000 - 1_000_000
    assert b.monthsToGoal == -1
    assert len(b.trend) == 13

    b.moveItem(1, -1)
    assert b.items.data(b.items.index(0), b.items.NameRole) == "월세"
    b.updateItem(0, "월세+", 5, 200_000, 0, True)
    assert b.monthlyCost == 200_000
    b.removeItem(0)
    assert b.itemCount == 1 and b.monthlyCost == 0
    b.clearItems()
    assert b.itemCount == 0


def test_properties_and_helpers():
    b = Backend(Plan())
    b.months = 6
    b.target = 123.0
    assert b.months == 6 and b.target == 123.0
    assert b.won(1234) == "1,234원"
    info = b.categoryInfo(2)                           # 2 = 대출/이자
    assert info["usesRate"] and info["isLoan"] and info["dateMode"] == "range"
    assert b.monthlyInterest(1_200_000, 10) == 10_000
    assert len(b.categories) == 10
    assert b.categories[7] == "고정 지출" and b.categories[9] == "일시 지출"
    assert b.categories[3] == "월 수입" and b.categories[4] == "일시 수입"


def test_milestones_and_trend_for():
    b = Backend(Plan(months=12, target=1_500_000))
    b.addItem("현금", 0, 500_000, 0, True)
    b.addItem("수입", 3, 100_000, 0, True)            # 3 = 월 수입
    ms = b.milestones
    assert [m["month"] for m in ms] == [6, 12, 24, 36]
    assert ms[0]["net"] == 500_000 + 100_000 * 6
    assert ms[1]["net"] == 500_000 + 100_000 * 12
    assert ms[0]["reached"] is False and ms[1]["reached"] is True
    assert ms[1]["gap"] == 200_000
    t = b.trendFor(24)
    assert len(t) == 25 and t[24] == b.netAt(24) == 500_000 + 100_000 * 24


def test_loan_dates_and_repayments_via_backend():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    assert b.basisDate == "2026-01-01"
    reps = '[{"date":"2026-07-01","amount":6000000},{"date":"bad","amount":1}]'
    b.addItem("대출", 2, 12_000_000, 10.0, True, "2026-04-01", "", reps)
    m = b.items
    idx = m.index(0)
    assert m.data(idx, m.StartDateRole) == "2026-04-01"
    assert m.data(idx, m.EndDateRole) == ""                       # 종료일 생략 OK
    assert m.data(idx, m.RepaymentsRole) == [{"date": "2026-07-01", "amount": 6_000_000.0}]
    sub = m.data(idx, m.SubTextRole)
    assert "2026-04 ~ 계속" in sub and "중도상환 1건" in sub
    assert m.data(idx, m.MonthlyTextRole) == "3개월 뒤 시작"
    assert b.capital == 0                                          # 0개월엔 대출 전
    assert b.netAt(3) == 12_000_000
    assert abs(b.netAt(7) - (12_000_000 - 6_000_000 - 100_000 * 3 - 50_000 * 1)) < 1e-6

    # 기준일 변경 → 대출이 바로 활성
    b.basisDate = "2026-04-01"
    assert b.capital == 12_000_000 and b.monthlyCost == 100_000
    b.basisDate = "잘못된값"
    assert b.basisDate == "2026-04-01"
    assert b.isValidDate("") and b.isValidDate("2026-05-01") and not b.isValidDate("2026/05")


def test_rent_dates_via_backend():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("월세", 5, 500_000, 0, True, "2026-03-01", "2026-06-01", "[]")   # 3,4,5 개월째 3번
    b.addItem("관리비", 6, 100_000, 0, True, "", "", "[]")                       # 기간 생략 = 계속
    assert b.monthlyCost == 100_000
    assert b.required == 500_000 * 3 + 100_000 * 12
    assert b.items.data(b.items.index(0), b.items.SubTextRole) == "2026-03 ~ 2026-06"


def test_prediction_and_save_to_path(tmp_path):
    b = Backend(Plan(months=12, target=2_000_000, start_date="2026-01-01"))
    b.addItem("현금", 0, 1_000_000, 0, True, "", "", "[]")
    b.addItem("수입", 3, 50_000, 0, True, "", "", "[]")
    assert b.goalMonth == 20
    assert b.goalDateText == "2027년 9월"
    assert b.peakNet >= 2_000_000

    got = {}
    b.saved.connect(lambda p: got.setdefault("saved", p))
    b.loaded.connect(lambda p: got.setdefault("loaded", p))
    target = tmp_path / "sub" / "내계획"
    b.saveTo(str(target))
    assert got["saved"].endswith("내계획.json")
    assert b.dataPath.endswith("내계획.json")
    assert (tmp_path / "sub" / "내계획.json").exists()

    b2 = Backend(Plan())
    b2.loadFrom((tmp_path / "sub" / "내계획.json").as_uri())
    assert b2.itemCount == 2 and b2.target == 2_000_000
    assert b2.dataPath.endswith("내계획.json")

    fails = []
    b2.failed.connect(fails.append)
    b2.loadFrom(str(tmp_path / "없는파일.json"))
    assert fails and "불러오기 실패" in fails[0]


def test_backend_export_and_composition(tmp_path):
    b = Backend(sample_plan())
    got = []
    b.exported.connect(got.append)
    b.exportExcel((tmp_path / "out").as_uri())
    assert got and got[0].endswith("out.xlsx") and (tmp_path / "out.xlsx").exists()

    cap = b.compositionOf("보유 자금")
    assert [c["label"] for c in cap] == ["보유 현금", "적금 (3.5%)", "신용대출 (5%)"]
    assert abs(sum(c["share"] for c in cap) - 1.0) < 1e-9
    assert b.compositionTotal("보유 자금") == 35_000_000
    assert b.compositionOf("없는 그룹") == []


def test_monthly_repay_via_backend():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("대출", 2, 12_000_000, 12.0, True, "", "", "[]", 10.0)
    m = b.items
    idx = m.index(0)
    assert m.data(idx, m.MonthlyRepayRateRole) == 10.0
    sub = m.data(idx, m.SubTextRole)
    assert "월 10% 상환 1,200,000원" in sub and "10개월 완납" in sub
    assert m.data(idx, m.MonthlyTextRole) == "-1,320,000원"      # 이자 12만 + 정기 상환 120만
    assert b.payoffMonths(12_000_000, 10.0) == 10 and b.payoffMonths(1, 0) == 0
    b.updateItem(0, "대출", 2, 12_000_000, 12.0, True, "", "", "[]", 0.0)
    assert m.data(idx, m.MonthlyRepayRateRole) == 0.0
    b.addItem("현금", 0, 1, 0, True)                                # 5인자 호출도 여전히 동작
    assert b.itemCount == 2


def test_grouped_items_proxy():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("월세A", 5, 100, 0, True)        # 5 = 월세
    b.addItem("현금", 0, 500, 0, True)         # 0 = 현금/자산
    b.addItem("월세B", 5, 200, 0, True)
    g = b.groupedItems
    names = [g.data(g.index(r, 0), b.items.NameRole) for r in range(g.rowCount())]
    assert names == ["현금", "월세A", "월세B"]                      # 분류 순(자본 → 지출), 같은 분류는 원본 순
    rows = [g.data(g.index(r, 0), b.items.SourceRowRole) for r in range(g.rowCount())]
    assert rows == [1, 0, 2]

    gs = b.groupSummary("월세")
    assert gs["count"] == 2 and gs["total"] == 300 and gs["monthly"] == -300 and gs["catIndex"] == 5
    assert b.groupSummary("없음")["count"] == 0

    b.toggleGroup(5)                                                # 월세 접기
    assert b.isGroupCollapsed(5) and g.rowCount() == 1
    b.groupByCategory = False                                       # 묶기 해제 → 모두 펼침
    assert not b.isGroupCollapsed(5) and g.rowCount() == 3
    b.groupByCategory = True

    # 원본에서 삭제/이동해도 프록시가 따라온다
    b.removeItem(0)
    names = [g.data(g.index(r, 0), b.items.NameRole) for r in range(g.rowCount())]
    assert names == ["현금", "월세B"]


def test_backend_scenarios(tmp_path):
    b = Backend(Plan(months=12, target=5_000_000, start_date="2026-01-01"))
    b.addItem("현금", 0, 1_000_000, 0, True)
    b.addItem("급여", 3, 300_000, 0, True)
    assert b.scenarioNames == ["시나리오 1"] and b.scenarioCount == 1 and b.activeScenario == 0

    changes = []
    b.scenariosChanged.connect(lambda: changes.append(1))
    b.duplicateScenario()
    assert b.scenarioCount == 2 and b.activeScenario == 1 and b.itemCount == 2 and changes
    b.renameScenario(1, "부업")
    b.addItem("부업", 3, 200_000, 0, True)
    assert b.scenarioNames == ["시나리오 1", "부업"] and b.itemCount == 3

    rows = b.compareRows()
    assert [r["name"] for r in rows] == ["시나리오 1", "부업"]
    assert rows[1]["active"] and rows[1]["diff"] == 0
    assert rows[0]["net"] == 1_000_000 + 300_000 * 12 and rows[1]["net"] == 1_000_000 + 500_000 * 12
    assert abs(rows[0]["diff"] - (-200_000 * 12)) < 1e-6
    assert rows[1]["goalText"].startswith("2026년 9월")       # 1,000,000 + 500,000*8 = 5,000,000 → 8개월
    tr = b.compareTrends(6)
    assert len(tr) == 2 and len(tr[0]["values"]) == 7 and tr[1]["active"] and tr[1]["goalMonth"] == 8

    b.activeScenario = 0                                       # 전환하면 리스트·요약이 그 시나리오 것
    assert b.itemCount == 2 and b.monthlyIncome == 300_000
    b.months = 24
    assert b.compareRows()[0]["net"] == 1_000_000 + 300_000 * 24

    b.saveTo(str(tmp_path / "ws"))                             # 시나리오 전체가 저장/복원
    b2 = Backend(Plan())
    b2.loadFrom(str(tmp_path / "ws.json"))
    assert b2.scenarioNames == ["시나리오 1", "부업"] and b2.activeScenario == 0 and b2.months == 24
    b2.activeScenario = 1
    assert b2.itemCount == 3

    b2.loadSample()                                            # 현재 시나리오만 교체, 이름 유지
    assert b2.scenarioNames == ["시나리오 1", "부업"] and b2.itemCount == len(sample_plan().items)

    fails = []
    b2.failed.connect(fails.append)
    b2.removeScenario(1)
    assert b2.scenarioCount == 1 and b2.activeScenario == 0 and b2.itemCount == 2
    b2.removeScenario(0)
    assert b2.scenarioCount == 1 and fails


def test_backend_fixed_cost_and_dated_once():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("현금", 0, 10_000_000, 0, True)
    b.addItem("보험료", 7, 120_000, 0, True, "", "", "[]")          # 7 = 고정 지출, 기간 생략 = 계속
    assert b.monthlyCost == 120_000 and b.netAt(12) == 10_000_000 - 120_000 * 12

    info = b.categoryInfo(7)
    assert info["dateMode"] == "range" and info["usesDates"] and info["amountLabel"] == "월 고정 지출"
    assert b.categoryInfo(9)["dateMode"] == "once"                  # 9 = 일시 지출

    b.addItem("통신비", 7, 50_000, 0, True, "2026-04-01", "2026-07-01", "[]")   # 3,4,5 개월째만
    assert b.monthlyCost == 120_000                                 # 0개월엔 아직 아님
    assert b.netAt(12) == 10_000_000 - 120_000 * 12 - 50_000 * 3

    b.addItem("이사비", 9, 3_000_000, 0, True, "2026-07-01", "", "[]")          # 6개월째 지출
    assert b.onceCost == 3_000_000                                  # 12개월 안에 나감
    assert b.netAt(5) == 10_000_000 - 120_000 * 5 - 50_000 * 2      # 아직 안 나감
    assert b.netAt(6) == 10_000_000 - 120_000 * 6 - 50_000 * 3 - 3_000_000

    b.months = 3                                                    # 기간 밖이면 요약에서 빠진다
    assert b.onceCost == 0

    idx = b.items.index(3, 0)                                       # 목록 표시
    assert "2026-07" in b.items.data(idx, b.items.SubTextRole)
    assert b.items.data(idx, b.items.MonthlyTextRole) == "6개월 뒤 일시 -3,000,000원"
    assert b.items.data(idx, b.items.MonthlyKindRole) == "once"


def test_backend_repay_method():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    assert [m["value"] for m in b.repayMethods] == ["bullet", "equal_principal", "equal_payment", "rate"]
    assert b.repayMethods[2]["label"] == "원리금 균등"

    # 2 = 대출/이자, 원금 자본 미포함 → 원리금이 그대로 월 지출
    b.addItem("대출", 2, 12_000_000, 12.0, False, "2026-01-01", "2027-01-01", "[]", 0.0, "equal_principal")
    idx = b.items.index(0, 0)
    assert b.items.data(idx, b.items.RepayMethodRole) == "equal_principal"
    assert "원금 균등 12개월" in b.items.data(idx, b.items.SubTextRole)
    assert b.monthlyCost == 1_120_000

    b.updateItem(0, "대출", 2, 12_000_000, 12.0, False, "2026-01-01", "2027-01-01", "[]", 0.0, "equal_payment")
    pay = b.monthlyCost
    assert abs(pay - 1_066_190) < 1_000 and abs(b.netAt(12) + pay * 12) < 1e-6

    pv = b.loanPreview(12_000_000, 12.0, "equal_payment", "2026-01-01", "2027-01-01", 0)
    assert pv["months"] == 12 and not pv["needsEnd"]
    assert abs(pv["first"] - pv["last"]) < 1e-6 and "원리금 균등" in pv["text"]
    assert b.loanPreview(12_000_000, 12.0, "equal_payment", "2026-01-01", "", 0)["needsEnd"]
    assert "원금을 입력" in b.loanPreview(0, 12.0, "bullet", "", "", 0)["text"]
    assert "만기에 원금" in b.loanPreview(12_000_000, 12.0, "bullet", "2026-01-01", "2027-01-01", 0)["text"]
    assert "완납" in b.loanPreview(12_000_000, 12.0, "rate", "2026-01-01", "", 10.0)["text"]

    # 방식을 안 주면 예전처럼 상환율로 동작
    b.addItem("옛날", 2, 12_000_000, 12.0, True, "", "", "[]", 10.0)
    assert b.items.data(b.items.index(1, 0), b.items.RepayMethodRole) == "rate"


def test_backend_shortfall():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("현금", 0, 3_000_000, 0, True)
    assert b.shortfall["has"] is False and b.shortfall["month"] == -1

    b.addItem("월세", 5, 500_000, 0, True)
    sf = b.shortfall
    assert sf["has"] and sf["month"] == 7 and sf["dateText"] == "2026년 8월"
    assert sf["net"] == 3_000_000 - 500_000 * 7
    assert sf["minMonth"] == 36 and sf["minNet"] == 3_000_000 - 500_000 * 36
    assert sf["minDateText"] == "2029년 1월" and sf["months"] == 30 and sf["horizon"] == 36


def test_backend_income_dates():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    assert len(b.categories) == 10 and b.categories[4] == "일시 수입"

    info = b.categoryInfo(3)                                  # 월 수입
    assert info["dateMode"] == "range" and info["usesDates"] and info["flow"] == "income"
    once = b.categoryInfo(4)                                  # 일시 수입
    assert once["dateMode"] == "once" and once["onceWord"] == "수입"
    assert b.categoryInfo(9)["onceWord"] == "지출"              # 일시 지출

    # 월 수입에 적용 기간
    b.addItem("급여", 3, 2_000_000, 0, True, "2026-03-01", "2026-07-01")
    idx = b.items.index(0, 0)
    assert b.items.data(idx, b.items.SubTextRole) == "2026-03 ~ 2026-07"
    assert b.items.data(idx, b.items.MonthlyTextRole) == "2개월 뒤 시작"
    assert b.monthlyIncome == 0                               # 0개월에는 아직
    assert b.netAt(6) == 2_000_000 * 4 and b.netAt(12) == 2_000_000 * 4

    # 일시 수입에 수입일
    b.addItem("성과급", 4, 5_000_000, 0, True, "2026-05-01")
    idx = b.items.index(1, 0)
    assert "기준일에 수입" not in b.items.data(idx, b.items.SubTextRole)
    assert "4개월 뒤 수입" in b.items.data(idx, b.items.SubTextRole)
    assert b.items.data(idx, b.items.MonthlyTextRole) == "4개월 뒤 일시 +5,000,000원"
    assert b.items.data(idx, b.items.MonthlyKindRole) == "income"
    assert b.onceIncome == 5_000_000 and b.onceCost == 0
    assert b.netAt(4) == 2_000_000 * 2 + 5_000_000
