"""가져오기: 은행·카드사 파일과 메모장 글을 제대로 읽는지.

파일 모양은 제각각이라 '이런 모양도 들어온다' 를 여기에 모아 둔다.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from capital_calc.import_ledger import (parse_amount, parse_date_text,  # noqa: E402
                                        parse_file, parse_text)

BANK = """거래내역조회
계좌번호,123-456-789
조회기간,2026-11-01 ~ 2026-11-30

거래일시,적요,출금액,입금액,거래후잔액,메모
2026-11-02 12:30:00,스타벅스,"5,600",,"1,234,000",
2026-11-05,월세이체,"600,000",,"634,000",11월분
2026-11-25,급여,,"2,000,000","2,634,000",
"""

CARD = """이용일,가맹점명,이용금액,분류,결제수단
2026.11.03,GS25,3200,식비,신한카드
2026.11.04,지하철,1450,교통,신한카드
"""

MEMO = """11/13 점심 12,000 카드
11/14 커피 4500
2026-11-15 월급 +2000000
망가진 줄
"""


def test_parse_amount_handles_the_usual_decorations():
    assert parse_amount("1,234") == 1234
    assert parse_amount("₩1,234원") == 1234
    assert parse_amount("-1,234") == -1234
    assert parse_amount("(1,234)") == -1234          # 괄호는 음수 (은행 양식)
    assert parse_amount("1 234") == 1234
    assert parse_amount("") is None
    assert parse_amount("스타벅스") is None
    assert parse_amount("2026-11-02") is None        # 날짜를 금액으로 읽지 않는다


def test_parse_date_handles_the_usual_shapes():
    assert parse_date_text("2026-11-02") == "2026-11-02"
    assert parse_date_text("2026.11.02") == "2026-11-02"
    assert parse_date_text("2026/11/02") == "2026-11-02"
    assert parse_date_text("20261102") == "2026-11-02"
    assert parse_date_text("2026-11-02 12:30:00") == "2026-11-02"
    assert parse_date_text("2026년 11월 2일") == "2026-11-02"
    assert parse_date_text("11/02", default_year=2026) == "2026-11-02"
    assert parse_date_text("스타벅스") == ""


def test_bank_csv_with_title_rows_and_two_money_columns(tmp_path):
    p = tmp_path / "bank.csv"
    p.write_bytes(BANK.encode("cp949"))              # 은행 파일은 cp949 가 많다
    rows, problems, how = parse_file(p)

    assert problems == []
    assert "cp949" in how
    assert [(r["date"], r["amount"], r["kind"], r["name"]) for r in rows] == [
        ("2026-11-02", 5600, "cost", "스타벅스"),
        ("2026-11-05", 600000, "cost", "월세이체"),
        ("2026-11-25", 2000000, "income", "급여"),   # 입금 칸에 있으면 수입
    ]
    assert rows[1]["note"] == "11월분"


def test_card_csv_keeps_category_and_pay(tmp_path):
    p = tmp_path / "card.csv"
    p.write_text(CARD, encoding="utf-8")
    rows, problems, _how = parse_file(p)

    assert problems == []
    assert [(r["date"], r["category"], r["pay"], r["name"]) for r in rows] == [
        ("2026-11-03", "식비", "신한카드", "GS25"),
        ("2026-11-04", "교통", "신한카드", "지하철"),
    ]
    assert all(r["kind"] == "cost" for r in rows)


def test_memo_lines_without_any_header(tmp_path):
    p = tmp_path / "memo.txt"
    p.write_text(MEMO, encoding="utf-8")
    rows, problems, how = parse_file(p, default_year=2026)

    assert "줄마다" in how
    assert [(r["date"], r["amount"], r["kind"], r["name"], r["pay"]) for r in rows] == [
        ("2026-11-13", 12000, "cost", "점심", "카드"),   # 12,000 의 쉼표를 자르지 않는다
        ("2026-11-14", 4500, "cost", "커피", ""),
        ("2026-11-15", 2000000, "income", "월급", ""),   # + 가 붙으면 수입
    ]
    assert len(problems) == 1 and "4번째 줄" in problems[0]


def test_excel_is_read_the_same_way(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["날짜", "내용", "금액", "분류"])
    ws.append(["2026-11-03", "점심", 12000, "식비"])
    ws.append(["2026-11-04", "버스", 1450, "교통"])
    p = tmp_path / "a.xlsx"
    wb.save(p)

    rows, problems, how = parse_file(p)
    assert problems == [] and "엑셀" in how
    assert [(r["date"], r["amount"], r["category"]) for r in rows] == [
        ("2026-11-03", 12000, "식비"), ("2026-11-04", 1450, "교통")]


def test_excel_dates_come_as_real_dates(tmp_path):
    from datetime import datetime

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["거래일", "적요", "금액"])
    ws.append([datetime(2026, 11, 3, 9, 30), "점심", 12000])
    p = tmp_path / "b.xlsx"
    wb.save(p)

    rows, _p, _h = parse_file(p)
    assert rows[0]["date"] == "2026-11-03"           # 엑셀 날짜 칸도 읽는다


def test_pasted_text_takes_either_shape():
    rows, problems, how = parse_text("날짜,내용,금액\n2026-11-03,점심,12000")
    assert "머리글" in how and rows[0]["amount"] == 12000 and problems == []

    rows, _p, how = parse_text("11/13 점심 12000", default_year=2026)
    assert "줄마다" in how and rows[0]["date"] == "2026-11-13"


def test_nothing_readable_is_not_a_crash(tmp_path):
    p = tmp_path / "junk.txt"
    p.write_text("이건 그냥 글입니다\n아무 숫자도 없어요\n", encoding="utf-8")
    rows, problems, _how = parse_file(p)
    assert rows == []
    assert len(problems) == 2                        # 왜 못 읽었는지는 줄마다 알려 준다
