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
