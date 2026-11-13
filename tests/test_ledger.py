import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from capital_calc.ledger import (COST, INCOME, Entry, Ledger,  # noqa: E402
                                 kind_of, sample_ledger)
from capital_calc.model import Workspace  # noqa: E402


def test_entry_basics():
    e = Entry("2026-03-15", "식비", 12_000, "점심")
    assert e.ym == "2026-03" and e.year == "2026" and e.day == date(2026, 3, 15)
    assert e.kind == COST and not e.is_income and e.signed == -12_000

    inc = Entry("2026-03-25", "급여", 2_000_000)
    assert inc.kind == INCOME and inc.signed == 2_000_000

    # 분류로 수입/지출이 정해지고, 모르는 분류는 지출
    assert kind_of("상여금") == INCOME and kind_of("듣보 분류") == COST
    # 금액은 음수가 될 수 없고, 날짜가 이상하면 오늘로
    assert Entry("2026-03-01", "식비", -5).amount == 0
    assert Entry("아무거나", "식비", 100).date == date.today().isoformat()

    assert e.in_period("") and e.in_period("2026") and e.in_period("2026-03")
    assert not e.in_period("2026-04") and not e.in_period("2025")
    assert Entry.from_dict(e.to_dict()).to_dict() == e.to_dict()


def test_ledger_period_and_summary():
    lg = Ledger()
    lg.add(Entry("2026-01-10", "급여", 2_000_000))
    lg.add(Entry("2026-01-20", "식비", 300_000))
    lg.add(Entry("2026-02-05", "식비", 200_000))
    lg.add(Entry("2025-12-31", "급여", 1_000_000))

    assert lg.years() == ["2026", "2025"]                 # 최신순
    assert lg.months() == ["2026-02", "2026-01", "2025-12"]
    assert lg.months_of("2026") == ["2026-02", "2026-01"]

    jan = lg.summary("2026-01")
    assert jan == {"income": 2_000_000, "cost": 300_000, "net": 1_700_000, "count": 2}
    assert lg.summary("2026")["net"] == 1_500_000
    assert lg.summary()["count"] == 4                      # 기간을 비우면 전체

    # 최신 날짜가 위
    assert [e.date for e in lg.in_period("2026")] == ["2026-02-05", "2026-01-20", "2026-01-10"]

    assert lg.by_category("2026", COST) == [("식비", 500_000)]
    assert lg.by_category("2026", INCOME) == [("급여", 2_000_000)]

    months = lg.year_months("2026")
    assert len(months) == 12 and months[0]["ym"] == "2026-01"
    assert months[0]["net"] == 1_700_000 and months[1]["net"] == -200_000
    assert months[5]["count"] == 0 and months[5]["net"] == 0      # 기록 없는 달도 자리를 지킨다

    assert [r["year"] for r in lg.totals_by_year()] == ["2026", "2025"]


def test_ledger_edit():
    lg = Ledger()
    lg.add(Entry("2026-01-10", "식비", 10_000))
    lg.add(Entry("2026-01-11", "교통", 20_000))

    assert lg.update(1, Entry("2026-01-11", "교통", 25_000))
    assert lg.summary()["cost"] == 35_000
    assert not lg.update(9, Entry("2026-01-11", "교통", 1))

    removed = lg.remove(0)
    assert removed.category == "식비" and len(lg.entries) == 1
    assert lg.remove(9) is None

    lg.clear()
    assert lg.entries == [] and lg.years() == []


def test_ledger_saved_with_workspace(tmp_path):
    ws = Workspace()
    ws.ledger = sample_ledger(date(2026, 11, 3))
    before = ws.ledger.summary()
    path = tmp_path / "ws.json"
    ws.save(path)

    back = Workspace.load(path)
    assert back.ledger.summary() == before
    assert back.ledger.months() == ["2026-11", "2026-10"]

    # 가계부가 없는 예전 파일도 그대로 열린다
    import json
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d["version"] == 3
    del d["ledger"]
    path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert Workspace.load(path).ledger.entries == []


