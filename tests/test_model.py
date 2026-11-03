"""데이터 모델 계산 검증 (UI 없이 실행 가능)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capital_calc.model import Workspace, Category, Item, Plan, add_months, sample_plan, won  # noqa: E402


def test_item_derived_values():
    loan = Item("대출", Category.LOAN, 12_000_000, rate=5.0)
    assert loan.monthly_interest() == 50_000
    assert loan.capital() == 12_000_000
    assert loan.monthly_cost() == 50_000

    loan.include_principal = False
    assert loan.capital() == 0

    bank = Item("예금", Category.BANK, 12_000_000, rate=3.0)
    assert bank.monthly_income() == 30_000
    assert bank.capital() == 12_000_000

    assert Item("보증금", Category.DEPOSIT, 1_000).once_cost() == 1_000
    assert Item("월세", Category.RENT, 500).monthly_cost() == 500
    assert Item("관리비", Category.MAINT, 100).monthly_cost() == 100


def test_summary_and_goal():
    p = Plan(months=12, target=30_000_000)
    p.add(Item("현금", Category.CASH, 20_000_000))
    p.add(Item("예금", Category.BANK, 10_000_000, rate=3.6))   # 월 30,000 수입
    p.add(Item("보증금", Category.DEPOSIT, 10_000_000))
    p.add(Item("월세", Category.RENT, 500_000))
    p.add(Item("관리비", Category.MAINT, 100_000))

    s = p.summary()
    assert s.capital == 30_000_000
    assert s.once_cost == 10_000_000
    assert s.monthly_cost == 600_000
    assert abs(s.monthly_income - 30_000) < 1e-6
    assert s.required == 10_000_000 + 600_000 * 12
    assert abs(s.net - (30_000_000 - 17_200_000 + 360_000)) < 1e-6
    assert s.gap == s.net - 30_000_000
    assert s.gap < 0
    assert abs(s.progress - s.net / 30_000_000) < 1e-9
    assert s.months_to_goal() is None  # 월 순수입이 음수

    p.add(Item("부수입", Category.INCOME, 700_000))
    s = p.summary()
    assert abs(s.monthly_net - (700_000 + 30_000 - 600_000)) < 1e-6
    assert s.gap < 0
    assert s.months_to_goal() is not None and s.months_to_goal() > 0

    p.add(Item("월급", Category.INCOME, 3_000_000))
    assert p.summary().months_to_goal() == 0


def test_add_remove_move_and_io(tmp_path):
    p = Plan()
    a = p.add(Item("A", Category.CASH, 1))
    b = p.add(Item("B", Category.CASH, 2))
    assert p.items == [a, b]
    p.move(1, -1)
    assert p.items == [b, a]
    assert p.remove(5) is None
    assert p.remove(0) is b
    assert p.items == [a]

    path = tmp_path / "data.json"
    sample_plan().save(path)
    loaded = Plan.load(path)
    assert loaded.to_dict() == sample_plan().to_dict()
    assert json.loads(path.read_text(encoding="utf-8"))["months"] == 12


def test_won_format():
    assert won(1234567) == "1,234,567원"
    assert won(-5000) == "-5,000원"


def test_loan_dates_and_repayments():
    # 기준일 2026-01, 12개월. 대출 1,200만원 연 10% (월 이자 10만원), 2026-04 ~ 2026-10
    p = Plan(months=12, target=0, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 10_000_000))
    loan = p.add(Item("대출", Category.LOAN, 12_000_000, rate=10.0,
                      start_date="2026-04-01", end_date="2026-10-01"))
    b = p.basis
    assert loan.active_range(b) == (3, 9)
    assert not loan.is_active(2, b) and loan.is_active(3, b) and not loan.is_active(9, b)
    # 0개월엔 대출 전: 자본은 현금만, 월 지출 0
    assert p.capital_at(0) == 10_000_000 and p.monthly_cost_at(0) == 0
    # 대출 기간 중: 원금 포함, 이자 10만원
    assert p.capital_at(3) == 22_000_000 and p.monthly_cost_at(3) == 100_000
    # 종료 후: 원금 상환되어 자본에서 빠짐, 이자 없음
    assert p.capital_at(9) == 10_000_000 and p.monthly_cost_at(9) == 0
    # 12개월 후 순 자본 = 현금 - 이자 6개월
    assert abs(p.net_at(12) - (10_000_000 - 600_000)) < 1e-6
    # 종료일 생략 = 무기한
    loan.end_date = None
    assert loan.active_range(b) == (3, None) and loan.is_active(100, b)

    # 중도 상환: 2026-07 에 600만원 → 이후 잔액 600만원, 이자 5만원
    loan.end_date = "2026-10-01"
    loan.repayments = [{"date": "2026-07-01", "amount": 6_000_000}]
    assert loan.remaining_at(5, b) == 12_000_000 and loan.remaining_at(6, b) == 6_000_000
    assert p.monthly_cost_at(5) == 100_000 and p.monthly_cost_at(6) == 50_000
    assert p.capital_at(6) == 16_000_000
    # 순 자본: 이자 3개월 x 10만 + 3개월 x 5만 = 45만
    assert abs(p.net_at(12) - (10_000_000 - 450_000)) < 1e-6

    # 원금을 자본에 포함하지 않는 경우: 상환액과 만기 잔액이 지출로 잡힌다
    loan.include_principal = False
    assert p.capital_at(6) == 10_000_000
    assert p.monthly_cost_at(6) == 50_000 + 6_000_000
    assert p.monthly_cost_at(9) == 6_000_000          # 만기 일시 상환
    assert abs(p.net_at(12) - (10_000_000 - 450_000 - 12_000_000)) < 1e-6


def test_plan_dates_roundtrip(tmp_path):
    p = Plan(start_date="2026-03-01")
    p.add(Item("대출", Category.LOAN, 1_000, rate=1, start_date="2026-03-01", end_date=None,
               repayments=[{"date": "2026-06-01", "amount": 100}]))
    path = tmp_path / "d.json"
    p.save(path)
    q = Plan.load(path)
    assert q.start_date == "2026-03-01"
    assert q.items[0].end_date is None
    assert q.items[0].repayments == [{"date": "2026-06-01", "amount": 100.0}]
    assert q.to_dict() == p.to_dict()


def test_months_to_goal_simulated():
    p = Plan(months=12, target=2_000_000, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 1_000_000))
    p.add(Item("수입", Category.INCOME, 50_000))
    s = p.summary()
    assert s.net == 1_600_000
    assert s.months_to_goal() == 8


def test_rent_and_maint_dates():
    p = Plan(months=12, target=0, start_date="2026-01-01")
    p.add(Item("월세", Category.RENT, 500_000, start_date="2026-02-01", end_date="2026-05-01"))
    p.add(Item("관리비", Category.MAINT, 100_000))                       # 날짜 없음 = 계속
    assert p.monthly_cost_at(0) == 100_000
    assert p.monthly_cost_at(1) == 600_000 and p.monthly_cost_at(3) == 600_000
    assert p.monthly_cost_at(4) == 100_000
    assert p.summary().required == 500_000 * 3 + 100_000 * 12


def test_goal_month_prediction():
    from datetime import date
    assert add_months(date(2026, 10, 28), 3) == date(2027, 1, 1)
    assert add_months(date(2026, 1, 1), 24) == date(2028, 1, 1)

    p = Plan(months=12, target=2_000_000, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 1_000_000))
    p.add(Item("수입", Category.INCOME, 50_000))
    assert p.summary().goal_month() == 20          # 1,000,000 + 50,000*20 = 2,000,000
    p.target = 500_000
    assert p.summary().goal_month() == 0           # 이미 달성
    p.items[1].amount = 0
    p.target = 2_000_000
    assert p.summary().goal_month() is None        # 불가능


def test_monthly_repay_rate():
    # 대출 1,200만원, 연 12% (월 1%), 매달 원금의 10% (120만원) 정기 상환. 기준일부터 시작, 무기한
    p = Plan(months=12, target=0, start_date="2026-01-01")
    loan = p.add(Item("대출", Category.LOAN, 12_000_000, rate=12.0, monthly_repay_rate=10.0))
    b = p.basis
    assert loan.monthly_repay_amount() == 1_200_000
    assert loan.months_to_payoff(b) == 10
    assert loan.remaining_at(0, b) == 12_000_000
    assert loan.remaining_at(1, b) == 10_800_000
    assert loan.remaining_at(10, b) == 0 and loan.remaining_at(11, b) == 0
    # 이자는 달 초 잔액 기준
    assert abs(p.monthly_cost_at(0) - 120_000) < 1e-6
    assert abs(p.monthly_cost_at(1) - 108_000) < 1e-6
    assert p.monthly_cost_at(10) == 0
    assert loan.regular_repay_at(9, b) == 1_200_000 and loan.regular_repay_at(10, b) == 0
    # 원금 포함: 상환은 자본에서 빠진다 → 12개월 후 순자본 = -총이자 (잔액 0)
    total_interest = sum(12_000_000 * (1 - 0.1 * k) * 0.01 for k in range(10))
    assert abs(p.net_at(12) - (-total_interest)) < 1e-6
    # 원금 미포함: 상환이 지출로 잡힌다
    loan.include_principal = False
    assert abs(p.monthly_cost_at(0) - (120_000 + 1_200_000)) < 1e-6
    assert abs(p.net_at(12) - (-total_interest - 12_000_000)) < 1e-6

    # 정기 상환 + 중도 상환 혼합: 3개월째 600만원 중도 상환 후 잔액
    loan.include_principal = True
    loan.repayments = [{"date": "2026-04-01", "amount": 6_000_000}]
    # 3개월 초 잔액 = 1200 - 120*3 = 840만, 중도 600만 → 240만
    assert loan.remaining_at(3, b) == 2_400_000
    assert loan.regular_repay_at(4, b) == 1_200_000 and loan.regular_repay_at(5, b) == 0
    # 저장/불러오기 왕복
    d = Item.from_dict(loan.to_dict())
    assert d.monthly_repay_rate == 10.0


def test_workspace_scenarios(tmp_path):
    ws = Workspace([sample_plan()])
    assert ws.names() == ["시나리오 1"] and ws.active == 0
    ws.add()                                   # 빈 시나리오, 기간·목표 이어받음
    assert ws.names() == ["시나리오 1", "시나리오 2"] and ws.active == 1
    assert ws.plan.items == [] and ws.plan.target == 30_000_000
    ws.active = 0
    ws.duplicate()                             # 복제본은 바로 뒤에, 활성
    assert ws.names() == ["시나리오 1", "시나리오 1 복사 1", "시나리오 2"] and ws.active == 1
    assert len(ws.plan.items) == len(sample_plan().items) and ws.plan.items is not ws.plans[0].items
    assert ws.rename(1, "  전세 이사 ") and ws.plans[1].name == "전세 이사"
    assert not ws.rename(1, "   ")
    assert ws.remove(0) and ws.active == 0 and ws.names() == ["전세 이사", "시나리오 2"]
    assert ws.remove(1) and ws.active == 0
    assert not ws.remove(0)                    # 마지막 하나는 못 지움

    ws.add("B")
    path = tmp_path / "ws.json"
    ws.save(path)
    back = Workspace.load(path)
    assert back.names() == ["전세 이사", "B"] and back.active == 1
    assert back.plans[0].to_dict() == ws.plans[0].to_dict()
    assert Plan.load(path).name == "B"         # 묶음 파일에서 Plan.load 는 활성 시나리오

    legacy = tmp_path / "old.json"
    sample_plan().save(legacy)                 # 구버전(계획 하나) 파일
    old = Workspace.load(legacy)
    assert old.names() == ["시나리오 1"] and len(old.plan.items) == len(sample_plan().items)


def test_fixed_cost_category():
    p = Plan(months=12, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 10_000_000))
    f = p.add(Item("보험료", Category.FIXED, 100_000))
    assert f.uses_dates and f.date_mode == "range"
    assert p.monthly_cost_at(0) == 100_000 and p.monthly_cost_at(50) == 100_000

    f.start_date, f.end_date = "2026-03-01", "2026-06-01"       # 2,3,4,5 개월째만
    assert p.monthly_cost_at(1) == 0 and p.monthly_cost_at(2) == 100_000
    assert p.monthly_cost_at(5) == 0
    assert p.net_at(12) == 10_000_000 - 100_000 * 3


def test_once_cost_date():
    p = Plan(months=12, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 10_000_000))
    e = p.add(Item("이사비", Category.EXPENSE, 2_000_000))
    assert e.date_mode == "once" and not e.uses_dates
    assert e.once_month(p.basis) == 0                            # 날짜 없으면 기준일
    assert p.net_at(0) == 8_000_000 and p.once_cost_at(0) == 2_000_000

    e.start_date = "2026-05-01"                                  # 4개월째로 미루면
    assert e.once_month(p.basis) == 4
    assert p.once_cost_at(3) == 0 and p.once_cost_at(4) == 2_000_000
    assert p.net_at(3) == 10_000_000 and p.net_at(4) == 8_000_000
    assert p.summary().once_cost == 2_000_000                    # 12개월 안
    p.months = 2
    assert p.summary().once_cost == 0 and p.summary().required == 0

    # 기준일 전에 이미 나간 돈은 보유 자금에 없으므로 세지 않는다 (또 깎으면 이중 계산)
    e.start_date = "2025-06-01"
    assert e.once_month(p.basis) == -7
    assert p.once_cost_at(0) == 0 and p.net_at(0) == 10_000_000
    assert p.summary().once_cost == 0


def test_category_alias_from_old_file(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"months": 12, "target": 0, "start_date": "2026-01-01",
                                "items": [{"name": "공과금", "category": "기타 지출(일시)", "amount": 50_000}]},
                               ensure_ascii=False), encoding="utf-8")
    p = Plan.load(path)
    assert p.items[0].category is Category.EXPENSE and p.once_cost() == 50_000


def test_repay_methods():
    from datetime import date as _date
    b = _date(2026, 1, 1)
    common = dict(rate=12.0, start_date="2026-01-01", end_date="2027-01-01")   # 12개월, 월 1%

    bullet = Item("만기", Category.LOAN, 12_000_000, **common)
    assert bullet.repay_method == "bullet" and bullet.term_months(b) == 12
    assert bullet.remaining_at(6, b) == 12_000_000          # 기간 중엔 원금 그대로
    assert bullet.interest_at(0, b) == 120_000
    assert bullet.months_to_payoff(b) is None
    assert abs(bullet.total_interest(b) - 120_000 * 12) < 1e-6

    eq = Item("원금균등", Category.LOAN, 12_000_000, repay_method="equal_principal", **common)
    assert eq.regular_repay_at(0, b) == 1_000_000
    assert eq.remaining_at(6, b) == 6_000_000 and eq.interest_at(6, b) == 60_000
    assert eq.payment_at(0, b) == 1_120_000                 # 첫 달이 가장 크고
    assert eq.payment_at(11, b) == 1_010_000                # 마지막 달이 가장 작다
    assert eq.remaining_at(12, b) == 0 and eq.months_to_payoff(b) == 12
    assert abs(eq.total_interest(b) - 780_000) < 1e-6

    lv = Item("원리금균등", Category.LOAN, 12_000_000, repay_method="equal_payment", **common)
    pay = lv.level_payment(b)
    assert abs(pay - 1_066_190) < 1_000
    for m in range(12):
        assert abs(lv.payment_at(m, b) - pay) < 1e-6        # 매달 같은 금액
    assert abs(lv.remaining_at(12, b)) < 1e-6
    assert lv.total_interest(b) > eq.total_interest(b) and lv.total_interest(b) < bullet.total_interest(b)

    # 만기가 없으면 균등 상환은 계산되지 않는다 (이자만)
    noend = Item("만기없음", Category.LOAN, 12_000_000, rate=12.0, start_date="2026-01-01",
                 repay_method="equal_payment")
    assert noend.term_months(b) is None and noend.regular_repay_at(3, b) == 0
    assert noend.remaining_at(36, b) == 12_000_000

    # 저장/불러오기에서 방식이 유지되고, 예전 파일(상환율만 있는 것)은 rate 로 읽힌다
    assert Item.from_dict(lv.to_dict()).repay_method == "equal_payment"
    assert Item.from_dict({"name": "옛날", "category": "대출/이자", "amount": 100, "monthly_repay_rate": 10}).repay_method == "rate"
    assert Item.from_dict({"name": "옛날", "category": "대출/이자", "amount": 100}).repay_method == "bullet"


def test_equal_payment_in_plan():
    p = Plan(months=12, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 20_000_000))
    loan = p.add(Item("대출", Category.LOAN, 12_000_000, rate=12.0, include_principal=False,
                      start_date="2026-01-01", end_date="2027-01-01", repay_method="equal_payment"))
    pay = loan.level_payment(p.basis)
    assert abs(p.monthly_cost_at(0) - pay) < 1e-6           # 원금 미포함 → 원리금 전체가 월 지출
    assert abs(p.monthly_cost_at(11) - pay) < 1e-6
    assert p.monthly_cost_at(12) == 0                       # 만기 뒤엔 끝
    assert abs(p.net_at(12) - (20_000_000 - pay * 12)) < 1e-6


def test_shortfall():
    p = Plan(months=12, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 3_000_000))
    rent = p.add(Item("월세", Category.RENT, 500_000))
    s = p.shortfall()
    assert s["month"] == 7                                  # 3,000,000 - 500,000 x 7 < 0
    assert s["horizon"] == 36 and s["months"] == 30
    assert s["min_month"] == 36 and s["min_net"] == 3_000_000 - 500_000 * 36

    rent.amount = 50_000
    assert p.shortfall()["month"] is None                    # 36개월 내내 플러스
    assert p.shortfall(120)["month"] == 61                   # 더 멀리 보면 부족해진다


def test_income_period():
    from datetime import date as _date
    p = Plan(months=12, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 1_000_000))
    pay = p.add(Item("급여", Category.INCOME, 3_000_000,
                     start_date="2026-03-01", end_date="2026-07-01"))
    assert pay.uses_dates and pay.date_mode == "range" and pay.flow == "income"

    b = _date(2026, 1, 1)
    assert pay.monthly_income_at(1, b) == 0          # 아직 시작 전
    assert pay.monthly_income_at(2, b) == 3_000_000  # 3월부터
    assert pay.monthly_income_at(6, b) == 0          # 7월부터 끝
    assert p.monthly_income_at(0) == 0 and p.monthly_income_at(3) == 3_000_000

    # 4개월(3~6월)만 들어온다
    assert p.net_at(2) == 1_000_000
    assert p.net_at(6) == 1_000_000 + 3_000_000 * 4
    assert p.net_at(12) == 1_000_000 + 3_000_000 * 4
    assert p.summary().period_income == 3_000_000 * 4

    # 종료일을 비우면 계속
    pay.end_date = None
    assert p.net_at(12) == 1_000_000 + 3_000_000 * 10


def test_once_income_date():
    p = Plan(months=12, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 1_000_000))
    bonus = p.add(Item("성과급", Category.INCOME_ONCE, 5_000_000, start_date="2026-05-01"))
    assert bonus.date_mode == "once" and bonus.flow == "income"
    assert bonus.once_income() == 5_000_000 and bonus.once_cost() == 0
    assert bonus.monthly_income_at(4, p.basis) == 0          # 월 수입이 아니다

    assert p.once_income_at(3) == 0 and p.once_income_at(4) == 5_000_000
    assert p.net_at(3) == 1_000_000
    assert p.net_at(4) == 6_000_000 and p.net_at(12) == 6_000_000
    assert p.once_income() == 5_000_000

    s = p.summary()
    assert s.once_income == 5_000_000 and s.period_income == 5_000_000
    p.months = 3
    assert p.summary().once_income == 0                      # 기간 밖

    # 수입일을 비우면 기준일에 들어온다
    bonus.start_date = None
    assert p.once_income_at(0) == 5_000_000 and p.net_at(0) == 6_000_000


def test_income_date_in_sample():
    p = sample_plan()
    kinds = {i.category for i in p.items}
    assert Category.INCOME in kinds and Category.INCOME_ONCE in kinds
    assert p.summary().once_income == 3_000_000              # 6개월 뒤 성과급 (12개월 안)


def test_deposit_return():
    p = Plan(months=36, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 100_000_000))
    dep = p.add(Item("전세 보증금", Category.DEPOSIT, 80_000_000,
                     start_date="2026-04-01", end_date="2028-04-01"))
    assert dep.returnable and dep.once_month(p.basis) == 3 and dep.return_month(p.basis) == 27

    assert p.net_at(2) == 100_000_000                 # 아직 안 나감
    assert p.net_at(3) == 20_000_000                  # 보증금 나감
    assert p.net_at(26) == 20_000_000                 # 2년 동안 묶여 있다
    assert p.net_at(27) == 100_000_000                # 계약 끝 → 돌려받음

    # 반환일을 비우면 예전처럼 계속 묶여 있다
    dep.end_date = None
    assert dep.return_month(p.basis) is None and p.net_at(27) == 20_000_000

    # 보증금이 아닌 일시 지출은 반환일이 없다
    exp = Item("이사비", Category.EXPENSE, 1_000_000, end_date="2028-04-01")
    assert not exp.returnable and exp.return_month(p.basis) is None


def test_housing_types():
    p = Plan(months=36, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 300_000_000))

    # 전세: 보증금만, 만기에 반환
    j = p.add(Item("전셋집", Category.DEPOSIT, 100_000_000, housing_type="jeonse",
                   start_date="2026-04-01", end_date="2028-04-01"))
    assert j.housing_label == "전세" and j.housing_rent() == 0 and j.returnable
    assert p.monthly_cost_at(6) == 0
    assert p.net_at(3) == 200_000_000 and p.net_at(27) == 300_000_000

    # 반전세: 보증금 + 월세. 월세는 입주~만기 구간에만
    j.housing_type, j.monthly = "banjeonse", 600_000
    assert j.housing_rent() == 600_000
    assert p.monthly_cost_at(2) == 0           # 입주 전
    assert p.monthly_cost_at(3) == 600_000
    assert p.monthly_cost_at(26) == 600_000
    assert p.monthly_cost_at(27) == 0          # 만기 이후
    assert p.net_at(27) == 300_000_000 - 600_000 * 24

    # 매매: 돌려받지 않고 월세도 없다
    j.housing_type = "buy"
    assert j.is_purchase and not j.returnable and j.housing_rent() == 0
    assert j.return_month(p.basis) is None     # 만기가 있어도 무시
    assert p.net_at(27) == 200_000_000

    # 형태를 안 주면 월세 유무로 정해진다
    assert Item("a", Category.DEPOSIT, 1).housing_type == "jeonse"
    assert Item("b", Category.DEPOSIT, 1, monthly=500_000).housing_type == "wolse"
    # 주거가 아닌 분류는 형태·월세를 갖지 않는다
    other = Item("c", Category.EXPENSE, 1, housing_type="buy", monthly=1)
    assert other.housing_type == "" and other.monthly == 0

    # 저장/불러오기, 예전 파일의 '보증금' 분류
    assert Item.from_dict(j.to_dict()).housing_type == "buy"
    old = Item.from_dict({"name": "옛날", "category": "보증금", "amount": 1_000})
    assert old.category is Category.DEPOSIT and old.housing_type == "jeonse"


def test_saving():
    p = Plan(months=24, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 10_000_000))
    sv = p.add(Item("적금", Category.SAVING, 500_000,
                    start_date="2026-01-01", end_date="2027-01-01"))   # 12개월 납입

    assert sv.saving_months(0, p.basis) == 0 and sv.saving_months(5, p.basis) == 5
    assert sv.saving_months(12, p.basis) == 12
    assert sv.saving_months(24, p.basis) == 12                 # 만기 뒤엔 더 안 넣는다

    assert p.monthly_cost_at(0) == 500_000                     # 납입 기간 동안 매달 나가고
    assert p.monthly_cost_at(12) == 0
    assert p.capital_at(6) == 10_000_000 + 500_000 * 6         # 그만큼 자본으로 쌓인다
    assert p.net_at(6) == 10_000_000                           # 순 자본은 그대로 (돈이 옮겨간 것뿐)
    assert p.net_at(12) == 10_000_000 and p.net_at(24) == 10_000_000
    assert sv.saving_balance_at(12, p.basis) == 6_000_000

    # 이율을 넣으면 이자만큼 순 자본이 는다
    sv.rate = 3.0
    mr = 0.03 / 12
    # 0개월에 넣은 돈은 1개월 시점에 한 달치 이자가 붙는다
    assert abs(sv.saving_balance_at(1, p.basis) - 500_000 * (1 + mr)) < 1e-6
    assert abs(sv.saving_balance_at(2, p.basis) - (1_000_000 + 500_000 * mr * 3)) < 1e-6   # 2 + 1
    bal = sv.saving_balance_at(12, p.basis)
    assert abs(bal - (6_000_000 + 500_000 * mr * 78)) < 1e-6   # 12+11+...+1 = 78개월분
    assert sv.saving_balance_at(24, p.basis) == bal            # 만기 뒤엔 이자도 멈춘다
    assert abs(p.net_at(24) - (10_000_000 + 500_000 * mr * 78)) < 1e-6

    # 종료일이 없으면 계속 넣는다
    sv.end_date = None
    assert sv.saving_months(24, p.basis) == 24


def test_planned_flows():
    p = Plan(months=12, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 50_000_000))
    p.add(Item("급여", Category.INCOME, 3_000_000))
    p.add(Item("월세", Category.RENT, 500_000))
    p.add(Item("이사비", Category.EXPENSE, 1_200_000, start_date="2026-03-01"))
    p.add(Item("성과급", Category.INCOME_ONCE, 2_000_000, start_date="2026-04-01"))
    p.add(Item("전셋집", Category.DEPOSIT, 20_000_000, housing_type="banjeonse", monthly=300_000,
               start_date="2026-02-01", end_date="2026-08-01"))

    assert p.planned_out_at(0) == 500_000                       # 월세만
    assert p.planned_in_at(0) == 3_000_000

    # 2월: 보증금이 나가고 월세(주거)도 시작
    assert p.planned_out_at(1) == 500_000 + 300_000 + 20_000_000
    # 3월: 이사비
    assert p.planned_out_at(2) == 500_000 + 300_000 + 1_200_000
    # 4월: 성과급
    assert p.planned_in_at(3) == 3_000_000 + 2_000_000
    # 8월: 보증금 반환, 주거 월세는 끝
    assert p.planned_in_at(7) == 3_000_000 + 20_000_000
    assert p.planned_out_at(7) == 500_000


def test_planned_out_includes_loan_principal():
    p = Plan(months=12, start_date="2026-01-01")
    loan = p.add(Item("대출", Category.LOAN, 12_000_000, rate=12.0, include_principal=True,
                      start_date="2026-01-01", end_date="2027-01-01", repay_method="equal_principal"))
    # 원금을 자본에 넣었으면 월 지출에는 이자만 잡히지만, 실제로 나가는 돈은 원금 상환까지다
    assert p.monthly_cost_at(0) == 120_000
    assert p.planned_out_at(0) == 120_000 + 1_000_000
    assert loan.regular_repay_at(0, p.basis) == 1_000_000


def test_past_once_costs_are_not_counted_again():
    """기준일 전에 치른 보증금·이사비는 보유 자금에서 이미 빠져 있다. 또 빼면 이중 계산이다."""
    p = Plan(months=12, start_date="2026-10-28")
    p.add(Item("현금", Category.CASH, 5_000_000))
    # 2023-12 에 들어간 반전세 보증금, 만기 없음
    old = p.add(Item("전셋집", Category.DEPOSIT, 25_000_000, housing_type="banjeonse",
                     monthly=300_000, start_date="2023-12-01"))
    assert old.once_month(p.basis) < 0
    assert p.once_cost_at(0) == 0 and p.net_at(0) == 5_000_000
    assert p.summary().once_cost == 0
    # 월세는 그대로 나간다 (이미 입주했으니 계속 활성)
    assert p.monthly_cost_at(0) == 300_000

    # 만기를 넣으면 그 달에 돌려받는 것만 들어온다
    old.end_date = "2027-04-01"
    assert old.return_month(p.basis) == 6
    assert p.once_cost_at(6) == 0                       # 낸 적 없는 돈처럼 취급
    assert p.once_income_at(5) == 0 and p.once_income_at(6) == 25_000_000
    assert p.net_at(6) - p.net_at(5) == 25_000_000 - 300_000
    assert p.summary().once_income == 25_000_000

    # 이미 돌려받은 보증금은 아무 영향이 없다
    old.start_date, old.end_date = "2023-12-01", "2025-12-01"
    assert p.once_cost_at(0) == 0 and p.once_income_at(12) == 0
    assert p.net_at(0) == 5_000_000


def test_pending_inflows():
    """기간이 끝난 뒤에 들어올 돈. 기간 안에 들어오는 건 이미 순 자본에 들어 있다."""
    p = Plan(months=6, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 1_000_000))
    late = p.add(Item("전셋집", Category.DEPOSIT, 20_000_000, housing_type="jeonse",
                      start_date="2025-01-01", end_date="2027-01-01"))     # 12개월 뒤 반환
    soon = p.add(Item("원룸", Category.DEPOSIT, 5_000_000, housing_type="wolse", monthly=300_000,
                      start_date="2025-06-01", end_date="2026-04-01"))     # 3개월 뒤 반환 (기간 안)
    loan = p.add(Item("전세자금대출", Category.LOAN, 90_000_000, rate=2.0,
                      start_date="2026-11-01"))                            # 10개월 뒤 실행

    assert late.return_month(p.basis) == 12 and soon.return_month(p.basis) == 3
    rows = p.pending_inflows()
    assert [(r["name"], r["kind"], r["month"]) for r in rows] == [
        ("전세자금대출", "loan", 10), ("전셋집", "deposit", 12)]        # 이른 순
    assert rows[1]["amount"] == 20_000_000
    assert p.pending_total("deposit") == 20_000_000
    assert p.pending_total("loan") == 90_000_000
    assert p.pending_total() == 110_000_000

    # 기간을 늘려 모두 기간 안에 들어오면 남는 게 없다
    p.months = 24
    assert p.pending_inflows() == [] and p.pending_total() == 0
    p.months = 6

    # 원금을 자본에 넣지 않는 대출은 '들어올 돈'이 아니다 (빌려서 바로 나가는 돈)
    loan.include_principal = False
    assert [r["kind"] for r in p.pending_inflows()] == ["deposit"]
    loan.include_principal = True

    # 중도 상환이 걸려 있으면 실행 시점의 잔액만큼만 센다
    loan.repayments = [{"date": "2026-11-01", "amount": 10_000_000}]
    assert [r["amount"] for r in p.pending_inflows() if r["kind"] == "loan"] == [80_000_000]
    loan.repayments = []

    # 반환일이 없거나 이미 지난 보증금은 세지 않는다
    late.end_date = None
    assert [r["kind"] for r in p.pending_inflows()] == ["loan"]
    late.end_date = "2025-06-01"
    assert [r["kind"] for r in p.pending_inflows()] == ["loan"]

    # 가까운 순으로
    late.end_date = "2028-01-01"
    soon.end_date = "2027-06-01"
    assert [r["month"] for r in p.pending_inflows()] == [10, 17, 24]


def test_growth_rate():
    """해마다 한 번씩 오르는 금액 (급여 인상, 물가·월세 인상)."""
    p = Plan(months=36, start_date="2026-01-01")
    pay = p.add(Item("급여", Category.INCOME, 2_000_000, growth=5.0))
    assert pay.uses_growth and pay.growth == 5.0

    # 1년마다 한 번, 그 사이에는 그대로
    assert pay.growth_factor(0, p.basis) == 1.0
    assert p.monthly_income_at(11) == 2_000_000
    assert p.monthly_income_at(12) == 2_100_000
    assert p.monthly_income_at(23) == 2_100_000
    assert p.monthly_income_at(24) == 2_205_000
    assert abs(p.monthly_income_at(36) - 2_000_000 * 1.05 ** 3) < 1e-6

    # 시작일이 뒤면 그 시점부터 1년을 센다
    pay.start_date = "2026-07-01"
    assert p.monthly_income_at(17) == 2_000_000          # 시작 11개월째
    assert p.monthly_income_at(18) == 2_100_000          # 시작 12개월째
    pay.start_date = None

    # 지출도 오른다 (물가·월세)
    rent = p.add(Item("월세", Category.RENT, 500_000, growth=4.0))
    assert p.monthly_cost_at(11) == 500_000 and p.monthly_cost_at(12) == 520_000
    fixed = p.add(Item("생활비", Category.FIXED, 1_000_000, growth=2.0))
    assert p.monthly_cost_at(12) == 520_000 + 1_020_000

    # 순 자본에도 그대로 반영된다 (1년차 12달 + 2년차 12달 ...)
    p.items = [pay]
    assert p.net_at(24) == (2_000_000 * 12) + (2_100_000 * 12)

    # 상승률을 쓰지 않는 분류는 값을 갖지 않는다
    for cat in (Category.CASH, Category.BANK, Category.LOAN, Category.DEPOSIT,
                Category.EXPENSE, Category.INCOME_ONCE, Category.SAVING):
        it = Item("x", cat, 1_000, growth=5.0)
        assert not it.uses_growth and it.growth == 0
        assert it.growth_factor(24, p.basis) == 1.0

    # 저장/불러오기
    assert Item.from_dict(rent.to_dict()).growth == 4.0
    assert Item.from_dict({"name": "옛날", "category": "월세", "amount": 1}).growth == 0.0
    assert fixed.growth == 2.0


def test_saving_support():
    """청년도약계좌처럼 남이 보태 주는 돈. 내 지갑에서는 안 나가고 잔액만 는다."""
    p = Plan(months=60, start_date="2026-01-01")
    sv = p.add(Item("청년도약계좌", Category.SAVING, 200_000, support=300_000,
                    start_date="2026-01-01", end_date="2031-01-01"))
    assert sv.uses_support and sv.saving_deposit() == 500_000

    # 나가는 돈은 내 납입액뿐
    assert p.monthly_cost_at(0) == 200_000
    # 쌓이는 돈은 지원금까지
    assert sv.saving_balance_at(12, p.basis) == 500_000 * 12
    assert sv.support_total_at(12, p.basis) == 300_000 * 12
    assert sv.support_total_at(0, p.basis) == 0

    # 지원금만큼 순 자본이 는다 (12달 × 30만)
    assert p.net_at(12) == 300_000 * 12
    assert p.net_at(60) == 300_000 * 60
    assert p.net_at(72) == 300_000 * 60                  # 만기 뒤엔 멈춘다

    # 이자는 지원금까지 합친 금액에 붙는다
    sv.rate = 3.0
    mr = 0.03 / 12
    assert abs(sv.saving_balance_at(12, p.basis) - (500_000 * 12 + 500_000 * mr * 78)) < 1e-6

    # 지원금이 없으면 예전과 같다
    sv.support = 0
    assert sv.saving_deposit() == 200_000 and sv.support_total_at(12, p.basis) == 0
    assert p.net_at(12) == 0 + 200_000 * mr * 78

    # 적금이 아닌 분류는 지원금을 갖지 않는다
    for cat in (Category.CASH, Category.BANK, Category.LOAN, Category.INCOME,
                Category.RENT, Category.DEPOSIT, Category.EXPENSE):
        it = Item("x", cat, 1_000, support=50_000)
        assert not it.uses_support and it.support == 0
        assert it.saving_deposit() == 0

    # 저장 / 불러오기
    sv.support = 300_000
    assert Item.from_dict(sv.to_dict()).support == 300_000
    assert Item.from_dict({"name": "옛날", "category": "적금/저축(월)", "amount": 1}).support == 0.0


def test_locked_saving():
    """적금은 자본이지만 만기 전까지는 손댈 수 없다. 묶어 두면 만기에 한꺼번에 들어온다."""
    p = Plan(months=12, target=50_000_000, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 10_000_000))
    sv = p.add(Item("청년도약계좌", Category.SAVING, 200_000, support=300_000, locked=True,
                    start_date="2026-01-01", end_date="2031-01-01"))

    assert sv.maturity_month(p.basis) == 60 and sv.is_locked(p.basis)

    # 만기 전에는 보유 자금에 안 들어간다 (나가는 돈만 반영)
    assert p.capital_at(12) == 10_000_000
    assert p.capital_at(59) == 10_000_000
    assert p.net_at(12) == 10_000_000 - 200_000 * 12

    # 만기에 한꺼번에 들어온다 — 보유 자금이 아니라 '일시 수입' 으로 들어와 요약에 드러난다
    assert p.capital_at(60) == 10_000_000
    assert p.once_income_at(59) == 0
    assert p.once_income_at(60) == 500_000 * 60
    assert p.once_income_at(72) == 500_000 * 60           # 만기 뒤엔 그대로
    assert p.net_at(60) == 10_000_000 + 300_000 * 60      # 지원금만큼 는다
    p.months = 60
    assert p.summary().once_income == 500_000 * 60
    assert p.planned_in_at(60) == 500_000 * 60
    p.months = 12

    # 묶임을 풀면 예전처럼 쌓이는 대로 자본
    sv.locked = False
    assert p.capital_at(12) == 10_000_000 + 500_000 * 12
    assert p.net_at(12) == 10_000_000 + 300_000 * 12
    sv.locked = True

    # 만기가 없으면 묶임이 성립하지 않는다 (영원히 못 쓰는 돈은 없다)
    sv.end_date = None
    assert sv.maturity_month(p.basis) is None and not sv.is_locked(p.basis)
    assert p.capital_at(12) == 10_000_000 + 500_000 * 12
    sv.end_date = "2031-01-01"

    # 목표 바의 '앞으로 들어올 돈' 에 만기 수령액이 잡힌다
    rows = p.pending_inflows()
    assert [(r["kind"], r["month"]) for r in rows] == [("saving", 60)]
    assert rows[0]["amount"] == 500_000 * 60
    assert p.pending_total("saving") == 500_000 * 60

    # 기간이 만기를 넘으면 이미 순 자본에 있으므로 따로 세지 않는다
    p.months = 60
    assert p.pending_inflows() == []
    p.months = 12

    # 묶임을 풀면 들어올 돈이 아니라 이미 가진 돈이다
    sv.locked = False
    assert p.pending_inflows() == []

    # 적금이 아닌 분류는 묶을 수 없다
    for cat in (Category.CASH, Category.BANK, Category.LOAN, Category.DEPOSIT, Category.INCOME):
        it = Item("x", cat, 1_000, locked=True)
        assert it.locked is False and not it.is_locked(p.basis)

    # 저장 / 불러오기
    sv.locked = True
    assert Item.from_dict(sv.to_dict()).locked is True
    assert Item.from_dict({"name": "옛날", "category": "적금/저축(월)", "amount": 1}).locked is False
