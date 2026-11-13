"""QML 브리지(Backend) 동작 검증. 화면 없이 offscreen 으로 실행."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from capital_calc.backend import Backend  # noqa: E402
from capital_calc.model import Category, Item, Plan, sample_plan  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])


def test_add_remove_move_and_summary():
    b = Backend(Plan(months=12, target=1_000_000))
    assert b.itemCount == 0
    b.addItem("현금", 0, 2_000_000, 0, True)          # 0 = 현금/자산
    b.addItem("월세", 6, 100_000, 0, True)            # 6 = 월세
    assert b.itemCount == 2
    assert b.capital == 2_000_000
    assert b.monthlyCost == 100_000
    assert b.net == 2_000_000 - 1_200_000
    assert b.gap == 800_000 - 1_000_000
    assert b.monthsToGoal == -1
    assert len(b.trend) == 13

    b.moveItem(1, -1)
    assert b.items.data(b.items.index(0), b.items.NameRole) == "월세"
    b.updateItem(0, "월세+", 6, 200_000, 0, True)
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
    info = b.categoryInfo(3)                           # 3 = 대출/이자
    assert info["usesRate"] and info["isLoan"] and info["dateMode"] == "range"
    assert b.monthlyInterest(1_200_000, 10) == 10_000
    assert len(b.categories) == 11
    assert b.categories[8] == "고정 지출" and b.categories[10] == "일시 지출"
    assert b.categories[4] == "월 수입" and b.categories[5] == "일시 수입"


def test_milestones_and_trend_for():
    b = Backend(Plan(months=12, target=1_500_000))
    b.addItem("현금", 0, 500_000, 0, True)
    b.addItem("수입", 4, 100_000, 0, True)            # 4 = 월 수입
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
    b.addItem("대출", 3, 12_000_000, 10.0, True, "2026-04-01", "", reps)
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
    b.addItem("월세", 6, 500_000, 0, True, "2026-03-01", "2026-06-01", "[]")   # 3,4,5 개월째 3번
    b.addItem("관리비", 7, 100_000, 0, True, "", "", "[]")                       # 기간 생략 = 계속
    assert b.monthlyCost == 100_000
    assert b.required == 500_000 * 3 + 100_000 * 12
    assert b.items.data(b.items.index(0), b.items.SubTextRole) == "2026-03 ~ 2026-06"


def test_prediction_and_save_to_path(tmp_path):
    b = Backend(Plan(months=12, target=2_000_000, start_date="2026-01-01"))
    b.addItem("현금", 0, 1_000_000, 0, True, "", "", "[]")
    b.addItem("수입", 4, 50_000, 0, True, "", "", "[]")
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
    assert [c["label"] for c in cap] == ["보유 현금", "예금 (3.5%)", "신용대출 (5%)"]
    assert abs(sum(c["share"] for c in cap) - 1.0) < 1e-9
    assert b.compositionTotal("보유 자금") == 35_000_000
    assert b.compositionOf("없는 그룹") == []


def test_monthly_repay_via_backend():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("대출", 3, 12_000_000, 12.0, True, "", "", "[]", 10.0)
    m = b.items
    idx = m.index(0)
    assert m.data(idx, m.MonthlyRepayRateRole) == 10.0
    sub = m.data(idx, m.SubTextRole)
    assert "월 10% 상환 1,200,000원" in sub and "10개월 완납" in sub
    assert m.data(idx, m.MonthlyTextRole) == "-1,320,000원"      # 이자 12만 + 정기 상환 120만
    assert b.payoffMonths(12_000_000, 10.0) == 10 and b.payoffMonths(1, 0) == 0
    b.updateItem(0, "대출", 3, 12_000_000, 12.0, True, "", "", "[]", 0.0)
    assert m.data(idx, m.MonthlyRepayRateRole) == 0.0
    b.addItem("현금", 0, 1, 0, True)                                # 5인자 호출도 여전히 동작
    assert b.itemCount == 2


def test_grouped_items_proxy():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("월세A", 6, 100, 0, True)        # 6 = 월세
    b.addItem("현금", 0, 500, 0, True)         # 0 = 현금/자산
    b.addItem("월세B", 6, 200, 0, True)
    g = b.groupedItems
    names = [g.data(g.index(r, 0), b.items.NameRole) for r in range(g.rowCount())]
    assert names == ["현금", "월세A", "월세B"]                      # 분류 순(자본 → 지출), 같은 분류는 원본 순
    rows = [g.data(g.index(r, 0), b.items.SourceRowRole) for r in range(g.rowCount())]
    assert rows == [1, 0, 2]

    gs = b.groupSummary("월세")
    assert gs["count"] == 2 and gs["total"] == 300 and gs["monthly"] == -300 and gs["catIndex"] == 6
    assert b.groupSummary("없음")["count"] == 0

    # 접기는 걸러내기가 아니라 화면에서 숨기기다 (줄을 빼면 그 분류의 헤더까지 사라진다)
    b.toggleGroup(6)                                                # 월세 접기
    assert b.isGroupCollapsed(6) and g.rowCount() == 3
    b.groupByCategory = False                                       # 묶기 해제 → 모두 펼침
    assert not b.isGroupCollapsed(6) and g.rowCount() == 3
    # 묶기를 끄면 같은 프록시가 원본 순서로 돌아간다 (ListView 의 모델은 바꾸지 않는다)
    assert [g.data(g.index(r, 0), b.items.NameRole) for r in range(3)] == ["월세A", "현금", "월세B"]
    assert [g.data(g.index(r, 0), b.items.SourceRowRole) for r in range(3)] == [0, 1, 2]
    b.groupByCategory = True
    assert [g.data(g.index(r, 0), b.items.NameRole) for r in range(3)] == ["현금", "월세A", "월세B"]
    b.groupByCategory = False
    b.groupByCategory = True

    # 원본에서 삭제/이동해도 프록시가 따라온다
    b.removeItem(0)
    names = [g.data(g.index(r, 0), b.items.NameRole) for r in range(g.rowCount())]
    assert names == ["현금", "월세B"]


def test_backend_scenarios(tmp_path):
    b = Backend(Plan(months=12, target=5_000_000, start_date="2026-01-01"))
    b.addItem("현금", 0, 1_000_000, 0, True)
    b.addItem("급여", 4, 300_000, 0, True)
    assert b.scenarioNames == ["시나리오 1"] and b.scenarioCount == 1 and b.activeScenario == 0

    changes = []
    b.scenariosChanged.connect(lambda: changes.append(1))
    b.duplicateScenario()
    assert b.scenarioCount == 2 and b.activeScenario == 1 and b.itemCount == 2 and changes
    b.renameScenario(1, "부업")
    b.addItem("부업", 4, 200_000, 0, True)
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
    b.addItem("보험료", 8, 120_000, 0, True, "", "", "[]")          # 8 = 고정 지출, 기간 생략 = 계속
    assert b.monthlyCost == 120_000 and b.netAt(12) == 10_000_000 - 120_000 * 12

    info = b.categoryInfo(8)
    assert info["dateMode"] == "range" and info["usesDates"] and info["amountLabel"] == "월 고정 지출"
    assert b.categoryInfo(10)["dateMode"] == "once"                  # 10 = 일시 지출

    b.addItem("통신비", 8, 50_000, 0, True, "2026-04-01", "2026-07-01", "[]")   # 3,4,5 개월째만
    assert b.monthlyCost == 120_000                                 # 0개월엔 아직 아님
    assert b.netAt(12) == 10_000_000 - 120_000 * 12 - 50_000 * 3

    b.addItem("이사비", 10, 3_000_000, 0, True, "2026-07-01", "", "[]")          # 6개월째 지출
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

    # 3 = 대출/이자, 원금 자본 미포함 → 원리금이 그대로 월 지출
    b.addItem("대출", 3, 12_000_000, 12.0, False, "2026-01-01", "2027-01-01", "[]", 0.0, "equal_principal")
    idx = b.items.index(0, 0)
    assert b.items.data(idx, b.items.RepayMethodRole) == "equal_principal"
    assert "원금 균등 12개월" in b.items.data(idx, b.items.SubTextRole)
    assert b.monthlyCost == 1_120_000

    b.updateItem(0, "대출", 3, 12_000_000, 12.0, False, "2026-01-01", "2027-01-01", "[]", 0.0, "equal_payment")
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
    b.addItem("옛날", 3, 12_000_000, 12.0, True, "", "", "[]", 10.0)
    assert b.items.data(b.items.index(1, 0), b.items.RepayMethodRole) == "rate"


def test_backend_shortfall():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("현금", 0, 3_000_000, 0, True)
    assert b.shortfall["has"] is False and b.shortfall["month"] == -1

    b.addItem("월세", 6, 500_000, 0, True)
    sf = b.shortfall
    assert sf["has"] and sf["month"] == 7 and sf["dateText"] == "2026년 8월"
    assert sf["net"] == 3_000_000 - 500_000 * 7
    assert sf["minMonth"] == 36 and sf["minNet"] == 3_000_000 - 500_000 * 36
    assert sf["minDateText"] == "2029년 1월" and sf["months"] == 30 and sf["horizon"] == 36


def test_backend_income_dates():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    assert len(b.categories) == 11 and b.categories[5] == "일시 수입"

    info = b.categoryInfo(4)                                  # 월 수입
    assert info["dateMode"] == "range" and info["usesDates"] and info["flow"] == "income"
    once = b.categoryInfo(5)                                  # 일시 수입
    assert once["dateMode"] == "once" and once["onceWord"] == "수입"
    assert b.categoryInfo(10)["onceWord"] == "지출"              # 일시 지출

    # 월 수입에 적용 기간
    b.addItem("급여", 4, 2_000_000, 0, True, "2026-03-01", "2026-07-01")
    idx = b.items.index(0, 0)
    assert b.items.data(idx, b.items.SubTextRole) == "2026-03 ~ 2026-07"
    assert b.items.data(idx, b.items.MonthlyTextRole) == "2개월 뒤 시작"
    assert b.monthlyIncome == 0                               # 0개월에는 아직
    assert b.netAt(6) == 2_000_000 * 4 and b.netAt(12) == 2_000_000 * 4

    # 일시 수입에 수입일
    b.addItem("성과급", 5, 5_000_000, 0, True, "2026-05-01")
    idx = b.items.index(1, 0)
    assert "기준일에 수입" not in b.items.data(idx, b.items.SubTextRole)
    assert "4개월 뒤 수입" in b.items.data(idx, b.items.SubTextRole)
    assert b.items.data(idx, b.items.MonthlyTextRole) == "4개월 뒤 일시 +5,000,000원"
    assert b.items.data(idx, b.items.MonthlyKindRole) == "income"
    assert b.onceIncome == 5_000_000 and b.onceCost == 0
    assert b.netAt(4) == 2_000_000 * 2 + 5_000_000


def test_backend_deposit_return():
    b = Backend(Plan(months=36, target=0, start_date="2026-01-01"))
    assert b.categoryInfo(9)["returnable"] and not b.categoryInfo(10)["returnable"]

    b.addItem("현금", 0, 100_000_000, 0, True)
    b.addItem("전세 보증금", 9, 80_000_000, 0, True, "2026-04-01", "2028-04-01")   # 9 = 주거
    sub = b.items.data(b.items.index(1, 0), b.items.SubTextRole)
    assert "전세 · 2026-04 입주" in sub and "2028-04 반환 (27개월 뒤)" in sub

    assert b.netAt(3) == 20_000_000 and b.netAt(26) == 20_000_000
    assert b.netAt(27) == 100_000_000
    # 나간 것은 나간 대로, 돌려받은 것은 일시 수입으로 잡힌다
    assert b.onceCost == 80_000_000 and b.onceIncome == 80_000_000

    b.updateItem(1, "전세 보증금", 9, 80_000_000, 0, True, "2026-04-01", "")
    assert b.netAt(27) == 20_000_000 and b.onceCost == 80_000_000 and b.onceIncome == 0

    # 기준일 전에 낸 보증금은 빼지 않고, 돌려받는 것만 들어온다
    b.updateItem(1, "전세 보증금", 9, 80_000_000, 0, True, "2024-04-01", "2027-04-01")
    assert b.onceCost == 0 and b.netAt(0) == 100_000_000
    assert b.netAt(14) == 100_000_000 and b.netAt(15) == 180_000_000


def test_backend_housing():
    b = Backend(Plan(months=36, target=0, start_date="2026-01-01"))
    assert [h["value"] for h in b.housingTypes] == ["jeonse", "banjeonse", "wolse", "buy"]
    assert b.housingTypes[3]["label"] == "매매"
    assert b.categoryInfo(9)["isHousing"] and not b.categoryInfo(10)["isHousing"]

    hi = b.housingInfo("buy")
    assert hi["amountLabel"] == "매매가" and not hi["returnable"] and not hi["usesRent"]
    assert b.housingInfo("banjeonse")["usesRent"] and b.housingInfo("")["label"] == "전세"

    b.addItem("현금", 0, 300_000_000, 0, True)
    # 9 = 주거, 반전세 보증금 1억 + 월세 60만, 2026-04 입주 ~ 2028-04 만기
    b.addItem("신혼집", 9, 100_000_000, 0, True, "2026-04-01", "2028-04-01", "[]", 0, "", "banjeonse", 600_000)
    idx = b.items.index(1, 0)
    assert b.items.data(idx, b.items.HousingTypeRole) == "banjeonse"
    assert b.items.data(idx, b.items.MonthlyRole) == 600_000
    sub = b.items.data(idx, b.items.SubTextRole)
    assert "반전세 · 2026-04 입주" in sub and "월세 600,000원" in sub and "2028-04 반환" in sub
    assert b.netAt(3) == 200_000_000 and b.netAt(27) == 300_000_000 - 600_000 * 24

    # 매매로 바꾸면 월세가 사라지고 돌려받지 않는다
    b.updateItem(1, "신혼집", 9, 100_000_000, 0, True, "2026-04-01", "2028-04-01", "[]", 0, "", "buy", 600_000)
    idx = b.items.index(1, 0)
    assert b.items.data(idx, b.items.MonthlyRole) == 600_000      # 값은 남아 있지만
    assert b.netAt(6) == 200_000_000                               # 월세로 나가지 않고
    assert b.netAt(27) == 200_000_000                              # 돌려받지도 않는다


def test_backend_saving():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    assert b.categories[2] == "적금/저축(월)"
    info = b.categoryInfo(2)
    assert info["group"] == "자본" and info["usesDates"] and info["usesRate"]
    assert info["amountLabel"] == "월 납입액"

    b.addItem("현금", 0, 10_000_000, 0, True)
    b.addItem("청약", 2, 500_000, 0, True, "2026-01-01", "2027-01-01")
    assert b.monthlyCost == 500_000 and b.capital == 10_000_000
    assert b.netAt(6) == 10_000_000 and b.netAt(12) == 10_000_000      # 순 자본은 그대로
    assert "12개월 후 6,000,000원 (12회 납입)" in b.items.data(b.items.index(1, 0), b.items.SubTextRole)


def test_backend_ledger():
    from datetime import date
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    assert b.ledgerYears == [] and b.ledgerPeriod == "" and b.ledgerPeriodText == "기록 없음"
    assert b.ledgerItems.rowCount() == 0
    assert b.today == date.today().isoformat()
    assert [c["value"] for c in b.ledgerCategories][:2] == ["급여", "부업"]
    assert b.ledgerKindOf("급여") == "income" and b.ledgerKindOf("식비") == "cost"

    changes = []
    b.ledgerChanged.connect(lambda: changes.append(1))

    # 첫 기록을 넣으면 그 달로 기간이 맞춰진다
    b.addEntry("2026-03-15", "식비", 12_000, "점심")
    assert changes and b.ledgerYear == "2026" and b.ledgerMonth == 3
    assert b.ledgerPeriod == "2026-03" and b.ledgerPeriodText == "2026년 3월"
    assert b.ledgerItems.rowCount() == 1

    b.addEntry("2026-03-25", "급여", 2_000_000, "회사")
    b.addEntry("2026-04-02", "교통", 50_000)
    assert b.ledgerSummary == {"income": 2_000_000, "cost": 12_000, "net": 1_988_000, "count": 2}
    assert b.ledgerItems.rowCount() == 2                      # 3월만 보인다

    m = b.ledgerItems
    idx = m.index(0, 0)                                        # 최신(3/25)이 위
    assert m.data(idx, m.DateTextRole) == "3월 25일"
    assert m.data(idx, m.CategoryRole) == "급여" and m.data(idx, m.KindRole) == "income"
    assert m.data(idx, m.AmountTextRole) == "+2,000,000원"
    assert m.data(idx, m.SourceRowRole) == 1

    b.ledgerMonth = 4
    assert b.ledgerItems.rowCount() == 1 and b.ledgerSummary["cost"] == 50_000
    b.ledgerMonth = 0                                          # 그 해 전체
    assert b.ledgerPeriod == "2026" and b.ledgerSummary["count"] == 3
    assert [r["month"] for r in b.ledgerYearMonths if r["count"]] == [3, 4]
    assert b.ledgerByCategory("cost")[0]["label"] == "교통"
    assert b.ledgerYearTotals[0]["year"] == "2026"

    # 수정 / 삭제는 원본 번호로
    b.updateEntry(0, "2026-03-15", "식비", 30_000, "점심")
    assert b.ledgerSummary["cost"] == 80_000
    b.removeEntry(2)
    assert b.ledgerSummary["count"] == 2

    b.clearLedger()
    assert b.ledgerItems.rowCount() == 0 and b.ledgerYears == []


def test_backend_ledger_save_and_export(tmp_path):
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("현금", 0, 1_000_000, 0, True)
    b.addEntry("2026-03-15", "식비", 12_000, "점심")
    b.saveTo(str(tmp_path / "ws"))

    b2 = Backend(Plan())
    b2.loadFrom(str(tmp_path / "ws.json"))
    assert b2.ledgerSummary["count"] == 1 and b2.ledgerPeriod == "2026-03"

    got = []
    b2.exported.connect(got.append)
    b2.exportExcel((tmp_path / "out").as_uri())
    from openpyxl import load_workbook
    wb = load_workbook(tmp_path / "out.xlsx")
    assert "가계부 내역" in wb.sheetnames and "가계부 월별" in wb.sheetnames
    assert wb["가계부 월별"].cell(row=2, column=1).value == "2026-03"


def test_backend_ledger_filters_and_repeat():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addEntry("2026-01-10", "급여", 2_000_000, "회사")
    b.addEntry("2026-01-12", "식비", 30_000, "김밥천국", "점심")
    b.addEntry("2026-01-20", "교통", 50_000, "지하철")

    assert b.ledgerUsedCategories == ["전체", "교통", "급여", "식비"]
    assert not b.ledgerFiltered and b.ledgerItems.rowCount() == 3

    b.ledgerQuery = "회사"
    assert b.ledgerFiltered and b.ledgerItems.rowCount() == 1
    assert b.ledgerFilteredSummary["income"] == 2_000_000
    b.ledgerQuery = ""

    b.ledgerKindFilter = "cost"
    assert b.ledgerItems.rowCount() == 2 and b.ledgerFilteredSummary["cost"] == 80_000
    b.ledgerCategoryFilter = "식비"
    assert b.ledgerItems.rowCount() == 1
    b.clearLedgerFilters()
    assert not b.ledgerFiltered and b.ledgerItems.rowCount() == 3

    # 그 달에 없는 분류가 걸려 있으면 달을 옮길 때 저절로 풀린다
    b.ledgerCategoryFilter = "교통"
    b.ledgerMonth = 2
    assert b.ledgerCategoryFilter == ""

    # 날짜 구분줄
    info = b.ledgerDayInfo("2026-01-12")
    assert info["label"] == "1월 12일 (월)" and info["net"] == -30_000

    # 지난달 대비 (1월엔 비교 대상이 없다)
    b.ledgerMonth = 1
    assert b.ledgerPrev["has"] is False
    b.addEntry("2026-02-10", "식비", 40_000)
    b.ledgerMonth = 2
    prev = b.ledgerPrev
    assert prev["has"] and prev["label"] == "지난달" and prev["cost"] == 80_000
    assert prev["costDiff"] == -40_000 and prev["costPct"] == -50.0


def test_backend_ledger_repeat_and_copy():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addEntryRepeat("2026-01-31", "보험", 50_000, "실손", "", 3)
    assert b.ledgerSummary["count"] == 1                       # 1월엔 한 건
    assert b.ledgerYear == "2026" and b.ledgerMonth == 1
    b.ledgerMonth = 2
    assert b.ledgerItems.rowCount() == 1
    assert b.ledgerItems.data(b.ledgerItems.index(0, 0), b.ledgerItems.DateRole) == "2026-02-28"

    # 지난달 복사
    b.ledgerMonth = 1
    b.addEntry("2026-01-05", "주거/관리비", 600_000, "월세")
    b.ledgerMonth = 2
    assert b.canCopyPreviousMonth
    b.copyPreviousMonth()
    assert b.ledgerSummary["count"] == 2                       # 보험은 이미 있어 월세만 들어온다
    b.copyPreviousMonth()
    assert b.ledgerSummary["count"] == 2                       # 두 번 눌러도 늘지 않는다

    b.ledgerMonth = 0
    assert not b.canCopyPreviousMonth                           # 연 단위에서는 못 쓴다


def test_backend_plan_vs_actual(tmp_path):
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    assert b.planVsActual()["has"] is False            # 가계부가 비었으면 비교할 게 없다

    b.addItem("급여", 4, 2_000_000, 0, True)           # 4 = 월 수입
    b.addItem("월세", 6, 500_000, 0, True)             # 6 = 월세
    b.addEntry("2026-02-10", "급여", 1_800_000, "회사")
    b.addEntry("2026-02-12", "식비", 600_000)

    pva = b.planVsActual()
    assert pva["has"] and pva["months"] == 1
    assert pva["planIn"] == 2_000_000 and pva["planOut"] == 500_000
    assert pva["actIn"] == 1_800_000 and pva["actOut"] == 600_000
    assert pva["inDiff"] == -200_000 and pva["outDiff"] == 100_000
    assert pva["netDiff"] == 1_200_000 - 1_500_000
    assert pva["outPct"] == 20.0

    # 연 단위로 보면 기준일 이후 달을 모두 합친다
    b.ledgerMonth = 0
    year = b.planVsActual()
    assert year["months"] == 12 and year["planOut"] == 500_000 * 12

    # 기준일보다 앞선 기록은 계획에 없다
    b2 = Backend(Plan(months=12, target=0, start_date="2027-01-01"))
    b2.addItem("월세", 6, 500_000, 0, True)
    b2.addEntry("2026-02-10", "식비", 10_000)
    assert b2.planVsActual()["has"] is False


def test_export_ledger_plan_columns(tmp_path):
    from capital_calc.ledger import Entry, Ledger
    from capital_calc.export_excel import export_plan
    from capital_calc.model import Category, Item
    from openpyxl import load_workbook
    p = Plan(months=12, start_date="2026-01-01")
    p.add(Item("월세", Category.RENT, 500_000))
    lg = Ledger([Entry("2026-02-10", "식비", 600_000)])
    wb = load_workbook(export_plan(p, tmp_path / "l.xlsx", ledger=lg))
    ws = wb["가계부 월별"]
    assert ws.cell(row=1, column=7).value == "계획 지출"
    assert ws.cell(row=2, column=7).value == 500_000
    assert ws.cell(row=2, column=8).value == 100_000


def test_backend_budgets(tmp_path):
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    assert not b.hasBudgets and b.ledgerBudgets == []
    assert [r["category"] for r in b.budgetEditRows][:2] == ["식비", "주거/관리비"]

    b.addEntry("2026-01-05", "식비", 300_000)
    b.addEntry("2026-01-10", "교통", 120_000)
    b.setBudget("식비", 400_000)
    assert b.hasBudgets and b.budgetMonths == 1

    rows = {r["category"]: r for r in b.ledgerBudgets}
    assert rows["식비"]["ratio"] == 0.75 and rows["교통"]["limit"] == 0
    assert b.ledgerBudgetTotals == {"limit": 400_000, "spent": 300_000, "left": 100_000,
                                    "ratio": 0.75, "over": False, "count": 1}

    b.ledgerMonth = 0
    assert b.budgetMonths == 12 and b.ledgerBudgetTotals["limit"] == 400_000 * 12
    b.ledgerMonth = 1

    b.fillBudgetsFromPeriod()
    assert b.ledgerBudgetTotals["limit"] == 420_000          # 식비 300,000 + 교통 120,000
    assert b.ledgerBudgetTotals["over"] is False

    b.setBudget("식비", 0)
    assert "식비" not in [r["category"] for r in b.budgetEditRows if r["limit"] > 0]

    b.clearBudgets()
    assert not b.hasBudgets

    # 저장 / 불러오기에 예산이 따라간다
    b.setBudget("통신", 90_000)
    b.saveTo(str(tmp_path / "ws"))
    b2 = Backend(Plan())
    b2.loadFrom(str(tmp_path / "ws.json"))
    assert b2.hasBudgets and b2.ledgerBudgets[0]["limit"] == 90_000


def test_export_budget_sheet(tmp_path):
    from capital_calc.ledger import Entry, Ledger
    from capital_calc.export_excel import export_plan
    from openpyxl import load_workbook
    lg = Ledger([Entry("2026-01-05", "식비", 300_000)])
    wb = load_workbook(export_plan(Plan(months=12, start_date="2026-01-01"), tmp_path / "a.xlsx", ledger=lg))
    assert "가계부 예산" not in wb.sheetnames          # 예산이 없으면 시트도 없다

    lg.set_budget("식비", 400_000)
    wb = load_workbook(export_plan(Plan(months=12, start_date="2026-01-01"), tmp_path / "b.xlsx", ledger=lg))
    ws = wb["가계부 예산"]
    assert ws.cell(row=1, column=2).value == "한 달 예산"
    assert ws.cell(row=2, column=1).value == "식비"
    assert ws.cell(row=2, column=2).value == 400_000
    assert ws.cell(row=2, column=4).value == -100_000


def test_ledger_maps_always_complete():
    """QML 바인딩은 숨겨진 카드의 값도 계산한다. 비어 있어도 칸이 다 있어야 TypeError 가 안 난다."""
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    pva_keys = {"has", "scenario", "months", "planIn", "planOut", "planNet",
                "actIn", "actOut", "actNet", "inDiff", "outDiff", "netDiff", "outPct"}
    prev_keys = {"has", "label", "income", "cost", "net",
                 "incomeDiff", "costDiff", "incomePct", "costPct"}

    # 가계부가 비었을 때 (기간 자체가 없다)
    assert set(b.planVsActual()) == pva_keys and b.planVsActual()["outPct"] == 0.0
    assert set(b.ledgerPrev) == prev_keys

    # 기록은 있지만 계획이 없을 때 / 지난달이 없을 때
    b.addEntry("2026-01-10", "식비", 10_000)
    assert set(b.planVsActual()) == pva_keys and not b.planVsActual()["has"]
    assert set(b.ledgerPrev) == prev_keys and not b.ledgerPrev["has"]

    # 값이 있을 때도 키는 그대로
    b.addItem("월세", 6, 500_000, 0, True)
    assert set(b.planVsActual()) == pva_keys and b.planVsActual()["has"]
    b.addEntry("2026-02-10", "식비", 20_000)
    b.ledgerMonth = 2
    assert set(b.ledgerPrev) == prev_keys and b.ledgerPrev["has"]


def test_setbudget_does_not_rebuild_ledger():
    """예산 슬라이더를 끌 때 가계부 집계까지 다시 계산되면 느려진다."""
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addEntry("2026-01-10", "식비", 10_000)

    ledger_hits, budget_hits, resets = [], [], []
    b.ledgerChanged.connect(lambda: ledger_hits.append(1))
    b.budgetsChanged.connect(lambda: budget_hits.append(1))
    b.ledgerItems.modelReset.connect(lambda: resets.append(1))

    for v in range(100_000, 600_000, 100_000):
        b.setBudget("식비", v)
    assert len(budget_hits) == 5
    assert ledger_hits == [] and resets == []          # 내역 모델은 건드리지 않는다
    assert b.ledgerBudgets[0]["limit"] == 500_000

    # 내역이 바뀌면 둘 다 알린다
    b.addEntry("2026-01-11", "교통", 5_000)
    assert ledger_hits and len(budget_hits) == 6


def test_source_row_renumbering_is_announced():
    """SourceRowRole 은 행 번호 그 자체라 삭제·이동만으로 값이 달라진다.
    알리지 않으면 QML 델리게이트가 예전 번호를 들고 있다가 엉뚱한 항목을 지운다."""
    b = Backend(sample_plan())
    m = b.items
    hits = []
    m.dataChanged.connect(lambda tl, br, roles: hits.append((tl.row(), br.row(), [int(r) for r in roles])))

    # 번호(sourceRow)와 묶음 안 위치(groupPos/groupCount)가 함께 달라진다.
    # 묶음 안 위치는 지운 자리보다 앞쪽 항목도 달라질 수 있어 전체를 알린다.
    want = [int(m.SourceRowRole), int(m.GroupPosRole), int(m.GroupCountRole)]
    m.remove(2)
    assert hits == [(0, m.rowCount() - 1, want)]

    hits.clear()
    m.move(1, 1)
    assert hits == [(0, m.rowCount() - 1, want)]

    hits.clear()
    m.remove(m.rowCount() - 1)
    assert hits == [(0, m.rowCount() - 1, want)]

    # 어떤 경우에도 번호는 자기 자리와 같다
    assert [m.data(m.index(r, 0), m.SourceRowRole) for r in range(m.rowCount())] == list(range(m.rowCount()))

    # 다 지우면 알릴 줄이 없다
    while m.rowCount():
        m.remove(m.rowCount() - 1)
    hits.clear()
    m.remove(0)
    assert hits == []


def test_source_row_at_maps_visible_to_real():
    b = Backend(sample_plan())
    g, m = b.groupedItems, b.items

    def visible():
        return [(g.data(g.index(r, 0), m.NameRole), b.sourceRowAt(r)) for r in range(g.rowCount())]

    # 묶어 보기는 분류 순으로 재배치되므로 화면 순서 != 원본 순서
    rows = visible()
    assert [name for name, _ in rows][:3] == ["보유 현금", "예금 (3.5%)", "청년도약계좌"]
    for name, src in rows:
        assert m.data(m.index(src, 0), m.NameRole) == name    # 가리키는 원본이 맞는다

    assert b.sourceRowAt(99) == -1 and b.sourceRowAt(-1) == -1

    # 화면 두 번째 줄을 지우면 그 항목만 사라지고, 나머지 매핑은 그대로 맞는다
    gone = rows[1][0]
    b.removeItem(b.sourceRowAt(1))
    rows = visible()
    assert gone not in [name for name, _ in rows]
    for name, src in rows:
        assert m.data(m.index(src, 0), m.NameRole) == name

    # 같은 화면 줄 번호로 계속 지워도 그 줄의 항목만 사라진다 (예전 번호를 쓰면 엉뚱한 게 지워졌다)
    for _ in range(3):
        target = visible()[1][0]
        b.removeItem(b.sourceRowAt(1))
        names = [name for name, _ in visible()]
        assert target not in names
        for name, src in visible():
            assert m.data(m.index(src, 0), m.NameRole) == name


def test_collapse_keeps_rows_and_headers():
    """접기로 줄을 걸러내면 그 분류의 섹션 헤더까지 사라져 다시 펼 수가 없다.
    그래서 접기는 상태만 바꾸고, 숨기는 건 화면이 한다."""
    b = Backend(sample_plan())
    g, m = b.groupedItems, b.items
    n = g.rowCount()

    cats = sorted({m.data(m.index(r, 0), m.CategoryIndexRole) for r in range(m.rowCount())})
    for c in cats:
        b.toggleGroup(c)
        assert b.isGroupCollapsed(c)
        assert g.rowCount() == n                 # 줄은 그대로 남는다 → 헤더도 남는다

    # 전부 접어도 목록이 비지 않는다 (비면 다시 펼 방법이 없다)
    assert g.rowCount() == n

    for c in cats:
        b.toggleGroup(c)
        assert not b.isGroupCollapsed(c)

    # 묶기를 끄면 접힘이 모두 풀린다
    b.toggleGroup(cats[0])
    b.groupByCategory = False
    assert not b.isGroupCollapsed(cats[0])
    b.groupByCategory = True
    assert g.rowCount() == n


def test_backend_pending_inflow():
    keys = {"has", "total", "count", "withNet", "shortfall", "progress", "progressWith", "groups"}
    gkeys = {"kind", "label", "total", "count", "month", "dateText", "name", "progressTo"}

    b = Backend(Plan(months=6, target=100_000_000, start_date="2026-01-01"))
    assert set(b.pendingInflow) == keys and not b.pendingInflow["has"]   # 비어도 칸은 다 있다
    assert b.pendingInflow["groups"] == []

    b.addItem("현금", 0, 20_000_000, 0, True)
    # 9 = 주거. 2025-01 입주(기준일 전) → 낸 돈은 안 세고 2027-01 반환만 기다린다
    b.addItem("전셋집", 9, 30_000_000, 0, True, "2025-01-01", "2027-01-01")
    assert b.onceCost == 0 and b.net == 20_000_000 and b.progress == 0.2

    pi = b.pendingInflow
    assert set(pi) == keys and pi["has"] and pi["count"] == 1
    assert pi["total"] == 30_000_000 and pi["withNet"] == 50_000_000
    assert pi["progress"] == 0.2 and pi["progressWith"] == 0.5
    assert pi["shortfall"] == 50_000_000
    g = pi["groups"][0]
    assert set(g) == gkeys and g["kind"] == "deposit" and g["label"] == "돌려받을 보증금"
    assert g["month"] == 12 and g["dateText"] == "2027년 1월" and g["progressTo"] == 0.5

    # 3 = 대출/이자. 기간 뒤에 실행되는 대출도 들어올 돈이다
    b.addItem("전세자금대출", 3, 40_000_000, 0, True, "2026-09-01", "")   # 이율 0 (이자는 이 테스트의 관심사가 아니다)
    pi = b.pendingInflow
    assert pi["count"] == 2 and pi["total"] == 70_000_000
    assert pi["withNet"] == 90_000_000 and pi["shortfall"] == 10_000_000
    kinds = [g["kind"] for g in pi["groups"]]
    assert kinds == ["deposit", "loan"]                       # 바에 칠하는 순서
    assert pi["groups"][0]["progressTo"] == 0.5               # 순 자본 + 보증금
    assert pi["groups"][1]["progressTo"] == 0.9               # 거기에 대출까지
    assert pi["groups"][1]["label"] == "받을 대출" and pi["groups"][1]["month"] == 8

    # 기간이 둘 다 품으면 순 자본에 이미 들어 있으므로 따로 세지 않는다
    b.months = 12
    assert b.net == 90_000_000 and not b.pendingInflow["has"]
    assert b.pendingInflow["progressWith"] == b.progress == 0.9
    assert b.pendingInflow["shortfall"] == 10_000_000

    # 여러 건이면 가장 이른 것과 건수를 알려준다
    b.months = 6
    b.addItem("원룸", 9, 5_000_000, 0, True, "2025-01-01", "2027-06-01")
    dep = b.pendingInflow["groups"][0]
    assert dep["count"] == 2 and dep["total"] == 35_000_000
    assert dep["month"] == 12 and "외 1건" in dep["name"]


def test_backend_growth():
    b = Backend(Plan(months=36, target=0, start_date="2026-01-01"))
    assert b.categoryInfo(4)["usesGrowth"] and b.categoryInfo(6)["usesGrowth"]      # 월 수입, 월세
    assert b.categoryInfo(8)["usesGrowth"]                                          # 고정 지출
    assert not b.categoryInfo(0)["usesGrowth"] and not b.categoryInfo(5)["usesGrowth"]

    # 4 = 월 수입, 마지막 인자가 연 상승률
    b.addItem("급여", 4, 2_000_000, 0, True, "", "", "[]", 0, "", "", 0, 5.0)
    idx = b.items.index(0, 0)
    assert b.items.data(idx, b.items.GrowthRole) == 5.0
    assert "해마다 5% 인상" in b.items.data(idx, b.items.SubTextRole)

    assert b.monthlyIncome == 2_000_000                   # 0개월은 그대로
    assert b.netAt(12) == 2_000_000 * 12
    assert b.netAt(24) == 2_000_000 * 12 + 2_100_000 * 12

    pv = b.growthPreview(2_000_000, 5.0, 3)
    assert abs(pv["amount"] - 2_000_000 * 1.05 ** 3) < 1e-6 and "3년 뒤" in pv["text"]
    assert b.growthPreview(2_000_000, 0, 3)["text"] == "오르지 않습니다"

    # 상승률을 빼면 다시 평평해진다
    b.updateItem(0, "급여", 4, 2_000_000, 0, True, "", "", "[]", 0, "", "", 0, 0)
    assert b.items.data(b.items.index(0, 0), b.items.GrowthRole) == 0
    assert b.netAt(24) == 2_000_000 * 24

    # 상승률을 안 주는 예전 호출도 그대로 동작한다
    b.addItem("부업", 4, 100_000, 0, True)
    assert b.items.data(b.items.index(1, 0), b.items.GrowthRole) == 0


def test_to_ledger_single():
    b = Backend(sample_plan())
    fails = []
    b.failed.connect(fails.append)

    rows = {b.items.data(b.items.index(r, 0), b.items.NameRole): r for r in range(b.itemCount)}

    assert b.toLedger(rows["관리비"]) is True
    assert b.ledgerSummary["count"] == 1 and not fails

    # 같은 이름을 또 넣으면 거절하고 알린다
    assert b.toLedger(rows["관리비"]) is False
    assert b.ledgerSummary["count"] == 1               # 늘지 않는다
    assert "관리비" in fails[-1] and "이미" in fails[-1]

    # 가계부에 넣을 수 없는 분류
    assert b.toLedger(rows["보유 현금"]) is False
    assert "기록할 수 없습니다" in fails[-1]

    # 분류 짝짓기와 금액
    b2 = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b2.addItem("급여", 4, 2_000_000, 0, True)
    b2.addItem("대출", 3, 12_000_000, 12.0, False, "", "", "[]", 0, "bullet")
    assert b2.toLedger(0) and b2.toLedger(1)
    m = b2.ledgerItems
    got = {m.data(m.index(r, 0), m.NameRole): (m.data(m.index(r, 0), m.CategoryRole),
                                               m.data(m.index(r, 0), m.AmountRole))
           for r in range(m.rowCount())}
    assert got["급여"] == ("급여", 2_000_000)
    assert got["대출"][0] == "대출 상환" and abs(got["대출"][1] - 120_000) < 1   # 그 달 이자


def test_import_plan_to_ledger():
    b = Backend(sample_plan())
    fails = []
    b.failed.connect(fails.append)

    added = b.importPlanToLedger()
    assert added == 7 and b.ledgerSummary["count"] == 7      # 현금·예금은 빠진다
    names = {b.ledgerItems.data(b.ledgerItems.index(r, 0), b.ledgerItems.NameRole)
             for r in range(b.ledgerItems.rowCount())}
    assert "보유 현금" not in names and "급여" in names

    # 두 번째는 전부 건너뛴다
    assert b.importPlanToLedger() == 0
    assert "이미 가계부에 있습니다" in fails[-1]
    assert b.ledgerSummary["count"] == 7

    # 하나를 지우면 그것만 다시 들어온다
    b.removeEntry(0)
    assert b.importPlanToLedger() == 1
    assert b.ledgerSummary["count"] == 7

    # 기록할 게 없으면 알린다
    b3 = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    msgs = []
    b3.failed.connect(msgs.append)
    b3.addItem("현금", 0, 1_000_000, 0, True)
    assert b3.importPlanToLedger() == 0
    assert "기록할 항목이 없습니다" in msgs[-1]


def test_backend_saving_support_and_loan_interest():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    assert b.categoryInfo(2)["usesSupport"]                       # 2 = 적금/저축(월)
    assert not b.categoryInfo(3)["usesSupport"]                   # 3 = 대출/이자

    # 마지막 인자가 월 지원금
    b.addItem("청년도약계좌", 2, 200_000, 0, True, "2026-01-01", "2027-01-01",
              "[]", 0, "", "", 0, 0, 300_000)
    idx = b.items.index(0, 0)
    assert b.items.data(idx, b.items.SupportRole) == 300_000
    sub = b.items.data(idx, b.items.SubTextRole)
    assert "내 돈 200,000원 + 지원 300,000원 = 매달 500,000원" in sub
    assert "12개월 후 6,000,000원 (12회 납입)" in sub
    assert "받은 지원금 3,600,000원" in sub

    assert b.monthlyCost == 200_000                               # 나가는 건 내 돈뿐
    assert b.netAt(12) == 300_000 * 12                            # 지원금만큼 순 자본이 는다

    # 대출은 목록에서도 월 이자가 보인다 (아직 시작 전이어도)
    b.addItem("전세대출", 3, 94_000_000, 1.7, True, "2027-01-01", "")
    sub = b.items.data(b.items.index(1, 0), b.items.SubTextRole)
    assert "월 이자 133,167원" in sub and "만기 일시 상환" in sub
    assert b.items.data(b.items.index(1, 0), b.items.MonthlyTextRole) == "12개월 뒤 시작"

    # 이율이 0 이면 이자 줄은 붙지 않는다
    b.addItem("무이자", 3, 1_000_000, 0, True, "", "")
    assert "월 이자" not in b.items.data(b.items.index(2, 0), b.items.SubTextRole)

    # 지원금을 안 주는 예전 호출도 그대로 동작한다
    b.addItem("적금", 2, 100_000, 0, True, "", "")
    assert b.items.data(b.items.index(3, 0), b.items.SupportRole) == 0


def test_backend_locked_saving():
    b = Backend(Plan(months=12, target=50_000_000, start_date="2026-01-01"))
    assert b.categoryInfo(2)["canLock"] and not b.categoryInfo(1)["canLock"]

    b.addItem("현금", 0, 10_000_000, 0, True)
    # 마지막 인자가 '만기까지 묶임'
    b.addItem("청년도약계좌", 2, 200_000, 0, True, "2026-01-01", "2031-01-01",
              "[]", 0, "", "", 0, 0, 300_000, True)
    idx = b.items.index(1, 0)
    assert b.items.data(idx, b.items.LockedRole) is True
    assert "만기까지 묶임 · 60개월 뒤 30,000,000원 수령" in b.items.data(idx, b.items.SubTextRole)

    assert b.capital == 10_000_000                       # 만기 전에는 안 잡힌다
    assert b.netAt(12) == 10_000_000 - 200_000 * 12
    assert b.netAt(60) == 10_000_000 + 300_000 * 60

    pi = b.pendingInflow
    assert pi["has"] and [g["kind"] for g in pi["groups"]] == ["saving"]
    g = pi["groups"][0]
    assert g["label"] == "만기에 받을 적금" and g["total"] == 30_000_000
    assert g["month"] == 60 and g["dateText"] == "2031년 1월"

    # 묶임을 풀면 바로 자본이 되고 들어올 돈에서 빠진다
    b.updateItem(1, "청년도약계좌", 2, 200_000, 0, True, "2026-01-01", "2031-01-01",
                 "[]", 0, "", "", 0, 0, 300_000, False)
    assert b.items.data(b.items.index(1, 0), b.items.LockedRole) is False
    assert not b.pendingInflow["has"]
    assert b.netAt(12) == 10_000_000 + 300_000 * 12

    # 만기 없이 묶으면 그렇다고 알려 준다
    b.updateItem(1, "청년도약계좌", 2, 200_000, 0, True, "2026-01-01", "",
                 "[]", 0, "", "", 0, 0, 300_000, True)
    assert "만기(종료일)가 없습니다" in b.items.data(b.items.index(1, 0), b.items.SubTextRole)
    assert not b.pendingInflow["has"]

    # 묶임을 안 주는 예전 호출도 그대로 동작한다
    b.addItem("적금", 2, 100_000, 0, True, "", "")
    assert b.items.data(b.items.index(2, 0), b.items.LockedRole) is False


def test_locked_saving_shows_in_summary():
    """묶인 적금의 만기 수령액이 요약 어디에도 안 나오면 사라진 것처럼 보인다."""
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("현금", 0, 10_000_000, 0, True)
    b.addItem("청년적금", 2, 200_000, 0, True, "2026-01-01", "2027-01-01",
              "[]", 0, "", "", 0, 0, 300_000, True)

    # 기간이 만기(12개월)를 품으면 '일시 수입' 으로 드러난다
    assert b.capital == 10_000_000                    # 보유 자금에는 안 들어간다
    assert b.onceIncome == 500_000 * 12
    assert b.periodIncome == 500_000 * 12
    assert b.net == 10_000_000 + 300_000 * 12
    assert not b.pendingInflow["has"]                 # 기간 안이라 '들어올 돈' 은 아니다

    # 기간이 만기 전이면 요약에는 안 나오고 목표 바의 '들어올 돈' 이 된다
    b.months = 6
    assert b.onceIncome == 0
    assert [g["kind"] for g in b.pendingInflow["groups"]] == ["saving"]
    assert b.pendingInflow["groups"][0]["total"] == 500_000 * 12


def test_months_change_refreshes_item_text():
    """목록의 'N개월 후 …' 는 기간을 따라가야 한다."""
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("적금", 2, 100_000, 0, True, "2026-01-01", "")
    idx = b.items.index(0, 0)
    assert "12개월 후" in b.items.data(idx, b.items.SubTextRole)

    changed = []
    b.items.dataChanged.connect(lambda tl, br, roles: changed.append(1))
    b.months = 30
    assert changed                                     # 목록에 다시 그리라고 알린다
    assert "30개월 후" in b.items.data(b.items.index(0, 0), b.items.SubTextRole)


def test_backend_average_monthly():
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("급여", 4, 2_000_000, 0, True)
    b.addItem("생활비", 8, 1_000_000, 0, True)
    assert not b.monthlyVaries
    assert b.avgMonthlyCost == b.monthlyCost == 1_000_000
    assert b.avgMonthlyNet == b.monthlyNet == 1_000_000

    # 3 = 대출/이자, 6개월 뒤 시작 (월 이자 100,000)
    b.addItem("대출", 3, 12_000_000, 10.0, True, "2026-07-01", "")
    assert b.monthlyVaries
    assert b.monthlyCost == 1_000_000                   # 지금
    assert b.lastMonthlyCost == 1_100_000               # 마지막 달
    assert b.avgMonthlyCost == (1_000_000 * 12 + 100_000 * 6) / 12
    assert b.lastMonthlyNet == 900_000
    assert b.avgMonthlyNet == b.avgMonthlyIncome - b.avgMonthlyCost
    assert abs(b.required - b.avgMonthlyCost * 12) < 1e-6

    # 기간을 바꾸면 평균도 따라간다
    b.months = 6
    assert not b.monthlyVaries and b.avgMonthlyCost == 1_000_000
    b.months = 24
    assert b.monthlyVaries and b.avgMonthlyCost > 1_000_000


def test_summary_cache_is_cleared_on_change():
    """요약을 담아 두되, 계획이 바뀌면 반드시 버려야 한다."""
    b = Backend(Plan(months=12, target=0, start_date="2026-01-01"))
    b.addItem("현금", 0, 1_000_000, 0, True)
    assert b.capital == 1_000_000

    calls = []
    real = b._plan.summary
    b._plan.summary = lambda: (calls.append(1), real())[1]
    b._clear_cache()                       # 이미 담아 둔 것을 비우고 센다

    # 한 번 계산하면 여러 번 읽어도 다시 계산하지 않는다
    for _ in range(5):
        _ = b.capital, b.net, b.required, b.monthlyNet
    assert len(calls) == 1

    # 항목이 바뀌면 다시 계산한다
    b.addItem("급여", 4, 500_000, 0, True)
    assert b.monthlyIncome == 500_000
    assert len(calls) == 2

    # 기간이 바뀌어도
    b.months = 24
    assert b.months == 24 and b.net == 1_000_000 + 500_000 * 24
    assert len(calls) == 3

    # 시나리오를 바꾸면 그 시나리오의 요약이 나온다
    b._plan.summary = real
    b.duplicateScenario()
    b.addItem("보너스", 5, 7_000_000, 0, True)
    other = b.net
    b.activeScenario = 0
    assert b.net != other


def test_end_date_sets_months():
    """기간을 개월 수 대신 끝 날짜로도 정할 수 있다."""
    b = Backend(Plan(months=12, target=0, start_date="2026-10-28"))
    assert b.endDate == "2027-10-28"                 # 기준일 + 12개월 (날짜도 지킨다)
    assert b.endDateText == "2027년 10월"

    b.endDate = "2029-01-15"
    assert b.months == 27                            # 기준일이 28일이라 15일은 아직 26개월째
    assert b.endDate == "2029-01-15"                 # 친 날짜 그대로 되읽는다

    b.months = 6
    assert b.endDate == "2027-04-28"                 # 개월 수를 바꾸면 끝 날짜도

    # 기준일을 바꾸면 끝 날짜가 따라 움직인다 (기간은 그대로)
    b.basisDate = "2027-01-01"
    assert b.months == 6 and b.endDate == "2027-07-01"

    # 이상한 값은 무시한다
    b.endDate = "이상한값"
    assert b.months == 6
    b.endDate = ""
    assert b.months == 6

    # 기준일보다 앞선 날짜는 0개월
    b.endDate = "2020-01-01"
    assert b.months == 0 and b.endDate == "2027-01-01"

    # 날짜가 바뀌면 알림이 간다 (요약이 다시 계산되도록)
    hits = []
    b.summaryChanged.connect(lambda: hits.append(1))
    b.endDate = "2028-01-01"
    assert hits and b.months == 12


def test_capital_at_end_makes_the_summary_add_up():
    """요약을 위에서 아래로 더하면 'N개월 후 순 자본' 이 나와야 한다.
    적금 납입은 월 지출로 보이는데 쌓이는 쪽이 안 보여서 숫자가 안 맞아 보였다."""
    p = Plan(months=12, target=0, start_date="2026-11-02")
    p.add(Item("현금", Category.CASH, 10_000_000))
    p.add(Item("적금", Category.SAVING, 300_000, rate=5.0))
    p.add(Item("급여", Category.INCOME, 2_000_000))
    b = Backend(p)

    assert b.capital == p.capital_at(0)
    assert b.capitalAtEnd == p.capital_at(12)
    assert abs(b.capitalGrowth - (p.capital_at(12) - p.capital_at(0))) < 0.5
    assert b.capitalGrowth > 0                      # 적금이 쌓였으니 늘어야 한다
    assert abs((b.capitalAtEnd - b.required + b.periodIncome) - b.net) < 0.5

    # 쌓일 게 없으면 줄이 숨도록 0 이 나와야 한다
    p2 = Plan(months=12, target=0, start_date="2026-11-02")
    p2.add(Item("현금", Category.CASH, 1_000_000))
    assert Backend(p2).capitalGrowth == 0



def test_move_in_group_reorders_within_category_only():
    """묶어 보기에서 ▲▼. 보이는 차례와 원본 차례가 다르므로 같은 분류끼리만 맞바꾼다."""
    p = Plan(months=12)
    p.add(Item("현금A", Category.CASH, 1))
    p.add(Item("월세", Category.RENT, 2))
    p.add(Item("현금B", Category.CASH, 3))
    p.add(Item("현금C", Category.CASH, 4))
    b = Backend(p)

    names = lambda: [x.name for x in p.items]
    assert names() == ["현금A", "월세", "현금B", "현금C"]

    # 현금B(2번)를 위로 → 사이에 '월세' 가 끼어 있어도 현금A 와 자리를 바꾼다
    assert b.moveInGroup(2, -1) is True
    assert names() == ["현금B", "월세", "현금A", "현금C"], "월세가 끌려 다니면 안 된다"

    # 현금B 를 또 위로 → 그 분류의 맨 위라 더 못 간다
    assert b.moveInGroup(0, -1) is False
    assert names() == ["현금B", "월세", "현금A", "현금C"]

    # 아래로
    assert b.moveInGroup(0, 1) is True
    assert names() == ["현금A", "월세", "현금B", "현금C"]

    # 혼자뿐인 분류는 어느 쪽으로도 못 간다
    assert b.moveInGroup(1, -1) is False and b.moveInGroup(1, 1) is False

    # 맨 아래 현금C 는 더 못 내려간다
    assert b.moveInGroup(3, 1) is False

    # 묶음 안 위치·개수가 자리와 맞는다
    m = b.items
    pos = [m.data(m.index(r, 0), m.GroupPosRole) for r in range(m.rowCount())]
    cnt = [m.data(m.index(r, 0), m.GroupCountRole) for r in range(m.rowCount())]
    assert pos == [0, 0, 1, 2]
    assert cnt == [3, 1, 3, 3]

    # 번호는 언제나 자기 자리와 같다
    assert [m.data(m.index(r, 0), m.SourceRowRole) for r in range(m.rowCount())] == [0, 1, 2, 3]


def test_fixed_entries_are_written_and_kept_on_edit():
    """고정 항목을 만들면 밀린 달까지 적히고, 그 줄을 고쳐도 '고정' 표시가 남는다."""
    from datetime import date

    from capital_calc.ledger import Ledger, month_key
    from capital_calc.model import Workspace

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    b = Backend(ws)
    start = "2026-09"
    assert b.addFixed("월세", "주거/관리비", 600_000, 5, "", start, "") == ""

    rows = b.fixedRows
    assert len(rows) == 1 and rows[0]["made"] > 0 and rows[0]["active"] is True
    assert b.fixedTotals["cost"] == 600_000
    # 이번 달까지 한 번씩
    made = [e for e in ws.ledger.entries if e.rule == rows[0]["rid"]]
    assert {e.ym for e in made} == set(_months_between(start, month_key(date.today())))

    row = ws.ledger.entries.index(made[0])
    b.updateEntry(row, made[0].date, "주거/관리비", 610_000, "월세", "")
    assert ws.ledger.entries[row].rule == rows[0]["rid"]     # 표시가 사라지지 않는다

    # 쉬게 하면 다음 달부터 적지 않는다
    assert b.toggleFixed(rows[0]["rid"]) is True
    assert b.fixedRows[0]["active"] is False
    assert b.fixedTotals["count"] == 0


def _months_between(a: str, b: str) -> list[str]:
    from capital_calc.ledger import shift_month

    out, ym = [], a
    while ym <= b:
        out.append(ym)
        ym = shift_month(ym, 1)
    return out


def test_fixed_from_entry_starts_next_month():
    """적어 둔 내역을 고정으로 올리면 그 달은 그대로 두고 다음 달부터 적는다."""
    from capital_calc.ledger import Entry, Ledger, month_key, shift_month
    from capital_calc.model import Workspace
    from datetime import date

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    last = shift_month(month_key(date.today()), -1)
    ws.ledger.add(Entry(f"{last}-12", "통신", 88_000, "휴대폰"))
    b = Backend(ws)

    assert b.fixedFromEntry(0) == ""
    rid = b.fixedRows[0]["rid"]
    assert b.fixedRows[0]["day"] == 12
    made = [e for e in ws.ledger.entries if e.rule == rid]
    assert [e.ym for e in made] == [month_key(date.today())]     # 이번 달치만 새로 생겼다
    assert b.fixedFromEntry(ws.ledger.entries.index(made[0])) != ""   # 고정이 적은 줄은 거절


def test_overview_numbers_agree_with_the_other_screens():
    """한눈에 보기는 따로 계산하지 않는다 — 계획·가계부 화면과 같은 값이어야 한다."""
    b = Backend()
    b.loadSample()

    plan = b.overviewPlan
    assert plan["capital"] == b.capital
    assert plan["net"] == b.net
    assert plan["months"] == b.months
    assert plan["target"] == b.target
    assert plan["goalMonth"] == b.goalMonth
    assert plan["itemCount"] == b.itemCount

    months = b.overviewMonths
    assert len(months) == 12
    assert sum(m["isThis"] for m in months) == 1 and months[-1]["isThis"]

    led = b.overviewLedger
    assert led["income"] == sum(m["income"] for m in months)
    assert led["cost"] == sum(m["cost"] for m in months)
    assert led["net"] == led["income"] - led["cost"]
    assert led["months"] == sum(1 for m in months if m["count"] > 0)

    pie = b.overviewByCategory("cost")
    assert abs(sum(r["value"] for r in pie) - led["cost"]) < 1
    assert abs(sum(r["share"] for r in pie) - 1.0) < 1e-9
    assert pie == sorted(pie, key=lambda r: -r["value"])      # 큰 금액부터

    now = b.overviewThisMonth
    assert now["ym"] == months[-1]["ym"]
    assert (now["income"], now["cost"]) == (months[-1]["income"], months[-1]["cost"])
    assert now["vsPlan"] == b.planVsActualFor(now["ym"])


def test_overview_is_empty_but_well_formed_without_a_ledger():
    """가계부가 비어도 칸이 모두 채워져 와야 한다 (QML 바인딩이 undefined 를 보지 않게)."""
    from capital_calc.ledger import Ledger
    from capital_calc.model import Workspace

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    b = Backend(ws)

    led = b.overviewLedger
    assert led["has"] is False and led["count"] == 0 and led["avgNet"] == 0
    assert led["bestLabel"] == "" and led["worstLabel"] == ""
    assert len(b.overviewMonths) == 12 and all(m["count"] == 0 for m in b.overviewMonths)
    assert b.overviewByCategory("cost") == [] and b.overviewBudgets == []
    assert b.overviewThisMonth["vsPlan"]["has"] is False


# ───────────────────────── 되돌리기

def _fresh_backend():
    from capital_calc.ledger import Ledger
    from capital_calc.model import Category, Item, Workspace

    plan = Plan(months=12, target=10_000_000)
    plan.add(Item("현금", Category.CASH, 5_000_000))
    ws = Workspace(plans=[plan])
    ws.ledger = Ledger()
    return Backend(ws)


def test_undo_and_redo_restore_items():
    b = _fresh_backend()
    assert b.canUndo is False and b.undoLabel == ""

    b.addItem("급여", 4, 2_000_000, 0, True)           # 4 = 월 수입
    assert b.itemCount == 2 and b.canUndo and b.undoLabel == "항목 추가"

    b.removeItem(1)
    assert b.itemCount == 1 and b.undoLabel == "항목 삭제"

    assert b.undo() is True
    assert b.itemCount == 2 and b.canRedo and b.redoLabel == "항목 삭제"
    assert b.undo() is True
    assert b.itemCount == 1 and b.canUndo is False       # 처음 상태로

    assert b.undo() is False                              # 더 되돌릴 것이 없다
    assert b.redo() is True and b.itemCount == 2
    assert b.redo() is True and b.itemCount == 1


def test_undo_covers_the_ledger_too():
    b = _fresh_backend()
    b.addEntry("2026-11-11", "식비", 12_000, "점심", "")
    b.addEntry("2026-11-12", "식비", 9_000, "커피", "")
    assert len(b._ws.ledger.entries) == 2

    b.removeEntry(0)
    assert len(b._ws.ledger.entries) == 1
    assert b.undo() and len(b._ws.ledger.entries) == 2
    assert b._ws.ledger.entries[0].name == "점심"         # 지웠던 그 줄이 그대로

    b.clearLedger()
    assert b._ws.ledger.entries == []
    assert b.undo() and len(b._ws.ledger.entries) == 2


def test_undo_ignores_actions_that_changed_nothing():
    """거절당한 동작으로 더미가 더러워지면 Ctrl+Z 가 헛돈다."""
    b = _fresh_backend()
    b.addEntry("2026-11-11", "식비", 12_000, "점심", "")
    assert b.undoLabel == "가계부 내역 추가"

    assert b.toLedger(0) is False                         # 현금은 기록할 수 없다
    assert b.addFixed("", "", 0, 1) != ""                 # 분류·금액이 없다
    assert b.removeScenario(0) is None and b.scenarioCount == 1   # 마지막 하나는 못 지운다
    assert b.undoLabel == "가계부 내역 추가"               # 그대로다

    assert b.undo() and b._ws.ledger.entries == []


def test_undo_forgets_redo_after_a_new_action():
    b = _fresh_backend()
    b.addEntry("2026-11-11", "식비", 12_000, "점심", "")
    b.undo()
    assert b.canRedo is True
    b.addEntry("2026-11-12", "교통", 1_500, "버스", "")
    assert b.canRedo is False                             # 갈래가 생기지 않게


def test_undo_keeps_only_the_recent_steps():
    b = _fresh_backend()
    for i in range(Backend.UNDO_LIMIT + 5):
        b.addEntry("2026-11-11", "식비", 1_000 + i, f"{i}", "")
    assert len(b._undo) == Backend.UNDO_LIMIT
    for _ in range(Backend.UNDO_LIMIT):
        b.undo()
    assert b.canUndo is False
    assert len(b._ws.ledger.entries) == 5                 # 더미에서 밀려난 다섯 건은 남는다


def test_undo_restores_fixed_rules_without_rewriting_them():
    """고정 항목 추가를 되돌리면 규칙도 그것이 적은 내역도 함께 사라진다."""
    b = _fresh_backend()
    b.addFixed("월세", "주거/관리비", 600_000, 5, "", "2026-09", "")
    assert b.fixedCount == 1 and b._ws.ledger.entries

    assert b.undo() and b.fixedCount == 0
    assert b._ws.ledger.entries == []                     # 되돌린 자리에 다시 적지 않는다


# ───────────────────────── 여러 건 한꺼번에

def _ledger_backend():
    from capital_calc.ledger import Entry, Ledger
    from capital_calc.model import Workspace

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    for d, c, a, n in (("2026-11-02", "식비", 12_000, "점심"),
                       ("2026-11-03", "식비", 9_000, "커피"),
                       ("2026-11-04", "교통", 1_500, "버스"),
                       ("2026-11-25", "급여", 2_000_000, "회사"),
                       ("2026-10-02", "식비", 20_000, "지난달")):
        ws.ledger.add(Entry(d, c, a, n))
    return Backend(ws)


def test_selection_adds_up_and_toggles():
    b = _ledger_backend()
    assert b.selectedCount == 0 and b.selectionSummary["net"] == 0

    b.toggleEntrySelected(0)
    b.toggleEntrySelected(3)
    s = b.selectionSummary
    assert (s["count"], s["income"], s["cost"]) == (2, 2_000_000, 12_000)
    assert s["net"] == 2_000_000 - 12_000

    b.toggleEntrySelected(0)                       # 다시 누르면 풀린다
    assert b.selectedCount == 1
    b.clearSelection()
    assert b.selectedCount == 0


def test_select_visible_follows_the_filter():
    """'보이는 것 모두' 는 걸러져 보이는 줄만 고른다."""
    b = _ledger_backend()
    b.ledgerYear = "2026"
    b.ledgerMonth = 11                              # 11월만 보기 (4건)
    b.selectVisibleEntries()
    assert b.selectedCount == 4

    b.selectVisibleEntries()                        # 다 골라 둔 상태면 모두 푼다
    assert b.selectedCount == 0

    b.ledgerCategoryFilter = "식비"
    b.selectVisibleEntries()
    assert b.selectedCount == 2                     # 11월 식비 두 건만


def test_remove_selected_deletes_every_chosen_row():
    b = _ledger_backend()
    b.toggleEntrySelected(0)
    b.toggleEntrySelected(2)
    b.toggleEntrySelected(4)

    assert b.removeSelectedEntries() == 3
    names = [e.name for e in b._ws.ledger.entries]
    assert names == ["커피", "회사"]                 # 고르지 않은 줄만 남는다
    assert b.selectedCount == 0                      # 번호가 밀리므로 고른 것을 푼다

    assert b.undo() and len(b._ws.ledger.entries) == 5
    assert b.undoLabel == ""                         # 한 번에 되돌아간다 (한 건씩이 아니라)


def test_set_selected_category_moves_kind_too():
    b = _ledger_backend()
    b.toggleEntrySelected(0)
    b.toggleEntrySelected(2)

    assert b.setSelectedCategory("문화/여가") == 2
    assert [e.category for e in b._ws.ledger.entries][:3] == ["문화/여가", "식비", "문화/여가"]
    assert b.selectedCount == 2                      # 이어서 또 바꿀 수 있게 고른 채로 둔다

    # 수입 분류로 바꾸면 수입이 된다
    assert b.setSelectedCategory("용돈") == 2
    assert all(b._ws.ledger.entries[i].is_income for i in (0, 2))
    assert b.ledgerSummary["income"] == 2_000_000 + 12_000 + 1_500

    assert b.undo() and b._ws.ledger.entries[0].category == "문화/여가"


def test_selection_is_dropped_when_rows_shift():
    """한 건 삭제·비우기·되돌리기 뒤에 남은 선택은 엉뚱한 줄을 가리킨다."""
    b = _ledger_backend()
    b.toggleEntrySelected(3)
    b.removeEntry(0)
    assert b.selectedCount == 0

    b.toggleEntrySelected(1)
    b.clearLedger()
    assert b.selectedCount == 0

    b.undo()
    assert b.selectedCount == 0


# ───────────────────────── 항목 잠시 끄기

def test_toggle_item_active_changes_the_summary_and_undoes():
    b = Backend()
    b.loadSample()
    net_on, capital_on = b.net, b.capital
    loan = next(i for i, it in enumerate(b._ws.plan.items) if it.category.value == "대출/이자")

    assert b.toggleItemActive(loan) is True
    assert b.offCount == 1
    assert b.itemCount == 10 or b.itemCount == 9      # 목록에서 사라지지는 않는다
    assert b.net != net_on and b.capital != capital_on
    assert b._ws.plan.items[loan].active is False

    g = b.groupSummary("대출/이자")
    assert g["count"] == 1 and g["off"] == 1 and g["total"] == 0   # 합계는 켜진 것만

    assert b.toggleItemActive(loan) is True            # 다시 켜면 그대로
    assert (b.net, b.capital, b.offCount) == (net_on, capital_on, 0)

    b.undo()
    assert b.offCount == 1 and b.undoLabel == "항목 끄기/켜기"


def test_editing_an_off_item_keeps_it_off():
    b = Backend()
    b.loadSample()
    row = 0
    b.toggleItemActive(row)
    before = b._ws.plan.items[row]
    b.updateItem(row, "보유 현금", 0, 9_000_000, 0, True)
    assert b._ws.plan.items[row].amount == 9_000_000
    assert b._ws.plan.items[row].active is False       # 고쳐도 꺼진 채로
    assert before is not b._ws.plan.items[row]


def test_summary_is_fresh_the_moment_it_is_announced():
    """캐시 때문에 '알림을 받자마자 읽은 값' 이 옛날 값이면 안 된다 (QML 바인딩이 그렇게 읽는다)."""
    b = Backend()
    b.loadSample()
    seen = []
    b.summaryChanged.connect(lambda: seen.append((b.capital, b.net, b.monthlyCost)))

    b.capital, b.net, b.monthlyCost          # 캐시를 채워 둔다
    loan = next(i for i, it in enumerate(b._ws.plan.items) if it.category.value == "대출/이자")
    b.toggleItemActive(loan)

    assert seen, "요약이 바뀌었다고 알리지 않았다"
    assert seen[-1] == (b.capital, b.net, b.monthlyCost)


# ───────────────────────── 결제수단

def test_pay_filter_and_breakdown():
    from capital_calc.ledger import Entry, Ledger
    from capital_calc.model import Workspace

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    for d, c, a, n, pay in (("2026-11-02", "식비", 12_000, "점심", "카드"),
                            ("2026-11-03", "식비", 9_000, "커피", "현금"),
                            ("2026-11-04", "교통", 1_500, "버스", "카드"),
                            ("2026-11-05", "통신", 88_000, "휴대폰", "")):
        ws.ledger.add(Entry(d, c, a, n, pay=pay))
    b = Backend(ws)

    assert b.ledgerUsedPays == ["전체", "카드", "현금"]
    rows = b.ledgerByPay("cost")
    assert [(r["label"], r["value"]) for r in rows] == [
        ("지정 안 함", 88_000), ("카드", 13_500), ("현금", 9_000)]      # 큰 금액부터
    assert abs(sum(r["share"] for r in rows) - 1.0) < 1e-9

    b.ledgerPayFilter = "카드"
    assert b.ledgerItems.rowCount() == 2 and b.ledgerFiltered is True
    assert b.ledgerFilteredSummary["cost"] == 13_500

    b.clearLedgerFilters()
    assert b.ledgerPayFilter == "" and b.ledgerItems.rowCount() == 4


def test_pay_goes_in_and_out_of_every_entry_point():
    """추가·수정·반복·고정 어디로 넣어도 결제수단이 붙어 다닌다."""
    from capital_calc.ledger import Ledger
    from capital_calc.model import Workspace

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    b = Backend(ws)

    b.addEntry("2026-11-02", "식비", 12_000, "점심", "", "신한카드")
    assert ws.ledger.entries[0].pay == "신한카드"
    assert "신한카드" in b.ledgerPays                      # 직접 적은 이름이 목록에 들어온다

    b.updateEntry(0, "2026-11-02", "식비", 12_000, "점심", "", "현금")
    assert ws.ledger.entries[0].pay == "현금"

    b.addEntryRepeat("2026-11-03", "통신", 88_000, "휴대폰", "", 3, "자동이체")
    assert [e.pay for e in ws.ledger.entries[1:]] == ["자동이체"] * 3

    assert b.addFixed("월세", "주거/관리비", 600_000, 5, "", "2026-11", "", "계좌이체") == ""
    assert b.fixedRows[0]["pay"] == "계좌이체"
    assert [e.pay for e in ws.ledger.entries if e.rule] == ["계좌이체"]


def test_set_selected_pay_changes_many_at_once():
    from capital_calc.ledger import Entry, Ledger
    from capital_calc.model import Workspace

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    for d in ("2026-11-02", "2026-11-03", "2026-11-04"):
        ws.ledger.add(Entry(d, "식비", 10_000, "밥", pay="카드"))
    b = Backend(ws)

    b.toggleEntrySelected(0)
    b.toggleEntrySelected(2)
    assert b.setSelectedPay("현금") == 2
    assert [e.pay for e in ws.ledger.entries] == ["현금", "카드", "현금"]

    assert b.setSelectedPay("지정 안 함") == 2            # 비우기
    assert [e.pay for e in ws.ledger.entries] == ["", "카드", ""]
    assert b.setSelectedPay("지정 안 함") == 0            # 바뀐 게 없으면 더미에도 안 쌓인다

    b.undo()
    # 되돌리기는 가계부를 통째로 새로 만든다 — 그래서 b 쪽에서 다시 꺼내 본다
    assert [e.pay for e in b._ws.ledger.entries] == ["현금", "카드", "현금"]


# ───────────────────────── 가져오기

IMPORT_CSV = """날짜,내용,금액,분류,결제수단,구분
2026-11-03,점심,12000,식비,신한카드,지출
2026-11-04,버스,1450,교통,,지출
2026-11-25,회사,2000000,급여,,수입
"""


def _import_backend():
    from capital_calc.ledger import Ledger
    from capital_calc.model import Workspace

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    return Backend(ws)


def test_import_preview_then_apply(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text(IMPORT_CSV, encoding="utf-8")
    b = _import_backend()

    info = b.previewImportFile(str(p))
    assert info["ok"] is True
    assert (info["count"], info["fresh"], info["dupes"]) == (3, 3, 0)
    assert (info["from"], info["to"]) == ("2026-11-03", "2026-11-25")
    assert info["income"] == 2_000_000 and info["cost"] == 13_450
    assert b._ws.ledger.entries == []                 # 미리보기는 아직 넣지 않는다

    rows = b.importRows
    assert rows[0]["amountText"].startswith("-") and rows[2]["amountText"].startswith("+")

    assert b.applyImport(True, "") == 3
    got = [(e.date, e.category, e.amount, e.kind, e.pay) for e in b._ws.ledger.entries]
    assert got == [("2026-11-03", "식비", 12_000, "cost", "신한카드"),
                   ("2026-11-04", "교통", 1_450, "cost", ""),
                   ("2026-11-25", "급여", 2_000_000, "income", "")]
    assert b.importInfo == {}                          # 넣고 나면 미리보기는 치운다

    b.undo()
    assert b._ws.ledger.entries == [] and b.undoLabel == ""


def test_import_marks_what_is_already_there(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text(IMPORT_CSV, encoding="utf-8")
    b = _import_backend()
    b.previewImportFile(str(p))
    b.applyImport(True, "")

    info = b.previewImportFile(str(p))                 # 같은 파일을 또 읽으면
    assert (info["count"], info["fresh"], info["dupes"]) == (3, 0, 3)
    assert all(r["dupe"] for r in b.importRows)
    assert b.applyImport(True, "") == 0                # 건너뛰면 아무것도 안 들어간다
    assert len(b._ws.ledger.entries) == 3

    b.previewImportFile(str(p))
    assert b.applyImport(False, "") == 3               # 건너뛰기를 끄면 그대로 또 넣는다
    assert len(b._ws.ledger.entries) == 6


def test_import_makes_unknown_categories_and_fills_the_pay():
    b = _import_backend()
    b.previewImportText("날짜,내용,금액,분류\n2026-11-03,사료,30000,반려동물\n"
                        "2026-11-04,뭔가,1000,아주아주긴분류이름입니다그래서못만듭니다\n")
    assert b.applyImport(True, "현금") == 2

    e1, e2 = b._ws.ledger.entries
    assert e1.category == "반려동물" and "반려동물" in b._ws.ledger.custom
    assert e1.pay == "현금"                            # 비어 있던 결제수단을 채워 준다
    assert e2.category == "기타 지출"                   # 만들 수 없는 이름은 기타로
    assert "원래 분류" in e2.note                       # 무엇이었는지는 메모에 남긴다


def test_import_of_a_broken_file_says_why(tmp_path):
    b = _import_backend()
    info = b.previewImportFile(str(tmp_path / "없는파일.csv"))
    assert info["ok"] is False and info["problems"]
    assert b.applyImport(True, "") == 0


def test_repeating_once_item_through_the_backend():
    """팝업이 넘기는 대로 되풀이가 들어가고, 목록 글씨에도 나온다."""
    from PySide6.QtCore import Qt

    b = _fresh_backend()
    b.months = 36
    b.basisDate = "2026-11-02"
    # 일시 지출(10) · 2026-12-02 부터 해마다
    b.addItem("자동차세", 10, 500_000, 0, True, "2026-12-02", "", "[]", 0, "", "", 0, 0, 0, False, 12)

    it = b._ws.plan.items[-1]
    assert it.every == 12 and it.repeats
    row = b.items.index(b.itemCount - 1)
    sub = b.items.data(row, Qt.ItemDataRole.UserRole + 15)
    assert "해마다" in sub and "3번" in sub
    assert b.items.data(row, Qt.ItemDataRole.UserRole + 8) == "해마다 -500,000원"
    assert b.items.data(row, Qt.ItemDataRole.UserRole + 27) == 12
    assert b.onceCost == 1_500_000

    # 되풀이를 끄면 한 번만
    b.updateItem(b.itemCount - 1, "자동차세", 10, 500_000, 0, True, "2026-12-02", "", "[]",
                 0, "", "", 0, 0, 0, False, 0)
    assert b._ws.plan.items[-1].every == 0
    assert b.onceCost == 500_000


def test_repeat_is_ignored_where_it_makes_no_sense():
    """보증금·월세처럼 되풀이가 어울리지 않는 분류에는 붙지 않는다."""
    b = _fresh_backend()
    b.addItem("전셋집", 9, 30_000_000, 0, True, "2026-12-02", "", "[]", 0, "", "jeonse", 0, 0, 0, False, 12)
    b.addItem("월세", 6, 500_000, 0, True, "", "", "[]", 0, "", "", 0, 0, 0, False, 12)
    assert [i.every for i in b._ws.plan.items[-2:]] == [0, 0]


def test_sort_and_amount_range_in_the_ledger_view():
    from PySide6.QtCore import Qt

    from capital_calc.ledger import Entry, Ledger
    from capital_calc.model import Workspace

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    for d, c, a, n in (("2026-11-02", "식비", 12_000, "점심"),
                       ("2026-11-03", "급여", 2_000_000, "회사"),
                       ("2026-11-04", "교통", 1_500, "버스")):
        ws.ledger.add(Entry(d, c, a, n))
    b = Backend(ws)
    m = b.ledgerItems

    def names():
        return [m.data(m.index(r), Qt.ItemDataRole.UserRole + 4) for r in range(m.rowCount())]

    assert names() == ["버스", "회사", "점심"]          # 기본은 최신 날짜부터
    assert (b.ledgerSort, b.ledgerSortDesc) == ("date", True)

    b.sortLedgerBy("amount")
    assert (b.ledgerSort, b.ledgerSortDesc) == ("amount", True)
    assert names() == ["회사", "점심", "버스"]
    # 금액순일 때는 날짜 구분줄을 접는다
    assert m.data(m.index(0), Qt.ItemDataRole.UserRole + 10) == ""

    b.sortLedgerBy("amount")                            # 같은 걸 또 누르면 뒤집힌다
    assert b.ledgerSortDesc is False and names() == ["버스", "점심", "회사"]

    b.sortLedgerBy("date")
    assert (b.ledgerSort, b.ledgerSortDesc) == ("date", True)
    assert m.data(m.index(0), Qt.ItemDataRole.UserRole + 10) == "2026-11-04"

    b.ledgerMinAmount = 10_000
    assert names() == ["회사", "점심"] and b.ledgerFiltered is True
    assert b.ledgerFilteredSummary["count"] == 2
    b.ledgerMaxAmount = 100_000
    assert names() == ["점심"]

    b.clearLedgerFilters()
    assert (b.ledgerMinAmount, b.ledgerMaxAmount) == (0, 0) and len(names()) == 3
    assert b.ledgerSort == "date"                       # 정렬은 거르기 해제로 건드리지 않는다


# ───────────────────────── 분류별 계획 대비 실적

def test_plan_vs_actual_by_category():
    from capital_calc.ledger import Entry, Ledger
    from capital_calc.model import Category, Item, Workspace

    plan = Plan(months=12, start_date="2026-11-02")
    plan.add(Item("현금", Category.CASH, 10_000_000))
    plan.add(Item("월세", Category.RENT, 600_000, start_date="2026-11-02"))
    plan.add(Item("생활비", Category.FIXED, 800_000, start_date="2026-11-02"))
    plan.add(Item("급여", Category.INCOME, 2_000_000, start_date="2026-11-02"))
    ws = Workspace(plans=[plan])
    ws.ledger = Ledger()
    for d, c, a in (("2026-11-05", "주거/관리비", 650_000), ("2026-11-07", "식비", 420_000),
                    ("2026-11-25", "급여", 2_000_000)):
        ws.ledger.add(Entry(d, c, a))
    b = Backend(ws)
    b.ledgerYear, b.ledgerMonth = "2026", 11

    rows = {r["category"]: r for r in b.planVsActualByCategory()}
    assert rows["주거/관리비"]["plan"] == 600_000
    assert rows["주거/관리비"]["actual"] == 650_000
    assert rows["주거/관리비"]["diff"] == 50_000 and rows["주거/관리비"]["inPlan"] is True
    assert rows["기타 지출"]["plan"] == 800_000 and rows["기타 지출"]["actual"] == 0
    assert rows["식비"]["plan"] == 0 and rows["식비"]["inPlan"] is False   # 계획에 없던 지출
    assert rows["급여"]["kind"] == "income" and rows["급여"]["diff"] == 0

    # 합계는 총액 비교와 맞아야 한다
    total = b.planVsActual()
    assert sum(r["plan"] for r in b.planVsActualByCategory() if r["kind"] == "cost") == total["planOut"]
    assert sum(r["actual"] for r in b.planVsActualByCategory() if r["kind"] == "cost") == total["actOut"]


def test_item_can_be_pinned_to_a_ledger_category():
    """항목의 '가계부 분류' 를 정해 두면 비교도 가져오기도 그것을 따른다."""
    from capital_calc.ledger import Entry, Ledger
    from capital_calc.model import Category, Item, Workspace

    plan = Plan(months=12, start_date="2026-11-02")
    plan.add(Item("생활비", Category.FIXED, 800_000, start_date="2026-11-02"))
    ws = Workspace(plans=[plan])
    ws.ledger = Ledger()
    ws.ledger.add(Entry("2026-11-07", "식비", 420_000))
    b = Backend(ws)
    b.ledgerYear, b.ledgerMonth = "2026", 11

    rows = {r["category"]: r for r in b.planVsActualByCategory()}
    assert rows["기타 지출"]["plan"] == 800_000          # 분류표대로 (자동)

    b.updateItem(0, "생활비", 8, 800_000, 0, True, "2026-11-02", "", "[]",
                 0, "", "", 0, 0, 0, False, 0, "식비")
    assert b._ws.plan.items[0].ledger_category == "식비"
    rows = {r["category"]: r for r in b.planVsActualByCategory()}
    assert rows["식비"]["plan"] == 800_000 and rows["식비"]["actual"] == 420_000
    assert "기타 지출" not in rows

    # 가계부로 가져올 때도 그 분류로
    assert b.toLedger(0) is True
    assert b._ws.ledger.entries[-1].category == "식비"


def test_by_category_is_empty_without_a_period():
    from capital_calc.ledger import Ledger
    from capital_calc.model import Workspace

    ws = Workspace(plans=[Plan(months=12)])
    ws.ledger = Ledger()
    b = Backend(ws)
    assert b.planVsActualByCategory() == []           # 기록이 없으면 기간도 없다
