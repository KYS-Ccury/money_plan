"""계획(Plan)을 엑셀(.xlsx)로 내보내기.

시트 구성
- 요약     : 기준일·기간·목표·보유 자금·필요 자금·순 자본·달성 예측
- 항목     : 입력한 항목 전체 (분류, 금액, 이율, 적용 기간, 중도 상환)
- 월별 추이: 0 ~ max(기간, 36) 개월의 보유 자금 / 월 지출 / 월 수입 / 순 자본 / 목표 대비
- 비중     : 보유 자금 · 월 지출 · 월 수입 구성 비율
- 시나리오 비교: 시나리오가 2개 이상일 때, 시나리오별 월별 순 자본 (선 그래프 포함)
- 가계부     : 기록이 있을 때 내역 / 월별(막대 그래프) / 연도별
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import LineChart, PieChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from datetime import date

from .model import CATEGORY_INFO, REPAY_METHODS, Category, Plan, add_months, month_offset

WON = '#,##0"원"'
PCT = "0.0%"
HEAD_FILL = PatternFill("solid", fgColor="2B3B62")
HEAD_FONT = Font(bold=True, color="FFFFFF")


def _header(ws, row: int, labels: list[str]) -> None:
    for c, label in enumerate(labels, start=1):
        cell = ws.cell(row=row, column=c, value=label)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center")


def _autowidth(ws, min_width: int = 10, max_width: int = 48) -> None:
    widths: dict[int, int] = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            n = len(str(cell.value))
            widths[cell.column] = max(widths.get(cell.column, 0), n)
    for col, n in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = max(min_width, min(max_width, int(n * 1.4) + 2))


def composition(plan: Plan) -> dict[str, list[tuple[str, float]]]:
    """비중 계산 (항목 이름 기준). 0 이하 값은 제외."""
    basis = plan.basis
    out: dict[str, list[tuple[str, float]]] = {"보유 자금": [], "월 지출": [], "월 수입": []}
    for it in plan.items:
        c = it.capital_at(0, basis)
        if c > 0:
            out["보유 자금"].append((it.name, c))
        cost = it.monthly_cost_at(0, basis)
        if cost > 0:
            out["월 지출"].append((it.name, cost))
        inc = it.monthly_income_at(0, basis)
        if inc > 0:
            out["월 수입"].append((it.name, inc))
    return out


def _shortfall_text(plan: Plan) -> str:
    sf = plan.shortfall()
    if sf["month"] is None:
        return f"없음 ({sf['horizon']}개월 내 순 자본이 마이너스가 되지 않음)"
    d = add_months(plan.basis, sf["month"])
    return f"{d.strftime('%Y년 %m월')} ({sf['month']}개월 뒤) · {sf['horizon']}개월 중 {sf['months']}개월 부족"




def _ledger_sheets(wb, ledger, plan=None) -> None:
    """가계부 시트 3장: 내역 / 월별(계획 대비 포함) / 연도별 (+ 막대 그래프)."""
    from openpyxl.chart import BarChart

    ws = wb.create_sheet("가계부 내역")
    _header(ws, 1, ["날짜", "수입/지출", "분류", "내용", "금액", "메모"])
    rows = sorted(ledger.entries, key=lambda e: e.date)
    for r, e in enumerate(rows, start=2):
        ws.cell(row=r, column=1, value=e.date)
        ws.cell(row=r, column=2, value="수입" if e.is_income else "지출")
        ws.cell(row=r, column=3, value=e.category)
        ws.cell(row=r, column=4, value=e.name)
        ws.cell(row=r, column=5, value=e.signed).number_format = WON
        ws.cell(row=r, column=6, value=e.note or None)
    _autowidth(ws)

    ws = wb.create_sheet("가계부 월별")
    _header(ws, 1, ["연월", "수입", "지출", "남은 돈", "건수",
                    "계획 수입", "계획 지출", "지출 차이"])
    months = sorted({e.ym for e in ledger.entries})
    basis = plan.basis if plan is not None else None
    for r, ym in enumerate(months, start=2):
        s = ledger.summary(ym)
        ws.cell(row=r, column=1, value=ym)
        ws.cell(row=r, column=2, value=s["income"]).number_format = WON
        ws.cell(row=r, column=3, value=s["cost"]).number_format = WON
        ws.cell(row=r, column=4, value=s["net"]).number_format = WON
        ws.cell(row=r, column=5, value=s["count"])
        if basis is None:
            continue
        m = month_offset(basis, date(int(ym[:4]), int(ym[5:7]), 1))
        if m < 0:
            continue
        p_in, p_out = plan.planned_in_at(m), plan.planned_out_at(m)
        ws.cell(row=r, column=6, value=p_in).number_format = WON
        ws.cell(row=r, column=7, value=p_out).number_format = WON
        ws.cell(row=r, column=8, value=s["cost"] - p_out).number_format = WON
    _autowidth(ws)
    if months:
        bar = BarChart()
        bar.title = "월별 수입 · 지출"
        bar.y_axis.title = "원"
        bar.height, bar.width = 9, 22
        bar.add_data(Reference(ws, min_col=2, max_col=3, min_row=1, max_row=len(months) + 1), titles_from_data=True)
        bar.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(months) + 1))
        ws.add_chart(bar, "G2")

    ws = wb.create_sheet("가계부 연도별")
    _header(ws, 1, ["연도", "수입", "지출", "남은 돈", "건수"])
    for r, row in enumerate(ledger.totals_by_year(), start=2):
        ws.cell(row=r, column=1, value=row["year"])
        ws.cell(row=r, column=2, value=row["income"]).number_format = WON
        ws.cell(row=r, column=3, value=row["cost"]).number_format = WON
        ws.cell(row=r, column=4, value=row["net"]).number_format = WON
        ws.cell(row=r, column=5, value=row["count"])
    _autowidth(ws)


def export_plan(plan: Plan, path: str | Path, scenarios: list[Plan] | None = None, ledger=None) -> Path:
    """plan 을 내보낸다. scenarios 에 2개 이상을 주면 '시나리오 비교', ledger 에 기록이 있으면 가계부 시트가 붙는다."""
    path = Path(path)
    if path.suffix.lower() != ".xlsx":
        path = path.with_suffix(".xlsx")
    s = plan.summary()
    sf = plan.shortfall()
    wb = Workbook()

    # ---------------------------------------------------------- 요약
    ws = wb.active
    ws.title = "요약"
    goal = s.goal_month()
    goal_text = (
        "이미 달성" if goal == 0
        else f"{add_months(plan.basis, goal).strftime('%Y년 %m월')} ({goal}개월 뒤)" if goal is not None
        else "50년 내 도달 불가"
    )
    rows = [
        ("기준일", plan.start_date, None),
        ("기간(개월)", plan.months, None),
        ("목표 자본금", plan.target, WON),
        ("보유 자금 (0개월)", s.capital, WON),
        (f"일시 지출 ({plan.months}개월 내)", s.once_cost, WON),
        (f"일시 수입 ({plan.months}개월 내)", s.once_income, WON),
        ("월 지출 (0개월)", s.monthly_cost, WON),
        ("월 수입 (0개월)", s.monthly_income, WON),
        (f"{s.months}개월 필요 자금", s.required, WON),
        (f"{s.months}개월 수입", s.period_income, WON),
        (f"{s.months}개월 후 순 자본", s.net, WON),
        ("목표 대비", s.gap, WON),
        ("달성률", s.progress if plan.target > 0 else None, PCT),
        ("달성 예측", goal_text, None),
        ("현금 부족 시작", _shortfall_text(plan), None),
        (f"최저 순 자본 ({sf['horizon']}개월 내)", sf["min_net"], WON),
        ("최저 시점", f"{add_months(plan.basis, sf['min_month']).strftime('%Y년 %m월')} ({sf['min_month']}개월 뒤)", None),
    ]
    _header(ws, 1, ["항목", "값"])
    for i, (label, value, fmt) in enumerate(rows, start=2):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True)
        cell = ws.cell(row=i, column=2, value=value)
        if fmt:
            cell.number_format = fmt
    _autowidth(ws)

    # ---------------------------------------------------------- 항목
    ws = wb.create_sheet("항목")
    _header(ws, 1, ["이름", "분류", "금액", "연이율(%)", "원금 자본 포함", "시작일", "종료일",
                    "상환 방식", "첫 달 상환액", "총 이자", "중도 상환", "월 환산(0개월)"])
    basis = plan.basis
    for r, it in enumerate(plan.items, start=2):
        info = CATEGORY_INFO[it.category]
        reps = ", ".join(f"{x['date']} {x['amount']:,.0f}원" for x in it.repayments)
        ws.cell(row=r, column=1, value=it.name)
        ws.cell(row=r, column=2, value=f"{it.category.value} ({it.housing_label})" if it.is_housing else it.category.value)
        ws.cell(row=r, column=3, value=it.amount).number_format = WON
        ws.cell(row=r, column=4, value=it.rate if info["uses_rate"] else None)
        is_loan = it.category == Category.LOAN
        ws.cell(row=r, column=5, value=("예" if it.include_principal else "아니오") if is_loan else None)
        if it.uses_dates:
            ws.cell(row=r, column=6, value=it.start_date or plan.start_date)
            ws.cell(row=r, column=7, value=it.end_date or "계속")
        elif it.date_mode == "once":
            ws.cell(row=r, column=6, value=it.start_date or plan.start_date)
            ws.cell(row=r, column=7, value=(it.end_date + " 반환") if it.return_month(basis) is not None else "일시")
        if is_loan:
            label = REPAY_METHODS.get(it.repay_method, "")
            if it.repay_method == "rate":
                label += f" ({it.monthly_repay_rate:g}%)"
            start_m, _ = it.active_range(basis)
            ws.cell(row=r, column=8, value=label)
            ws.cell(row=r, column=9, value=it.payment_at(start_m, basis)).number_format = WON
            ws.cell(row=r, column=10, value=it.total_interest(basis) or None).number_format = WON
        ws.cell(row=r, column=11, value=reps or None)
        ws.cell(row=r, column=12, value=it.monthly_net_at(0, basis)).number_format = WON
    _autowidth(ws)

    # ---------------------------------------------------------- 월별 추이 (+ 선 그래프)
    ws = wb.create_sheet("월별 추이")
    _header(ws, 1, ["개월", "날짜", "보유 자금", "월 지출", "월 수입", "순 자본", "목표", "목표 대비"])
    n = max(plan.months, 36)
    for m in range(0, n + 1):
        r = m + 2
        ws.cell(row=r, column=1, value=m)
        ws.cell(row=r, column=2, value=add_months(basis, m).strftime("%Y-%m"))
        ws.cell(row=r, column=3, value=plan.capital_at(m)).number_format = WON
        ws.cell(row=r, column=4, value=plan.monthly_cost_at(m)).number_format = WON
        ws.cell(row=r, column=5, value=plan.monthly_income_at(m)).number_format = WON
        ws.cell(row=r, column=6, value=plan.net_at(m)).number_format = WON
        ws.cell(row=r, column=7, value=plan.target).number_format = WON
        ws.cell(row=r, column=8, value=plan.net_at(m) - plan.target).number_format = WON
    _autowidth(ws)
    chart = LineChart()
    chart.title = "월별 순 자본 추이"
    chart.y_axis.title = "원"
    chart.x_axis.title = "개월"
    chart.height, chart.width = 9, 22
    chart.add_data(Reference(ws, min_col=6, min_row=1, max_row=n + 2), titles_from_data=True)
    chart.add_data(Reference(ws, min_col=7, min_row=1, max_row=n + 2), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n + 2))
    ws.add_chart(chart, "J2")

    # ---------------------------------------------------------- 비중 (+ 원형 그래프)
    ws = wb.create_sheet("비중")
    comp = composition(plan)
    row = 1
    for group, entries in comp.items():
        total = sum(v for _, v in entries)
        _header(ws, row, [group, "금액", "비중"])
        start = row + 1
        for i, (name, v) in enumerate(entries):
            r = start + i
            ws.cell(row=r, column=1, value=name)
            ws.cell(row=r, column=2, value=v).number_format = WON
            ws.cell(row=r, column=3, value=(v / total) if total else 0).number_format = PCT
        end = start + max(0, len(entries) - 1)
        if entries:
            pie = PieChart()
            pie.title = f"{group} 비중"
            pie.height, pie.width = 7.5, 11
            pie.add_data(Reference(ws, min_col=2, min_row=start, max_row=end))
            pie.set_categories(Reference(ws, min_col=1, min_row=start, max_row=end))
            ws.add_chart(pie, f"E{row}")
        row = end + (2 if entries else 1) + max(0, 15 - len(entries))   # 다음 그룹은 그래프 아래로
    _autowidth(ws)

    # ---------------------------------------------------------- 시나리오 비교 (+ 선 그래프)
    if scenarios and len(scenarios) >= 2:
        ws = wb.create_sheet("시나리오 비교")
        n = max([plan.months, 36] + [p.months for p in scenarios])
        _header(ws, 1, ["개월"] + [p.name or f"시나리오 {i + 1}" for i, p in enumerate(scenarios)])
        for m in range(0, n + 1):
            ws.cell(row=m + 2, column=1, value=m)
            for c, p in enumerate(scenarios, start=2):
                ws.cell(row=m + 2, column=c, value=p.net_at(m)).number_format = WON
        _autowidth(ws)
        chart = LineChart()
        chart.title = "시나리오별 순 자본 추이"
        chart.y_axis.title = "원"
        chart.x_axis.title = "개월"
        chart.height, chart.width = 9, 22
        for c in range(2, 2 + len(scenarios)):
            chart.add_data(Reference(ws, min_col=c, min_row=1, max_row=n + 2), titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n + 2))
        ws.add_chart(chart, f"{get_column_letter(len(scenarios) + 3)}2")

    # ---------------------------------------------------------- 가계부
    if ledger is not None and ledger.entries:
        _ledger_sheets(wb, ledger, plan)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