def test_ledger_search_and_filters():
    lg = Ledger()
    lg.add(Entry("2026-01-10", "급여", 2_000_000, "회사"))
    lg.add(Entry("2026-01-12", "식비", 30_000, "김밥천국", note="점심"))
    lg.add(Entry("2026-01-20", "교통", 50_000, "지하철"))
    lg.add(Entry("2026-02-01", "식비", 20_000, "회사 앞 식당"))

    assert [e.name for e in lg.search("2026-01")] == ["지하철", "김밥천국", "회사"]
    assert [e.name for e in lg.search("2026-01", query="회사")] == ["회사"]
    assert [e.name for e in lg.search("2026", query="회사")] == ["회사 앞 식당", "회사"]
    assert [e.name for e in lg.search("2026-01", query="점심")] == ["김밥천국"]      # 메모도 찾는다
    assert [e.name for e in lg.search("2026-01", query="식비")] == ["김밥천국"]      # 분류도 찾는다
    assert len(lg.search("2026", kind=INCOME)) == 1
    assert len(lg.search("2026", category="식비")) == 2
    assert lg.search("2026", query="없는말") == []

    assert lg.categories_used("2026-01") == ["교통", "급여", "식비"]
    assert lg.categories_used("2026-02") == ["식비"]
    assert lg.day_total("2026-01-12") == -30_000
    assert lg.day_total("2026-01-10") == 2_000_000
    assert lg.day_total("2026-01-11") == 0


def test_ledger_repeat_and_copy():
    from capital_calc.ledger import prev_period, same_day_in, shift_month
    assert prev_period("2026-03") == "2026-02" and prev_period("2026-01") == "2025-12"
    assert prev_period("2026") == "2025" and prev_period("") == ""
    assert shift_month("2026-11", 2) == "2027-01" and shift_month("2026-01", -1) == "2025-12"
    assert same_day_in("2026-02", 31) == "2026-02-28"      # 말일로 맞춘다

    lg = Ledger()
    e = lg.add(Entry("2026-01-31", "보험", 50_000, "실손"))
    made = lg.repeat(e, 3)
    assert [x.date for x in made] == ["2026-02-28", "2026-03-31"]
    assert len(lg.entries) == 3 and lg.summary("2026")["cost"] == 150_000

    # 한 달치 통째로 복사. 이미 같은 내역이 있으면 건너뛴다
    lg2 = Ledger()
    lg2.add(Entry("2026-01-05", "주거/관리비", 600_000, "월세"))
    lg2.add(Entry("2026-01-25", "급여", 2_000_000, "회사"))
    lg2.add(Entry("2026-02-05", "주거/관리비", 600_000, "월세"))     # 이미 있음

    made = lg2.copy_month("2026-01", "2026-02")
    assert [x.category for x in made] == ["급여"]
    assert lg2.summary("2026-02")["count"] == 2
    assert lg2.copy_month("2026-01", "2026-01") == []
    assert lg2.copy_month("2026-09", "2026-10") == []                 # 원본이 비었으면 아무것도 안 함


