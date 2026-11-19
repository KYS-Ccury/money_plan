"""계획 항목 가져오기: 엑셀·CSV·메모장에 적어 둔 항목을 제대로 읽는지.

가계부 가져오기와 달리 '분류' 를 알아보는 것이 일의 절반이다. 그래서 분류를
어떻게 적어도 알아보는지, 분류에 뜻이 없는 값은 털어 내는지를 집중해서 본다.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from capital_calc.import_plan import (match_category, parse_count,  # noqa: E402
                                      parse_file, parse_percent, parse_text)
from capital_calc.model import Category  # noqa: E402

SHEET = """이름,분류,금액,연이율(%),시작일,종료일,월세,연 상승률(%),월 지원금
현금,현금/자산,2000000,,,,,,
청약,적금/저축(월),200000,2.1,2026-12-01,2029-12-01,,,40000
전세금,주거 (전세),150000000,,2027-03-01,2029-03-01,,,
월급,월 수입,3200000,,,,,3.0,
전셋집 월세,월세,600000,,2027-03-01,,,2.0,
"""

MEMO = """월급 월 수입 3,200,000
청약 적금 200000 2.1%
전세 보증금 주거 150000000
뭔지 모를 줄 123
"""


def test_percent_and_count_are_read_loosely():
    assert parse_percent("3.5%") == 3.5
    assert parse_percent("연 3.5 %") == 3.5
    assert parse_percent("") == 0.0
    assert parse_count("3개월") == 3
    assert parse_count("분기") == 3
    assert parse_count("매년") == 12
    assert parse_count("") == 0


def test_category_names_are_recognised_in_several_shapes():
    assert match_category("현금/자산")[0] == Category.CASH
    assert match_category("월 수입")[0] == Category.INCOME
    assert match_category("보증금")[0] == Category.DEPOSIT      # 예전 이름
    assert match_category("급여")[0] == Category.INCOME         # 낱말로
    assert match_category("월세")[0] == Category.RENT
    assert match_category("알 수 없는 말")[0] is None
    assert match_category("")[0] is None


def test_housing_type_comes_along_in_brackets():
    cat, housing = match_category("주거 (전세)")
    assert cat == Category.DEPOSIT and housing == "jeonse"
    cat, housing = match_category("주거 (반전세)")
    assert cat == Category.DEPOSIT and housing == "banjeonse"
    assert match_category("전세")[1] == "jeonse"


def test_table_with_headers_reads_every_field():
    rows, problems, how = parse_text(SHEET)
    assert len(rows) == 5
    assert "머리글" in how
    assert not problems

    by = {r["name"]: r for r in rows}
    assert by["현금"]["category"] == Category.CASH.value
    assert by["현금"]["amount"] == 2_000_000

    chung = by["청약"]
    assert chung["category"] == Category.SAVING.value
    assert chung["rate"] == 2.1
    assert chung["start"] == "2026-12-01" and chung["end"] == "2029-12-01"
    assert chung["support"] == 40_000

    jeonse = by["전세금"]
    assert jeonse["category"] == Category.DEPOSIT.value
    assert jeonse["housing"] == "jeonse"

    assert by["월급"]["growth"] == 3.0


def test_values_that_make_no_sense_for_the_category_are_dropped():
    rows, _problems, _how = parse_text(
        "이름,분류,금액,연이율(%),월 지원금,연 상승률(%)\n"
        "현금,현금/자산,1000000,5.0,99999,7.0\n")
    r = rows[0]
    assert r["rate"] == 0.0        # 현금에는 이율이 없다
    assert r["support"] == 0.0     # 지원금은 적금에서만
    assert r["growth"] == 0.0      # 상승률은 월 수입·월세 같은 것에만


def test_memo_lines_are_read_and_bad_ones_are_reported():
    rows, problems, how = parse_text(MEMO)
    assert "줄마다" in how
    assert len(rows) == 3
    assert len(problems) == 1 and "분류" in problems[0]

    by = {r["category"]: r for r in rows}
    assert by[Category.INCOME.value]["amount"] == 3_200_000
    assert by[Category.SAVING.value]["rate"] == 2.1
    assert by[Category.DEPOSIT.value]["amount"] == 150_000_000


def test_name_falls_back_to_the_category_when_blank():
    rows, _p, _h = parse_text("이름,분류,금액\n,월 수입,100\n")
    assert rows[0]["name"] == Category.INCOME.value


def test_rows_without_a_category_are_skipped_with_a_reason():
    rows, problems, _how = parse_text("이름,분류,금액\n뭔가,아무말,1000\n월급,월 수입,200\n")
    assert len(rows) == 1
    assert len(problems) == 1 and "분류" in problems[0]


def test_amount_that_is_not_a_number_is_skipped():
    rows, problems, _how = parse_text("이름,분류,금액\n월급,월 수입,없음\n")
    assert rows == []
    assert problems and "금액" in problems[0]


def test_excel_round_trip(tmp_path):
    """내보낸 .xlsx 를 그대로 다시 읽을 수 있어야 한다 ('요약' 시트가 먼저 와도)."""
    from capital_calc.export_excel import export_plan
    from capital_calc.model import sample_plan

    plan = sample_plan()
    out = export_plan(plan, tmp_path / "plan.xlsx")
    rows, _problems, how = parse_file(out)

    assert "항목" in how
    assert len(rows) == len(plan.items)
    assert [r["name"] for r in rows] == [it.name for it in plan.items]
    assert [r["category"] for r in rows] == [it.category.value for it in plan.items]
    assert [round(r["amount"]) for r in rows] == [round(it.amount) for it in plan.items]


def test_csv_file_is_read_from_disk(tmp_path):
    p = tmp_path / "plan.csv"
    p.write_text(SHEET, encoding="utf-8")
    rows, problems, how = parse_file(p)
    assert len(rows) == 5 and not problems
    assert "머리글" in how


def test_housing_row_with_rent_becomes_two_rows():
    """'주거' 줄에 월세가 함께 적혀 있으면 보증금 줄 + 월세 줄로 갈라진다."""
    from capital_calc.import_plan import parse_text

    rows, problems, how = parse_text("\n".join([
        "이름,분류,금액,월세,시작일,종료일",
        "전셋집,주거 (반전세),100000000,600000,2026-04-01,2028-04-01",
        "내집,주거 (매매),300000000,0,2026-04-01,",
    ]))
    assert not problems
    assert [(r["name"], r["category"], r["amount"]) for r in rows] == [
        ("전셋집", Category.DEPOSIT.value, 100_000_000),
        ("전셋집 월세", Category.RENT.value, 600_000),
        ("내집", Category.DEPOSIT.value, 300_000_000),
    ]
    dep, rent = rows[0], rows[1]
    assert dep["monthly"] == 0 and dep["housing"] == "banjeonse"
    assert (rent["start"], rent["end"]) == ("2026-04-01", "2028-04-01")
    assert rent["housing"] == ""


def test_excel_round_trip_keeps_every_setting(tmp_path):
    """내보낸 뒤 그대로 가져오면 **설정이 하나도 안 날아가야** 한다.

    엑셀 시트는 보고서이기도 해서, 예전에는 받는 날·복리·세후·가계부 분류가
    아예 안 적혔고 원금 자본 포함·묶임·상환 방식·꺼짐은 적히기만 하고 되읽지
    못했다. 그래서 '모두 지우고 새로 채우기' 로 되돌리면 기본값으로 돌아갔다.
    """
    from capital_calc.backend import Backend
    from capital_calc.export_excel import export_plan
    from capital_calc.model import Item, Plan

    plan = Plan(months=36, start_date="2026-01-01")
    plan.add(Item("월급", Category.INCOME, 3_200_000, pay_day=25, growth=3.0))
    plan.add(Item("청년도약계좌", Category.SAVING, 200_000, rate=5.0, support=300_000,
                  locked=True, compound=True, after_tax=False,
                  start_date="2026-01-01", end_date="2029-01-01",
                  ledger_category="저축"))
    plan.add(Item("전세자금대출", Category.LOAN, 90_000_000, rate=2.5,
                  include_principal=False, repay_method="rate", monthly_repay_rate=1.5,
                  start_date="2026-02-01", end_date="2029-02-01",
                  repayments=[{"date": "2027-03-01", "amount": 5_000_000}]))
    plan.add(Item("안 쓰는 적금", Category.SAVING, 100_000, active=False))

    rows, problems, how = parse_file(export_plan(plan, tmp_path / "plan.xlsx"))
    assert not problems and "항목" in how
    got = {r["name"]: r for r in rows}

    assert got["월급"]["payDay"] == 25
    assert got["청년도약계좌"]["locked"] is True
    assert got["청년도약계좌"]["compound"] is True
    assert got["청년도약계좌"]["afterTax"] is False
    assert got["청년도약계좌"]["ledgerCategory"] == "저축"
    assert got["전세자금대출"]["includePrincipal"] is False
    assert got["전세자금대출"]["repayMethod"] == "rate"
    assert got["전세자금대출"]["repayRate"] == 1.5
    assert got["전세자금대출"]["repayments"] == [{"date": "2027-03-01", "amount": 5_000_000}]
    assert got["안 쓰는 적금"]["active"] is False
    assert got["월급"]["active"] is True

    # 계획에 넣었을 때도 그대로여야 한다 (미리보기까지만 맞아도 소용이 없다)
    b = Backend(Plan(months=36, start_date="2026-01-01"))
    b._plan_import = rows                            # 읽어 온 줄을 그대로 넣는다
    assert b.applyPlanImport(False) == len(rows)
    back = {it.name: it for it in b._plan.items}
    assert back["월급"].pay_day == 25
    assert back["청년도약계좌"].locked is True and back["청년도약계좌"].compound is True
    assert back["전세자금대출"].include_principal is False
    assert back["전세자금대출"].repay_method == "rate"
    assert back["전세자금대출"].monthly_repay_rate == 1.5
    assert back["안 쓰는 적금"].active is False


def test_a_hand_written_table_still_uses_the_defaults():
    """설정 칸이 없는 표(사람이 손으로 적은 것)는 예전처럼 기본값으로 들어온다."""
    rows, problems, _how = parse_text(SHEET)
    assert not problems
    got = {r["name"]: r for r in rows}
    assert got["청약"]["locked"] is False            # '묶임' 칸이 없으니 묶지 않는다
    assert got["현금"]["active"] is True
    assert got["월급"]["payDay"] == 0
    assert all(r["includePrincipal"] is True for r in rows)   # 대출이 없으면 기본값


def test_yesno_and_repay_method_are_read_loosely():
    from capital_calc.import_plan import parse_day, parse_repay_method, parse_yesno

    assert parse_yesno("예") is True and parse_yesno("Y") is True
    assert parse_yesno("아니오") is False and parse_yesno("x") is False
    assert parse_yesno("") is None and parse_yesno("글쎄") is None
    assert parse_day("매달 25일") == 25 and parse_day("32일") == 0 and parse_day("") == 0
    assert parse_repay_method("원리금 균등") == ("equal_payment", 0.0)
    assert parse_repay_method("매달 원금의 % (1.5%)") == ("rate", 1.5)
    assert parse_repay_method("") == ("", 0.0)
