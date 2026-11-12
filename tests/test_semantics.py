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