def test_budgets():
    lg = Ledger()
    lg.add(Entry("2026-01-05", "식비", 300_000))
    lg.add(Entry("2026-01-10", "교통", 120_000))
    lg.add(Entry("2026-01-25", "급여", 2_000_000))      # 수입은 예산과 무관
    lg.add(Entry("2026-02-05", "식비", 500_000))

    assert not lg.has_budgets()
    lg.set_budget("식비", 400_000)
    lg.set_budget("통신", 90_000)
    lg.set_budget("의료", 0)                              # 0 은 지우기
    assert lg.has_budgets() and lg.budget_of("식비") == 400_000 and lg.budget_of("의료") == 0

    rows = {r["category"]: r for r in lg.budget_rows("2026-01")}
    assert rows["식비"]["limit"] == 400_000 and rows["식비"]["spent"] == 300_000
    assert rows["식비"]["left"] == 100_000 and rows["식비"]["ratio"] == 0.75 and not rows["식비"]["over"]
    assert rows["교통"]["limit"] == 0 and rows["교통"]["spent"] == 120_000   # 예산 없이 쓴 것도 나온다
    assert rows["통신"]["spent"] == 0                                        # 예산만 있고 안 쓴 것도
    assert "급여" not in rows

    # 2월엔 예산을 넘는다
    feb = {r["category"]: r for r in lg.budget_rows("2026-02")}
    assert feb["식비"]["over"] and feb["식비"]["left"] == -100_000

    # 연 단위로 보면 12달치
    assert lg.period_months("2026") == 12 and lg.period_months("2026-01") == 1
    year = {r["category"]: r for r in lg.budget_rows("2026")}
    assert year["식비"]["limit"] == 400_000 * 12 and year["식비"]["spent"] == 800_000

    t = lg.budget_totals("2026-01")
    assert t["limit"] == 490_000 and t["spent"] == 300_000 and t["count"] == 2   # 교통은 예산이 없다
    assert not t["over"] and t["left"] == 190_000

    # 실적으로 채우기 (천원 단위)
    lg2 = Ledger()
    lg2.add(Entry("2026-01-05", "식비", 301_200))
    lg2.add(Entry("2026-01-06", "교통", 50_000))
    assert lg2.budget_from_period("2026-01") == 2
    assert lg2.budget_of("식비") == 301_000 and lg2.budget_of("교통") == 50_000

    # 저장 / 불러오기
    back = Ledger.from_dict(lg.to_dict())
    assert back.budgets == {"식비": 400_000, "통신": 90_000}
    assert Ledger.from_dict({"entries": [], "budgets": {"식비": "이상한값", "교통": -1}}).budgets == {}


def test_has_name():
    lg = Ledger()
    lg.add(Entry("2026-01-10", "주거/관리비", 500_000, "월세"))
    lg.add(Entry("2026-02-10", "식비", 10_000, ""))

    assert lg.has_name("2026-01", "월세")
    assert lg.has_name("2026-01", " 월세 ")          # 앞뒤 공백 무시
    assert lg.has_name("2026", "월세")
    assert not lg.has_name("2026-02", "월세")        # 다른 달이면 겹치는 게 아니다
    assert not lg.has_name("2026-01", "관리비")
    assert not lg.has_name("2026-02", "")            # 이름 없는 것끼리는 안 따진다


def test_aggregates_add_up_across_views():
    """같은 돈을 여러 화면에서 보여 주므로, 어느 쪽으로 더해도 같아야 한다."""
    from datetime import date
    from capital_calc.ledger import sample_ledger, INCOME, COST

    lg = sample_ledger(date(2026, 11, 11))
    for period in ("", "2026", "2026-11", "2026-10"):
        s = lg.summary(period)
        # 분류별 카드의 합 = 집계 카드의 합
        assert abs(sum(v for _, v in lg.by_category(period, COST)) - s["cost"]) < 0.5
        assert abs(sum(v for _, v in lg.by_category(period, INCOME)) - s["income"]) < 0.5
        assert abs(s["net"] - (s["income"] - s["cost"])) < 0.5

    # 월별 표 12줄의 합 = 그 해 집계
    ym = lg.year_months("2026")
    assert len(ym) == 12
    assert abs(sum(r["income"] for r in ym) - lg.summary("2026")["income"]) < 0.5
    assert abs(sum(r["cost"] for r in ym) - lg.summary("2026")["cost"]) < 0.5

    # 연도별 카드의 합 = 전체
    assert abs(sum(r["net"] for r in lg.totals_by_year()) - lg.summary("")["net"]) < 0.5

    # 예산: 합계 줄 = 한도를 정한 분류만 더한 값, 연 단위는 그 12배
    rows = lg.budget_rows("2026-11")
    tot = lg.budget_totals("2026-11")
    assert abs(tot["limit"] - sum(v for v in lg.budgets.values() if v > 0)) < 0.5
    assert abs(tot["spent"] - sum(r["spent"] for r in rows if r["limit"] > 0)) < 0.5
    for r in rows:
        assert abs(r["left"] - (r["limit"] - r["spent"])) < 0.5
        assert r["over"] == (r["limit"] > 0 and r["spent"] > r["limit"])
    assert abs(lg.budget_totals("2026")["limit"] - tot["limit"] * 12) < 0.5



