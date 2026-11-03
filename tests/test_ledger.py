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
