"""엑셀 내보내기 · 비중 계산 검증."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openpyxl import load_workbook  # noqa: E402

from capital_calc.export_excel import composition, export_plan  # noqa: E402
from capital_calc.model import Category, Item, Plan, sample_plan  # noqa: E402


def test_composition():
    p = Plan(start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 60))
    p.add(Item("예금", Category.BANK, 30, rate=12))     # 월 이자 0.3
    p.add(Item("대출", Category.LOAN, 10, rate=12))     # 월 이자 0.1
    p.add(Item("월세", Category.RENT, 5))
    c = composition(p)
    assert c["보유 자금"] == [("현금", 60), ("예금", 30), ("대출", 10)]
    assert [n for n, _ in c["월 지출"]] == ["대출", "월세"]
    assert c["월 수입"] == [("예금", 0.3)]


def test_export_creates_sheets(tmp_path):
    out = export_plan(sample_plan(), tmp_path / "plan")      # 확장자 자동 보정
    assert out.suffix == ".xlsx" and out.exists()
    wb = load_workbook(out)
    assert wb.sheetnames == ["요약", "항목", "월별 추이", "비중"]
    ws = wb["항목"]
    assert ws.cell(row=1, column=1).value == "이름"
    assert ws.cell(row=1, column=8).value == "상환 방식"
    loan_row = 1 + [i.name for i in sample_plan().items].index("신용대출 (5%)") + 1
    assert ws.cell(row=loan_row, column=8).value == "만기 일시 상환"
    assert ws.max_row == 1 + len(sample_plan().items)
    ws = wb["월별 추이"]
    assert ws.cell(row=2, column=1).value == 0 and ws.cell(row=38, column=1).value == 36
    assert ws.cell(row=2, column=6).value == sample_plan().net_at(0)
    assert len(ws._charts) == 1
    assert len(wb["비중"]._charts) == 3


def test_export_scenario_sheet(tmp_path):
    a = sample_plan(); a.name = "A"
    b = sample_plan(); b.name = "B"; b.months = 48
    out = export_plan(a, tmp_path / "cmp.xlsx", scenarios=[a, b])
    wb = load_workbook(out)
    assert wb.sheetnames[-1] == "시나리오 비교"
    ws = wb["시나리오 비교"]
    assert [ws.cell(row=1, column=c).value for c in (1, 2, 3)] == ["개월", "A", "B"]
    assert ws.cell(row=50, column=1).value == 48 and ws.max_row == 50
    assert ws.cell(row=2, column=3).value == b.net_at(0)
    assert len(ws._charts) == 1
    # 하나뿐이면 시트가 생기지 않는다
    out2 = export_plan(a, tmp_path / "one.xlsx", scenarios=[a])
    assert "시나리오 비교" not in load_workbook(out2).sheetnames


def test_export_shortfall_rows(tmp_path):
    p = Plan(months=12, start_date="2026-01-01")
    p.add(Item("현금", Category.CASH, 3_000_000))
    p.add(Item("월세", Category.RENT, 500_000))
    wb = load_workbook(export_plan(p, tmp_path / "sf.xlsx"))
    labels = [wb["요약"].cell(row=r, column=1).value for r in range(1, 20)]
    i = labels.index("현금 부족 시작")
    assert "2026년 08월" in wb["요약"].cell(row=i + 1, column=2).value
    assert wb["요약"].cell(row=i + 2, column=2).value == 3_000_000 - 500_000 * 36
    assert "2029년 01월" in wb["요약"].cell(row=i + 3, column=2).value