def test_custom_categories():
    """분류를 직접 만들 수 있다. 수입으로 만든 분류는 수입으로 기록된다."""
    from capital_calc.ledger import Entry, Ledger, LEDGER_CATEGORIES

    lg = Ledger()
    assert lg.add_category("반려동물", "cost") == ""
    assert lg.add_category("부모님 용돈", "income") == ""
    assert "반려동물" in lg.cost_categories()
    assert "부모님 용돈" in lg.income_categories()
    assert lg.kind_of("반려동물") == "cost"
    assert lg.kind_of("부모님 용돈") == "income"
    assert lg.kind_of("식비") == "cost"            # 기본 분류는 그대로

    # 겹치는 이름·빈 이름·너무 긴 이름은 거절
    assert lg.add_category("식비", "cost") != ""
    assert lg.add_category("반려동물", "cost") != ""
    assert lg.add_category("   ", "cost") != ""
    assert lg.add_category("가" * 13, "cost") != ""

    # 기본 분류는 지울 수 없다
    assert lg.remove_category("식비") != ""
    assert set(LEDGER_CATEGORIES) <= set(lg.categories())

    # 쓰고 있으면 못 지운다
    lg.add(Entry("2026-11-11", "반려동물", 50_000, "사료", kind=lg.kind_of("반려동물")))
    assert lg.category_in_use("반려동물") == 1
    assert lg.remove_category("반려동물") != ""
    # 내역을 치우면 지울 수 있다
    lg.remove(0)
    assert lg.remove_category("반려동물") == ""
    assert "반려동물" not in lg.cost_categories()


def test_custom_categories_survive_save(tmp_path):
    from capital_calc.ledger import Entry, Ledger

    lg = Ledger()
    lg.add_category("반려동물", "cost")
    lg.add_category("부모님 용돈", "income")
    lg.add(Entry("2026-11-11", "부모님 용돈", 300_000, "엄마", kind="income"))
    lg.set_budget("반려동물", 80_000)

    lg2 = Ledger.from_dict(lg.to_dict())
    assert lg2.custom == {"반려동물": "cost", "부모님 용돈": "income"}
    assert lg2.kind_of("부모님 용돈") == "income"
    assert lg2.summary("")["income"] == 300_000      # 지출로 둔갑하지 않는다
    assert lg2.budget_of("반려동물") == 80_000


def test_repeat_and_copy_keep_custom_kind():
    """반복·복사로 만든 내역도 수입/지출을 그대로 물려받는다."""
    from capital_calc.ledger import Entry, Ledger

    lg = Ledger()
    lg.add_category("부모님 용돈", "income")
    e = lg.add(Entry("2026-01-10", "부모님 용돈", 200_000, "엄마", kind="income"))
    made = lg.repeat(e, 3)
    assert len(made) == 2 and all(m.is_income for m in made)
    copied = lg.copy_month("2026-01", "2026-06")
    assert copied and all(c.is_income for c in copied)
    assert lg.summary("2026")["cost"] == 0


# ───────────────────────── 고정 지출·수입

