"""돈이 실제로 맞는지 보는 검산.

test_model.py 는 함수끼리 아귀가 맞는지를 보지만, 요약의 항등식은 net_at 의
정의와 같은 식이라 자기 자신을 검산하는 꼴이 된다. 여기서는 **답을 손으로 아는**
시나리오만 만들어, 나온 숫자가 그 답과 같은지 본다.

시간 축 약속 (여기서 못을 박아 둔다):
  · 0개월 = 기준일. m개월째의 값은 **그 달에 돈이 오가기 전** 상태다.
  · 그래서 m개월째의 적금 납입 횟수·대출 이자 횟수는 m 번이다.
  · 항목 날짜는 그 날이 지난 첫 눈금으로 올려 붙인다 (month_offset).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capital_calc.model import Category, Item, Plan  # noqa: E402

BASIS = "2026-11-02"


def mk(months: int, *items: Item, basis: str = BASIS, target: float = 0.0) -> Plan:
    p = Plan(months=months, target=target, start_date=basis)
    for it in items:
        p.add(it)
    return p


def near(a: float, b: float) -> bool:
    return abs(a - b) < 1.0


# ───────────────────────── 적금은 '옮기는 돈'

def test_saving_without_interest_does_not_change_net():
    """적금 납입은 월 지출로 빠지지만 그만큼 통장에 쌓인다. 이자가 0이면 순 자본은 그대로."""
    p = mk(12, Item("현금", Category.CASH, 10_000_000),
               Item("적금", Category.SAVING, 300_000, rate=0.0))
    for m in range(13):
        assert near(p.net_at(m), 10_000_000), f"{m}개월에서 돈이 사라지거나 생겼다"


def test_saving_support_is_the_only_gain():
    """정부 지원금은 공짜로 들어오는 돈 — 딱 납입 횟수만큼만 늘어야 한다."""
    p = mk(10, Item("현금", Category.CASH, 10_000_000),
               Item("청년적금", Category.SAVING, 200_000, rate=0.0, support=300_000))
    for m in range(11):
        assert near(p.net_at(m), 10_000_000 + 300_000 * m)


def test_locked_saving_leaves_hand_and_comes_back_at_maturity():
    """묶인 적금은 만기 전엔 자본에서 빠지고, 만기에 통째로 돌아온다."""
    p = mk(30, Item("현금", Category.CASH, 10_000_000),
               Item("묶인적금", Category.SAVING, 500_000, rate=0.0, locked=True,
                    start_date=BASIS, end_date="2027-11-02"))
    assert near(p.net_at(5), 10_000_000 - 500_000 * 5)
    assert near(p.net_at(11), 10_000_000 - 500_000 * 11)
    assert near(p.net_at(12), 10_000_000)          # 만기: 넣은 돈이 통째로
    assert near(p.net_at(13), 10_000_000)          # 그 뒤로는 그대로


# ───────────────────────── 대출

def test_bullet_loan_costs_only_interest():
    """만기 일시 상환: 원금은 들어왔다 나가고, 남는 건 이자 손실뿐."""
    p = mk(24, Item("현금", Category.CASH, 5_000_000),
               Item("대출", Category.LOAN, 100_000_000, rate=3.6, include_principal=True,
                    repay_method="bullet", start_date=BASIS, end_date="2027-11-02"))
    assert near(p.net_at(0), 105_000_000)                        # 원금이 손에 있다
    assert near(p.net_at(6), 105_000_000 - 300_000 * 6)          # 월 이자 30만
    assert near(p.net_at(13), 5_000_000 - 300_000 * 12)          # 갚고 나면 이자만 손실
    assert near(p.net_at(20), 5_000_000 - 300_000 * 12)          # 그 뒤로 더 나갈 게 없다


def test_loan_without_principal_only_drains_interest():
    """원금을 자본에 안 넣는 대출은 이자만 축낸다."""
    p = mk(12, Item("현금", Category.CASH, 5_000_000),
               Item("대출", Category.LOAN, 100_000_000, rate=3.6, include_principal=False,
                    repay_method="bullet", start_date=BASIS))
    assert near(p.net_at(5), 5_000_000 - 300_000 * 5)


# ───────────────────────── 주거

def test_jeonse_deposit_comes_back_whole():
    """전세 보증금은 나갔다가 돌아오면 본전."""
    p = mk(30, Item("현금", Category.CASH, 50_000_000),
               Item("전셋집", Category.DEPOSIT, 30_000_000, housing_type="jeonse",
                    start_date=BASIS, end_date="2028-11-02"))
    assert near(p.net_at(0), 20_000_000)
    assert near(p.net_at(23), 20_000_000)
    assert near(p.net_at(24), 50_000_000)


def test_banjeonse_takes_deposit_and_rent():
    p = mk(12, Item("현금", Category.CASH, 50_000_000),
               Item("반전세", Category.DEPOSIT, 20_000_000, housing_type="banjeonse",
                    monthly=500_000, start_date=BASIS))
    assert near(p.net_at(6), 50_000_000 - 20_000_000 - 500_000 * 6)


# ───────────────────────── 월 수지 · 일시 · 상승률

def test_monthly_flows_are_plain_addition():
    p = mk(12, Item("현금", Category.CASH, 5_000_000),
               Item("급여", Category.INCOME, 2_000_000),
               Item("월세", Category.RENT, 700_000))
    for m in range(13):
        assert near(p.net_at(m), 5_000_000 + 1_300_000 * m)


def test_once_items_land_on_their_month_only():
    p = mk(12, Item("현금", Category.CASH, 1_000_000),
               Item("성과급", Category.INCOME_ONCE, 3_000_000, start_date="2027-02-02"),
               Item("이사비", Category.EXPENSE, 500_000, start_date="2027-01-02"))
    assert near(p.net_at(1), 1_000_000)
    assert near(p.net_at(2), 500_000)            # 이사비만 나갔다
    assert near(p.net_at(3), 3_500_000)          # 성과급이 들어왔다
    assert near(p.net_at(9), 3_500_000)          # 한 번씩만


def test_growth_raises_once_a_year():
    p = mk(30, Item("현금", Category.CASH, 0),
               Item("급여", Category.INCOME, 1_000_000, growth=10.0, start_date=BASIS))
    want = 0.0
    for m in range(25):
        assert near(p.net_at(m), want), f"{m}개월"
        want += 1_000_000 * (1.1 ** (m // 12))


# ───────────────────────── 요약·그래프가 같은 값을 말하는가

def test_summary_adds_up_on_screen():
    """요약을 위에서 아래로 그대로 더하면 'N개월 후 순 자본' 이 나와야 한다."""
    p = mk(12, Item("현금", Category.CASH, 10_000_000),
               Item("적금", Category.SAVING, 300_000, rate=5.0),
               Item("급여", Category.INCOME, 2_000_000),
               Item("월세", Category.RENT, 700_000),
               Item("이사비", Category.EXPENSE, 500_000, start_date="2027-03-02"))
    s = p.summary()
    assert near(p.capital_at(p.months) - s.required + s.period_income, s.net)


def test_trend_series_matches_point_values():
    """그래프(net_series)와 한 점씩 묻는 값(net_at)이 달라선 안 된다."""
    p = mk(18, Item("현금", Category.CASH, 10_000_000),
               Item("적금", Category.SAVING, 300_000, rate=5.0, locked=True,
                    start_date=BASIS, end_date="2027-11-02"),
               Item("대출", Category.LOAN, 50_000_000, rate=4.0, include_principal=True,
                    repay_method="equal_principal", start_date="2026-12-02",
                    end_date="2028-12-02"),
               Item("급여", Category.INCOME, 2_500_000, growth=3.0))
    series = p.net_series(36)
    for m in range(37):
        assert near(series[m], p.net_at(m)), f"{m}개월"


# ───────────────────────── 금융 공식과 맞는가

LOAN_A, LOAN_RATE, LOAN_N = 120_000_000, 4.8, 24
LOAN_I = LOAN_RATE / 100 / 12


def loan(method: str):
    p = Plan(months=40, start_date=BASIS)
    it = p.add(Item("대출", Category.LOAN, LOAN_A, rate=LOAN_RATE, include_principal=True,
                    repay_method=method, start_date=BASIS, end_date="2028-11-02"))
    return p, it


def test_equal_payment_matches_annuity_formula():
    """원리금 균등: 매달 같은 돈을 내고, 잔액은 연금 공식대로 줄어야 한다."""
    p, it = loan("equal_payment")
    f = (1 + LOAN_I) ** LOAN_N
    pay = LOAN_A * LOAN_I * f / (f - 1)
    assert abs(it.level_payment(p.basis) - pay) < 0.01

    bal = LOAN_A
    for k in range(LOAN_N):
        assert near(it.remaining_at(k, p.basis), bal), f"{k}개월 잔액"
        interest = bal * LOAN_I
        assert near(it.interest_at(k, p.basis), interest)
        assert near(it.regular_repay_at(k, p.basis), pay - interest)
        assert near(it.payment_at(k, p.basis), pay)        # 매달 같은 금액
        bal -= pay - interest
    assert near(it.remaining_at(LOAN_N, p.basis), 0.0)
    assert near(it.total_interest(p.basis), pay * LOAN_N - LOAN_A)


def test_equal_principal_matches_schedule():
    """원금 균등: 원금은 매달 똑같이, 이자는 줄어드는 잔액에 붙는다."""
    p, it = loan("equal_principal")
    per = LOAN_A / LOAN_N
    bal = LOAN_A
    for k in range(LOAN_N):
        assert near(it.remaining_at(k, p.basis), bal), f"{k}개월 잔액"
        assert near(it.regular_repay_at(k, p.basis), per)
        assert near(it.interest_at(k, p.basis), bal * LOAN_I)
        assert near(it.payment_at(k, p.basis), per + bal * LOAN_I)
        bal -= per
    assert near(it.remaining_at(LOAN_N, p.basis), 0.0)
    # 총 이자 = A·i·(N+1)/2
    assert near(it.total_interest(p.basis), LOAN_A * LOAN_I * (LOAN_N + 1) / 2)


def test_bullet_loan_keeps_principal_until_maturity():
    p, it = loan("bullet")
    for k in range(LOAN_N):
        assert near(it.remaining_at(k, p.basis), LOAN_A)
        assert near(it.interest_at(k, p.basis), LOAN_A * LOAN_I)
    assert near(it.total_interest(p.basis), LOAN_A * LOAN_I * LOAN_N)


def test_saving_interest_is_simple_interest_per_deposit():
    """적금 이자는 납입분마다 묶여 있던 개월 수에 붙는 단리다 (은행 적금과 같은 방식).

    세금(이자소득세)은 떼지 않는다 — 세후로 보려면 연이율을 낮춰 넣어야 한다.
    """
    S, rate, n = 500_000, 6.0, 24
    i = rate / 100 / 12
    p = Plan(months=40, start_date=BASIS)
    sv = p.add(Item("적금", Category.SAVING, S, rate=rate,
                    start_date=BASIS, end_date="2028-11-02"))
    for m in range(n + 1):
        want = S * m + sum(S * i * (m - j) for j in range(m))
        assert near(sv.saving_balance_at(m, p.basis), want), f"{m}개월"
    # 만기 이자 = S·i·n(n+1)/2
    assert near(sv.saving_balance_at(n, p.basis) - S * n, S * i * n * (n + 1) / 2)
    # 만기 뒤엔 납입도 이자도 멈춘다
    assert near(sv.saving_balance_at(n + 5, p.basis), sv.saving_balance_at(n, p.basis))



# ───────────────────────── 잠시 꺼 둔 항목

def test_inactive_items_leave_the_calculation_but_stay_in_the_list():
    """꺼 둔 항목은 계산에서만 빠진다 (지운 것과 같은 숫자가 나와야 한다)."""
    def plan(loan_on: bool) -> Plan:
        p = mk(12, Item("현금", Category.CASH, 10_000_000),
                   Item("급여", Category.INCOME, 2_000_000))
        if loan_on:
            p.add(Item("대출", Category.LOAN, 50_000_000, rate=6.0, include_principal=True,
                       repay_method="bullet", start_date=BASIS))
        return p

    with_loan = plan(True)
    without = plan(False)
    off = plan(True)
    off.items[2].active = False

    assert len(off.items) == 3 and len(off.live) == 2 and off.off_count == 1
    for m in range(13):
        assert near(off.net_at(m), without.net_at(m)), f"{m}개월"
    assert not near(with_loan.net_at(6), without.net_at(6))     # 켜면 달라진다

    off.items[2].active = True                                   # 다시 켜면 그대로 돌아온다
    assert near(off.net_at(6), with_loan.net_at(6))


def test_active_flag_survives_save():
    p = mk(12, Item("현금", Category.CASH, 1_000_000),
               Item("월세", Category.RENT, 700_000))
    p.items[1].active = False
    p2 = Plan.from_dict(p.to_dict())
    assert [i.active for i in p2.items] == [True, False]
    assert near(p2.net_at(5), 1_000_000)                         # 월세가 안 나간다


# ───────────────────────── 몇 달마다 되풀이되는 일시 지출·수입

def test_yearly_expense_lands_once_a_year():
    """자동차세처럼 해마다 나가는 돈 — 기준일에서 1개월 뒤부터 12개월마다."""
    p = mk(36, Item("현금", Category.CASH, 10_000_000),
               Item("자동차세", Category.EXPENSE, 500_000, start_date="2026-12-02", every=12))
    for m in range(37):
        want = 10_000_000 - 500_000 * (1 + (m - 1) // 12 if m >= 1 else 0)
        assert near(p.net_at(m), want), f"{m}개월"
    assert near(p.summary().once_cost, 1_500_000)      # 36개월 안에 세 번


def test_repeat_stops_at_the_end_date():
    p = mk(36, Item("현금", Category.CASH, 10_000_000),
               Item("보험", Category.EXPENSE, 300_000, start_date="2026-12-02",
                    end_date="2028-06-02", every=6))
    it = p.items[1]
    assert [m for m in range(37) if it.occurs_at(m, p.basis)] == [1, 7, 13, 19]
    assert near(p.net_at(36), 10_000_000 - 300_000 * 4)


def test_repeat_that_started_before_the_basis_still_counts_later_rounds():
    """작년부터 내던 돈이면, 기준일 전 회차는 빼고 앞으로 나갈 것만 센다."""
    p = mk(24, Item("현금", Category.CASH, 10_000_000),
               Item("자동차세", Category.EXPENSE, 500_000, start_date="2025-06-02", every=12))
    it = p.items[1]
    assert it.once_month(p.basis) == -17                  # 기준일보다 한참 앞
    assert [m for m in range(25) if it.occurs_at(m, p.basis)] == [7, 19]
    assert near(p.net_at(6), 10_000_000)
    assert near(p.net_at(7), 9_500_000)


def test_repeating_income_adds_up_the_same_way():
    p = mk(24, Item("현금", Category.CASH, 0),
               Item("상여금", Category.INCOME_ONCE, 1_000_000, start_date="2027-01-02", every=6))
    assert near(p.net_at(1), 0)
    assert near(p.net_at(2), 1_000_000)
    assert near(p.net_at(8), 2_000_000)
    assert near(p.net_at(24), 4_000_000)
    assert near(p.summary().once_income, 4_000_000)


def test_a_plain_once_item_is_unchanged():
    """되풀이를 안 쓰면 예전과 똑같아야 한다."""
    p = mk(24, Item("현금", Category.CASH, 1_000_000),
               Item("이사비", Category.EXPENSE, 500_000, start_date="2027-01-02"))
    assert near(p.net_at(1), 1_000_000)
    assert near(p.net_at(2), 500_000)
    assert near(p.net_at(24), 500_000)


def test_planned_out_sees_each_round(tmp_path=None):
    """가계부 비교(그 달에 나갈 돈)도 회차마다 잡힌다."""
    p = mk(36, Item("자동차세", Category.EXPENSE, 500_000, start_date="2026-12-02", every=12))
    assert near(p.planned_out_at(1), 500_000)
    assert near(p.planned_out_at(2), 0)
    assert near(p.planned_out_at(13), 500_000)


def test_every_survives_save():
    p = mk(12, Item("자동차세", Category.EXPENSE, 500_000, start_date="2026-12-02", every=12))
    p2 = Plan.from_dict(p.to_dict())
    assert p2.items[0].every == 12 and p2.items[0].repeats


def test_item_planned_amounts_add_up_to_the_plan():
    """항목별 '그 달에 오가는 돈' 을 모으면 계획 전체와 같아야 한다 (한 곳에서만 계산)."""
    p = mk(24, Item("현금", Category.CASH, 20_000_000),
               Item("급여", Category.INCOME, 2_500_000, growth=3.0),
               Item("월세", Category.RENT, 700_000),
               Item("자동차세", Category.EXPENSE, 500_000, start_date="2026-12-02", every=12),
               Item("전셋집", Category.DEPOSIT, 30_000_000, housing_type="jeonse",
                    start_date=BASIS, end_date="2028-11-02"),
               Item("대출", Category.LOAN, 50_000_000, rate=4.0, include_principal=True,
                    repay_method="equal_principal", start_date=BASIS, end_date="2028-11-02"),
               Item("적금", Category.SAVING, 300_000, rate=3.0, locked=True,
                    start_date=BASIS, end_date="2027-11-02"))
    b = p.basis
    for m in range(25):
        assert near(sum(i.planned_out_at(m, b) for i in p.live), p.planned_out_at(m)), f"{m}개월 지출"
        assert near(sum(i.planned_in_at(m, b) for i in p.live), p.planned_in_at(m)), f"{m}개월 수입"


# ───────────────────────── 이자소득세 · 복리 · 물가

def test_interest_tax_takes_15_4_percent_of_the_interest_only():
    """세금은 이자에만 붙는다. 원금은 그대로다."""
    from capital_calc.model import INTEREST_TAX

    keep = 1 - INTEREST_TAX / 100

    # 예금: 이자가 매달 수입으로 들어온다
    gross = mk(12, Item("예금", Category.BANK, 10_000_000, rate=4.0))
    net = mk(12, Item("예금", Category.BANK, 10_000_000, rate=4.0, after_tax=True))
    assert near(gross.net_at(12), 10_000_000 + 400_000)
    assert near(net.net_at(12), 10_000_000 + 400_000 * keep)

    # 적금: 만기 잔액의 이자분만 깎인다
    g = mk(12, Item("적금", Category.SAVING, 500_000, rate=4.0,
                    start_date=BASIS, end_date="2027-11-02"))
    n = mk(12, Item("적금", Category.SAVING, 500_000, rate=4.0, after_tax=True,
                    start_date=BASIS, end_date="2027-11-02"))
    gi = g.items[0].saving_balance_at(12, g.basis) - 6_000_000
    ni = n.items[0].saving_balance_at(12, n.basis) - 6_000_000
    assert near(ni, gi * keep) and gi > 0


def test_tax_only_applies_where_interest_is_earned():
    """대출 이자에는 세금이 없다 (내는 돈이다)."""
    loan = Item("대출", Category.LOAN, 10_000_000, rate=6.0, after_tax=True,
                include_principal=False, repay_method="bullet", start_date=BASIS)
    assert loan.taxes_interest is False
    p = mk(12, Item("현금", Category.CASH, 10_000_000), loan)
    assert near(p.net_at(6), 10_000_000 - 50_000 * 6)      # 월 이자 5만 그대로


def test_compound_grows_faster_than_simple():
    """복리 예금은 이자를 빼지 않고 안에서 굴린다 (월 수입이 아니라 잔액이 는다)."""
    simple = mk(24, Item("예금", Category.BANK, 10_000_000, rate=6.0))
    comp = mk(24, Item("예금", Category.BANK, 10_000_000, rate=6.0, compound=True))

    i = 0.06 / 12
    assert near(comp.items[0].bank_balance_at(24), 10_000_000 * (1 + i) ** 24)
    assert near(comp.capital_at(24), 10_000_000 * (1 + i) ** 24)
    assert near(comp.monthly_income_at(0), 0)              # 이자가 밖으로 나오지 않는다
    assert near(simple.monthly_income_at(0), 50_000)
    assert comp.net_at(24) > simple.net_at(24)
    assert near(comp.net_at(0), simple.net_at(0))          # 시작은 같다


def test_compound_saving_matches_the_formula():
    """월복리 적금: 납입분마다 (1+i)^묶인개월."""
    S, rate, n = 500_000, 6.0, 12
    i = rate / 100 / 12
    p = mk(24, Item("적금", Category.SAVING, S, rate=rate, compound=True,
                    start_date=BASIS, end_date="2027-11-02"))
    sv = p.items[0]
    want = sum(S * (1 + i) ** (n - j) for j in range(n))
    assert near(sv.saving_balance_at(n, p.basis), want)


def test_inflation_converts_to_todays_money():
    p = mk(24, Item("현금", Category.CASH, 10_000_000))
    assert near(p.real_value(10_000_000), 10_000_000)       # 물가 0 이면 그대로

    p.inflation = 3.0
    assert near(p.real_value(10_000_000), 10_000_000 / 1.03 ** 2)
    assert near(p.real_value(10_000_000, 12), 10_000_000 / 1.03)
    assert near(p.real_value(10_000_000, 0), 10_000_000)
    assert near(p.net_at(24), 10_000_000)                   # 계산 자체는 건드리지 않는다


def test_tax_and_compound_survive_save():
    p = mk(12, Item("예금", Category.BANK, 10_000_000, rate=4.0, after_tax=True, compound=True))
    p.inflation = 2.5
    p2 = Plan.from_dict(p.to_dict())
    assert p2.items[0].after_tax and p2.items[0].compound
    assert p2.inflation == 2.5
