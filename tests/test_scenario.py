"""종합 시나리오 — 전세에 들어가며 적금·대출·지출을 함께 굴린다.

낱개 기능은 `test_model.py` 가 본다. 여기서는 **기능들이 한 계획 안에서 서로를
망치지 않는지**를 본다 — 보증금을 자산으로 켜 둔 채 대출을 끼고, 적금 셋(만기
있는 것·묶어 둔 것·만기 없는 것)을 돌리고, 되풀이 지출과 꺼 둔 항목을 섞는다.
이 조합에서 한 번씩 틀렸던 것들이라 한 자리에 모아 둔다:

- 보증금을 치르는 달에 순 자본이 튀던 것 (일시 지출과 자산 편입이 안 맞았다)
- 보증금을 자산으로 켜면 돈이 없어도 부족 경고가 안 뜨던 것 (순 자본을 보았다)
- 만기 일시 상환이 월 지출 평균에 녹아 달마다 나가는 것처럼 읽히던 것
- 꺼 둔 항목이 어느 한 군데에만 남아 계산에 끼던 것

UI 와 Qt 를 쓰지 않는다 — `model.py` 만 올린다.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capital_calc.export_excel import composition  # noqa: E402
from capital_calc.model import Category, Item, Plan  # noqa: E402

BASIS = "2026-11-25"

# 기준일 2026-11-25 을 0개월로 본 눈금 (month_offset 은 '그 날이 지난 첫 눈금' 으로 올린다)
M_SALARY = 0        # 2026-11-01
M_SAVE = 1          # 2026-12-01  적금 시작, 자동차세 첫 해
M_MOVE = 2          # 2027-01-01  전세 입주 (보증금 지출 + 대출 시작)
M_MATURE = 25       # 2028-12-01  적금 만기
M_RETURN = 26       # 2029-01-01  보증금 반환 + 대출 만기 일시 상환

DEPOSIT = 120_000_000
LOAN = 80_000_000
CASH = 30_000_000


def build() -> Plan:
    """같은 계획을 여러 테스트가 쓴다 (서로 고치지 않도록 매번 새로 세운다)."""
    p = Plan(name="전세 들어가기", months=24, target=150_000_000, start_date=BASIS)
    p.add(Item("비상금", Category.CASH, CASH))
    p.add(Item("월급", Category.INCOME, 3_500_000, growth=3.0,
               start_date="2026-11-01", pay_day=25))
    p.add(Item("청약 적금", Category.SAVING, 500_000, rate=3.0,
               start_date="2026-12-01", end_date="2028-12-01"))
    p.add(Item("도약계좌", Category.SAVING, 700_000, support=300_000, locked=True,
               start_date="2026-12-01", end_date="2028-12-01"))
    p.add(Item("자유 적금", Category.SAVING, 200_000,
               start_date="2026-12-01"))                       # 만기 없음 → 경고 대상
    p.add(Item("전세 보증금", Category.DEPOSIT, DEPOSIT, housing_type="jeonse",
               as_asset=True, start_date="2027-01-01", end_date="2029-01-01"))
    p.add(Item("전세자금 대출", Category.LOAN, LOAN, rate=3.5, repay_method="bullet",
               start_date="2027-01-01", end_date="2029-01-01"))
    p.add(Item("생활비", Category.FIXED, 1_500_000, start_date="2026-11-01"))
    p.add(Item("자동차세", Category.EXPENSE, 300_000, every=12, start_date="2026-12-10"))
    p.add(Item("안 쓰는 계획", Category.FIXED, 9_999_999, active=False,
               start_date="2026-11-01"))
    return p


def item(p: Plan, name: str) -> Item:
    return next(i for i in p.items if i.name == name)


# ───────────────────────────── 눈금 ─────────────────────────────

def test_month_grid_is_where_we_think_it_is():
    """나머지 테스트가 전부 이 눈금 위에 서 있으므로 먼저 못을 박는다."""
    p = build()
    b = p.basis
    assert b == date(2026, 11, 25)
    assert item(p, "청약 적금").active_range(b) == (M_SAVE, M_MATURE)
    assert item(p, "자유 적금").active_range(b) == (M_SAVE, None)
    assert item(p, "전세 보증금").once_month(b) == M_MOVE
    assert item(p, "전세 보증금").return_month(b) == M_RETURN
    assert item(p, "전세자금 대출").active_range(b) == (M_MOVE, M_RETURN)


# ───────────────────────── 꺼 둔 항목 ──────────────────────────

def test_disabled_item_is_gone_from_every_number():
    """한 군데라도 남으면 거기만 900만원이 더 나간다 — 모든 입구를 본다."""
    p = build()
    off = item(p, "안 쓰는 계획")
    assert off not in p.live
    assert p.monthly_cost_at(0) == 1_500_000              # 생활비만
    assert off.amount not in [p.monthly_cost_at(m) for m in range(30)]
    s = p.summary()
    assert s.monthly_cost == 1_500_000
    off.active = True
    assert p.monthly_cost_at(0) == 1_500_000 + 9_999_999  # 켜면 바로 든다


# ───────────────────────────── 적금 ─────────────────────────────

def test_three_savings_behave_differently():
    p = build()
    b = p.basis
    chong, doyak, free = item(p, "청약 적금"), item(p, "도약계좌"), item(p, "자유 적금")

    # 시작 전에는 아무것도 안 나간다
    assert (chong.monthly_cost_at(0, b), doyak.monthly_cost_at(0, b)) == (0, 0)

    # 납입 중: 지원금은 내 돈이 아니라 잔액만 불린다
    assert doyak.monthly_cost_at(M_SAVE, b) == 700_000
    assert doyak.saving_deposit() == 1_000_000

    # 만기 달부터 납입이 멈추고 잔액은 그대로 남는다
    assert chong.monthly_cost_at(M_MATURE - 1, b) == 500_000
    assert chong.monthly_cost_at(M_MATURE, b) == 0
    assert chong.saving_balance_at(M_MATURE + 12, b) == chong.saving_balance_at(M_MATURE, b)

    # 만기가 없으면 멈추지 않는다 (그래서 경고한다)
    assert free.monthly_cost_at(M_MATURE + 12, b) == 200_000
    assert [i.name for i in p.items if i.open_ended_saving()] == ["자유 적금"]

    # 묶어 둔 적금은 보유 자금에 없고, 만기에 일시 수입으로 들어온다
    assert doyak.capital_at(M_SAVE + 6, b) == 0
    assert chong.capital_at(M_SAVE + 6, b) > 0
    received = doyak.once_income_at(M_MATURE, b)
    assert received == doyak.saving_balance_at(M_MATURE, b) > 0
    assert doyak.once_income_at(M_MATURE - 1, b) == 0


# ──────────────────── 보증금 · 대출 · 쓸 수 있는 돈 ────────────────────

def test_moving_in_does_not_jolt_net_capital():
    """현금이 보증금으로 모양만 바뀌는 달이다 — 순 자본은 월 수지만큼만 움직여야 한다."""
    p = build()
    assert p.tied_capital_at(M_MOVE - 1) == 0
    assert p.tied_capital_at(M_MOVE) == DEPOSIT
    # 계획 전체 보유 자금은 적금 잔액도 함께 늘므로, 두 항목만 떼어 본다
    b = p.basis
    dep, loan = item(p, "전세 보증금"), item(p, "전세자금 대출")
    assert dep.capital_at(M_MOVE, b) - dep.capital_at(M_MOVE - 1, b) == DEPOSIT
    assert loan.capital_at(M_MOVE, b) - loan.capital_at(M_MOVE - 1, b) == LOAN
    assert p.once_cost_at(M_MOVE) - p.once_cost_at(M_MOVE - 1) == DEPOSIT

    # 순 자본이 이 달에 움직인 몫은 **월 수지 + 받은 대출 + 적금으로 옮겨 둔 돈**
    # 뿐이어야 한다. 보증금은 한 푼도 끼지 않는다 (현금이 집으로 모양만 바뀌었다).
    flow = p.monthly_income_at(M_MOVE - 1) - p.monthly_cost_at(M_MOVE - 1)
    saved = sum(i.capital_at(M_MOVE, b) - i.capital_at(M_MOVE - 1, b)
                for i in p.live if i.category == Category.SAVING)
    jolt = p.net_at(M_MOVE) - p.net_at(M_MOVE - 1) - flow - LOAN - saved
    assert abs(jolt) < 1

    # 자산으로 보지 않으면 그 달에 순 자본이 보증금만큼 깎여야 한다 (대조군)
    q = build()
    item(q, "전세 보증금").as_asset = False
    drop = q.net_at(M_MOVE) - p.net_at(M_MOVE)
    assert abs(drop + DEPOSIT) < 1


def test_deposit_comes_back_without_a_jolt_either():
    p = build()
    assert p.tied_capital_at(M_RETURN - 1) == DEPOSIT
    assert p.tied_capital_at(M_RETURN) == 0
    assert p.once_income_at(M_RETURN) - p.once_income_at(M_RETURN - 1) >= DEPOSIT


def test_spendable_is_net_minus_what_is_tied_up():
    p = build()
    for m in (0, M_SAVE, M_MOVE, 12, M_MATURE, M_RETURN):
        assert abs(p.spendable_at(m) - (p.net_at(m) - p.tied_capital_at(m))) < 1
    series = p.spendable_series(24)
    assert len(series) == 25
    assert abs(series[M_MOVE] - p.spendable_at(M_MOVE)) < 1
    # 입주하는 달에는 순 자본이 멀쩡해도 손에 쥔 돈은 그만큼 줄어 있다
    assert p.spendable_at(M_MOVE) < p.net_at(M_MOVE) - DEPOSIT + 1


def test_shortfall_warns_even_though_net_capital_looks_fine():
    """보증금을 자산으로 켜면 순 자본은 안 깎인다 — 경고는 쓸 수 있는 돈을 봐야 한다."""
    p = build()
    sf = p.shortfall()
    assert p.net_at(M_MOVE) > 0            # 순 자본만 보면 멀쩡하다
    assert sf["month"] == M_MOVE           # 그런데 입주하는 달에 현금이 빈다
    assert sf["min_net"] < 0
    assert sf["months"] >= 1
    assert sf["horizon"] >= p.months

    # 보증금을 자산으로 보지 않으면 순 자본 자체가 깎이므로 경고도 그대로 선다
    item(p, "전세 보증금").as_asset = False
    assert p.tied_capital_at(M_MOVE) == 0
    assert p.shortfall()["month"] == M_MOVE
    assert abs(p.spendable_at(M_MOVE) - p.net_at(M_MOVE)) < 1


# ───────────────────────────── 요약 ─────────────────────────────

def test_summary_keeps_the_bullet_repayment_out_of_the_monthly_average():
    """만기에 한 번 갚는 8천만원이 월 평균에 녹으면 달마다 나가는 것처럼 읽힌다."""
    p = build()
    p.months = 30                       # 대출 만기(26개월)를 기간 안에 넣는다
    s = p.summary()
    assert s.months == 30
    assert s.avg_cost < 10_000_000      # 8천만원이 녹아들었다면 수백만원대가 아니다
    assert p.once_repay_at(M_RETURN) == 0        # 원금을 자본에 넣은 대출이므로 0
    # 요약의 합은 흩어진 숫자와 같아야 한다
    assert abs(s.net - p.net_at(30)) < 1
    assert abs(s.gap - (s.net - s.target)) < 1


def test_summary_matches_the_month_by_month_numbers():
    p = build()
    s = p.summary()
    assert s.monthly_cost == p.monthly_cost_at(0)
    assert s.monthly_income == p.monthly_income_at(0)
    assert s.last_cost == p.monthly_cost_at(p.months - 1) - p.once_repay_at(p.months - 1)
    assert s.monthly_varies                      # 중간에 대출 이자가 끼어든다
    assert abs(s.net_at(12) - p.net_at(12)) < 1


def test_salary_rises_once_a_year():
    p = build()
    b = p.basis
    pay = item(p, "월급")
    assert pay.monthly_income_at(0, b) == 3_500_000
    assert pay.monthly_income_at(11, b) == 3_500_000
    assert pay.monthly_income_at(12, b) == 3_500_000 * 1.03
    assert pay.monthly_income_at(24, b) == 3_500_000 * 1.03 ** 2


def test_recurring_expense_lands_once_a_year():
    p = build()
    b = p.basis
    tax = item(p, "자동차세")
    assert tax.count_upto(M_SAVE, b) == 1
    assert tax.count_upto(M_SAVE + 11, b) == 1
    assert tax.count_upto(M_SAVE + 12, b) == 2
    assert tax.once_cost_at(M_SAVE + 12, b) == 600_000


# ─────────────────────── 저장하고 다시 열기 ───────────────────────

def test_the_whole_scenario_survives_a_save_and_load():
    """새로 더한 칸(자산으로 포함·장·만기 묶임·지원금·받는 날)이 왕복에서 빠지면
    불러오기만 해도 숫자가 달라진다 — 그래서 숫자로 견준다."""
    p = build()
    item(p, "전세 보증금").page = "집"
    item(p, "청약 적금").page = "저축"
    p.pages = ["집", "저축"]
    p.page_title = "한눈에"

    back = Plan.from_dict(p.to_dict())

    assert back.page_list() == ["한눈에", "집", "저축"]
    assert [i.name for i in back.items] == [i.name for i in p.items]
    assert item(back, "전세 보증금").as_asset is True
    assert item(back, "도약계좌").locked is True
    assert item(back, "도약계좌").support == 300_000
    assert item(back, "월급").pay_day == 25
    assert item(back, "안 쓰는 계획").active is False
    assert item(back, "자동차세").every == 12

    for m in (0, M_SAVE, M_MOVE, 12, M_MATURE, M_RETURN):
        assert abs(back.net_at(m) - p.net_at(m)) < 1
        assert abs(back.spendable_at(m) - p.spendable_at(m)) < 1
        assert back.tied_capital_at(m) == p.tied_capital_at(m)
    assert back.shortfall() == p.shortfall()


def test_the_whole_scenario_survives_an_excel_round_trip(tmp_path):
    """엑셀로 내보내 다시 읽었을 때 설정 칸이 하나라도 빠지면 숫자가 달라진다.

    여기서는 **읽어 들인 줄**까지 본다 (줄을 항목으로 바꾸는 일은 백엔드가 하고
    `test_backend.py` 가 본다). 내보내기와 읽기 중 한쪽만 고쳐도 여기서 걸린다.
    """
    from capital_calc.export_excel import export_plan
    from capital_calc.import_plan import parse_file

    p = build()
    item(p, "전세 보증금").page = "집"
    item(p, "청약 적금").page = "저축"
    path = export_plan(p, tmp_path / "종합.xlsx")
    rows, problems, _note = parse_file(path)
    assert problems == []

    got = {r["name"]: r for r in rows}
    assert set(got) == {i.name for i in p.items}

    assert got["전세 보증금"]["asAsset"] is True
    assert got["전세 보증금"]["amount"] == DEPOSIT
    assert got["전세 보증금"]["end"][:7] == "2029-01"        # 반환일
    assert got["도약계좌"]["locked"] is True
    assert got["도약계좌"]["support"] == 300_000
    assert got["자유 적금"]["end"] == ""                      # 만기 없음이 그대로 돌아온다
    assert got["청약 적금"]["end"][:7] == "2028-12"
    assert got["월급"]["payDay"] == 25
    assert got["월급"]["growth"] == 3.0
    assert got["자동차세"]["every"] == 12               # 되풀이 주기
    assert got["전세 보증금"]["page"] == "집"           # 장(페이지)
    assert got["청약 적금"]["page"] == "저축"
    assert got["월급"]["page"] == ""                    # 첫 장은 빈 값이다
    assert got["안 쓰는 계획"]["active"] is False
    assert got["전세자금 대출"]["repayMethod"] == "bullet"
    assert got["전세자금 대출"]["includePrincipal"] is True


# ───────────────────────── 비중 (화면의 도넛) ─────────────────────────

def test_composition_follows_the_month():
    """`composition(plan, m)` 이 그 시점을 그려야 한다 (화면의 '비중' 카드가 쓴다).

    예전에는 0개월만 세어서, 미래 보기로 2년 뒤를 골라도 도넛은 오늘 모습
    그대로였다 — 끝난 적금이 여전히 월 지출의 한 조각으로 남아 있었다.
    """
    p = build()

    today = composition(p)                       # m 을 안 주면 오늘 (엑셀 시트가 그렇게 쓴다)
    assert today == composition(p, 0)

    def names(c, group):
        return {n for n, _ in c[group]}

    # 입주 전에는 대출 이자가 없고, 입주한 뒤에는 있다
    assert "전세자금 대출" not in names(composition(p, M_MOVE - 1), "월 지출")
    assert "전세자금 대출" in names(composition(p, M_MOVE), "월 지출")

    # 적금 만기가 지나면 납입이 월 지출에서 빠진다 (끝은 열려 있다 — 만기 달부터 0)
    before = dict(composition(p, M_MATURE - 1)["월 지출"])
    after = dict(composition(p, M_MATURE)["월 지출"])
    assert before["청약 적금"] == 500_000
    assert "청약 적금" not in after
    assert "자유 적금" in after                   # 만기를 안 넣은 적금은 계속 남는다

    # 그래도 모아 둔 돈은 보유 자금 조각으로 남는다 (사라지지 않는다)
    assert dict(composition(p, M_MATURE)["보유 자금"])["청약 적금"] > 0

    # 꺼 둔 항목은 어느 시점에서도 끼지 않는다
    for m in (0, M_MOVE, M_MATURE, M_RETURN):
        assert "안 쓰는 계획" not in names(composition(p, m), "월 지출")

    # 조각의 합은 그 시점의 plan 숫자와 같아야 한다 (도넛의 가운데 숫자)
    for m in (0, M_MOVE, M_MATURE):
        assert abs(sum(v for _, v in composition(p, m)["월 지출"])
                   - p.monthly_cost_at(m)) < 1
        assert abs(sum(v for _, v in composition(p, m)["월 수입"])
                   - p.monthly_income_at(m)) < 1

    # 음수 m 은 오늘로 본다 (화면이 0 보다 작은 시점을 넘기지 않지만, 막아 둔다)
    assert composition(p, -5) == today


if __name__ == "__main__":        # pytest 없이도 돌려 볼 수 있게 (Qt 를 올리지 않는다)
    import inspect
    import tempfile
    import traceback

    fails = 0
    tmp = Path(tempfile.mkdtemp(prefix="scenario_"))
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(tmp) if inspect.signature(fn).parameters else fn()
                print(f"  ok   {name}")
            except Exception:
                fails += 1
                print(f"  FAIL {name}")
                traceback.print_exc()
    print("모두 통과" if not fails else f"{fails}개 실패")
    sys.exit(1 if fails else 0)