def test_fixed_fills_missed_months_once():
    """고정 항목은 밀린 달까지 한 번씩만 적는다."""
    from capital_calc.ledger import Fixed, Ledger

    lg = Ledger()
    lg.add_fixed(Fixed(name="월세", category="주거/관리비", amount=600_000, day=5,
                       start="2026-09"))
    made = lg.apply_fixed("2026-11")
    assert [e.date for e in made] == ["2026-09-05", "2026-10-05", "2026-11-05"]
    assert all(e.rule == "f1" and e.kind == "cost" for e in made)

    assert lg.apply_fixed("2026-11") == []          # 두 번 적지 않는다
    assert lg.apply_fixed("2026-12")[0].date == "2026-12-05"


def test_fixed_does_not_resurrect_deleted_entries():
    """적힌 줄을 지우는 건 '그 달은 아니다' 라는 뜻이므로 되살리지 않는다."""
    from capital_calc.ledger import Fixed, Ledger

    lg = Ledger()
    lg.add_fixed(Fixed(name="통신", category="통신", amount=88_000, day=12, start="2026-10"))
    lg.apply_fixed("2026-11")
    lg.remove(0)                                     # 10월치를 지운다
    assert lg.apply_fixed("2026-11") == []
    assert len(lg.entries) == 1


def test_fixed_respects_end_month_and_pause():
    from capital_calc.ledger import Fixed, Ledger

    lg = Ledger()
    f = lg.add_fixed(Fixed(name="적금", category="저축/투자", amount=300_000, day=25,
                           start="2026-01", end="2026-03"))
    assert [e.date for e in lg.apply_fixed("2026-12")] == [
        "2026-01-25", "2026-02-25", "2026-03-25"]

    g = lg.add_fixed(Fixed(name="급여", category="급여", amount=2_000_000, day=25,
                           start="2026-01"))
    assert g.is_income
    lg.set_fixed_active(g.rid, False)
    assert lg.apply_fixed("2026-03") == []           # 쉬는 중에는 적지 않는다
    lg.set_fixed_active(g.rid, True)
    assert len(lg.apply_fixed("2026-03")) == 3       # 다시 돌리면 밀린 달까지
    assert f.rid != g.rid


def test_fixed_end_of_month_is_clamped():
    from capital_calc.ledger import Fixed, Ledger

    lg = Ledger()
    lg.add_fixed(Fixed(name="카드", category="기타 지출", amount=100_000, day=31,
                       start="2026-01"))
    dates = [e.date for e in lg.apply_fixed("2026-03")]
    assert dates == ["2026-01-31", "2026-02-28", "2026-03-31"]


def test_fixed_remove_can_keep_or_purge_entries():
    from capital_calc.ledger import Fixed, Ledger

    lg = Ledger()
    lg.add_fixed(Fixed(name="월세", category="주거/관리비", amount=600_000, day=5,
                       start="2026-09"))
    lg.apply_fixed("2026-11")
    assert lg.remove_fixed("f1") == 0                # 규칙만 지운다
    assert len(lg.entries) == 3                      # 실제로 쓴 돈은 남는다

    lg.add_fixed(Fixed(name="월세", category="주거/관리비", amount=600_000,
                       day=5, start="2026-12"))
    lg.apply_fixed("2026-12")
    assert lg.fixed[0].rid != "f1"                   # 번호를 다시 쓰면 옛 내역이 딸려 간다
    assert lg.remove_fixed(lg.fixed[0].rid, purge=True) == 1
    assert len(lg.entries) == 3


def test_fixed_survives_save():
    from capital_calc.ledger import Fixed, Ledger

    lg = Ledger()
    lg.add_fixed(Fixed(name="월세", category="주거/관리비", amount=600_000, day=5,
                       start="2026-09", end="2027-08", note="집주인"))
    lg.apply_fixed("2026-10")
    lg2 = Ledger.from_dict(lg.to_dict())
    assert len(lg2.fixed) == 1
    f = lg2.fixed[0]
    assert (f.name, f.day, f.start, f.end, f.note) == ("월세", 5, "2026-09", "2027-08", "집주인")
    assert f.done == ["2026-09", "2026-10"]
    assert lg2.apply_fixed("2026-10") == []          # 저장 뒤에도 다시 적지 않는다
    assert lg2.entries[0].rule == "f1"
    assert lg2.fixed_totals()["cost"] == 600_000


