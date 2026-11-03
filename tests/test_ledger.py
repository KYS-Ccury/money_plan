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