def test_fixed_update_keeps_what_was_already_written():
    from capital_calc.ledger import Fixed, Ledger

    lg = Ledger()
    lg.add_fixed(Fixed(name="월세", category="주거/관리비", amount=600_000, day=5,
                       start="2026-09"))
    lg.apply_fixed("2026-10")
    lg.update_fixed("f1", Fixed(name="월세", category="주거/관리비", amount=650_000,
                                day=5, start="2026-09"))
    assert lg.fixed[0].amount == 650_000
    assert lg.apply_fixed("2026-10") == []           # 이미 적은 달은 그대로
    assert lg.entries[0].amount == 600_000           # 지난 내역을 고치지 않는다
    assert lg.apply_fixed("2026-11")[0].amount == 650_000


# ───────────────────────── 한눈에 보기 (집계)

def test_recent_months_counts_back_from_this_month():
    from capital_calc.ledger import Entry, Ledger

    lg = Ledger()
    lg.add(Entry("2026-11-05", "식비", 100_000))
    lg.add(Entry("2026-10-05", "급여", 2_000_000))
    lg.add(Entry("2025-11-05", "식비", 50_000))      # 12개월 창 밖 (2025-12 부터이므로)

    rows = lg.recent_months(12, upto="2026-11")
    assert len(rows) == 12
    assert rows[0]["ym"] == "2025-12" and rows[-1]["ym"] == "2026-11"
    assert rows[-1]["cost"] == 100_000 and rows[-2]["income"] == 2_000_000
    assert sum(r["count"] for r in rows) == 2       # 2025-11 은 빠진다
    assert rows[0]["label"] == "12월"


def test_range_aggregates_match_the_months_they_cover():
    from capital_calc.ledger import Entry, Ledger

    lg = Ledger()
    for ym in ("2026-09", "2026-10", "2026-11"):
        lg.add(Entry(f"{ym}-05", "식비", 300_000))
        lg.add(Entry(f"{ym}-25", "급여", 2_000_000))
    yms = ["2026-10", "2026-11"]

    s = lg.range_summary(yms)
    assert (s["income"], s["cost"], s["net"], s["count"]) == (4_000_000, 600_000, 3_400_000, 4)
    # 달별 합을 더한 것과 같아야 한다
    assert s["cost"] == sum(lg.summary(ym)["cost"] for ym in yms)
    assert lg.range_by_category(yms, "cost") == [("식비", 600_000)]
    assert lg.range_by_category(yms, "income") == [("급여", 4_000_000)]


# ───────────────────────── 결제수단

def test_pay_is_kept_and_listed():
    from capital_calc.ledger import LEDGER_PAYS, Entry, Ledger

    lg = Ledger()
    lg.add(Entry("2026-11-02", "식비", 12_000, "점심", pay="신한카드"))
    lg.add(Entry("2026-11-03", "식비", 9_000, "커피", pay="현금"))
    lg.add(Entry("2026-11-04", "교통", 1_500, "버스"))          # 지정 안 함

    assert lg.pays() == LEDGER_PAYS + ["신한카드"]              # 직접 적은 이름이 목록에 들어온다
    assert lg.pays_used("2026-11") == ["신한카드", "현금"]
    assert lg.by_pay("2026-11") == [("신한카드", 12_000), ("현금", 9_000), ("지정 안 함", 1_500)]

    lg2 = Ledger.from_dict(lg.to_dict())
    assert [e.pay for e in lg2.entries] == ["신한카드", "현금", ""]


def test_pay_filters_and_search():
    from capital_calc.ledger import Entry, Ledger

    lg = Ledger()
    lg.add(Entry("2026-11-02", "식비", 12_000, "점심", pay="카드"))
    lg.add(Entry("2026-11-03", "식비", 9_000, "커피", pay="현금"))

    assert [e.name for e in lg.search(pay="카드")] == ["점심"]
    assert [e.name for e in lg.search(pay="")] == ["커피", "점심"]      # 빈 조건은 통과
    assert [e.name for e in lg.search(query="현금")] == ["커피"]        # 검색어가 결제수단도 본다
    assert lg.search(pay="카드", kind="income") == []


def test_repeat_copy_and_fixed_carry_the_pay():
    from capital_calc.ledger import Entry, Fixed, Ledger

    lg = Ledger()
    e = lg.add(Entry("2026-01-10", "통신", 88_000, "휴대폰", pay="자동이체"))
    assert all(x.pay == "자동이체" for x in lg.repeat(e, 3))
    assert all(x.pay == "자동이체" for x in lg.copy_month("2026-01", "2026-06"))

    lg.add_fixed(Fixed(name="월세", category="주거/관리비", amount=600_000, day=5,
                       pay="계좌이체", start="2026-09"))
    made = lg.apply_fixed("2026-10")
    assert made and all(x.pay == "계좌이체" for x in made)


# ───────────────────────── 금액순 · 금액 범위

def test_amount_range_ignores_the_sign():
    from capital_calc.ledger import Entry, Ledger

    lg = Ledger()
    lg.add(Entry("2026-11-02", "식비", 12_000, "점심"))
    lg.add(Entry("2026-11-03", "급여", 2_000_000, "회사"))
    lg.add(Entry("2026-11-04", "교통", 1_500, "버스"))

    assert [e.name for e in lg.search(min_amount=10_000)] == ["회사", "점심"]
    assert [e.name for e in lg.search(max_amount=20_000)] == ["버스", "점심"]    # 최신 날짜부터
    assert [e.name for e in lg.search(min_amount=1_000, max_amount=20_000)] == ["버스", "점심"]
    assert lg.search(min_amount=3_000_000) == []
    assert len(lg.search()) == 3                      # 0 이면 제한 없음


def test_sorting_by_amount():
    from capital_calc.ledger import Entry, Ledger

    lg = Ledger()
    lg.add(Entry("2026-11-02", "식비", 12_000, "점심"))
    lg.add(Entry("2026-11-09", "식비", 12_000, "같은금액"))
    lg.add(Entry("2026-11-03", "급여", 2_000_000, "회사"))

    assert [e.name for e in lg.search(sort="amount")] == ["회사", "같은금액", "점심"]
    assert [e.name for e in lg.search(sort="amount", desc=False)] == ["점심", "같은금액", "회사"]
    # 같은 금액은 날짜로 한 번 더 정렬한다 (목록이 들썩이지 않게)
    assert [e.name for e in lg.search(sort="date")] == ["같은금액", "회사", "점심"]


# ───────────────────────── 달력

def test_month_days_fills_every_day_of_the_month():
    from capital_calc.ledger import Entry, Ledger

    lg = Ledger()
    lg.add(Entry("2026-11-05", "주거/관리비", 600_000))
    lg.add(Entry("2026-11-05", "식비", 12_000))
    lg.add(Entry("2026-11-25", "급여", 2_000_000))
    lg.add(Entry("2026-10-05", "식비", 9_000))          # 다른 달

    days = lg.month_days("2026-11")
    assert len(days) == 30 and days[0]["date"] == "2026-11-01"
    d5 = days[4]
    assert (d5["count"], d5["cost"], d5["net"]) == (2, 612_000, -612_000)
    assert days[24]["income"] == 2_000_000 and days[24]["net"] == 2_000_000
    assert sum(d["count"] for d in days) == 3

    assert lg.month_days("2026-02")[0]["date"] == "2026-02-01"
    assert len(lg.month_days("2026-02")) == 28
    assert lg.month_days("2026") == []                  # 달이 아니면 빈 목록
